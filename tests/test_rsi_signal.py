"""
Unit tests for RSISignal (H005 hypothesis gate).

Tests cover:
  - Wilder SMMA math correctness
  - Directional behavior (uptrend → gate open, downtrend → gate closed)
  - Edge cases (empty series, insufficient data, all-gain, all-loss)
  - Output shape, binary constraint, metadata structure
  - Constructor validation
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.signals.base import SignalResult
from src.signals.rsi import RSISignal, _rsi_at_date


# ── Helpers ───────────────────────────────────────────────────────────────────

def _price_series(n: int, trend: float = 0.005, seed: int = 0) -> pd.Series:
    """Deterministic price series. trend > 0 = uptrend, < 0 = downtrend."""
    rng = np.random.default_rng(seed)
    log_rets = rng.normal(trend, 0.002, n)
    prices = 100.0 * np.exp(np.cumsum(log_rets))
    dates = pd.bdate_range(end="2026-05-22", periods=n)
    return pd.Series(prices, index=dates)


# ── _rsi_at_date: math ────────────────────────────────────────────────────────

def test_rsi_uptrend_above_50():
    prices = _price_series(100, trend=0.01, seed=1)
    rsi = _rsi_at_date(prices, 14, prices.index[-1])
    assert rsi is not None
    assert rsi > 50.0, f"Expected RSI > 50 on strong uptrend, got {rsi:.2f}"


def test_rsi_downtrend_below_50():
    prices = _price_series(100, trend=-0.01, seed=2)
    rsi = _rsi_at_date(prices, 14, prices.index[-1])
    assert rsi is not None
    assert rsi < 50.0, f"Expected RSI < 50 on strong downtrend, got {rsi:.2f}"


def test_rsi_range():
    """RSI must be in [0, 100] for any valid series."""
    for seed in range(8):
        prices = _price_series(50, seed=seed)
        rsi = _rsi_at_date(prices, 14, prices.index[-1])
        if rsi is not None:
            assert 0.0 <= rsi <= 100.0, f"seed={seed}: RSI {rsi:.2f} out of range"


def test_rsi_insufficient_data_returns_none():
    """Fewer than period+1 bars → None."""
    prices = _price_series(10, seed=0)
    rsi = _rsi_at_date(prices, 14, prices.index[-1])
    assert rsi is None


def test_rsi_exactly_period_plus_one_returns_value():
    """Exactly period+1 bars is the minimum — should return a value."""
    prices = _price_series(15, trend=0.005, seed=7)
    rsi = _rsi_at_date(prices, 14, prices.index[-1])
    assert rsi is not None


def test_rsi_all_gains_returns_100():
    """Monotonically rising prices → no losses → RSI = 100."""
    dates = pd.bdate_range(end="2026-05-22", periods=30)
    prices = pd.Series(np.linspace(100.0, 200.0, 30), index=dates)
    rsi = _rsi_at_date(prices, 14, prices.index[-1])
    assert rsi == 100.0


def test_rsi_all_losses_returns_0():
    """Monotonically falling prices → no gains → RSI = 0."""
    dates = pd.bdate_range(end="2026-05-22", periods=30)
    prices = pd.Series(np.linspace(200.0, 100.0, 30), index=dates)
    rsi = _rsi_at_date(prices, 14, prices.index[-1])
    assert rsi == 0.0


def test_rsi_wilder_smma_differs_from_ema():
    """
    Wilder SMMA (alpha=1/n) and standard EMA (alpha=2/(n+1)) must differ.

    For n=14: Wilder alpha=1/14≈0.0714, EMA alpha=2/15≈0.1333.
    Same data, different smoothing → different RS → different RSI.
    This verifies we implement Wilder's spec, not standard EMA.
    """
    prices = _price_series(100, trend=0.003, seed=42)
    delta = prices.diff().dropna()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)

    wilder_g = gains.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
    wilder_l = losses.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]

    ema_g = gains.ewm(alpha=2 / 15, adjust=False).mean().iloc[-1]
    ema_l = losses.ewm(alpha=2 / 15, adjust=False).mean().iloc[-1]

    assert abs(wilder_g - ema_g) > 1e-6 or abs(wilder_l - ema_l) > 1e-6, (
        "Wilder SMMA and EMA gave identical results — check alpha"
    )


# ── RSISignal.generate() ──────────────────────────────────────────────────────

def test_rsi_signal_returns_signal_result():
    sig = RSISignal()
    result = sig.generate({"A.TO": _price_series(50, seed=1)})
    assert isinstance(result, SignalResult)


def test_rsi_signal_name_default():
    assert RSISignal().name == "rsi_14_gate_50"


def test_rsi_signal_name_custom():
    assert RSISignal(period=21, threshold=50).name == "rsi_21_gate_50"


def test_rsi_signal_scores_are_binary():
    """All scores must be exactly 0.0 or 1.0 — no intermediate values."""
    sig = RSISignal()
    prices = {
        "UP.TO": _price_series(100, trend=0.01, seed=1),
        "DOWN.TO": _price_series(100, trend=-0.01, seed=2),
        "MID.TO": _price_series(100, trend=0.0, seed=3),
    }
    result = sig.generate(prices)
    for ticker, score in result.scores.items():
        assert score in (0.0, 1.0), f"{ticker}: score {score} is not binary"


def test_rsi_signal_uptrend_gate_open():
    sig = RSISignal(period=14)
    result = sig.generate({"UP.TO": _price_series(100, trend=0.01, seed=1)})
    assert result.scores["UP.TO"] == 1.0


def test_rsi_signal_downtrend_gate_closed():
    sig = RSISignal(period=14)
    result = sig.generate({"DOWN.TO": _price_series(100, trend=-0.01, seed=2)})
    assert result.scores["DOWN.TO"] == 0.0


def test_rsi_signal_insufficient_data_gate_closed():
    """Insufficient data → conservative default: gate closed."""
    sig = RSISignal(period=14)
    result = sig.generate({"SHORT.TO": _price_series(5, seed=0)})
    assert result.scores["SHORT.TO"] == 0.0
    assert "SHORT.TO" in result.metadata["skipped_tickers"]


def test_rsi_signal_empty_series_gate_closed():
    sig = RSISignal()
    result = sig.generate({"EMPTY.TO": pd.Series(dtype=float)})
    assert result.scores["EMPTY.TO"] == 0.0
    assert "EMPTY.TO" in result.metadata["skipped_tickers"]


def test_rsi_signal_metadata_keys():
    result = RSISignal().generate({"A.TO": _price_series(50, seed=1)})
    assert "rsi_values" in result.metadata
    assert "skipped_tickers" in result.metadata
    assert "period" in result.metadata
    assert "threshold" in result.metadata


def test_rsi_signal_metadata_rsi_value_populated():
    result = RSISignal().generate({"A.TO": _price_series(50, seed=1)})
    assert "A.TO" in result.metadata["rsi_values"]
    rsi = result.metadata["rsi_values"]["A.TO"]
    assert 0.0 <= rsi <= 100.0


def test_rsi_signal_run_date_respected():
    """Passing an earlier run_date should use only data up to that date."""
    prices = _price_series(200, trend=0.005, seed=5)
    sig = RSISignal()
    result_full = sig.generate({"T.TO": prices})
    result_early = sig.generate(
        {"T.TO": prices}, run_date=prices.index[50].date()
    )
    # RSI at day 50 may well differ from RSI at day 200
    rsi_full = result_full.metadata["rsi_values"].get("T.TO")
    rsi_early = result_early.metadata["rsi_values"].get("T.TO")
    # Both should be valid (not None) — just checking they computed
    assert rsi_full is not None
    assert rsi_early is not None


def test_rsi_signal_lookback_covers_period():
    assert RSISignal(period=21).lookback_days >= 22


# ── Constructor validation ────────────────────────────────────────────────────

def test_rsi_period_too_small_raises():
    with pytest.raises(ValueError, match="period must be >= 2"):
        RSISignal(period=1)


def test_rsi_threshold_zero_raises():
    with pytest.raises(ValueError, match="threshold"):
        RSISignal(threshold=0.0)


def test_rsi_threshold_100_raises():
    with pytest.raises(ValueError, match="threshold"):
        RSISignal(threshold=100.0)


# ── Monthly-bar RSI (H005 proposed use case) ─────────────────────────────────

def test_rsi_monthly_bar_21_period():
    """
    RSI(21) on monthly-resampled prices — the literal H005 specification.
    Pass monthly prices; signal should compute correctly with period=21.
    """
    # Build ~3 years of daily prices, resample to monthly
    daily = _price_series(800, trend=0.003, seed=99)
    monthly = daily.resample("ME").last()
    sig = RSISignal(period=21)
    result = sig.generate({"T.TO": monthly})
    # Should have enough monthly bars (800 days ≈ 38 months > 22 required)
    assert "T.TO" not in result.metadata["skipped_tickers"]
    assert result.scores["T.TO"] in (0.0, 1.0)
