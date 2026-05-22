"""
Unit tests for mean reversion signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.signals.mean_reversion import MeanReversionSignal, _REGIME_WEIGHTS
from src.signals.base import SignalResult


def _make_prices(n: int, seed: int = 0, vol: float = 0.005) -> pd.Series:
    """Deterministic random-walk price series."""
    rng = np.random.default_rng(seed)
    log_rets = rng.normal(0.0, vol, n)
    prices = 100.0 * np.exp(np.cumsum(log_rets))
    dates = pd.bdate_range(end="2026-05-22", periods=n)
    return pd.Series(prices, index=dates)


@pytest.fixture
def three_ticker_prices():
    """Three tickers with 200 trading days each — enough for warmup."""
    return {
        "A.TO": _make_prices(200, seed=1),
        "B.TO": _make_prices(200, seed=2),
        "C.TO": _make_prices(200, seed=3),
    }


# ── Output shape and type ──────────────────────────────────────────────────────

def test_mr_returns_signal_result(three_ticker_prices):
    sig = MeanReversionSignal()
    result = sig.generate(three_ticker_prices)
    assert isinstance(result, SignalResult)
    assert result.signal_name == "mean_reversion_20_60"


def test_mr_scores_all_tickers_present(three_ticker_prices):
    sig = MeanReversionSignal()
    result = sig.generate(three_ticker_prices)
    assert set(result.scores.keys()) == {"A.TO", "B.TO", "C.TO"}


def test_mr_scores_in_range(three_ticker_prices):
    sig = MeanReversionSignal()
    result = sig.generate(three_ticker_prices)
    for ticker, score in result.scores.items():
        assert -1.0 <= score <= 1.0, f"{ticker} score {score} out of [-1, 1]"


def test_mr_metadata_has_required_keys(three_ticker_prices):
    sig = MeanReversionSignal()
    result = sig.generate(three_ticker_prices)
    assert "regime" in result.metadata
    assert "regime_weights" in result.metadata
    assert "z_ts_raw" in result.metadata
    assert "skipped_tickers" in result.metadata


# ── Sign convention: oversold ticker → positive score ─────────────────────────

def test_mr_oversold_ticker_gets_positive_score():
    """
    Ticker with a sudden large negative return (oversold) should score positive.

    Construct: 150 days of near-flat prices, then a -5% drop on the last day.
    The last return will be ~6 sigma below the rolling mean → very negative z_ts
    → flip → positive final score.
    """
    rng = np.random.default_rng(99)
    n = 150
    dates = pd.bdate_range(end="2026-05-22", periods=n)

    # OVERSOLD.TO: tiny normal noise, then a -5% crash on the last day
    log_rets = rng.normal(0.0, 0.001, n)
    log_rets[-1] = np.log(0.95)  # hard -5% drop
    oversold_prices = pd.Series(100.0 * np.exp(np.cumsum(log_rets)), index=dates)

    # NEUTRAL.TO: same tiny noise, no crash
    neutral_prices = pd.Series(
        100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.001, n))), index=dates
    )

    # Use benchmark XIC.TO so VolRegimeSignal doesn't return "unknown"
    xic_prices = _make_prices(1400, seed=7, vol=0.008)

    prices = {
        "OVERSOLD.TO": oversold_prices,
        "NEUTRAL.TO": neutral_prices,
        "XIC.TO": xic_prices,
    }

    sig = MeanReversionSignal()
    result = sig.generate(prices)

    assert result.scores["OVERSOLD.TO"] > 0, (
        f"Oversold ticker should be positive; got {result.scores['OVERSOLD.TO']:.4f}"
    )
    assert result.scores["OVERSOLD.TO"] > result.scores["NEUTRAL.TO"], (
        "Oversold ticker should rank above neutral ticker"
    )


# ── Warmup period: fewer than long_window rows ────────────────────────────────

def test_mr_short_series_gets_neutral_score():
    """Ticker with fewer than 60 rows (long_window) gets 0.0 (neutral)."""
    dates = pd.bdate_range(end="2026-05-22", periods=30)
    prices = {"SHORT.TO": pd.Series(np.linspace(100, 105, 30), index=dates)}
    sig = MeanReversionSignal()
    result = sig.generate(prices)
    assert result.scores["SHORT.TO"] == 0.0


def test_mr_empty_series_gets_neutral_score():
    prices = {"EMPTY.TO": pd.Series(dtype=float)}
    sig = MeanReversionSignal()
    result = sig.generate(prices)
    assert result.scores["EMPTY.TO"] == 0.0


def test_mr_skipped_tickers_in_metadata():
    """Short-data tickers appear in skipped_tickers metadata."""
    dates_short = pd.bdate_range(end="2026-05-22", periods=30)
    dates_long = pd.bdate_range(end="2026-05-22", periods=200)
    prices = {
        "SHORT.TO": pd.Series(np.linspace(100, 105, 30), index=dates_short),
        "LONG.TO": _make_prices(200, seed=5),
    }
    sig = MeanReversionSignal()
    result = sig.generate(prices)
    assert "SHORT.TO" in result.metadata["skipped_tickers"]
    assert "SHORT.TO" not in result.metadata["z_ts_raw"]


# ── Regime weight lookup ───────────────────────────────────────────────────────

def test_regime_weights_all_regimes_defined():
    """All four expected regimes plus 'unknown' are in the weights table."""
    for key in ("crisis", "high_vol", "normal", "low_vol", "unknown"):
        assert key in _REGIME_WEIGHTS, f"Missing regime key: {key}"


def test_regime_weights_sum_to_one():
    """w_ts + w_cs must equal 1.0 for every regime."""
    for regime, (w_ts, w_cs) in _REGIME_WEIGHTS.items():
        assert abs(w_ts + w_cs - 1.0) < 1e-9, f"{regime}: weights sum to {w_ts + w_cs}"


def test_regime_weights_crisis_ts_heavy():
    """CRISIS regime should weight TS more than CS."""
    w_ts, w_cs = _REGIME_WEIGHTS["crisis"]
    assert w_ts > w_cs


def test_regime_weights_low_vol_cs_heavy():
    """LOW_VOL regime should weight CS more than TS."""
    w_ts, w_cs = _REGIME_WEIGHTS["low_vol"]
    assert w_cs > w_ts


def test_mr_metadata_contains_regime_weights(three_ticker_prices):
    sig = MeanReversionSignal()
    result = sig.generate(three_ticker_prices)
    weights = result.metadata["regime_weights"]
    assert "w_ts" in weights and "w_cs" in weights
    assert abs(weights["w_ts"] + weights["w_cs"] - 1.0) < 1e-9


# ── Name and lookback ──────────────────────────────────────────────────────────

def test_mr_name():
    assert MeanReversionSignal().name == "mean_reversion_20_60"
    assert MeanReversionSignal(short_window=5, long_window=20).name == "mean_reversion_5_20"


def test_mr_lookback_days():
    sig = MeanReversionSignal()
    assert sig.lookback_days >= 60  # must cover at least the long window


# ── Single-ticker edge case ────────────────────────────────────────────────────

def test_mr_single_ticker_score_is_zero():
    """With only one ticker, rank-normalization returns 0.0."""
    prices = {"SOLO.TO": _make_prices(200, seed=42)}
    sig = MeanReversionSignal()
    result = sig.generate(prices)
    assert result.scores["SOLO.TO"] == 0.0
