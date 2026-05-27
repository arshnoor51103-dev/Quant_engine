"""
Tests for src/alerts/ntfy.py (HTTP transport) and the trigger logic
in src/cli/phase3_commands.py.

All network calls are mocked — no real HTTP is made.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.alerts.ntfy import send_alert


# ─── Transport: send_alert ────────────────────────────────────────────────────

def test_send_alert_posts_correct_payload() -> None:
    """URL, title header, and body must match the ntfy.sh POST contract."""
    with patch("src.alerts.ntfy.requests.post") as mock_post:
        send_alert("my-topic", "Alert Title", "Alert body")
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        kwargs = mock_post.call_args[1]
        assert url == "https://ntfy.sh/my-topic"
        assert kwargs["data"] == b"Alert body"
        assert kwargs["headers"]["X-Title"] == "Alert Title"


def test_send_alert_priority_maps_to_header() -> None:
    """priority=4 must appear as X-Priority: '4' in request headers."""
    with patch("src.alerts.ntfy.requests.post") as mock_post:
        send_alert("t", "T", "M", priority=4)
        assert mock_post.call_args[1]["headers"]["X-Priority"] == "4"


def test_send_alert_no_tags_omits_header() -> None:
    """tags=None must not produce an X-Tags header."""
    with patch("src.alerts.ntfy.requests.post") as mock_post:
        send_alert("t", "T", "M", tags=None)
        assert "X-Tags" not in mock_post.call_args[1]["headers"]


def test_send_alert_silences_network_error() -> None:
    """Any requests exception must be swallowed — never propagates."""
    with patch("src.alerts.ntfy.requests.post", side_effect=ConnectionError("down")):
        send_alert("t", "T", "M")  # must not raise


# ─── Trigger logic: _run_alert_triggers ──────────────────────────────────────

import pandas as pd
from src.cli.phase3_commands import _run_alert_triggers
from src.portfolio.recommendations import GateStatus


def _nav_series_with_dd(dd: float) -> pd.Series:
    """Price series whose peak-to-trough drawdown equals dd (positive fraction).
    Series is [1.0, 1.0, 1.0 - dd], so max_drawdown returns -(dd)."""
    return pd.Series(
        [1.0, 1.0, 1.0 - dd],
        index=pd.date_range("2026-01-01", periods=3),
    )


def _cfg(enabled: bool = True, triggers: list[str] | None = None) -> dict:
    return {
        "alerts": {
            "enabled": enabled,
            "ntfy_topic": "test-topic",
            "triggers": triggers if triggers is not None
                        else ["NEW_RECOMMENDATION", "REGIME_CHANGE", "DRAWDOWN_WARNING"],
        },
        "risk": {"drawdown_alert": 0.15},
    }


def _buy_card() -> MagicMock:
    c = MagicMock()
    c.action = "BUY"
    c.gate_status = GateStatus.PASS
    c.ticker = "VFV.TO"
    c.combined_signal = 0.75
    c.expected_return_pct = 0.08
    return c


def _skip_card() -> MagicMock:
    c = MagicMock()
    c.action = "SKIP"
    c.gate_status = GateStatus.SKIP_SIGNAL
    return c


# Test 5
def test_alerts_disabled_suppresses_send() -> None:
    """enabled: false → send_alert never called regardless of cards or regime."""
    with patch("src.cli.phase3_commands.send_alert") as mock_send:
        _run_alert_triggers([_buy_card()], "NORMAL", _cfg(enabled=False), [], {})
        mock_send.assert_not_called()


# Test 6
def test_new_recommendation_fires_on_passing_card() -> None:
    """A PASS-gate BUY card triggers a NEW_RECOMMENDATION alert and log entry."""
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.log_alert") as mock_log:
        _run_alert_triggers([_buy_card()], "NORMAL",
                            _cfg(triggers=["NEW_RECOMMENDATION"]), [], {})
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == "New Recommendation"
        mock_log.assert_called_once()
        logged = json.loads(mock_log.call_args[0][1])
        assert logged[0]["ticker"] == "VFV.TO"
        assert logged[0]["action"] == "BUY"


# Test 7
def test_new_recommendation_silent_on_all_skip() -> None:
    """Only SKIP-action cards → send_alert not called."""
    with patch("src.cli.phase3_commands.send_alert") as mock_send:
        _run_alert_triggers([_skip_card()], "NORMAL",
                            _cfg(triggers=["NEW_RECOMMENDATION"]), [], {})
        mock_send.assert_not_called()


# Test 8
def test_regime_change_fires_on_transition() -> None:
    """Persisted regime NORMAL, current HIGH_VOL → REGIME_CHANGE alert fires."""
    last_row = {"payload": json.dumps({"regime": "NORMAL", "previous": None})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands.log_alert") as mock_log:
        _run_alert_triggers([], "HIGH_VOL", _cfg(triggers=["REGIME_CHANGE"]), [], {})
        mock_send.assert_called_once()
        assert "HIGH_VOL" in mock_send.call_args[0][2].upper()
        logged = json.loads(mock_log.call_args[0][1])
        assert logged["regime"] == "HIGH_VOL"
        assert logged["previous"] == "NORMAL"


# Test 9
def test_regime_change_silent_if_same() -> None:
    """Persisted regime equals current regime → send_alert not called."""
    last_row = {"payload": json.dumps({"regime": "NORMAL", "previous": None})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["REGIME_CHANGE"]), [], {})
        mock_send.assert_not_called()


# Test 10
def test_drawdown_warning_fires_on_crossing() -> None:
    """Last status RECOVERED + current drawdown 17% > 15% threshold → WARNING fires."""
    last_row = {"payload": json.dumps({"status": "RECOVERED", "drawdown": 0.10})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands.log_alert") as mock_log, \
         patch("src.cli.phase3_commands._portfolio_nav_series",
               return_value=_nav_series_with_dd(0.17)):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["DRAWDOWN_WARNING"]), [], {})
        mock_send.assert_called_once()
        assert mock_send.call_args[1]["priority"] == 5
        logged = json.loads(mock_log.call_args[0][1])
        assert logged["status"] == "WARNING"
        assert abs(logged["drawdown"] - 0.17) < 0.01


# Test 11
def test_drawdown_warning_silent_if_already_in_warning() -> None:
    """Portfolio already in WARNING state (18% dd) → do not re-fire."""
    last_row = {"payload": json.dumps({"status": "WARNING", "drawdown": 0.16})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands._portfolio_nav_series",
               return_value=_nav_series_with_dd(0.18)):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["DRAWDOWN_WARNING"]), [], {})
        mock_send.assert_not_called()


# Test 12
def test_drawdown_warning_logs_recovery_no_post() -> None:
    """Drawdown recovers below threshold → log RECOVERED row, no ntfy POST."""
    last_row = {"payload": json.dumps({"status": "WARNING", "drawdown": 0.16})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands.log_alert") as mock_log, \
         patch("src.cli.phase3_commands._portfolio_nav_series",
               return_value=_nav_series_with_dd(0.10)):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["DRAWDOWN_WARNING"]), [], {})
        mock_send.assert_not_called()
        mock_log.assert_called_once()
        logged = json.loads(mock_log.call_args[0][1])
        assert logged["status"] == "RECOVERED"
        assert abs(logged["drawdown"] - 0.10) < 0.01
