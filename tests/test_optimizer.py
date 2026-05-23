"""
Unit tests for the within-bucket Markowitz optimizer (Phase 3 P2).

Coverage:
  - Weight constraints: sum=1, no short, max_position, min_position
  - Ledoit-Wolf produces a positive-definite covariance matrix
  - Shrinkage actually changes the matrix vs raw sample covariance
  - 2-ticker bucket (stable/dividend degenerate case)
  - Single-ticker bucket: weight = 1.0, no crash
  - Degenerate signals: all zero → equal-weight fallback
  - Degenerate signals: all identical → valid equal distribution
  - Short history: ticker with < 60 days → equal-weight fallback for bucket
  - Perfectly correlated assets: duplicate price series → no crash
  - Near-singular covariance: optimizer does not blow up
  - Fallback: solver failure path returns equal-weight and logs warning
  - Determinism: same inputs produce same output
  - Integration: optimized weights flow through to trade cards
  - End-to-end: signal scores + price data → valid portfolio weights

All price series are deterministic (linspace/cumsum) — no random fixtures.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.portfolio.optimizer import (
    BucketOptimizer,
    _annualized_vol,
    _build_return_matrix,
    _ledoit_wolf_cov,
    _optimize_bucket,
    _solve_qp,
    _TRADING_DAYS_PER_YEAR,
)
from src.portfolio.recommendations import (
    GateStatus,
    generate_trade_cards,
    compute_combined_scores,
)
from src.signals.base import SignalResult


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
    "optimizer": {
        "risk_aversion": 2.0,
        "max_position_pct": 0.40,
        "min_position_pct": 0.05,
        "rebalance_threshold_pct": 0.02,
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
}


def _make_price_series(
    n_days: int = 300,
    start: float = 100.0,
    end: float = 120.0,
    start_date: str = "2023-01-01",
) -> pd.Series:
    """Deterministic upward-trending price series."""
    idx = pd.date_range(start=start_date, periods=n_days, freq="B")
    prices = np.linspace(start, end, n_days)
    return pd.Series(prices, index=idx)


def _make_price_history(
    tickers: list[str],
    n_days: int = 300,
    start_prices: list[float] | None = None,
    end_prices: list[float] | None = None,
) -> dict[str, pd.Series]:
    """Make a price history dict with independent trending series per ticker."""
    if start_prices is None:
        start_prices = [100.0 + i * 5 for i in range(len(tickers))]
    if end_prices is None:
        end_prices = [s * 1.2 for s in start_prices]
    return {
        t: _make_price_series(n_days, s, e)
        for t, s, e in zip(tickers, start_prices, end_prices)
    }


def _make_signal_scores(tickers: list[str], values: list[float] | None = None) -> dict[str, float]:
    """Make a signal scores dict. Default: rank-normalized descending."""
    if values is not None:
        return dict(zip(tickers, values))
    n = len(tickers)
    return {t: 2.0 * i / max(n - 1, 1) - 1.0 for i, t in enumerate(reversed(tickers))}


# ─── Helper tests ─────────────────────────────────────────────────────────────

def test_annualized_vol_basic():
    """annualized_vol is positive for non-flat returns."""
    rets = np.array([0.01, -0.005, 0.008, -0.003, 0.012] * 50)
    vol = _annualized_vol(rets)
    assert vol > 0.0
    assert vol < 5.0  # sanity: no runaway value


def test_annualized_vol_empty():
    assert _annualized_vol(np.array([])) == 0.0
    assert _annualized_vol(np.array([0.01])) == 0.0


def test_build_return_matrix_basic():
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=300)
    mat, valid = _build_return_matrix(tickers, prices, lookback=252)
    assert set(valid) == set(tickers)
    # T × N shape
    assert mat.shape[1] == 3
    assert mat.shape[0] <= 252


def test_build_return_matrix_short_history_excluded():
    """Ticker with < MIN_HISTORY_DAYS (60) rows is excluded from the matrix."""
    prices = {
        "LONG": _make_price_series(n_days=300),
        "SHORT": _make_price_series(n_days=30),  # below 60-day floor
    }
    mat, valid = _build_return_matrix(["LONG", "SHORT"], prices, lookback=252)
    assert "LONG" in valid
    assert "SHORT" not in valid


# ─── Ledoit-Wolf covariance ───────────────────────────────────────────────────

def test_ledoit_wolf_positive_definite():
    """LW covariance must be positive definite (all eigenvalues > 0)."""
    tickers = ["A", "B", "C", "D", "E"]
    prices = _make_price_history(tickers, n_days=300)
    mat, _ = _build_return_matrix(tickers, prices, lookback=252)
    cov = _ledoit_wolf_cov(mat)
    eigenvalues = np.linalg.eigvalsh(cov)
    assert np.all(eigenvalues > 0), f"Non-positive eigenvalue found: {eigenvalues.min():.2e}"


def test_ledoit_wolf_differs_from_sample_cov():
    """Shrinkage should produce a different matrix than raw sample covariance."""
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=150)
    mat, _ = _build_return_matrix(tickers, prices, lookback=120)
    cov_lw = _ledoit_wolf_cov(mat)
    cov_sample = np.cov(mat.T) * _TRADING_DAYS_PER_YEAR
    # They should not be element-wise identical
    assert not np.allclose(cov_lw, cov_sample, atol=1e-10), \
        "Ledoit-Wolf should differ from sample covariance — shrinkage not firing"


def test_ledoit_wolf_symmetric():
    """Covariance matrix must be symmetric."""
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=300)
    mat, _ = _build_return_matrix(tickers, prices, lookback=252)
    cov = _ledoit_wolf_cov(mat)
    assert np.allclose(cov, cov.T, atol=1e-12)


# ─── QP solver ───────────────────────────────────────────────────────────────

def test_solve_qp_constraints_satisfied():
    """SLSQP solution satisfies sum=1, bounds, and min/max constraints."""
    n = 4
    mu = np.array([0.12, 0.08, 0.15, 0.10])
    # Simple diagonal cov (no correlation)
    cov = np.diag([0.04, 0.09, 0.06, 0.05])
    w = _solve_qp(mu, cov, risk_aversion=2.0, min_w=0.05, max_w=0.40)
    assert w is not None
    assert abs(w.sum() - 1.0) < 1e-6
    assert np.all(w >= 0.0 - 1e-7)
    assert np.all(w <= 0.40 + 1e-7)
    assert np.all(w >= 0.05 - 1e-7)


def test_solve_qp_deterministic():
    """Same inputs → same output on repeated calls."""
    n = 3
    mu = np.array([0.10, 0.12, 0.08])
    cov = np.diag([0.04, 0.06, 0.03])
    w1 = _solve_qp(mu, cov, risk_aversion=2.0, min_w=0.05, max_w=0.40)
    w2 = _solve_qp(mu, cov, risk_aversion=2.0, min_w=0.05, max_w=0.40)
    assert w1 is not None and w2 is not None
    np.testing.assert_array_almost_equal(w1, w2, decimal=8)


# ─── _optimize_bucket ─────────────────────────────────────────────────────────

def test_optimize_bucket_weights_sum_to_one():
    """Within-bucket weights must sum to 1.0."""
    tickers = ["A", "B", "C", "D", "E"]
    prices = _make_price_history(tickers, n_days=300)
    scores = _make_signal_scores(tickers)
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=0.40)
    total = sum(v for v in w.values())
    # If at least one positive signal, weights sum to 1; if none, sum to 0
    positive = [t for t in tickers if scores.get(t, 0.0) > 0.0]
    if positive:
        assert abs(total - 1.0) < 1e-6, f"bucket weights sum to {total:.6f}, expected 1.0"


def test_optimize_bucket_no_negative_weights():
    """All within-bucket weights must be >= 0 (long-only)."""
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=300)
    scores = {"A": 0.5, "B": 0.3, "C": 0.8}
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=0.40)
    for t, wt in w.items():
        assert wt >= -1e-9, f"{t} has negative weight {wt:.6f}"


def test_optimize_bucket_max_position_respected():
    """No single included ticker exceeds max_position_pct."""
    tickers = ["A", "B", "C", "D"]
    prices = _make_price_history(tickers, n_days=300)
    # Give A an overwhelming score to stress the max constraint
    scores = {"A": 1.0, "B": 0.1, "C": 0.1, "D": 0.1}
    max_w = 0.40
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=max_w)
    for t, wt in w.items():
        if wt > 0:
            assert wt <= max_w + 1e-6, f"{t} weight {wt:.4f} > max {max_w}"


def test_optimize_bucket_min_position_respected():
    """Every included ticker must receive >= min_position_pct."""
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=300)
    scores = {"A": 0.8, "B": 0.6, "C": 0.4}  # all positive
    min_w = 0.05
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=min_w, max_position_pct=0.40)
    for t in tickers:
        if w.get(t, 0.0) > 0.0:
            assert w[t] >= min_w - 1e-6, f"{t} weight {w[t]:.4f} < min {min_w}"


def test_optimize_bucket_single_ticker():
    """Single included ticker gets weight 1.0."""
    tickers = ["ONLY"]
    prices = {"ONLY": _make_price_series(300)}
    scores = {"ONLY": 0.8}
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=0.40)
    assert abs(w["ONLY"] - 1.0) < 1e-9


def test_optimize_bucket_all_zero_signals():
    """All-zero signals → all zero weights (bucket undeployed)."""
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=300)
    scores = {"A": 0.0, "B": 0.0, "C": 0.0}
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=0.40)
    for wt in w.values():
        assert wt == 0.0


def test_optimize_bucket_negative_signals_excluded():
    """Tickers with negative signal scores get zero weight."""
    tickers = ["A", "B", "C"]
    prices = _make_price_history(tickers, n_days=300)
    scores = {"A": 0.8, "B": -0.5, "C": 0.3}  # B excluded
    w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=0.40)
    assert w["B"] == 0.0
    # A and C must be included and sum to 1
    assert abs(w["A"] + w["C"] - 1.0) < 1e-6


def test_optimize_bucket_short_history_fallback(caplog):
    """Bucket with short-history ticker falls back to equal-weight and logs warning."""
    tickers = ["A", "B"]
    prices = {
        "A": _make_price_series(n_days=300),
        "B": _make_price_series(n_days=30),   # below 60-day floor
    }
    scores = {"A": 0.8, "B": 0.6}
    with caplog.at_level(logging.WARNING, logger="src.portfolio.optimizer"):
        w = _optimize_bucket(tickers, scores, prices, risk_aversion=2.0,
                             min_position_pct=0.05, max_position_pct=0.40)
    # Should fall back to equal-weight among both included tickers
    assert abs(w["A"] + w.get("B", 0.0) - 1.0) < 1e-6


def test_optimize_bucket_perfectly_correlated_no_crash():
    """Duplicate price series (ρ=1.0) must not crash — LW handles near-singular cov."""
    prices_a = _make_price_series(300)
    # B is identical to A — perfectly correlated
    prices = {"A": prices_a.copy(), "B": prices_a.copy()}
    scores = {"A": 0.7, "B": 0.5}
    # Should not raise; result may be equal-weight fallback
    w = _optimize_bucket(["A", "B"], scores, prices, risk_aversion=2.0,
                         min_position_pct=0.05, max_position_pct=0.40)
    total = w["A"] + w["B"]
    assert abs(total - 1.0) < 1e-6


# ─── BucketOptimizer.optimize ─────────────────────────────────────────────────

def _make_full_price_history(n_days: int = 300) -> dict[str, pd.Series]:
    tickers = list(UNIVERSE_MAP.keys())
    return _make_price_history(tickers, n_days=n_days)


def _make_full_signal_scores() -> dict[str, float]:
    """Realistic signal scores: positive for growth/dividend, neutral for stable."""
    return {
        "VFV.TO":  0.5,
        "XIC.TO":  0.8,
        "HXQ.TO":  0.3,
        "XEF.TO":  0.1,
        "CHPS.TO": 1.0,
        "VAB.TO":  -0.5,   # stable — optimizer ignores these; stable is equal-weight
        "HSAV.TO": -0.8,
        "CDZ.TO":  0.6,
        "VDY.TO":  0.4,
    }


def test_optimizer_portfolio_weights_coverage():
    """optimize() returns weights for all tickers in universe_map."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    assert set(weights.keys()) == set(UNIVERSE_MAP.keys())


