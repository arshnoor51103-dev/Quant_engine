"""
Unit tests for Phase 3 SELL logic (signal-driven and drift-driven).

Covers:
  - SELL_SIGNAL: negative combined signal on held position → full exit
  - SELL_SIGNAL: cost gate blocks signals too weak to justify sell cost
  - SELL_SIGNAL: no holding → SKIP_SIGNAL, never SELL
  - SELL_DRIFT: bucket exits tolerance band + delta < 0 → partial trim
  - SELL_DRIFT: dollar floor blocks sub-threshold corrections
  - SELL_DRIFT: within tolerance → HOLD, not SELL
  - Min-hold gate applies to both SELL types (CRA round-trip prevention)
  - CRA warn/limit gates apply to SELL cards
  - sell_reason field populated correctly; None on non-SELL cards
  - SELL cards sorted before BUY cards in output
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import pytest

from src.portfolio.model import Holding
from src.portfolio.recommendations import (
    GateStatus,
    generate_trade_cards,
)
from src.signals.base import SignalResult
from src.signals.vol_regime import STABLE_TICKERS


# ─── Shared fixtures ──────────────────────────────────────────────────────────

UNIVERSE_MAP = {
    "VFV.TO":  {"bucket": "growth",   "spread_override": None},
    "XIC.TO":  {"bucket": "growth",   "spread_override": None},
    "HXQ.TO":  {"bucket": "growth",   "spread_override": None},
    "XEF.TO":  {"bucket": "growth",   "spread_override": None},
    "CHPS.TO": {"bucket": "growth",   "spread_override": None},
    "VAB.TO":  {"bucket": "stable",   "spread_override": None},
    "HSAV.TO": {"bucket": "stable",   "spread_override": None},
    "CDZ.TO":  {"bucket": "dividend", "spread_override": None},
    "VDY.TO":  {"bucket": "dividend", "spread_override": None},
}

BUCKET_CFG = {
    "growth":   {"target": 0.60, "tolerance": 0.10},
    "stable":   {"target": 0.25, "tolerance": 0.05},
    "dividend": {"target": 0.15, "tolerance": 0.05},
}

PORTFOLIO_CONFIG = {
    "allocation": BUCKET_CFG,
    "trading": {
        "spread_proxy": 0.0005,
        "anchor_return_annualized": 0.1398,
        "profit_floor": 0.005,
        "trade_threshold_multiplier": 2.0,
        "max_trades_per_year": 24,
        "cra_warn_threshold": 20,
        "min_holding_days": 14,
    },
    "rebalance": {
        "min_rebalance_trade": 50.0,
    },
}

LATEST_PRICES = {
    "VFV.TO": 120.0, "XIC.TO": 38.0, "HXQ.TO": 55.0, "XEF.TO": 32.0,
    "CHPS.TO": 80.0, "VAB.TO": 24.0, "HSAV.TO": 50.0,
    "CDZ.TO": 30.0,  "VDY.TO": 42.0,
}

RUN_DATE = date(2026, 5, 20)


def _mom_result(scores: dict[str, float]) -> SignalResult:
    return SignalResult(
        signal_name="momentum_252_21",
        run_date=RUN_DATE,
        scores=scores,
        metadata={"raw_returns": {}, "skipped_tickers": []},
    )


def _regime_result(regime: str) -> SignalResult:
    regime_scores = {
        "low_vol": 1.0, "normal": 0.3, "high_vol": -0.5, "crisis": -1.0,
    }
    base = regime_scores.get(regime, 0.3)
    scores = {
        t: (-base if t in STABLE_TICKERS else base)
        for t in UNIVERSE_MAP
    }
    return SignalResult(
        signal_name="vol_regime_21d",
        run_date=RUN_DATE,
        scores=scores,
        metadata={"regime": regime, "vol_percentile": 0.5},
    )


def _no_last_buys() -> dict:
    return {t: None for t in UNIVERSE_MAP}


def _run(
    mom_scores: dict[str, float],
    holdings: list[Holding] | None = None,
    nav: float | None = None,
    cash: float = 0.0,
    regime: str = "normal",
    annual_trades: int = 0,
    last_buys: dict | None = None,
    config: dict | None = None,
) -> list:
    """Helper: call generate_trade_cards with test fixtures."""
    h = holdings or []
    portfolio_nav = nav if nav is not None else sum(hld.market_value for hld in h)
    if portfolio_nav == 0.0 and cash == 0.0:
        cash = 800.0
    return generate_trade_cards(
        momentum_result=_mom_result(mom_scores),
        regime_result=_regime_result(regime),
        holdings=h,
        portfolio_config=config or PORTFOLIO_CONFIG,
        universe_map=UNIVERSE_MAP,
        portfolio_nav=portfolio_nav,
        cash=cash,
        annual_trade_count=annual_trades,
        last_buy_dates=last_buys or _no_last_buys(),
        latest_prices=LATEST_PRICES,
    )


# ─── Scenario helpers ─────────────────────────────────────────────────────────

def _vfv_overweight(units: float = 8.0) -> list[Holding]:
    """VFV.TO: {units} × $120 in growth bucket.  All-cash portfolio → growth 100% > 70%."""
    return [
        Holding(ticker="VFV.TO", units=units, avg_cost=100.0,
                bucket="growth", last_price=120.0)
    ]


def _vfv_positive_only_mom() -> dict[str, float]:
    """Only VFV.TO has a positive momentum score; all others negative."""
    return {t: (-1.0 if t != "VFV.TO" else 1.0) for t in UNIVERSE_MAP}


# ─── SELL_SIGNAL tests ────────────────────────────────────────────────────────

def test_sell_signal_fires_on_held_negative_signal():
    """Held ticker with negative combined signal → SELL card with sell_reason SIGNAL."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=0.0)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.action == "SELL"
    assert cdz.sell_reason == "SIGNAL"


