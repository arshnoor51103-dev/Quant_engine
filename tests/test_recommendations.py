"""
Unit tests for Phase 3 P0 trade recommendation engine.

Tests cover:
  - Combined signal computation (multiplicative regime gate + stable equal-weight)
  - Target weight allocation within buckets
  - Gate logic: signal, cost, min-hold, CRA warn/limit
  - Cold-start (NAV=0 + --cash) math
  - BUY-only constraint (no SELL cards generated)
  - NAV=0 with no cash raises clear error
  - CRISIS regime suppresses all growth/dividend buys
  - OVERWEIGHT bucket detection
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.portfolio.recommendations import (
    GateStatus,
    STABLE_TICKERS,
    compute_combined_scores,
    compute_target_weights,
    generate_trade_cards,
)
from src.signals.base import SignalResult
from src.portfolio.model import Holding


# ─── Fixtures ────────────────────────────────────────────────────────────────

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
        "low_vol": 1.0, "normal": 0.3, "high_vol": -0.5, "crisis": -1.0
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


def _no_holdings() -> list:
    return []


def _no_last_buys() -> dict:
    return {t: None for t in UNIVERSE_MAP}


# ─── compute_combined_scores ─────────────────────────────────────────────────

def test_combined_stable_always_equal_weight():
    """Stable tickers get 1/n_stable regardless of regime or momentum."""
    mom = _mom_result({t: -1.0 for t in UNIVERSE_MAP})
    regime = _regime_result("normal")
    scores = compute_combined_scores(mom, regime)
    for t in STABLE_TICKERS:
        assert scores[t] == pytest.approx(1.0 / len(STABLE_TICKERS))


def test_combined_crisis_kills_growth():
    """In CRISIS regime, all growth/dividend tickers get combined score = 0."""
    mom = _mom_result({t: 1.0 for t in UNIVERSE_MAP})
    regime = _regime_result("crisis")
    scores = compute_combined_scores(mom, regime)
    for t in UNIVERSE_MAP:
        if t not in STABLE_TICKERS:
            assert scores[t] == pytest.approx(0.0)


def test_combined_normal_multiplies_momentum():
    """In NORMAL regime, growth/dividend combined = momentum × 0.3."""
    mom_scores = {t: 0.5 for t in UNIVERSE_MAP}
    mom = _mom_result(mom_scores)
    regime = _regime_result("normal")
    scores = compute_combined_scores(mom, regime)
    for t in UNIVERSE_MAP:
        if t not in STABLE_TICKERS:
            assert scores[t] == pytest.approx(0.5 * 0.3)


def test_combined_low_vol_full_momentum():
    """In LOW_VOL regime, combined = momentum × 1.0 for growth/dividend."""
    mom_scores = {t: 0.75 for t in UNIVERSE_MAP}
    mom = _mom_result(mom_scores)
    regime = _regime_result("low_vol")
    scores = compute_combined_scores(mom, regime)
    for t in UNIVERSE_MAP:
        if t not in STABLE_TICKERS:
            assert scores[t] == pytest.approx(0.75)


def test_combined_negative_momentum_skipped_in_normal():
    """Negative momentum × positive regime = negative combined → SKIP."""
    mom_scores = {t: -0.5 for t in UNIVERSE_MAP}
    mom = _mom_result(mom_scores)
    regime = _regime_result("normal")
    scores = compute_combined_scores(mom, regime)
    for t in UNIVERSE_MAP:
        if t not in STABLE_TICKERS:
            assert scores[t] < 0.0


# ─── compute_target_weights ──────────────────────────────────────────────────

def test_target_weights_sum_to_bucket_targets_when_fully_allocated():
    """When all tickers have positive signals, bucket weights sum to 1.0."""
    combined = {t: 0.5 for t in UNIVERSE_MAP}
    weights = compute_target_weights(combined, BUCKET_CFG, UNIVERSE_MAP)
    growth_sum = sum(weights[t] for t in UNIVERSE_MAP if UNIVERSE_MAP[t]["bucket"] == "growth")
    stable_sum = sum(weights[t] for t in UNIVERSE_MAP if UNIVERSE_MAP[t]["bucket"] == "stable")
    div_sum    = sum(weights[t] for t in UNIVERSE_MAP if UNIVERSE_MAP[t]["bucket"] == "dividend")
    assert growth_sum == pytest.approx(0.60)
    assert stable_sum == pytest.approx(0.25)
    assert div_sum    == pytest.approx(0.15)


def test_target_weights_proportional_within_bucket():
    """Higher combined score → higher weight within bucket."""
    combined = {t: 0.0 for t in UNIVERSE_MAP}
    combined["VFV.TO"] = 0.6
    combined["XIC.TO"] = 0.3
    combined["HXQ.TO"] = 0.0
    combined["XEF.TO"] = 0.0
    for t in STABLE_TICKERS:
        combined[t] = 1.0 / 3
    combined["CDZ.TO"] = 0.5
    combined["VDY.TO"] = 0.5

    weights = compute_target_weights(combined, BUCKET_CFG, UNIVERSE_MAP)
    assert weights["VFV.TO"] > weights["XIC.TO"]
    assert weights["HXQ.TO"] == pytest.approx(0.0)
    assert weights["CDZ.TO"] == pytest.approx(weights["VDY.TO"])


def test_target_weights_zero_bucket_when_no_positive_signals():
    """Bucket with no positive combined scores gets zero allocation."""
    combined = {t: -0.5 for t in UNIVERSE_MAP}
    for t in STABLE_TICKERS:
        combined[t] = 1.0 / 3  # stable still positive
    weights = compute_target_weights(combined, BUCKET_CFG, UNIVERSE_MAP)
    growth_sum = sum(weights[t] for t in UNIVERSE_MAP if UNIVERSE_MAP[t]["bucket"] == "growth")
    div_sum    = sum(weights[t] for t in UNIVERSE_MAP if UNIVERSE_MAP[t]["bucket"] == "dividend")
    assert growth_sum == pytest.approx(0.0)
    assert div_sum    == pytest.approx(0.0)


# ─── generate_trade_cards ────────────────────────────────────────────────────

def _run(
    mom_scores: dict[str, float],
    regime: str = "normal",
    nav: float = 0.0,
    cash: float = 800.0,
    annual_trades: int = 0,
    last_buys: dict | None = None,
) -> list:
    return generate_trade_cards(
        momentum_result=_mom_result(mom_scores),
        regime_result=_regime_result(regime),
        holdings=_no_holdings(),
        portfolio_config=PORTFOLIO_CONFIG,
        universe_map=UNIVERSE_MAP,
        portfolio_nav=nav,
        cash=cash,
        annual_trade_count=annual_trades,
        last_buy_dates=last_buys or _no_last_buys(),
        latest_prices=LATEST_PRICES,
    )


def test_cold_start_generates_buy_cards():
    """NAV=0 + cash=800 → BUY cards using target_weight × cash sizing."""
    mom_scores = {t: 0.5 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, cash=800.0)
    buy_cards = [c for c in cards if c.action == "BUY"]
    assert len(buy_cards) > 0


def test_cold_start_math_no_double_count():
    """
    Cold-start delta must equal target_weight × cash exactly.
    No existing holdings, so there is nothing to subtract.
    """
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cash = 1000.0
    cards = _run(mom_scores, cash=cash)
    total_delta = sum(c.delta_dollars for c in cards if c.delta_dollars and c.delta_dollars > 0)
    # All buckets positive → total deployed ≈ 100% of cash
    assert total_delta == pytest.approx(cash, rel=1e-6)


def test_raises_when_nav_zero_and_no_cash():
    """NAV=0 and cash=0 must raise ValueError with a clear message."""
    mom_scores = {t: 0.5 for t in UNIVERSE_MAP}
    with pytest.raises(ValueError, match="--cash"):
        generate_trade_cards(
            momentum_result=_mom_result(mom_scores),
            regime_result=_regime_result("normal"),
            holdings=_no_holdings(),
            portfolio_config=PORTFOLIO_CONFIG,
            universe_map=UNIVERSE_MAP,
            portfolio_nav=0.0,
            cash=0.0,
            annual_trade_count=0,
            last_buy_dates=_no_last_buys(),
            latest_prices=LATEST_PRICES,
        )


def test_buy_only_no_sell_cards():
    """No SELL action cards are ever generated (P0 constraint)."""
    mom_scores = {t: 0.5 for t in UNIVERSE_MAP}
    cards = _run(mom_scores)
    assert all(c.action != "SELL" for c in cards)


def test_crisis_suppresses_growth_dividend_buys():
    """In CRISIS regime, growth and dividend tickers must not produce BUY cards."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, regime="crisis")
    buy_cards = [c for c in cards if c.action == "BUY"]
    for c in buy_cards:
        assert c.bucket == "stable", (
            f"{c.ticker} ({c.bucket}) should not BUY in CRISIS"
        )


