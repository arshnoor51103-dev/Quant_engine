"""
Core risk and return metrics.

All functions are pure: they take pandas Series/DataFrame of returns or prices
and return scalar metrics. No I/O, no side effects.

Conventions:
- Returns are simple returns unless noted (log returns explicit).
- Daily frequency assumed; annualization factor = 252 trading days.
- All annualized metrics use sqrt(252) for vol, 252 for return compounding.

References:
- Sharpe, W. F. (1966). Mutual Fund Performance.
- Sortino, F. A. & Price, L. N. (1994). Performance Measurement in a Downside Risk Framework.
- Magdon-Ismail, M. & Atiya, A. F. (2004). Maximum Drawdown.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(prices: pd.Series) -> pd.Series:
    """
    Simple daily returns: r_t = P_t / P_{t-1} - 1.

    Drops the first NaN.
    """
    return prices.pct_change().dropna()


def log_returns(prices: pd.Series) -> pd.Series:
    """Log returns: r_t = ln(P_t / P_{t-1}). Drops first NaN."""
    return np.log(prices / prices.shift(1)).dropna()


def annualized_return(returns: pd.Series) -> float:
    """
    Geometric annualized return.

    Formula: (1 + total_return)^(TRADING_DAYS / n) - 1
    """
    n = len(returns)
    if n == 0:
        return float("nan")
    total = (1 + returns).prod()
    return float(total ** (TRADING_DAYS / n) - 1)


def annualized_volatility(returns: pd.Series) -> float:
    """
    Annualized standard deviation of daily returns.

    Formula: std(r) * sqrt(TRADING_DAYS)
    """
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def downside_volatility(returns: pd.Series, mar: float = 0.0) -> float:
    """
    Annualized downside deviation (returns below MAR).

    mar: minimum acceptable return, daily.
    """
    downside = returns[returns < mar]
    if len(downside) < 2:
        return float("nan")
    return float(downside.std(ddof=1) * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.045) -> float:
    """
    Annualized Sharpe ratio.

    Formula: (annualized_return - risk_free) / annualized_vol

    risk_free: annualized rate (e.g. 0.045 = 4.5%).
    """
    ar = annualized_return(returns)
    av = annualized_volatility(returns)
    if av == 0 or np.isnan(av):
        return float("nan")
    return float((ar - risk_free) / av)


def sortino_ratio(returns: pd.Series, risk_free: float = 0.045) -> float:
    """
    Annualized Sortino ratio — uses downside deviation instead of total vol.

    Daily MAR derived from annualized risk-free: rf_daily = (1+rf)^(1/252) - 1
    """
    daily_mar = (1 + risk_free) ** (1 / TRADING_DAYS) - 1
    ar = annualized_return(returns)
    dv = downside_volatility(returns, mar=daily_mar)
    if dv == 0 or np.isnan(dv):
        return float("nan")
    return float((ar - risk_free) / dv)


def max_drawdown(prices_or_returns: pd.Series, is_returns: bool = False) -> float:
    """
    Maximum peak-to-trough decline.

    Returns a negative number (e.g. -0.20 = 20% drawdown).

    Args:
        prices_or_returns: price series, or returns series if is_returns=True
        is_returns: if True, treats input as returns and compounds to equity curve

    Formula: min(equity / cummax(equity) - 1)
    """
    if is_returns:
        equity = (1 + prices_or_returns).cumprod()
    else:
        equity = prices_or_returns
    if len(equity) == 0:
        return float("nan")
    peak = equity.cummax()
    drawdown = equity / peak - 1
    return float(drawdown.min())


def calmar_ratio(returns: pd.Series) -> float:
    """
    Calmar ratio: annualized return / |max drawdown|.

    Penalizes strategies with deep drawdowns.
    """
    ar = annualized_return(returns)
    mdd = max_drawdown(returns, is_returns=True)
    if mdd == 0 or np.isnan(mdd):
        return float("nan")
    return float(ar / abs(mdd))


def beta(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    CAPM beta: cov(asset, bench) / var(bench).

    Aligns on common index, drops NaN pairs.
    """
    df = pd.concat([asset_returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(df) < 2:
        return float("nan")
    cov = df.iloc[:, 0].cov(df.iloc[:, 1])
    var = df.iloc[:, 1].var()
    if var == 0:
        return float("nan")
    return float(cov / var)


def alpha(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free: float = 0.045,
) -> float:
    """
    Annualized Jensen's alpha.

    Formula: alpha = asset_ret - [rf + beta * (bench_ret - rf)]
    All annualized.
    """
    b = beta(asset_returns, benchmark_returns)
    if np.isnan(b):
        return float("nan")
    ar_asset = annualized_return(asset_returns)
    ar_bench = annualized_return(benchmark_returns)
    return float(ar_asset - (risk_free + b * (ar_bench - risk_free)))


def rolling_metric(
    returns: pd.Series, window_days: int, fn
) -> pd.Series:
    """
    Generic rolling-window metric calculator.

    fn must accept a pd.Series and return a float.

    Example:
        rolling_sharpe = rolling_metric(rets, 63, sharpe_ratio)  # 3-month rolling
    """
    return returns.rolling(window=window_days).apply(
        lambda w: fn(pd.Series(w)) if len(w) == window_days else np.nan,
        raw=True,
    )


def summary(returns: pd.Series, benchmark: pd.Series | None = None,
            risk_free: float = 0.045) -> dict:
    """
    Return a dict of all core metrics. For dashboards and reports.
    """
    out = {
        "n_days": len(returns),
        "annualized_return": annualized_return(returns),
        "annualized_vol": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns, risk_free),
        "sortino": sortino_ratio(returns, risk_free),
        "max_drawdown": max_drawdown(returns, is_returns=True),
        "calmar": calmar_ratio(returns),
    }
    if benchmark is not None:
        out["beta_vs_benchmark"] = beta(returns, benchmark)
        out["alpha_vs_benchmark"] = alpha(returns, benchmark, risk_free)
    return out
