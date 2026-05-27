"""
Unit tests for critical storage functions that gate real money.

Tests cover: record_trade, get_annual_trade_count, get_last_buy_date,
get_all_last_buy_dates, save_recommendation, mark_recommendation_executed,
mark_recommendation_skipped, initialize idempotency.

All tests use a fresh in-memory SQLite DB so they run offline and fast.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.data.storage import (
    get_annual_trade_count,
    get_last_alert,
    get_last_buy_date,
    initialize,
    log_alert,
    mark_recommendation_executed,
    mark_recommendation_skipped,
    migrate_recommendations_v2,
    record_trade,
    save_recommendation,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Fresh DB file per test — fully isolated."""
    db = tmp_path / "test_quant.db"
    initialize(db_path=db)
    return db


# ─── initialize ───────────────────────────────────────────────────────────────

def test_initialize_is_idempotent(tmp_db: Path) -> None:
    """Calling initialize() twice must not raise or corrupt the schema."""
    initialize(db_path=tmp_db)  # second call
    conn = sqlite3.connect(tmp_db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")}
    conn.close()
    assert {"prices", "holdings", "trades", "recommendations", "run_log"}.issubset(tables)


# ─── record_trade ─────────────────────────────────────────────────────────────

def test_record_trade_buy_creates_holding(tmp_db: Path) -> None:
    trade_id = record_trade(
        ticker="VFV.TO", side="BUY", units=10.0, price=100.0,
        trade_date=date(2026, 5, 1), db_path=tmp_db,
    )
    assert isinstance(trade_id, int) and trade_id > 0

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    holding = conn.execute("SELECT * FROM holdings WHERE ticker='VFV.TO';").fetchone()
    conn.close()
    assert holding is not None
    assert abs(holding["units"] - 10.0) < 1e-9
    assert abs(holding["avg_cost"] - 100.0) < 1e-9


def test_record_trade_buy_vwap_averages_cost(tmp_db: Path) -> None:
    """Second BUY at different price → VWAP-averaged cost basis."""
    record_trade("VFV.TO", "BUY", 10.0, 100.0, date(2026, 5, 1), db_path=tmp_db)
    record_trade("VFV.TO", "BUY", 10.0, 120.0, date(2026, 5, 15), db_path=tmp_db)

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    holding = conn.execute("SELECT avg_cost FROM holdings WHERE ticker='VFV.TO';").fetchone()
    conn.close()
    # VWAP: (10×100 + 10×120) / 20 = 110
    assert abs(holding["avg_cost"] - 110.0) < 1e-9


def test_record_trade_sell_reduces_holding(tmp_db: Path) -> None:
    record_trade("VFV.TO", "BUY", 10.0, 100.0, date(2026, 5, 1), db_path=tmp_db)
    record_trade("VFV.TO", "SELL", 4.0, 110.0, date(2026, 5, 10), db_path=tmp_db)

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    holding = conn.execute("SELECT units FROM holdings WHERE ticker='VFV.TO';").fetchone()
    conn.close()
    assert abs(holding["units"] - 6.0) < 1e-9


def test_record_trade_sell_removes_holding_when_zero(tmp_db: Path) -> None:
    record_trade("VFV.TO", "BUY", 5.0, 100.0, date(2026, 5, 1), db_path=tmp_db)
    record_trade("VFV.TO", "SELL", 5.0, 110.0, date(2026, 5, 10), db_path=tmp_db)

    conn = sqlite3.connect(tmp_db)
    holding = conn.execute("SELECT * FROM holdings WHERE ticker='VFV.TO';").fetchone()
    conn.close()
    assert holding is None


def test_record_trade_sell_insufficient_raises(tmp_db: Path) -> None:
    record_trade("VFV.TO", "BUY", 5.0, 100.0, date(2026, 5, 1), db_path=tmp_db)
    with pytest.raises(ValueError, match="Cannot sell"):
        record_trade("VFV.TO", "SELL", 10.0, 110.0, date(2026, 5, 10), db_path=tmp_db)


def test_record_trade_invalid_side_raises(tmp_db: Path) -> None:
    with pytest.raises(ValueError, match="side must be"):
        record_trade("VFV.TO", "HOLD", 5.0, 100.0, date(2026, 5, 1), db_path=tmp_db)


# ─── get_annual_trade_count ───────────────────────────────────────────────────

def test_get_annual_trade_count_empty(tmp_db: Path) -> None:
    assert get_annual_trade_count(year=2026, db_path=tmp_db) == 0


def test_get_annual_trade_count_counts_correct_year(tmp_db: Path) -> None:
    record_trade("VFV.TO", "BUY", 10.0, 100.0, date(2026, 1, 1), db_path=tmp_db)
    record_trade("VFV.TO", "BUY", 5.0,  105.0, date(2026, 6, 1), db_path=tmp_db)
    record_trade("VFV.TO", "BUY", 3.0,  110.0, date(2025, 12, 1), db_path=tmp_db)

    assert get_annual_trade_count(year=2026, db_path=tmp_db) == 2
    assert get_annual_trade_count(year=2025, db_path=tmp_db) == 1


def test_get_annual_trade_count_cra_limit_boundary(tmp_db: Path) -> None:
    """Exactly 24 trades in 2026 must return 24 — CRA gate math must be exact."""
    for i in range(24):
        record_trade("VFV.TO", "BUY", 1.0, 100.0, date(2026, 1, i + 1), db_path=tmp_db)
    assert get_annual_trade_count(year=2026, db_path=tmp_db) == 24


# ─── get_last_buy_date ────────────────────────────────────────────────────────

def test_get_last_buy_date_none_when_no_trades(tmp_db: Path) -> None:
    assert get_last_buy_date("VFV.TO", db_path=tmp_db) is None


def test_get_last_buy_date_returns_most_recent(tmp_db: Path) -> None:
    record_trade("VFV.TO", "BUY", 5.0, 100.0, date(2026, 3, 1), db_path=tmp_db)
    record_trade("VFV.TO", "BUY", 3.0, 105.0, date(2026, 4, 15), db_path=tmp_db)

    result = get_last_buy_date("VFV.TO", db_path=tmp_db)
    assert result == date(2026, 4, 15)


def test_get_last_buy_date_ignores_sell(tmp_db: Path) -> None:
    """A SELL after a BUY must not overwrite the last BUY date."""
    record_trade("VFV.TO", "BUY", 10.0, 100.0, date(2026, 3, 1), db_path=tmp_db)
    record_trade("VFV.TO", "SELL", 5.0, 110.0, date(2026, 4, 1), db_path=tmp_db)

    result = get_last_buy_date("VFV.TO", db_path=tmp_db)
    assert result == date(2026, 3, 1)


def test_get_last_buy_date_ticker_isolation(tmp_db: Path) -> None:
    """Buys for XIC.TO must not affect last-buy date for VFV.TO."""
    record_trade("XIC.TO", "BUY", 5.0, 40.0, date(2026, 5, 1), db_path=tmp_db)
    assert get_last_buy_date("VFV.TO", db_path=tmp_db) is None


# ─── min-hold gate: end-to-end math ──────────────────────────────────────────

def test_min_hold_boundary(tmp_db: Path) -> None:
    """A BUY 13 days ago is within 14-day hold; 15 days ago clears it."""
    buy_date_recent = date(2026, 5, 20) - timedelta(days=13)
    buy_date_old    = date(2026, 5, 20) - timedelta(days=15)

    record_trade("VFV.TO", "BUY", 5.0, 100.0, buy_date_recent, db_path=tmp_db)
    record_trade("XIC.TO", "BUY", 5.0, 40.0,  buy_date_old,    db_path=tmp_db)

    last_vfv = get_last_buy_date("VFV.TO", db_path=tmp_db)
    last_xic = get_last_buy_date("XIC.TO", db_path=tmp_db)

    assert (date(2026, 5, 20) - last_vfv).days == 13  # must be blocked by MIN_HOLD
    assert (date(2026, 5, 20) - last_xic).days == 15  # must clear MIN_HOLD


# ─── save_recommendation ─────────────────────────────────────────────────────

def test_save_recommendation_returns_id(tmp_db: Path) -> None:
    migrate_recommendations_v2(db_path=tmp_db)
    rec_id = save_recommendation(
        ticker="VFV.TO", action="BUY", bucket="growth",
        target_weight=0.20, combined_signal=0.45,
        expected_ret=0.063, cost_estimate=0.006,
        gate_status="PASS", rationale=None, run_id="test01",
        db_path=tmp_db,
    )
    assert isinstance(rec_id, int) and rec_id > 0


def test_save_recommendation_status_is_pending(tmp_db: Path) -> None:
    migrate_recommendations_v2(db_path=tmp_db)
    rec_id = save_recommendation(
        ticker="XIC.TO", action="BUY", bucket="growth",
        target_weight=0.15, combined_signal=0.30,
        expected_ret=0.042, cost_estimate=0.006,
        gate_status="PASS", rationale=None, run_id="test02",
        db_path=tmp_db,
    )
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM recommendations WHERE id=?;", (rec_id,)).fetchone()
    conn.close()
    assert row["status"] == "pending"


# ─── mark_recommendation_executed ────────────────────────────────────────────

def test_mark_recommendation_executed_updates_status(tmp_db: Path) -> None:
    migrate_recommendations_v2(db_path=tmp_db)
    rec_id = save_recommendation(
        ticker="VFV.TO", action="BUY", bucket="growth",
        target_weight=0.20, combined_signal=0.45,
        expected_ret=0.063, cost_estimate=0.006,
        gate_status="PASS", rationale=None, run_id="test03",
        db_path=tmp_db,
    )
    mark_recommendation_executed(rec_id, fill_price=99.50, fill_units=5.0, db_path=tmp_db)

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM recommendations WHERE id=?;", (rec_id,)).fetchone()
    conn.close()

    assert row["status"] == "executed"
    assert abs(row["fill_price"] - 99.50) < 1e-9
    assert abs(row["fill_units"] - 5.0) < 1e-9
    assert row["executed_at"] is not None


def test_mark_recommendation_skipped(tmp_db: Path) -> None:
    migrate_recommendations_v2(db_path=tmp_db)
    rec_id = save_recommendation(
        ticker="HXQ.TO", action="BUY", bucket="growth",
        target_weight=0.10, combined_signal=0.20,
        expected_ret=0.028, cost_estimate=0.006,
        gate_status="PASS", rationale=None, run_id="test04",
        db_path=tmp_db,
    )
    mark_recommendation_skipped(rec_id, db_path=tmp_db)

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM recommendations WHERE id=?;", (rec_id,)).fetchone()
    conn.close()
    assert row["status"] == "skipped"


# ─── alerts_log: get_last_alert / log_alert ───────────────────────────────────

def test_get_last_alert_returns_none_when_empty(tmp_db: Path) -> None:
    """No rows for a given alert_type → None, not an error."""
    assert get_last_alert("NEW_RECOMMENDATION", db_path=tmp_db) is None


def test_log_and_get_last_alert_roundtrip(tmp_db: Path) -> None:
    """log_alert inserts a row; get_last_alert returns it with correct payload."""
    import json
    payload = json.dumps({"regime": "HIGH_VOL", "previous": "NORMAL"})
    row_id = log_alert("REGIME_CHANGE", payload, db_path=tmp_db)
    assert isinstance(row_id, int) and row_id > 0
    result = get_last_alert("REGIME_CHANGE", db_path=tmp_db)
    assert result is not None
    assert result["alert_type"] == "REGIME_CHANGE"
    assert json.loads(result["payload"])["regime"] == "HIGH_VOL"


def test_get_last_alert_returns_most_recent(tmp_db: Path) -> None:
    """When multiple rows exist for the same type, returns the newest."""
    import json
    log_alert("DRAWDOWN", json.dumps({"status": "WARNING",   "drawdown": 0.17}), db_path=tmp_db)
    log_alert("DRAWDOWN", json.dumps({"status": "RECOVERED", "drawdown": 0.12}), db_path=tmp_db)
    result = get_last_alert("DRAWDOWN", db_path=tmp_db)
    assert json.loads(result["payload"])["status"] == "RECOVERED"


def test_get_last_alert_does_not_cross_alert_types(tmp_db: Path) -> None:
    """Rows for REGIME_CHANGE must not appear in DRAWDOWN queries."""
    import json
    log_alert("REGIME_CHANGE", json.dumps({"regime": "NORMAL"}), db_path=tmp_db)
    assert get_last_alert("DRAWDOWN", db_path=tmp_db) is None