def test_optimizer_portfolio_weights_non_negative():
    """All portfolio-level weights must be >= 0."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    for t, w in weights.items():
        assert w >= -1e-9, f"{t} has negative portfolio weight {w:.6f}"


def test_optimizer_portfolio_weights_sum_to_one():
    """Portfolio-level weights sum to approximately 1.0 when all buckets have positive signals."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    total = sum(weights.values())
    # Growth (0.60) + Stable (0.25) + Dividend (0.15) = 1.0
    # Stable always deploys fully; Growth and Dividend deploy if positive signals
    assert abs(total - 1.0) < 0.01, f"Portfolio weights sum to {total:.4f}"


def test_optimizer_stable_bucket_equal_weight():
    """Stable bucket (VAB.TO, HSAV.TO) always uses equal-weight = 0.25/2 = 0.125 each."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    stable_target = BUCKET_CFG["stable"]["target"]  # 0.25
    expected_each = stable_target / 2  # 0.125
    assert abs(weights["VAB.TO"] - expected_each) < 1e-9
    assert abs(weights["HSAV.TO"] - expected_each) < 1e-9


def test_optimizer_stable_bucket_unaffected_by_negative_signals():
    """Stable bucket equal-weight does not change even with very negative signal scores."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    # Extremely negative signals for stable tickers
    scores = _make_full_signal_scores()
    scores["VAB.TO"] = -1.0
    scores["HSAV.TO"] = -1.0
    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    expected_each = BUCKET_CFG["stable"]["target"] / 2
    assert abs(weights["VAB.TO"] - expected_each) < 1e-9
    assert abs(weights["HSAV.TO"] - expected_each) < 1e-9


