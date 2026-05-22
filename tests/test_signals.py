"""
Unit tests for momentum signal.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.signals.momentum import MomentumSignal, ShortTermMomentum
from src.signals.base import SignalResult


@pytest.fixture
def mock_prices():
    """Create deterministic price series for 3 tickers with known momentum."""
    dates = pd.bdate_range(start="2020-01-01", periods=500)

    # UP.TO: steady uptrend — guaranteed positive 12-1 momentum
    a = pd.Series(np.linspace(100, 200, 500), index=dates)

    # FLAT.TO: perfectly flat — zero 12-1 momentum
    b = pd.Series(np.full(500, 100.0), index=dates)

    # DOWN.TO: steady downtrend — guaranteed negative 12-1 momentum
    c = pd.Series(np.linspace(100, 50, 500), index=dates)

    return {"UP.TO": a, "FLAT.TO": b, "DOWN.TO": c}


def test_momentum_returns_signal_result(mock_prices):
    sig = MomentumSignal()
    result = sig.generate(mock_prices)
    assert isinstance(result, SignalResult)
    assert result.signal_name == "momentum_252_21"
    assert len(result.scores) == 3


def test_momentum_scores_in_range(mock_prices):
    sig = MomentumSignal()
    result = sig.generate(mock_prices)
    for ticker, score in result.scores.items():
        assert -1.0 <= score <= 1.0, f"{ticker} score {score} out of range"


def test_momentum_ranks_correctly(mock_prices):
    """Uptrend ticker should rank highest, downtrend lowest."""
    sig = MomentumSignal()
    result = sig.generate(mock_prices)
    assert result.scores["UP.TO"] > result.scores["FLAT.TO"]
    assert result.scores["FLAT.TO"] > result.scores["DOWN.TO"]


def test_momentum_uptrend_is_positive(mock_prices):
    sig = MomentumSignal()
    result = sig.generate(mock_prices)
    assert result.scores["UP.TO"] > 0


def test_momentum_downtrend_is_negative(mock_prices):
    sig = MomentumSignal()
    result = sig.generate(mock_prices)
    assert result.scores["DOWN.TO"] < 0


def test_momentum_metadata_has_raw_returns(mock_prices):
    sig = MomentumSignal()
    result = sig.generate(mock_prices)
    assert "raw_returns" in result.metadata
    assert len(result.metadata["raw_returns"]) == 3


def test_short_term_momentum_different_name():
    sig = ShortTermMomentum()
    assert sig.name == "momentum_63_21"
    assert sig.lookback_days < MomentumSignal().lookback_days


def test_momentum_handles_empty_series():
    prices = {"EMPTY.TO": pd.Series(dtype=float)}
    sig = MomentumSignal()
    result = sig.generate(prices)
    assert result.scores["EMPTY.TO"] == 0.0


def test_momentum_handles_short_series():
    dates = pd.bdate_range(start="2024-01-01", periods=10)
    prices = {"SHORT.TO": pd.Series(range(100, 110), index=dates, dtype=float)}
    sig = MomentumSignal()
    result = sig.generate(prices)
    assert result.scores["SHORT.TO"] == 0.0  # insufficient data → neutral


# ---------------------------------------------------------------------------
# Regression tests for Bug #6: VolRegimeSignal silently returns unknown when
# caller passes fewer rows than lookback_days (1291 = 1260 + 21 + 10).
# ---------------------------------------------------------------------------
from src.signals.vol_regime import VolRegimeSignal


def _make_vol_prices(n: int) -> pd.Series:
    rng = np.random.default_rng(42)
    prices = rng.lognormal(0, 0.01, n).cumprod() * 100
    dates = pd.bdate_range(end="2026-05-19", periods=n)
    return pd.Series(prices, index=dates)


def test_vol_regime_insufficient_data_returns_unknown():
    """Bug #6 regression: 1290 rows (one short of 1291 required) yields unknown."""
    sig = VolRegimeSignal()
    result = sig.generate({"XIC.TO": _make_vol_prices(1290)})
    assert result.metadata["regime"] == "unknown"
    assert all(s == 0.0 for s in result.scores.values())


def test_vol_regime_sufficient_data_returns_real_regime():
    """Bug #6 regression: 1350 rows (enough headroom) yields a real regime."""
    sig = VolRegimeSignal()
    result = sig.generate({"XIC.TO": _make_vol_prices(1350)})
    assert result.metadata["regime"] != "unknown"
    assert result.metadata["regime"] in {"low_vol", "normal", "high_vol", "crisis"}