def test_negative_momentum_produces_skip_signal():
    """Tickers with negative combined signal get SKIP_SIGNAL gate."""
    mom_scores = {t: -1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores)
    non_stable = [c for c in cards if c.ticker not in STABLE_TICKERS]
    for c in non_stable:
        assert c.gate_status == GateStatus.SKIP_SIGNAL


def test_cra_warn_fires_at_threshold():
    """Annual trade count at warn threshold → CRA_WARN gate on BUY cards."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, annual_trades=20)
    buy_cards = [c for c in cards if c.action == "BUY"]
    assert len(buy_cards) > 0
    for c in buy_cards:
        assert c.gate_status == GateStatus.CRA_WARN


def test_cra_limit_still_shows_buy_cards():
    """At max trades (24), BUY cards are still generated with CRA_LIMIT gate."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, annual_trades=24)
    buy_cards = [c for c in cards if c.action == "BUY"]
    assert len(buy_cards) > 0
    for c in buy_cards:
        assert c.gate_status == GateStatus.CRA_LIMIT


def test_min_hold_gate_fires():
    """Ticker bought 5 days ago → MIN_HOLD gate."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    recent_buy = {t: None for t in UNIVERSE_MAP}
    recent_buy["VFV.TO"] = RUN_DATE - timedelta(days=5)
    cards = _run(mom_scores, last_buys=recent_buy)
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    assert vfv.gate_status == GateStatus.MIN_HOLD


def test_min_hold_passes_after_threshold():
    """Ticker bought 15 days ago → gate passes (min hold = 14)."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    old_buy = {t: None for t in UNIVERSE_MAP}
    old_buy["VFV.TO"] = RUN_DATE - timedelta(days=15)
    cards = _run(mom_scores, last_buys=old_buy)
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    assert vfv.gate_status in (GateStatus.PASS, GateStatus.CRA_WARN, GateStatus.CRA_LIMIT)
    assert vfv.action == "BUY"