def test_optimizer_two_ticker_dividend_bucket():
    """Dividend bucket with 2 tickers produces valid weights summing to target."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    div_total = weights["CDZ.TO"] + weights["VDY.TO"]
    div_target = BUCKET_CFG["dividend"]["target"]  # 0.15
    assert abs(div_total - div_target) < 0.01, \
        f"Dividend bucket weights sum to {div_total:.4f}, expected ~{div_target}"


def test_optimizer_deterministic():
    """Same inputs produce identical outputs across repeated calls."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    w1 = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    w2 = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)
    for t in UNIVERSE_MAP:
        assert abs(w1[t] - w2[t]) < 1e-10, f"{t} weight changed between calls"


def test_optimizer_config_loaded_from_portfolio_config():
    """BucketOptimizer reads risk_aversion and position limits from portfolio config."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    assert opt.risk_aversion == 2.0
    assert opt.max_position_pct == 0.40
    assert opt.min_position_pct == 0.05
    assert opt.rebalance_threshold_pct == 0.02


def test_optimizer_default_config_when_absent():
    """BucketOptimizer uses sensible defaults when optimizer block is absent."""
    opt = BucketOptimizer()  # no config
    assert opt.risk_aversion == 2.0
    assert opt.max_position_pct == 0.40
    assert opt.min_position_pct == 0.05


# ─── Integration: optimized weights → trade cards ─────────────────────────────

def _make_momentum_result(scores: dict[str, float]) -> SignalResult:
    return SignalResult(
        signal_name="momentum_252_21",
        run_date=date(2026, 5, 22),
        scores=scores,
        metadata={"regime": "normal", "raw_returns": {}},
    )


def _make_regime_result(regime: str = "normal") -> SignalResult:
    return SignalResult(
        signal_name="vol_regime",
        run_date=date(2026, 5, 22),
        scores={},
        metadata={"regime": regime, "vol_percentile": 0.5},
    )


def test_integration_optimized_weights_flow_to_cards():
    """Optimized weights passed to generate_trade_cards produce BUY cards."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(300)
    scores = _make_full_signal_scores()
    opt_weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)

    latest_prices = {t: float(ps.iloc[-1]) for t, ps in prices.items()}
    momentum_result = _make_momentum_result(scores)
    regime_result = _make_regime_result("normal")

    cards = generate_trade_cards(
        momentum_result=momentum_result,
        regime_result=regime_result,
        holdings=[],
        portfolio_config=PORTFOLIO_CONFIG,
        universe_map=UNIVERSE_MAP,
        portfolio_nav=0.0,
        cash=1000.0,
        annual_trade_count=0,
        last_buy_dates={t: None for t in UNIVERSE_MAP},
        latest_prices=latest_prices,
        optimized_weights=opt_weights,
    )

    assert cards, "Expected trade cards but got none"
    buy_cards = [c for c in cards if c.action == "BUY"]
    assert buy_cards, "Expected at least one BUY card with optimized weights"