def test_sell_signal_full_exit_uses_all_held_units():
    """Signal-driven SELL sets units = all held units (full exit)."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=0.0)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.units == pytest.approx(5.0)


def test_sell_signal_delta_is_full_negative_market_value():
    """delta_dollars for SELL_SIGNAL equals -(units × price) of the full position."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=0.0)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.delta_dollars == pytest.approx(-(5.0 * 30.0))


def test_sell_signal_no_holding_produces_skip_not_sell():
    """Negative signal with no holding → SKIP_SIGNAL gate, never SELL."""
    mom_scores = {t: -1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, cash=800.0)
    for c in cards:
        if c.ticker not in STABLE_TICKERS:
            assert c.action != "SELL", f"{c.ticker} produced SELL with no holding"
            assert c.gate_status == GateStatus.SKIP_SIGNAL


def test_sell_signal_blocked_by_cost_gate():
    """
    Very weak negative signal fails the cost gate.

    LOW_VOL regime (clamped=1.0) + momentum=-0.001:
      combined = -0.001 × 1.0 = -0.001
      sell_exp_ret = 0.001 × 0.1398 = 0.0001398 < cost_threshold 0.006 → SKIP_COST
    """
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: -0.001 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=0.0, regime="low_vol")
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.action == "SKIP"
    assert cdz.gate_status == GateStatus.SKIP_COST
    assert cdz.sell_reason == "SIGNAL"


# ─── SELL_DRIFT tests ─────────────────────────────────────────────────────────

def test_sell_drift_fires_when_bucket_overweight():
    """
    Growth bucket at 100% (well above 70% tolerance) with positive signal
    and delta < 0 → SELL card with sell_reason DRIFT.

    VFV.TO: 8 × $120 = $960.  total_capital = $960.
    bucket_actual[growth] = 1.0 > 0.70 → overweight.
    target = 60% × $960 = $576.  delta = $576 − $960 = −$384 < 0.
    """
    cards = _run(_vfv_positive_only_mom(), holdings=_vfv_overweight(), cash=0.0)
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    assert vfv.action == "SELL"
    assert vfv.sell_reason == "DRIFT"


def test_sell_drift_partial_units():
    """
    Drift-driven SELL units = round(|delta| / price, 2).

    |delta| = $384, price = $120 → round(3.2, 2) = 3.2.
    """
    cards = _run(_vfv_positive_only_mom(), holdings=_vfv_overweight(), cash=0.0)
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    expected_units = round(384.0 / 120.0, 2)
    assert vfv.units == pytest.approx(expected_units)


def test_sell_drift_blocked_by_dollar_floor():
    """Dollar floor blocks drift correction when |delta| < min_rebalance_trade."""
    # Set floor to $1000; |delta| = $384 < $1000 → HOLD not SELL
    config = {**PORTFOLIO_CONFIG, "rebalance": {"min_rebalance_trade": 1000.0}}
    cards = _run(
        _vfv_positive_only_mom(),
        holdings=_vfv_overweight(),
        cash=0.0,
        config=config,
    )
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    assert vfv.action == "HOLD"
    assert vfv.sell_reason is None


