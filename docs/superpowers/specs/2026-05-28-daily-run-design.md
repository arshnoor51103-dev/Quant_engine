# P3.6 Scheduled Daily Run — Design Spec

**Date:** 2026-05-28  
**Status:** Approved  
**Phase:** 3 P3.6  
**Goal:** Engine runs daily without manual intervention. Fetch → signals → recommend → alert, all logged, all guarded against cascade failure.

---

## Overview

A `DailyRunner` class in `src/cli/daily_run_command.py` orchestrates four CLI steps via subprocess. It is the single source of truth for pipeline ordering, logging, timeout enforcement, and error alerting. Two callers invoke it:

- `scripts/daily_run.py` — called by Windows Task Scheduler via `daily_run.bat`; passes a dated log file path
- `quant daily-run` CLI command — interactive / manual trigger; passes `log_target=None` (stdout only)

One subprocess layer: DailyRunner → four CLI steps. No nesting beyond that.

---

## Architecture

```
src/cli/daily_run_command.py   ← DailyRunner class + daily_run_command() typer function
scripts/daily_run.py           ← sys.path bootstrap, reads config, calls DailyRunner(log_target=dated_path)
scripts/daily_run.bat          ← PYTHONUTF8=1, activate .venv, run daily_run.py >> logs\bat.log 2>&1
scripts/setup_scheduler.ps1   ← Register-ScheduledTask, dual trigger, no WakeToRun
tests/test_daily_run.py        ← 8 unit tests, mocks subprocess.run
src/cli/main.py                ← +1 line: app.command("daily-run")(daily_run_command)
config/portfolio.yaml          ← new daily_run: block
```

---

## DailyRunner Class

```python
class DailyRunner:
    def __init__(
        self,
        log_target: Path | None = None,
        default_cash: float = 0.0,
        step_timeout_seconds: int = 300,
    ): ...
    def __enter__(self) -> "DailyRunner": ...  # opens log file if log_target set
    def __exit__(self, *_) -> None: ...        # closes log file handle
    def run(self) -> int: ...                  # returns number of failed steps (0 = all ok)
    def _run_step(self, name: str, args: list[str]) -> bool: ...
    def _send_error_alert(self, step: str, rc: int, stderr: str) -> None: ...
    def _log(self, msg: str) -> None: ...      # file.write+flush OR print(stdout)
```

### Steps (in order, all run regardless of prior failures)

| Step | CLI args |
|------|----------|
| `fetch` | `fetch` |
| `momentum` | `signals --signal-type momentum --save` |
| `vol_regime` | `signals --signal-type vol_regime --save` |
| `recommend` | `recommend --optimize --save --notify [--cash <default_cash>]` |

`--cash <default_cash>` is appended to the recommend step only when `default_cash > 0.0`.

### Subprocess call

```python
try:
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main"] + step_args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",        # prevents Windows Unicode crash at capture boundary
        env={**os.environ, "NO_COLOR": "1", "PYTHONUTF8": "1"},
        cwd=_PROJECT_ROOT,       # module-level constant: Path(__file__).resolve().parent.parent
        timeout=self.step_timeout_seconds,
    )
except subprocess.TimeoutExpired:
    # subprocess.run kills child and collects output before raising
    self._log(f"  TIMEOUT after {self.step_timeout_seconds}s")
    self._send_error_alert(step_name, -1, f"Step timed out after {self.step_timeout_seconds}s")
    return False
```

### Log format

```
=== Quant Engine Daily Run — 2026-05-28 ===
[18:00:01] fetch ............. START
  <stdout from step, 2-space indent>
[18:00:04] fetch ............. OK (0) [3.2s]

[18:00:04] momentum .......... START
[18:00:07] momentum .......... OK (0) [2.8s]

[18:00:07] vol_regime ........ START
[18:00:09] vol_regime ........ FAIL (1) [1.9s]
  STDERR: <stderr text>
  ALERT: ntfy priority=5 sent

[18:00:09] recommend ......... START
...
=== Daily Run Complete: 1 STEP(S) FAILED — 2026-05-28 18:00:14 ===
```

- Stdout from each step is always logged (signal scores and trade cards are diagnostic)
- Stderr logged only on failure
- `TIMEOUT` logged identically to `FAIL`

### Error alert

`_send_error_alert` reads `config/portfolio.yaml` for `alerts.enabled` and `alerts.ntfy_topic`. Calls `send_alert(priority=5, tags=["error"])`. Wrapped in bare `except Exception` — alert failure never stops the next step.

### Logging

- `log_target=None` (interactive): `_log` calls `print()` to stdout
- `log_target=Path(...)` (scheduled): `__enter__` opens file in append mode (`"a"`, `encoding="utf-8"`), `_log` writes + flushes, `__exit__` closes

---

## scripts/daily_run.py

