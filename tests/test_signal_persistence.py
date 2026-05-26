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


# ── storage tests ─────────────────────────────────────────────────────────────

def test_persist_and_read_roundtrip(tmp_path: Path) -> None:
    """Persisted score and ticker-specific metadata are recoverable exactly."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    result = SignalResult(
        signal_name="momentum",
        run_date=date(2026, 5, 1),
        scores={"VFV.TO": 0.75, "XIC.TO": 0.50},
        metadata={"raw_returns": {"VFV.TO": 0.34, "XIC.TO": 0.46}},
    )
    n = persist_signals([result], run_id="abc12345", db_path=db)
    assert n == 2  # one row per ticker

    rows = query_signal_history("VFV.TO", limit=10, db_path=db)
    assert len(rows) == 1
    row = rows[0]
    assert row["signal_type"] == "momentum"
    assert abs(row["score"] - 0.75) < 1e-9
    assert row["run_id"] == "abc12345"
    meta = json.loads(row["metadata"])
    assert abs(meta["raw_return"] - 0.34) < 1e-9


def test_upsert_overwrites_on_same_pk(tmp_path: Path) -> None:
    """Re-persisting the same (run_date, ticker, signal_type) PK overwrites the row."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    persist_signals(
        [SignalResult(signal_name="momentum", run_date=date(2026, 5, 1),
                      scores={"VFV.TO": 0.75}, metadata=None)],
        run_id="run001", db_path=db,
    )
    persist_signals(
        [SignalResult(signal_name="momentum", run_date=date(2026, 5, 1),
                      scores={"VFV.TO": 0.90}, metadata=None)],  # same PK, new score
        run_id="run002", db_path=db,
    )

    rows = query_signal_history("VFV.TO", limit=10, db_path=db)
    assert len(rows) == 1, "upsert must not create duplicate rows"
    assert abs(rows[0]["score"] - 0.90) < 1e-9
    assert rows[0]["run_id"] == "run002"


def test_signal_history_limit(tmp_path: Path) -> None:
    """15 records inserted; limit=12 returns exactly 12 rows, newest first."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    for day in range(1, 16):  # 15 distinct dates: 2025-01-01 through 2025-01-15
        persist_signals(
            [SignalResult(signal_name="momentum", run_date=date(2025, 1, day),
                          scores={"VFV.TO": day / 15.0}, metadata=None)],
            run_id=f"run{day:03d}", db_path=db,
        )

    rows = query_signal_history("VFV.TO", limit=12, db_path=db)
    assert len(rows) == 12
    assert rows[0]["run_date"] > rows[-1]["run_date"]  # newest first (ISO strings sort correctly)


def test_signal_history_empty_table(tmp_path: Path) -> None:
    """Fresh DB returns empty list without error."""
    from src.data.storage import query_signal_history

    db = _db(tmp_path)
    rows = query_signal_history("VFV.TO", limit=12, db_path=db)
    assert rows == []


def test_signal_type_filter(tmp_path: Path) -> None:
    """signal_types filter returns only rows matching the specified type."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    persist_signals(
        [
            SignalResult(signal_name="momentum",   run_date=date(2026, 5, 1),
                         scores={"VFV.TO": 0.75},  metadata=None),
            SignalResult(signal_name="vol_regime", run_date=date(2026, 5, 1),
                         scores={"VFV.TO": 0.30},  metadata=None),
        ],
        run_id="run001", db_path=db,
    )

    rows = query_signal_history("VFV.TO", limit=10, signal_types=["momentum"], db_path=db)
    assert len(rows) == 1
    assert rows[0]["signal_type"] == "momentum"
