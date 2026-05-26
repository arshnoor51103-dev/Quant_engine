"""Tests for P3.3 signal persistence: ticker_metadata, persist_signals, query_signal_history."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.signals.base import SignalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _db(tmp_path: Path) -> Path:
    """Initialize an isolated test DB and return its path."""
    from src.data.storage import initialize
    db = tmp_path / "test.db"
    initialize(db)
    return db


# ── ticker_metadata unit tests ────────────────────────────────────────────────

class TestTickerMetadata:
    def test_per_ticker_dict_key_rename(self) -> None:
        """raw_returns dict → raw_return scalar; key renamed via explicit map."""
        result = SignalResult(
            signal_name="momentum",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.75, "XIC.TO": 0.50},
            metadata={"raw_returns": {"VFV.TO": 0.34, "XIC.TO": 0.46}},
        )
        assert result.ticker_metadata("VFV.TO") == {"raw_return": 0.34}

    def test_broadcast_scalar_passthrough(self) -> None:
        """Scalar values pass through verbatim to every ticker."""
        result = SignalResult(
            signal_name="vol_regime",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.30},
            metadata={"regime": "NORMAL", "vol_percentile": 0.625},
        )
        assert result.ticker_metadata("VFV.TO") == {
            "regime": "NORMAL",
            "vol_percentile": 0.625,
        }

    def test_none_metadata_returns_empty_dict(self) -> None:
        """metadata=None returns {} without error."""
        result = SignalResult(
            signal_name="mean_reversion",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.10},
            metadata=None,
        )
        assert result.ticker_metadata("VFV.TO") == {}

    def test_ticker_absent_from_per_ticker_dict_excluded(self) -> None:
        """Ticker missing from a per-ticker dict is silently excluded."""
        result = SignalResult(
            signal_name="momentum",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.75},
            metadata={"raw_returns": {"XIC.TO": 0.46}},  # VFV.TO absent
        )
        assert result.ticker_metadata("VFV.TO") == {}