```python
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.cli.daily_run_command import DailyRunner
from src.portfolio.model import load_portfolio_config

def main() -> int:
    cfg = load_portfolio_config()
    dr_cfg = cfg.get("daily_run", {})
    log_path = _PROJECT_ROOT / "logs" / f"{date.today()}.log"
    with DailyRunner(
        log_target=log_path,
        default_cash=float(dr_cfg.get("default_cash", 0.0)),
        step_timeout_seconds=int(dr_cfg.get("step_timeout_seconds", 300)),
    ) as runner:
        return runner.run()

if __name__ == "__main__":
    sys.exit(main())
```

---

## scripts/daily_run.bat

- Sets `PYTHONUTF8=1`
- `cd /d "%~dp0.."` to project root
- Activates `.venv\Scripts\activate.bat`; exits on failure
- Derives date string via `wmic os get LocalDateTime` for the bat log filename
- Runs `python scripts\daily_run.py > "logs\bat.log" 2>&1`
  - `logs\bat.log` is **overwritten** each run (`>` not `>>`; startup failures only; DailyRunner owns the dated log)
- Exits with `%errorlevel%` from the python call

---

## scripts/setup_scheduler.ps1

**Task name:** `QuantEngine-DailyRun`

**Triggers (both registered):**
1. Daily at 18:00 local time
2. At logon (secondary fallback for missed runs)

**Settings:**
- `-StartWhenAvailable` — fires on next machine wake if the 18:00 trigger was missed
- `-WakeToRun $false` — **explicit**: laptop must never be woken for this task (thermal/hibernate risk in a closed bag)
- `-RunOnlyIfNetworkAvailable` — yfinance fetch requires internet
- `-ExecutionTimeLimit (New-TimeSpan -Minutes 30)`
- `-MultipleInstances IgnoreNew`

**Credentials:** `Get-Credential` GUI prompt (one-time setup). Required for "run whether user is logged on or not". Comment in script notes Microsoft account users may need an app password; alternative is to configure "run only when logged on" in Task Scheduler GUI post-registration.

**Verification commands printed on success:**
```powershell
Get-ScheduledTask -TaskName 'QuantEngine-DailyRun'
Start-ScheduledTask -TaskName 'QuantEngine-DailyRun'   # manual trigger / smoke test
Unregister-ScheduledTask -TaskName 'QuantEngine-DailyRun'  # removal
```

---

## quant daily-run CLI Command

Registered in `main.py`. Implemented in `daily_run_command.py`:

```python
def daily_run_command() -> None:
    """Run the full daily pipeline interactively (fetch → signals → recommend)."""
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
```

---

## config/portfolio.yaml additions

```yaml
daily_run:
  default_cash: 350.0        # CAD to deploy in recommend step; set to 0 when no new capital
  step_timeout_seconds: 300  # per-step subprocess timeout; TimeoutExpired treated as FAIL
```

`default_cash` reflects the monthly contribution ($300–400/month, midpoint $350). Prevents recommend from failing with NAV=0/cash=0 on first runs before any manual trade is recorded. Set to 0 to run in rebalance-only mode.

---

## Testing (tests/test_daily_run.py — 8 tests)

All tests mock `subprocess.run` via `unittest.mock.patch`.

| Test | Assertion |
|------|-----------|
| `test_all_steps_succeed` | `run()` returns 0; `subprocess.run` called 4 times |
| `test_one_step_fails_continues` | RC=1 on step 2 → returns 1; steps 3+4 still called |
| `test_timeout_treated_as_failure` | `TimeoutExpired` on step 1 → returns 1; step 2 still called |
| `test_no_alert_when_disabled` | `alerts.enabled=False` → `send_alert` not called on failure |
| `test_default_cash_zero_no_flag` | `default_cash=0.0` → recommend args have no `--cash` |
| `test_default_cash_nonzero_flag` | `default_cash=350.0` → recommend args include `["--cash", "350.0"]` |
| `test_log_target_none_prints_stdout` | `capsys` captures step lines when `log_target=None` |
| `test_log_target_path_writes_file` | `log_target=tmp_path/"run.log"` → file exists, contains step lines |

---

## Files Summary

**Created:**
- `src/cli/daily_run_command.py`
- `scripts/daily_run.py`
- `scripts/daily_run.bat`
- `scripts/setup_scheduler.ps1`
- `tests/test_daily_run.py`

**Modified:**
- `src/cli/main.py` — register `quant daily-run`
- `config/portfolio.yaml` — add `daily_run:` block
- `LEARNING.md` — append P3.6 decision entry
- `docs/PROJECT_STATUS.md` — update phase status row

---

## Constraints Preserved

- No LLM in signal path (DailyRunner only invokes existing deterministic CLI commands)
- CRA discipline: `quant recommend` already enforces 24-trade/year cap and 14-day min-hold
- All state in SQLite: `--save` flags ensure signals and recommendations are persisted
- Alerts never raise: `send_alert` is fire-and-forget; DailyRunner wraps `_send_error_alert` in `except Exception`