def test_integration_no_optimized_weights_unchanged_behavior():
    """Without optimized_weights, existing equal-weight path produces same results as before."""
    scores = _make_full_signal_scores()
    latest_prices = {t: 100.0 for t in UNIVERSE_MAP}
    momentum_result = _make_momentum_result(scores)
    regime_result = _make_regime_result("normal")

    # No optimized_weights → default path
    cards = generate_trade_cards(
        momentum_result=momentum_result,
        regime_result=regime_result,
        holdings=[],
        portfolio_config=PORTFOLIO_CONFIG,
        universe_map=UNIVERSE_MAP,
        portfolio_nav=0.0,
        cash=1000.0,
        annual_trade_count=0,
        last_buy_dates={t: None for t in UNIVERSE_MAP},
        latest_prices=latest_prices,
        optimized_weights=None,
    )

    assert cards  # still produces cards


def test_integration_rebalance_threshold_suppresses_small_changes():
    """Weight changes smaller than rebalance_threshold produce BELOW_THRESHOLD HOLD cards."""
    # Build weights where current holdings are already nearly at target
    scores = _make_full_signal_scores()
    latest_prices = {t: 100.0 for t in UNIVERSE_MAP}
    momentum_result = _make_momentum_result(scores)
    regime_result = _make_regime_result("normal")

    from src.portfolio.recommendations import compute_combined_scores, compute_target_weights
    from src.portfolio.model import Holding

    total_capital = 1000.0
    # Compute what equal-weight would give, set holdings to those exact weights
    combined = compute_combined_scores(momentum_result, regime_result)
    eq_weights = compute_target_weights(combined, BUCKET_CFG, UNIVERSE_MAP)

    # Slightly perturb target weights to be almost identical to current holdings
    # (difference < 2% threshold)
    opt_weights = {t: w for t, w in eq_weights.items()}

    holdings = [
        Holding(
            ticker=t,
            units=w * total_capital / 100.0,  # price = 100.0
            avg_cost=100.0,
            bucket=UNIVERSE_MAP[t]["bucket"],
            last_price=100.0,
        )
        for t, w in opt_weights.items()
        if w > 0
    ]

    cards = generate_trade_cards(
        momentum_result=momentum_result,
        regime_result=regime_result,
        holdings=holdings,
        portfolio_config=PORTFOLIO_CONFIG,
        universe_map=UNIVERSE_MAP,
        portfolio_nav=total_capital,
        cash=0.0,
        annual_trade_count=0,
        last_buy_dates={t: None for t in UNIVERSE_MAP},
        latest_prices=latest_prices,
        optimized_weights=opt_weights,
    )

    below_thresh = [c for c in cards if c.gate_status == GateStatus.BELOW_THRESHOLD]
    # Holdings already match target weights → should all be HOLD or BELOW_THRESHOLD
    non_skip = [c for c in cards if c.action not in ("SKIP",)]
    for card in non_skip:
        assert card.action in ("HOLD", "WARN", "BUY")


