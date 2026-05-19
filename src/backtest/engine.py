"""
Backtesting framework.

Validates signal strategies against historical data. No signal goes live
without a passing backtest.

Architecture:
    1. Walk forward through history in monthly steps
    2. At each step, generate signals and construct a portfolio
    3. Hold for one month, measure return
    4. Aggregate into performance metrics using portfolio.metrics

The simplest backtest:
    - Equal-weight long the top N tickers by signal score
    - Rebalance monthly
    - Compare to benchmark (buy-and-hold VFV.TO or VBAL.TO)

No lookahead bias: signals at time t use only data available at time t.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd

from ..portfolio import metrics as m
from ..signals.base import Signal


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    start_date: date
    end_date: date
    rebalance_freq_days: int = 21        # ~monthly
    top_n: int = 4                        # long top N by signal score
    benchmark_ticker: str = "VFV.TO"
    initial_capital: float = 10000.0      # notional (doesn't affect returns)
    long_only: bool = True                # no shorting in TFSA


@dataclass
class BacktestResult:
    """Output of a backtest run."""
    signal_name: str
    config: BacktestConfig
    portfolio_returns: pd.Series          # daily returns of the strategy
    benchmark_returns: pd.Series          # daily returns of benchmark
    rebalance_log: list[dict]             # what was held each period
    metrics: dict                         # sharpe, sortino, max_dd, alpha, etc.

    def summary_str(self) -> str:
        """Formatted summary for CLI output."""
        lines = [
            f"=== BACKTEST: {self.signal_name} ===",
            f"Period: {self.config.start_date} → {self.config.end_date}",
            f"Rebalance: every {self.config.rebalance_freq_days} days",
            f"Top-N: {self.config.top_n}",
            "",
        ]
        for k, v in self.metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k:25s}: {v:+.4f}")
            else:
                lines.append(f"  {k:25s}: {v}")
        return "\n".join(lines)


def run_backtest(
    signal: Signal,
    prices: dict[str, pd.Series],
    config: BacktestConfig,
) -> BacktestResult:
    """
    Walk-forward backtest of a signal strategy.

    Algorithm:
    1. Start at config.start_date
    2. Generate signal scores using only data up to current date
    3. Equal-weight long the top_n tickers by score
    4. Hold for rebalance_freq_days trading days
    5. Record portfolio return for the holding period
    6. Advance and repeat
    7. Compute aggregate metrics
    """

    # Get aligned date index from benchmark
    bench_ticker = config.benchmark_ticker
    if bench_ticker not in prices or prices[bench_ticker].empty:
        raise ValueError(f"Benchmark {bench_ticker} not in prices or empty.")

    bench_prices = prices[bench_ticker]
    all_dates = bench_prices.index.sort_values()

    # Filter to backtest window
    start_ts = pd.Timestamp(config.start_date)
    end_ts = pd.Timestamp(config.end_date)
    dates_in_range = all_dates[(all_dates >= start_ts) & (all_dates <= end_ts)]

    if len(dates_in_range) < config.rebalance_freq_days * 2:
        raise ValueError("Not enough data in the specified date range.")

    # Compute daily returns for all tickers
    all_returns = {}
    for ticker, ps in prices.items():
        r = ps.pct_change().dropna()
        all_returns[ticker] = r

    bench_daily = all_returns[bench_ticker]

    # Walk forward
    portfolio_daily_returns = []
    rebalance_log = []
    i = 0

    while i < len(dates_in_range):
        current_date = dates_in_range[i].date()

        # Generate signal using only data up to current_date
        result = signal.generate(prices, run_date=current_date)
        ranked = result.ranked()

        # Select top-N (highest scores)
        if config.long_only:
            holdings = [t for t, s in ranked[-config.top_n:] if s > 0]
        else:
            holdings = [t for t, _ in ranked[-config.top_n:]]

        if not holdings:
            # No positive signals — hold cash (0 return)
            holdings = []

        rebalance_log.append({
            "date": current_date,
            "holdings": holdings,
            "scores": {t: s for t, s in ranked if t in holdings},
        })

        # Hold for rebalance period
        period_end = min(i + config.rebalance_freq_days, len(dates_in_range))
        period_dates = dates_in_range[i:period_end]

        for dt in period_dates:
            if holdings:
                # Equal-weight portfolio return for this day
                day_rets = []
                for ticker in holdings:
                    if ticker in all_returns and dt in all_returns[ticker].index:
                        day_rets.append(all_returns[ticker][dt])
                if day_rets:
                    portfolio_daily_returns.append(
                        (dt, np.mean(day_rets))
                    )
                else:
                    portfolio_daily_returns.append((dt, 0.0))
            else:
                portfolio_daily_returns.append((dt, 0.0))

        i = period_end

    # Assemble return series
    port_series = pd.Series(
        [r for _, r in portfolio_daily_returns],
        index=pd.DatetimeIndex([d for d, _ in portfolio_daily_returns]),
    )

    # Align benchmark
    bench_aligned = bench_daily.reindex(port_series.index).fillna(0)

    # Compute metrics
    port_metrics = m.summary(port_series, benchmark=bench_aligned)
    bench_metrics = m.summary(bench_aligned)
    port_metrics["bench_annualized_return"] = bench_metrics["annualized_return"]
    port_metrics["bench_sharpe"] = bench_metrics["sharpe"]
    port_metrics["bench_max_drawdown"] = bench_metrics["max_drawdown"]
    port_metrics["n_rebalances"] = len(rebalance_log)
    port_metrics["avg_holdings_per_period"] = np.mean(
        [len(r["holdings"]) for r in rebalance_log]
    )

    return BacktestResult(
        signal_name=signal.name,
        config=config,
        portfolio_returns=port_series,
        benchmark_returns=bench_aligned,
        rebalance_log=rebalance_log,
        metrics=port_metrics,
    )
