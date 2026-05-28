"""
Scheduled daily run orchestrator.

Runs the full pipeline in order:
    fetch → momentum signals → vol_regime signals → recommend (with optimizer and alerts)

All steps are executed regardless of prior failures so partial data is never the
cause of a missing recommendation.  Failed steps are reported in the footer and
trigger a priority-5 ntfy.sh alert when alerts are configured.

Intended to be called by a task scheduler (Windows Task Scheduler, cron, etc.)
or interactively via ``quant daily-run``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import IO

import typer

from ..portfolio.model import load_portfolio_config
from ..alerts.ntfy import send_alert

# Three parents up from src/cli/daily_run_command.py → D:\Quant_engine
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Steps: (name, base_args) — recommend args are extended at runtime based on
# default_cash so they are built inside run().
_STEPS: list[tuple[str, list[str]]] = [
    ("fetch",      ["fetch"]),
    ("momentum",   ["signals", "--signal-type", "momentum", "--save"]),
    ("vol_regime", ["signals", "--signal-type", "vol_regime", "--save"]),
    ("recommend",  ["recommend", "--optimize", "--save", "--notify"]),
]


class DailyRunner:
    """
    Context-manager that orchestrates the full daily pipeline.

    Args:
        log_target:            Path to append-mode log file.  ``None`` means
                               write to stdout via ``print``.
        default_cash:          Cash to pass to the ``recommend`` step as
                               ``--cash <value>``.  Ignored when 0.0.
        step_timeout_seconds:  Per-step subprocess timeout in seconds.
    """

    def __init__(
        self,
        log_target: Path | None = None,
        default_cash: float = 0.0,
        step_timeout_seconds: int = 300,
    ) -> None:
        self.log_target = log_target
        self.default_cash = default_cash
        self.step_timeout_seconds = step_timeout_seconds
        self._handle: IO[str] | None = None

    def __enter__(self) -> "DailyRunner":
        """Open log file in append mode if ``log_target`` is set."""
        if self.log_target is not None:
            self._handle = open(self.log_target, "a", encoding="utf-8")
        return self

    def __exit__(self, *_: object) -> None:
        """Close log file handle."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def run(self) -> int:
        """
        Execute all pipeline steps and return the number that failed.

        Returns:
            int: Count of steps that returned a non-zero exit code or timed out.
                 0 means the full run succeeded.
        """
        today = date.today().isoformat()
        self._log(f"=== Quant Engine Daily Run — {today} ===")

        failures = 0
        for name, base_args in _STEPS:
            # Build full args list, extending recommend with --cash when needed
            if name == "recommend" and self.default_cash > 0.0:
                step_args = base_args + ["--cash", str(self.default_cash)]
            else:
                step_args = base_args

            ok = self._run_step(name, step_args)
            if not ok:
                failures += 1

        now = datetime.now().strftime("%H:%M:%S")
        if failures == 0:
            self._log(f"=== Daily Run Complete: 0 STEP(S) FAILED — {today} {now} ===")
        else:
            self._log(
                f"=== Daily Run Complete: {failures} STEP(S) FAILED — {today} {now} ==="
            )
        return failures

    def _run_step(self, name: str, args: list[str]) -> bool:
        """
        Run a single pipeline step as a subprocess.

        Args:
            name: Human-readable step label used in log output.
            args: CLI argument list passed after ``python -m src.cli.main``.

        Returns:
            bool: ``True`` if the step exited with return code 0, ``False``
                  otherwise (including timeout).
        """
        label = f"{name} {'.' * max(1, 14 - len(name))}"
        ts_start = datetime.now().strftime("%H:%M:%S")
        self._log(f"[{ts_start}] {label} START")

        t0 = datetime.now()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.cli.main"] + args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "NO_COLOR": "1", "PYTHONUTF8": "1"},
                cwd=_PROJECT_ROOT,
                timeout=self.step_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            elapsed = (datetime.now() - t0).total_seconds()
            ts_end = datetime.now().strftime("%H:%M:%S")
            self._log(f"[{ts_end}] {label} TIMEOUT [{elapsed:.1f}s]")
            self._send_error_alert(
                name, -1, f"Step timed out after {self.step_timeout_seconds}s"
            )
            return False

        elapsed = (datetime.now() - t0).total_seconds()
        ts_end = datetime.now().strftime("%H:%M:%S")

        # Always log stdout (indented)
        if result.stdout:
            for line in result.stdout.splitlines():
                self._log(f"  {line}")

        rc = result.returncode
        if rc == 0:
            self._log(f"[{ts_end}] {label} OK ({rc}) [{elapsed:.1f}s]")
            self._log("")
            return True
        else:
            self._log(f"[{ts_end}] {label} FAIL ({rc}) [{elapsed:.1f}s]")
            if result.stderr:
                self._log(f"  STDERR: {result.stderr}")
            self._send_error_alert(name, rc, result.stderr)
            self._log(f"  ALERT: error alert queued")
            self._log("")
            return False

    def _send_error_alert(self, step: str, rc: int, stderr: str) -> None:
        """
        Send a priority-5 ntfy.sh alert for a failed or timed-out step.

        Reads ``alerts.enabled`` and ``alerts.ntfy_topic`` from
        ``config/portfolio.yaml``.  No-ops when alerts are disabled.
        Swallows all exceptions — alert failure must never abort the run.

        Args:
            step:   Step name that failed.
            rc:     Return code (−1 for timeout).
            stderr: Stderr output or timeout message to include in alert body.
        """
        try:
            cfg = load_portfolio_config()
            alerts_cfg = cfg.get("alerts", {})
            if not alerts_cfg.get("enabled"):
                return
            topic: str = alerts_cfg["ntfy_topic"]
            send_alert(
                topic,
                f"Quant Engine — {step} FAILED",
                stderr,
                priority=5,
                tags=["error"],
            )
        except Exception as exc:  # noqa: BLE001
            self._log(f"  [alert send failed: {exc}]")

    def _log(self, msg: str) -> None:
        """
        Write a log line to the open file handle or stdout.

        Args:
            msg: Text to log (newline appended automatically).
        """
        if self._handle is not None:
            self._handle.write(msg + "\n")
            self._handle.flush()
        else:
            print(msg)


def daily_run_command() -> None:
    """Run the full daily pipeline interactively (fetch -> signals -> recommend)."""
    cfg = load_portfolio_config()
    dr_cfg = cfg.get("daily_run", {})
    with DailyRunner(
        log_target=None,
        default_cash=float(dr_cfg.get("default_cash", 0.0)),
        step_timeout_seconds=int(dr_cfg.get("step_timeout_seconds", 300)),
    ) as runner:
        result = runner.run()
    if result > 0:
        raise typer.Exit(result)