def test_cost_gate_blocks_weak_signal():
    """
    A combined score near zero should fail the cost gate.

    cost_threshold = 2×0.0005 + 0.005 = 0.006
    anchor = 0.1398
    minimum failing score: combined < 0.006/0.1398 ≈ 0.043
    We test with combined = 0.001 (very close to zero regime × momentum).
    """
    # In NORMAL regime (0.3), momentum of 0.001/0.3 ≈ 0.0033 → combined ≈ 0.001
    # Rank-normalization prevents fractional scores in practice, but we test
    # the engine directly with a crafted combined score via low_vol + tiny momentum.
    # Use a custom universe_map with just one growth ticker for isolation.
    tiny_mom = {t: 0.001 for t in UNIVERSE_MAP}  # near-zero, in LOW_VOL: combined = 0.001
    # In LOW_VOL (clamped=1.0): combined = 0.001 × 1.0 = 0.001
    # expected_ret = 0.001 × 0.1398 = 0.0001398 < 0.006 → SKIP_COST
    cards = _run(tiny_mom, regime="low_vol")
    non_stable_skip = [
        c for c in cards
        if c.ticker not in STABLE_TICKERS and c.gate_status == GateStatus.SKIP_COST
    ]
    assert len(non_stable_skip) > 0


def test_buy_cards_sorted_by_delta_desc():
    """BUY cards must be sorted by delta_dollars descending."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, cash=5000.0)
    buy_cards = [c for c in cards if c.action == "BUY"]
    deltas = [c.delta_dollars for c in buy_cards]
    assert deltas == sorted(deltas, reverse=True)


def test_units_computed_from_delta_over_price():
    """units == delta_dollars / est_price for BUY cards."""
    mom_scores = {t: 1.0 for t in UNIVERSE_MAP}
    cards = _run(mom_scores, cash=1000.0)
    for c in cards:
        if c.action == "BUY" and c.units is not None and c.est_price and c.delta_dollars:
            assert c.units == pytest.approx(c.delta_dollars / c.est_price, rel=1e-6)


# ─── spread_override (F8) ─────────────────────────────────────────────────────

def test_zero_spread_override_is_honoured():
    """F8: a deliberate spread_override of 0.0 must NOT fall back to spread_proxy."""
    cfg = {
        "allocation": BUCKET_CFG,
        "trading": {
            "spread_proxy": 0.10,  # large, so a falsy-zero fallback would blow the gate
            "anchor_return_annualized": 0.1398,
            "profit_floor": 0.005,
            "trade_threshold_multiplier": 2.0,
            "max_trades_per_year": 24,
            "cra_warn_threshold": 20,
            "min_holding_days": 14,
        },
    }
    cards = generate_trade_cards(
        momentum_result=_mom_result({"VFV.TO": 0.9}),
        regime_result=_regime_result("normal"),
        holdings=[],
        portfolio_config=cfg,
        universe_map={"VFV.TO": {"bucket": "growth", "spread_override": 0.0}},
        portfolio_nav=0.0,
        cash=1000.0,
        annual_trade_count=0,
        last_buy_dates={},
        latest_prices={"VFV.TO": 100.0},
    )
    vfv = next(c for c in cards if c.ticker == "VFV.TO")
    # spread=0.0 -> gate_threshold = 2*0 + 0.005 = 0.005; BUY fires, cost_estimate=0.005.
    # With the bug (spread=spread_proxy=0.10 -> threshold 0.205) VFV would SKIP_COST.
    assert vfv.action == "BUY"
    assert vfv.cost_estimate == pytest.approx(0.005)


# ─── drift-SELL cost_estimate (F5) ────────────────────────────────────────────

def test_drift_sell_sets_cost_estimate():
    """F5: a drift trim must populate cost_estimate (= 2*spread), not leave it None."""
    cfg = {
        "allocation": {
            "growth":   {"target": 0.10, "tolerance": 0.01},  # tiny target -> growth overweight
            "stable":   {"target": 0.25, "tolerance": 0.05},
            "dividend": {"target": 0.15, "tolerance": 0.05},
        },
        "trading": {
            "spread_proxy": 0.0005,
            "anchor_return_annualized": 0.1398,
            "profit_floor": 0.005,
            "trade_threshold_multiplier": 2.0,
            "max_trades_per_year": 24,
            "cra_warn_threshold": 20,
            "min_holding_days": 14,
        },
        "rebalance": {"min_rebalance_trade": 50.0},
    }
    holdings = [Holding(ticker="VFV.TO", units=100.0, avg_cost=100.0,
                        bucket="growth", last_price=100.0)]  # $10k, growth = 100% (overweight)
    cards = generate_trade_cards(
        momentum_result=_mom_result({"VFV.TO": 0.01, "VAB.TO": 0.0}),
        regime_result=_regime_result("normal"),
        holdings=holdings,
        portfolio_config=cfg,
        universe_map={"VFV.TO": {"bucket": "growth"}, "VAB.TO": {"bucket": "stable"}},
        portfolio_nav=10000.0,
        cash=0.0,
        annual_trade_count=0,
        last_buy_dates={},
        latest_prices={"VFV.TO": 100.0, "VAB.TO": 25.0},
    )
    drift = next((c for c in cards if c.sell_reason == "DRIFT" and c.action == "SELL"), None)
    assert drift is not None, f"expected a DRIFT SELL card; got {[(c.ticker, c.action, c.sell_reason) for c in cards]}"
    assert drift.cost_estimate == pytest.approx(2 * 0.0005)
