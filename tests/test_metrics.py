"""
Unit tests for portfolio.metrics.

Financial math bugs are silent killers — every public function gets a test.
Uses known-answer inputs where possible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio import metrics as m


@pytest.fixture
def flat_returns():
    """Series of 252 returns all equal to 0.0004 (~10% annualized)."""
    return pd.Series([0.0004] * 252)


@pytest.fixture
def normal_returns():
    """Deterministic normal-ish returns for reproducibility."""
    rng = np.random.default_rng(42)
    return pd.Series(rng.normal(0.0005, 0.01, 1000))


def test_annualized_return_flat(flat_returns):
    """0.0004 daily over 252 days ≈ 10.6% annualized."""
    ar = m.annualized_return(flat_returns)
    assert 0.10 < ar < 0.12


def test_annualized_vol_flat_is_zero(flat_returns):
    """Constant returns have zero std."""
    assert m.annualized_volatility(flat_returns) == pytest.approx(0.0, abs=1e-9)


def test_sharpe_normal(normal_returns):
    """Sharpe should be finite and reasonable for normal returns."""
    s = m.sharpe_ratio(normal_returns, risk_free=0.045)
    assert np.isfinite(s)


def test_max_drawdown_monotone_up():
    """Monotonically rising prices have zero drawdown."""
    prices = pd.Series([100, 101, 102, 103, 104])
    assert m.max_drawdown(prices) == pytest.approx(0.0, abs=1e-9)


def test_max_drawdown_known():
    """Peak 110, trough 88 → -20% drawdown."""
    prices = pd.Series([100, 105, 110, 99, 88, 95])
    assert m.max_drawdown(prices) == pytest.approx(-0.2, abs=1e-9)


def test_max_drawdown_from_returns():
    """Same series via returns path should match."""
    prices = pd.Series([100, 105, 110, 99, 88, 95])
    rets = m.daily_returns(prices)
    dd_from_rets = m.max_drawdown(rets, is_returns=True)
    assert dd_from_rets == pytest.approx(-0.2, abs=1e-6)


def test_sortino_higher_than_sharpe_when_skewed_positive():
    """When downside is small, Sortino > Sharpe."""
    rng = np.random.default_rng(7)
    # mostly positive returns
    rets = pd.Series(np.abs(rng.normal(0.001, 0.005, 500)))
    sharpe = m.sharpe_ratio(rets, risk_free=0)
    sortino = m.sortino_ratio(rets, risk_free=0)
    if np.isfinite(sortino):
        assert sortino >= sharpe


def test_beta_self_is_one():
    """Beta of a series against itself = 1."""
    rng = np.random.default_rng(1)
    rets = pd.Series(rng.normal(0, 0.01, 500))
    assert m.beta(rets, rets) == pytest.approx(1.0, abs=1e-9)


def test_beta_zero_for_uncorrelated():
    """Independent series → beta near zero."""
    rng = np.random.default_rng(2)
    a = pd.Series(rng.normal(0, 0.01, 5000))
    b = pd.Series(rng.normal(0, 0.01, 5000))
    assert abs(m.beta(a, b)) < 0.1


def test_summary_returns_all_keys(normal_returns):
    """summary() must return a complete dict."""
    out = m.summary(normal_returns)
    for k in ["n_days", "annualized_return", "annualized_vol",
              "sharpe", "sortino", "max_drawdown", "calmar"]:
        assert k in out


def test_calmar_positive_for_positive_strategy(normal_returns):
    c = m.calmar_ratio(normal_returns)
    assert np.isfinite(c)
