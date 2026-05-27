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