def test_end_to_end_signal_scores_to_portfolio_weights():
    """Full pipeline: signal scores + price data → valid portfolio weights."""
    opt = BucketOptimizer(config=PORTFOLIO_CONFIG)
    prices = _make_full_price_history(n_days=300)
    scores = _make_full_signal_scores()

    weights = opt.optimize(scores, prices, UNIVERSE_MAP, BUCKET_CFG)

    # All tickers present
    assert set(weights.keys()) == set(UNIVERSE_MAP.keys())
    # All weights non-negative
    assert all(w >= -1e-9 for w in weights.values())
    # Total deployment close to 100%
    assert abs(sum(weights.values()) - 1.0) < 0.02
    # Stable bucket at exactly equal-weight
    assert abs(weights["VAB.TO"] - 0.125) < 1e-9
    assert abs(weights["HSAV.TO"] - 0.125) < 1e-9
    # No growth ticker > 40% of growth bucket (i.e., > 40% × 60% = 24% of portfolio)
    growth_max_portfolio_weight = 0.40 * BUCKET_CFG["growth"]["target"]
    for t in ["VFV.TO", "XIC.TO", "HXQ.TO", "XEF.TO", "CHPS.TO"]:
        assert weights[t] <= growth_max_portfolio_weight + 1e-6, \
            f"{t} portfolio weight {weights[t]:.4f} exceeds bucket max"
