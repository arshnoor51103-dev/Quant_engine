"""
CLI-level tests for phase3 commands.

Covers behaviour that the pure-function tests in test_recommendations.py cannot:
  - F2: recommend_command soft-halts BUY cards at the drawdown ceiling
  - F1/F12: execute_command blocks at the CRA annual trade cap (logged --force override)

These tests monkeypatch the data-access functions imported into phase3_commands
so they run offline with no DB. Targets are the names as bound in the
phase3_commands module (import-site), not their definition modules.
"""
from __future__ import annotations

import pandas as pd
import pytest
import typer

import src.cli.phase3_commands as p3
from src.portfolio.model import Holding
from src.portfolio.recommendations import TradeCard, GateStatus


# ─── F2: drawdown soft-halt wiring ────────────────────────────────────────────

def test_recommend_halts_buys_at_drawdown_ceiling(monkeypatch, capsys):
    """recommend_command must convert BUY cards to SKIP and print a HALT banner
    when current drawdown is at/above the ceiling."""
    monkeypatch.setattr(p3, "get_holdings",
                        lambda: [Holding("VFV.TO", 10.0, 100.0, "growth", 70.0)])
    monkeypatch.setattr(p3, "nav", lambda h: 700.0)
    monkeypatch.setattr(p3, "load_universe_map", lambda: {"VFV.TO": {"bucket": "growth"}})
    monkeypatch.setattr(p3, "price_series",
                        lambda t, lookback_days=0: pd.Series(
                            [100.0, 110.0, 70.0],
                            index=pd.date_range("2025-01-01", periods=3)))
    monkeypatch.setattr(p3, "get_annual_trade_count", lambda: 0)
    monkeypatch.setattr(p3, "get_all_last_buy_dates", lambda: {})
    # Deep drawdown: peak 120 -> 70 = -41.7% (>= 20% ceiling)
    monkeypatch.setattr(p3, "_portfolio_nav_series",
                        lambda h, pdata: pd.Series([100.0, 120.0, 70.0]))
    # Force exactly one BUY card regardless of what the signals produce
    buy = TradeCard(ticker="VFV.TO", bucket="growth", action="BUY", units=1.0,
                    est_price=70.0, delta_dollars=70.0, combined_signal=0.5,
                    expected_return_pct=0.07, gate_status=GateStatus.PASS,
                    cost_estimate=0.006)
    monkeypatch.setattr(p3, "generate_trade_cards", lambda **k: [buy])

    p3.recommend_command(cash=1000.0, save=False, optimize=False, notify=False)

    out = capsys.readouterr().out
    assert "HALT" in out, f"expected a drawdown HALT banner; output was:\n{out}"
    assert buy.action == "SKIP", "BUY card should have been soft-halted to SKIP"
    assert buy.gate_status == GateStatus.DRAWDOWN_HALT


# ─── F1/F12: CRA cap enforcement in execute_command ───────────────────────────

def _pending_buy(rid: int = 1) -> dict:
    return {"id": rid, "status": "pending", "action": "BUY", "ticker": "VFV.TO"}


def test_execute_blocks_at_cra_cap(monkeypatch):
    """F12: trade #25 must be blocked before record_trade when at the CRA cap."""
    monkeypatch.setattr(p3, "get_recommendation_by_id", lambda rid: _pending_buy(rid))
    monkeypatch.setattr(p3, "load_universe_map", lambda: {"VFV.TO": {"bucket": "growth"}})
    monkeypatch.setattr(p3, "get_annual_trade_count", lambda: 24)
    called = {"record": False}
    monkeypatch.setattr(p3, "record_trade",
                        lambda **k: called.__setitem__("record", True) or 1)
    with pytest.raises(typer.Exit):
        p3.execute_command(rec_id=1, price=100.0, units=1.0,
                           trade_date_str=None, force=False, justification=None)
    assert called["record"] is False, "record_trade must NOT run when blocked"


def test_execute_force_requires_justification(monkeypatch):
    """--force without --justification must still be refused."""
    monkeypatch.setattr(p3, "get_recommendation_by_id", lambda rid: _pending_buy(rid))
    monkeypatch.setattr(p3, "load_universe_map", lambda: {"VFV.TO": {"bucket": "growth"}})
    monkeypatch.setattr(p3, "get_annual_trade_count", lambda: 24)
    with pytest.raises(typer.Exit):
        p3.execute_command(rec_id=1, price=100.0, units=1.0,
                           trade_date_str=None, force=True, justification=None)


