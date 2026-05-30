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
