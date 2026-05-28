"""
Unit tests for src/backtest/engine.py.

Covers:
  - avg_holdings_per_period > 0 on a universe with known positive momentum signals
  - BacktestResult.summary_str() contains expected metric names and formatting
  - Insufficient date range raises ValueError
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from src.signals.momentum import MomentumSignal


# ─── Shared fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def deterministic_prices() -> dict[str, pd.Series]:
    """
    800 business days of deterministic prices starting 2018-01-01.

    UP.TO:    steady uptrend  — guaranteed positive 12-1 momentum → selected
    FLAT.TO:  perfectly flat  — zero momentum, neutral score
    DOWN.TO:  steady downtrend — negative momentum → excluded by long-only gate
    VFV.TO:   mild uptrend    — used as benchmark ticker
    """
    dates = pd.bdate_range(start="2018-01-01", periods=800)
    return {
        "UP.TO":   pd.Series(np.linspace(100.0, 200.0, 800), index=dates),
        "FLAT.TO": pd.Series(np.full(800, 100.0), index=dates),
        "DOWN.TO": pd.Series(np.linspace(100.0, 50.0, 800), index=dates),
        "VFV.TO":  pd.Series(np.linspace(100.0, 150.0, 800), index=dates),
    }


@pytest.fixture
def backtest_config() -> BacktestConfig:
    """Backtest config covering a 1-year window within the deterministic fixture."""
    return BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
        top_n=2,
        benchmark_ticker="VFV.TO",
    )


@pytest.fixture
def backtest_result(
    deterministic_prices: dict[str, pd.Series],
    backtest_config: BacktestConfig,
) -> BacktestResult:
    sig = MomentumSignal()
    return run_backtest(sig, deterministic_prices, backtest_config)


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_avg_holdings_per_period_positive(backtest_result: BacktestResult) -> None:
    """
    With at least one uptrending ticker (UP.TO), the long-only engine must hold
    it every period. avg_holdings_per_period must be > 0.
    """
    avg = backtest_result.metrics["avg_holdings_per_period"]
    assert avg > 0, f"Expected avg_holdings_per_period > 0, got {avg}"


def test_avg_holdings_does_not_exceed_top_n(backtest_result: BacktestResult) -> None:
    """avg_holdings_per_period ≤ top_n (can be less when few tickers are positive)."""
    avg = backtest_result.metrics["avg_holdings_per_period"]
    assert avg <= backtest_result.config.top_n


def test_summary_str_contains_metric_names(backtest_result: BacktestResult) -> None:
    """summary_str() output must contain all key metric labels."""
    text = backtest_result.summary_str()
    for expected in ("Signal:", "Ann. Return:", "Sharpe:", "Max Drawdown:", "Rebalances:", "Avg holdings:"):
        assert expected in text, f"summary_str() missing '{expected}'"


def test_summary_str_contains_signal_name(backtest_result: BacktestResult) -> None:
    """summary_str() must include the signal name used in the run."""
    text = backtest_result.summary_str()
    assert backtest_result.signal_name in text


def test_summary_str_contains_period_dates(backtest_result: BacktestResult) -> None:
    """summary_str() must contain start and end dates from the config."""
    text = backtest_result.summary_str()
    assert str(backtest_result.config.start_date) in text
    assert str(backtest_result.config.end_date) in text


def test_backtest_insufficient_data_raises(deterministic_prices: dict[str, pd.Series]) -> None:
    """
    A date range narrower than 2 × rebalance_freq_days must raise ValueError.
    Default rebalance_freq is 21 days; 30-day window < 42-day minimum.
    """
    sig = MomentumSignal()
    config = BacktestConfig(
        start_date=date(2020, 1, 5),
        end_date=date(2020, 2, 5),   # ~22 business days — below 2 × 21 = 42
        top_n=2,
        benchmark_ticker="VFV.TO",
    )
    # Shrink prices to the same narrow window to force < 42 dates in range
    narrow: dict[str, pd.Series] = {}
    for ticker, s in deterministic_prices.items():
        start_ts = pd.Timestamp(config.start_date)
        end_ts = pd.Timestamp(config.end_date)
        narrow[ticker] = s[(s.index >= start_ts) & (s.index <= end_ts)]
    with pytest.raises(ValueError, match="Not enough data"):
        run_backtest(sig, narrow, config)


def test_backtest_rebalance_log_non_empty(backtest_result: BacktestResult) -> None:
    """The rebalance log must contain at least one entry for a valid backtest."""
    assert len(backtest_result.rebalance_log) > 0


def test_backtest_metrics_dict_has_required_keys(backtest_result: BacktestResult) -> None:
    """BacktestResult.metrics must contain all keys expected by the CLI display."""
    required = {
        "annualized_return", "annualized_vol", "sharpe", "sortino",
        "max_drawdown", "calmar", "alpha_vs_benchmark", "beta_vs_benchmark",
        "n_rebalances", "avg_holdings_per_period",
    }
    missing = required - set(backtest_result.metrics.keys())
    assert not missing, f"metrics dict missing keys: {missing}"
