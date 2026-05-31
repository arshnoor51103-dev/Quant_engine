"""
Unit tests for src/cli/daily_run_command.py.

All subprocess.run calls are mocked — no real subprocesses are launched.
Portfolio config is mocked where alert behaviour needs to be controlled.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.cli.daily_run_command import DailyRunner


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ok_proc() -> MagicMock:
    """Return a mock subprocess.CompletedProcess with RC=0."""
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "ok\n"
    proc.stderr = ""
    return proc


def _fail_proc(rc: int = 1) -> MagicMock:
    """Return a mock subprocess.CompletedProcess with a non-zero RC."""
    proc = MagicMock()
    proc.returncode = rc
    proc.stdout = ""
    proc.stderr = "something went wrong"
    return proc


def _alerts_cfg(enabled: bool = True) -> dict:
    """Minimal portfolio config dict for alert tests."""
    return {
        "alerts": {
            "enabled": enabled,
            "ntfy_topic": "test-topic",
        },
        "daily_run": {},
    }


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_daily_run_steps_no_redundant_signal_persistence() -> None:
    """F11: the standalone `signals --save` steps are gone; recommend re-persists
    momentum + vol_regime under a single run_id, so the pipeline is fetch→recommend."""
    from src.cli.daily_run_command import _STEPS
    names = [n for n, _ in _STEPS]
    assert names == ["fetch", "recommend"]


def test_all_steps_succeed() -> None:
    """run() returns 0 and subprocess.run is called exactly 2 times when all steps pass."""
    with patch("src.cli.daily_run_command.subprocess.run", return_value=_ok_proc()) as mock_run:
        with DailyRunner() as runner:
            result = runner.run()
    assert result == 0
    assert mock_run.call_count == 2


def test_one_step_fails_continues() -> None:
    """
    A failure on the recommend step (index 1) is reported but does not crash run().

    run() returns 1 and subprocess.run is still called 2 times (both steps run).
    """
    side_effects = [_ok_proc(), _fail_proc()]
    with patch("src.cli.daily_run_command.subprocess.run", side_effect=side_effects) as mock_run, \
         patch("src.cli.daily_run_command.load_portfolio_config", return_value=_alerts_cfg(enabled=False)):
        with DailyRunner() as runner:
            result = runner.run()
    assert result == 1
    assert mock_run.call_count == 2


def test_timeout_treated_as_failure() -> None:
    """
    A TimeoutExpired on step 1 (fetch) counts as failure and step 2 is still called.

    subprocess.run is called 2 times.
    """
    timeout_exc = subprocess.TimeoutExpired("cmd", 300)
    side_effects = [timeout_exc, _ok_proc()]
    with patch("src.cli.daily_run_command.subprocess.run", side_effect=side_effects) as mock_run, \
         patch("src.cli.daily_run_command.load_portfolio_config", return_value=_alerts_cfg(enabled=False)):
        with DailyRunner(step_timeout_seconds=300) as runner:
            result = runner.run()
    assert result == 1
    assert mock_run.call_count == 2


def test_no_alert_when_disabled() -> None:
    """
    When alerts.enabled is False, send_alert is never called even on step failure.
    """
    side_effects = [_ok_proc(), _fail_proc()]
    with patch("src.cli.daily_run_command.subprocess.run", side_effect=side_effects), \
         patch("src.cli.daily_run_command.load_portfolio_config",
               return_value=_alerts_cfg(enabled=False)), \
         patch("src.cli.daily_run_command.send_alert") as mock_send:
        with DailyRunner() as runner:
            runner.run()
    mock_send.assert_not_called()


def test_alert_sent_on_failure(tmp_path: Path) -> None:
    """When a step fails and alerts.enabled is True, send_alert is called with priority=5."""
    side_effects = [_fail_proc(), _ok_proc()]
    with patch("src.cli.daily_run_command.subprocess.run", side_effect=side_effects), \
         patch("src.cli.daily_run_command.load_portfolio_config",
               return_value=_alerts_cfg(enabled=True)), \
         patch("src.cli.daily_run_command.send_alert") as mock_send_alert:
        with DailyRunner() as runner:
            runner.run()
    assert mock_send_alert.called
    _, kwargs = mock_send_alert.call_args
    assert kwargs.get("priority") == 5
    assert kwargs.get("tags") == ["error"]


def test_default_cash_zero_no_flag() -> None:
    """
    default_cash=0.0 → the recommend subprocess call args must NOT contain '--cash'.
    """
    with patch("src.cli.daily_run_command.subprocess.run", return_value=_ok_proc()) as mock_run:
        with DailyRunner(default_cash=0.0) as runner:
            runner.run()
    # Find the recommend call — it is the last (2nd) call
    recommend_call_args = mock_run.call_args_list[1][0][0]  # positional arg: cmd list
    assert "--cash" not in recommend_call_args


def test_default_cash_nonzero_flag() -> None:
    """
    default_cash=350.0 → the recommend subprocess call args must include ['--cash', '350.0'].
    """
    with patch("src.cli.daily_run_command.subprocess.run", return_value=_ok_proc()) as mock_run:
        with DailyRunner(default_cash=350.0) as runner:
            runner.run()
    recommend_call_args = mock_run.call_args_list[1][0][0]
    assert "--cash" in recommend_call_args
    cash_idx = recommend_call_args.index("--cash")
    assert recommend_call_args[cash_idx + 1] == "350.0"


def test_log_target_none_prints_stdout(capsys: pytest.CaptureFixture) -> None:
    """
    log_target=None → _log writes via print; captured stdout contains step names.
    """
    with patch("src.cli.daily_run_command.subprocess.run", return_value=_ok_proc()):
        with DailyRunner(log_target=None) as runner:
            runner.run()
    captured = capsys.readouterr()
    assert "fetch" in captured.out
    assert "recommend" in captured.out


def test_log_target_path_writes_file(tmp_path: Path) -> None:
    """
    log_target=tmp_path/'run.log' → file is created and contains step name text.
    """
    log_file = tmp_path / "run.log"
    with patch("src.cli.daily_run_command.subprocess.run", return_value=_ok_proc()):
        with DailyRunner(log_target=log_file) as runner:
            runner.run()
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "fetch" in content
    assert "recommend" in content