def test_sell_drift_not_triggered_within_tolerance():
    """
    Positive signal + delta < 0 but bucket within tolerance band → HOLD not SELL.

    VFV.TO: 4 × $120 = $480. cash=$240. total=$720.
    bucket_actual[growth] = 480/720 = 66.7% < 70% → within tolerance → no SELL.
    """
    holdings = [Holding("VFV.TO", units=4.0, avg_cost=100.0, bucket="growth", last_price=120.0)]
    cards = _run(_vfv_positive_only_mom(), holdings=holdings, cash=240.0)
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    assert vfv.action == "HOLD"
    assert vfv.sell_reason is None


# ─── Min-hold gate tests ──────────────────────────────────────────────────────

def test_min_hold_blocks_signal_sell():
    """Last buy < 14 days ago → SELL_SIGNAL blocked with MIN_HOLD gate."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    recent_buys = {**_no_last_buys(), "CDZ.TO": RUN_DATE - timedelta(days=5)}
    cards = _run(mom_scores, holdings=holdings, cash=0.0, last_buys=recent_buys)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.gate_status == GateStatus.MIN_HOLD
    assert cdz.sell_reason == "SIGNAL"


def test_min_hold_blocks_drift_sell():
    """Last buy < 14 days ago → SELL_DRIFT blocked with MIN_HOLD gate."""
    recent_buys = {**_no_last_buys(), "VFV.TO": RUN_DATE - timedelta(days=5)}
    cards = _run(
        _vfv_positive_only_mom(),
        holdings=_vfv_overweight(),
        cash=0.0,
        last_buys=recent_buys,
    )
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    assert vfv.gate_status == GateStatus.MIN_HOLD
    assert vfv.sell_reason == "DRIFT"


def test_min_hold_passes_after_threshold_allows_sell():
    """Last buy >= 14 days ago → SELL not blocked by MIN_HOLD."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    old_buys = {**_no_last_buys(), "CDZ.TO": RUN_DATE - timedelta(days=15)}
    cards = _run(mom_scores, holdings=holdings, cash=0.0, last_buys=old_buys)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.action == "SELL"
    assert cdz.gate_status != GateStatus.MIN_HOLD


# ─── CRA gate tests ───────────────────────────────────────────────────────────

def test_sell_cra_warn_applies():
    """At cra_warn_threshold (20 trades), SELL card carries CRA_WARN gate."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=0.0, annual_trades=20)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.action == "SELL"
    assert cdz.gate_status == GateStatus.CRA_WARN


def test_sell_cra_limit_still_shows_sell_card():
    """At max_trades (24), SELL card is still generated but carries CRA_LIMIT gate."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=0.0, annual_trades=24)
    cdz = next(c for c in cards if c.ticker == "CDZ.TO")
    assert cdz.action == "SELL"
    assert cdz.gate_status == GateStatus.CRA_LIMIT


# ─── sell_reason field correctness ───────────────────────────────────────────

def test_non_sell_cards_have_sell_reason_none():
    """BUY, HOLD, WARN, and SKIP cards must always have sell_reason=None."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, cash=800.0)
    for c in cards:
        assert c.sell_reason is None, (
            f"{c.ticker} ({c.action}) has sell_reason={c.sell_reason!r}, expected None"
        )


# ─── Sort order ───────────────────────────────────────────────────────────────

def test_sell_cards_appear_before_buy_cards():
    """All SELL cards must sort before all BUY cards in generate_trade_cards output."""
    holdings = [Holding("CDZ.TO", units=5.0, avg_cost=28.0, bucket="dividend", last_price=30.0)]
    mom_scores = {t: (1.0 if t != "CDZ.TO" else -1.0) for t in UNIVERSE_MAP}
    cards = _run(mom_scores, holdings=holdings, cash=800.0)

    positions: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(cards):
        positions[c.action].append(i)

    sell_pos = positions.get("SELL", [])
    buy_pos = positions.get("BUY", [])
    if sell_pos and buy_pos:
        assert max(sell_pos) < min(buy_pos), (
            f"SELL positions {sell_pos} must all precede BUY positions {buy_pos}"
        )