def test_execute_force_with_justification_proceeds(monkeypatch):
    """--force --justification past the cap proceeds AND logs the override."""
    monkeypatch.setattr(p3, "get_recommendation_by_id", lambda rid: _pending_buy(rid))
    monkeypatch.setattr(p3, "load_universe_map", lambda: {"VFV.TO": {"bucket": "growth"}})
    monkeypatch.setattr(p3, "get_annual_trade_count", lambda: 24)
    logged = {}
    monkeypatch.setattr(p3, "record_trade", lambda **k: 99)
    monkeypatch.setattr(p3, "mark_recommendation_executed", lambda *a, **k: None)
    monkeypatch.setattr(p3, "log", lambda *a, **k: logged.setdefault("msg", a))
    p3.execute_command(rec_id=1, price=100.0, units=1.0,
                       trade_date_str=None, force=True, justification="month-end rebalance")
    assert logged.get("msg") is not None, "CRA override must be logged"


def test_execute_under_cap_proceeds_without_force(monkeypatch):
    """Below the cap, execution proceeds normally (no force needed)."""
    monkeypatch.setattr(p3, "get_recommendation_by_id", lambda rid: _pending_buy(rid))
    monkeypatch.setattr(p3, "load_universe_map", lambda: {"VFV.TO": {"bucket": "growth"}})
    monkeypatch.setattr(p3, "get_annual_trade_count", lambda: 5)
    recorded = {}
    monkeypatch.setattr(p3, "record_trade", lambda **k: recorded.update(k) or 7)
    monkeypatch.setattr(p3, "mark_recommendation_executed", lambda *a, **k: None)
    p3.execute_command(rec_id=1, price=100.0, units=1.0,
                       trade_date_str=None, force=False, justification=None)
    assert recorded.get("ticker") == "VFV.TO"


# ─── F17: persisted target_weight is the real weight, not hardcoded 0.0 ────────

def test_recommend_save_persists_real_target_weight(monkeypatch):
    """A saved BUY card must persist its computed target_weight, not 0.0 (F17)."""
    monkeypatch.setattr(p3, "get_holdings",
                        lambda: [Holding("VFV.TO", 10.0, 100.0, "growth", 100.0)])
    monkeypatch.setattr(p3, "nav", lambda h: 1000.0)
    monkeypatch.setattr(p3, "load_universe_map", lambda: {"VFV.TO": {"bucket": "growth"}})
    monkeypatch.setattr(p3, "price_series",
                        lambda t, lookback_days=0: pd.Series(
                            [100.0, 101.0, 102.0],
                            index=pd.date_range("2025-01-01", periods=3)))
    monkeypatch.setattr(p3, "get_annual_trade_count", lambda: 0)
    monkeypatch.setattr(p3, "get_all_last_buy_dates", lambda: {})
    # No drawdown → no halt
    monkeypatch.setattr(p3, "_portfolio_nav_series",
                        lambda h, pdata: pd.Series([100.0, 100.0, 100.0]))
    # Deterministic equal-weight result for the saved ticker
    monkeypatch.setattr(p3, "compute_target_weights", lambda *a, **k: {"VFV.TO": 0.6})
    buy = TradeCard(ticker="VFV.TO", bucket="growth", action="BUY", units=1.0,
                    est_price=100.0, delta_dollars=100.0, combined_signal=0.5,
                    expected_return_pct=0.07, gate_status=GateStatus.PASS,
                    cost_estimate=0.006)
    monkeypatch.setattr(p3, "generate_trade_cards", lambda **k: [buy])
    # Capture persistence without touching a DB
    monkeypatch.setattr(p3, "persist_signals", lambda *a, **k: 0)
    saved = {}
    monkeypatch.setattr(p3, "save_recommendation",
                        lambda **k: saved.update(k) or 1)

    p3.recommend_command(cash=0.0, save=True, optimize=False, notify=False)

    assert saved.get("ticker") == "VFV.TO"
    assert saved.get("target_weight") == pytest.approx(0.6)
