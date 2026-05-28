"""
H004 -- Portfolio-Level Volatility Targeting (Moreira-Muir Scaling)
Research script. Does NOT modify any src/ files.

Runs three pre-backtest checks, then a walk-forward backtest comparing:
  1. Baseline: equal-weight top-4 momentum (replicates established 0.807 Sharpe)
  2. Vol-targeted (21d RV): Moreira-Muir inverse-variance weighted top-4 momentum
  3. Vol-targeted (EWMA lambda=0.94): same, with EWMA variance estimator

Kill criteria evaluated (from H004_vol_targeting.md):
  Global: Sharpe < 0.3, Max DD > 20%, Corr(strategy, momentum) > 0.70, Alpha < 0%
  H004-specific:
    - Corr(equity_return, RV_{t-1}) > 0 [leverage effect absent -> no theoretical basis]
    - Corr(vol_regime_score, RV_t) > 0.85 [vol targeting redundant with existing signal]
    - 21-day RV vs EWMA Sharpe delta < 0 when EWMA wins by > 0.1

Key design invariant (user flag #2):
  Moreira-Muir scaling modifies portfolio WEIGHTS after signal ranking, not signal scores.
  Rank order is preserved. Scale is applied at weight construction time.
"""
from __future__ import annotations

import pathlib
import sys

# Add project root to path so src/ imports work
_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from datetime import date

import numpy as np
import pandas as pd
import scipy.stats as stats

from src.portfolio.model import price_series_batch
from src.signals.momentum import MomentumSignal


# ── Configuration ────────────────────────────────────────────────────────────

# Growth + Dividend buckets -- vol targeting applies to both (equity-like assets)
EQUITY_TICKERS = ["VFV.TO", "XIC.TO", "HXQ.TO", "XEF.TO", "CHPS.TO", "CDZ.TO", "VDY.TO"]
BENCHMARK_TICKER = "VFV.TO"
STABLE_TICKERS = ["VAB.TO", "HSAV.TO"]
ALL_TICKERS = EQUITY_TICKERS + STABLE_TICKERS

BACKTEST_YEARS = 5
REBALANCE_DAYS = 21   # ~monthly
TOP_N = 4
EWMA_LAMBDA = 0.94    # RiskMetrics EWMA parameter

# Kill criterion thresholds
SHARPE_KILL = 0.3
DD_KILL = 0.20
CORR_KILL = 0.70
REGIME_OVERLAP_KILL = 0.85   # H004-specific: if |Corr(vol_regime, RV)| > this -> KILL
EWMA_ADVANTAGE_THRESHOLD = 0.10  # if EWMA wins by > 0.1 Sharpe -> 21d RV is inadequate


# ── Data loading ──────────────────────────────────────────────────────────────

def load_prices(lookback_days: int = 252 * 7) -> dict[str, pd.Series]:
    """Load price series for all tickers. 7yr buffer for warmup."""
    return price_series_batch(ALL_TICKERS, lookback_days=lookback_days)


# ── Realized variance computations ───────────────────────────────────────────

def compute_monthly_rv(prices: pd.Series) -> pd.Series:
    """
    21-day realized variance per calendar month end.
    RV_month = sum of squared daily returns over the month.
    No look-ahead: RV at month t uses data from month t only.
    """
    daily_ret = prices.pct_change().dropna()
    sq_ret = daily_ret ** 2
    rv_monthly = sq_ret.resample("ME").sum()
    count_monthly = daily_ret.resample("ME").count()
    rv_monthly[count_monthly < 15] = np.nan
    return rv_monthly


def compute_ewma_variance(prices: pd.Series, lam: float = EWMA_LAMBDA) -> pd.Series:
    """
    EWMA variance estimate (RiskMetrics: lambda=0.94).
    sigma^2_t = lambda * sigma^2_{t-1} + (1-lambda) * r^2_{t-1}
    Returns month-end values to match monthly rebalance cadence.
    """
    daily_ret = prices.pct_change().dropna()
    sq_ret = daily_ret ** 2
    ewma_var = sq_ret.ewm(alpha=(1 - lam), adjust=False).mean()
    return ewma_var.resample("ME").last()


# ── Pre-backtest checks ───────────────────────────────────────────────────────

def check_leverage_effect(prices: dict[str, pd.Series]) -> dict[str, float]:
    """
    Pre-check 1: Corr(equity_return_{t+1}, RV_t) for each equity ticker.
    Leverage effect: high vol months should PRECEDE lower returns.
    Expected sign: negative (high RV -> lower forward return).
    If positive for majority of tickers -> leverage effect absent -> Moreira-Muir has no basis.
    """
    results = {}
    for ticker in EQUITY_TICKERS:
        if ticker not in prices:
            results[ticker] = float("nan")
            continue
        monthly_price = prices[ticker].resample("ME").last()
        monthly_ret = monthly_price.pct_change()
        rv = compute_monthly_rv(prices[ticker])
        aligned = pd.DataFrame({"rv": rv, "fwd_ret": monthly_ret.shift(-1)}).dropna()
        if len(aligned) < 20:
            results[ticker] = float("nan")
            continue
        r, _ = stats.pearsonr(aligned["rv"], aligned["fwd_ret"])
        results[ticker] = float(r)
    return results


def check_regime_signal_overlap(prices: dict[str, pd.Series]) -> float:
    """
    Pre-check 2: Corr(vol_regime_score, portfolio_RV).
    Replicates VolRegimeSignal's percentile-rank logic on XIC.TO.
    Kill if |corr| > REGIME_OVERLAP_KILL.
    """
    if "XIC.TO" not in prices:
        return float("nan")

    xic = prices["XIC.TO"]
    daily_ret = xic.pct_change().dropna()
    sq_ret = daily_ret ** 2

    rolling_rv_21 = sq_ret.rolling(21).sum()
    monthly_rv_xic = rolling_rv_21.resample("ME").last()

    # 5yr trailing percentile rank at each month-end (mirrors VolRegimeSignal)
    lookback = 252 * 5
    percentile_series = pd.Series(index=monthly_rv_xic.index, dtype=float)
    for i, dt in enumerate(monthly_rv_xic.index):
        window_rv = rolling_rv_21.loc[:dt].iloc[-lookback:]
        if len(window_rv) < 60:
            percentile_series.iloc[i] = np.nan
            continue
        current_rv = monthly_rv_xic.iloc[i]
        pct = (window_rv <= current_rv).sum() / len(window_rv)
        percentile_series.iloc[i] = float(pct)

    def _to_regime_score(p: float) -> float:
        if p < 0.25:
            return 1.0
        elif p < 0.75:
            return 0.3
        elif p < 0.95:
            return -0.5
        else:
            return -1.0

    regime_scores = percentile_series.dropna().apply(_to_regime_score)

    equity_rvs = [
        compute_monthly_rv(prices[t])
        for t in EQUITY_TICKERS if t in prices
    ]
    if not equity_rvs:
        return float("nan")

    portfolio_rv = pd.concat(equity_rvs, axis=1).mean(axis=1)
    combined = pd.DataFrame({
        "regime_score": regime_scores,
        "portfolio_rv": portfolio_rv,
    }).dropna()

    if len(combined) < 20:
        return float("nan")

    r, _ = stats.pearsonr(combined["regime_score"], combined["portfolio_rv"])
    return float(r)


# ── Moreira-Muir walk-forward backtest ───────────────────────────────────────

def _compute_scale_factors(
    holdings: list[str],
    rebalance_date: date,
    rv_series: dict[str, pd.Series],
    c: dict[str, float],
) -> dict[str, float]:
    """
    Moreira-Muir scale factor: scale_i = c_i / RV_i_{t-1}.
    Uses prior month-end realized variance (no look-ahead).
    Clips to [0.25, 4.0] to prevent extreme leverage.
    """
    dt = pd.Timestamp(rebalance_date)
    scales = {}
    for ticker in holdings:
        if ticker not in rv_series:
            scales[ticker] = 1.0
            continue
        prior_rv = rv_series[ticker][rv_series[ticker].index < dt]
        if prior_rv.empty or pd.isna(prior_rv.iloc[-1]) or prior_rv.iloc[-1] <= 0:
            scales[ticker] = 1.0
            continue
        raw_scale = c.get(ticker, prior_rv.iloc[-1]) / prior_rv.iloc[-1]
        scales[ticker] = float(np.clip(raw_scale, 0.25, 4.0))
    return scales


def run_vol_targeted_backtest(
    prices: dict[str, pd.Series],
    rv_series: dict[str, pd.Series],
    start_date: date,
    end_date: date,
    variant_name: str = "vol_target_rv21",
) -> dict:
    """
    Walk-forward backtest with Moreira-Muir vol-targeted weights.

    Invariant: scaling applies to portfolio weights after momentum ranking.
    Signal score rank order is NOT modified -- flag #2 compliance.
    """
    signal = MomentumSignal()
    if BENCHMARK_TICKER not in prices:
        raise ValueError(f"Benchmark {BENCHMARK_TICKER} not in prices.")

    all_returns = {t: ps.pct_change().dropna() for t, ps in prices.items()}
    bench_daily = all_returns[BENCHMARK_TICKER]

    # Unconditional mean RV per ticker (Moreira-Muir scaling constant c)
    c_per_ticker = {
        t: float(rv_series[t].dropna().mean())
        for t in rv_series
        if not rv_series[t].dropna().empty
    }

    bench_idx = prices[BENCHMARK_TICKER].index.sort_values()
    start_ts, end_ts = pd.Timestamp(start_date), pd.Timestamp(end_date)
    dates_in_range = bench_idx[(bench_idx >= start_ts) & (bench_idx <= end_ts)]

    if len(dates_in_range) < REBALANCE_DAYS * 4:
        raise ValueError("Insufficient data for backtest window.")

    portfolio_daily: list[tuple] = []
    rebalance_log: list[dict] = []
    i = 0

    while i < len(dates_in_range):
        current_date = dates_in_range[i].date()

        # Step 1: Signal ranking (unchanged -- no vol scaling applied to scores)
        result = signal.generate(prices, run_date=current_date)
        ranked = result.ranked()

        equity_candidates = [
            (t, s) for t, s in ranked if t in EQUITY_TICKERS and s > 0
        ]
        holdings = [t for t, _ in equity_candidates[:TOP_N]]

        # Step 2: Vol-targeted weights at construction time (not at score time)
        if holdings:
            scale_factors = _compute_scale_factors(
                holdings, current_date, rv_series, c_per_ticker
            )
            total_scale = sum(scale_factors.values())
            if total_scale > 0:
                weights = {t: scale_factors[t] / total_scale for t in holdings}
            else:
                weights = {t: 1.0 / len(holdings) for t in holdings}
        else:
            weights = {}

        rebalance_log.append({
            "date": current_date,
            "holdings": holdings,
            "weights": dict(weights),
        })

        # Step 3: Weighted daily returns over holding period
        period_end = min(i + REBALANCE_DAYS, len(dates_in_range))
        for dt in dates_in_range[i:period_end]:
            if weights:
                day_ret = sum(
                    weights[t] * all_returns[t][dt]
                    for t in weights
                    if t in all_returns and dt in all_returns[t].index
                )
                portfolio_daily.append((dt, float(day_ret)))
            else:
                portfolio_daily.append((dt, 0.0))

        i = period_end

    port_series = pd.Series(
        [r for _, r in portfolio_daily],
        index=pd.DatetimeIndex([d for d, _ in portfolio_daily]),
    )
    bench_aligned = bench_daily.reindex(port_series.index).fillna(0)

    from src.portfolio import metrics as m
    port_metrics = m.summary(port_series, benchmark=bench_aligned)
    bench_metrics = m.summary(bench_aligned)
    port_metrics["bench_annualized_return"] = bench_metrics["annualized_return"]
    port_metrics["bench_sharpe"] = bench_metrics["sharpe"]
    port_metrics["n_rebalances"] = len(rebalance_log)
    port_metrics["avg_holdings_per_period"] = float(
        np.mean([len(r["holdings"]) for r in rebalance_log])
    )
    port_metrics["variant"] = variant_name
    port_metrics["_port_series"] = port_series
    port_metrics["_rebalance_log"] = rebalance_log
    return port_metrics


def run_equal_weight_baseline(
    prices: dict[str, pd.Series],
    start_date: date,
    end_date: date,
) -> dict:
    """Equal-weight top-4 momentum baseline (no vol scaling)."""
    signal = MomentumSignal()
    all_returns = {t: ps.pct_change().dropna() for t, ps in prices.items()}
    bench_daily = all_returns[BENCHMARK_TICKER]

    bench_idx = prices[BENCHMARK_TICKER].index.sort_values()
    start_ts, end_ts = pd.Timestamp(start_date), pd.Timestamp(end_date)
    dates_in_range = bench_idx[(bench_idx >= start_ts) & (bench_idx <= end_ts)]

    portfolio_daily: list[tuple] = []
    rebalance_log: list[dict] = []
    i = 0

    while i < len(dates_in_range):
        current_date = dates_in_range[i].date()
        result = signal.generate(prices, run_date=current_date)
        ranked = result.ranked()

        equity_candidates = [
            (t, s) for t, s in ranked if t in EQUITY_TICKERS and s > 0
        ]
        holdings = [t for t, _ in equity_candidates[:TOP_N]]
        n = len(holdings)
        weights = {t: 1.0 / n for t in holdings} if n > 0 else {}

        rebalance_log.append({"date": current_date, "holdings": holdings})

        period_end = min(i + REBALANCE_DAYS, len(dates_in_range))
        for dt in dates_in_range[i:period_end]:
            if weights:
                day_ret = sum(
                    weights[t] * all_returns[t][dt]
                    for t in weights
                    if t in all_returns and dt in all_returns[t].index
                )
                portfolio_daily.append((dt, float(day_ret)))
            else:
                portfolio_daily.append((dt, 0.0))

        i = period_end

    port_series = pd.Series(
        [r for _, r in portfolio_daily],
        index=pd.DatetimeIndex([d for d, _ in portfolio_daily]),
    )
    bench_aligned = bench_daily.reindex(port_series.index).fillna(0)

    from src.portfolio import metrics as m
    port_metrics = m.summary(port_series, benchmark=bench_aligned)
    bench_metrics = m.summary(bench_aligned)
    port_metrics["bench_annualized_return"] = bench_metrics["annualized_return"]
    port_metrics["bench_sharpe"] = bench_metrics["sharpe"]
    port_metrics["n_rebalances"] = len(rebalance_log)
    port_metrics["avg_holdings_per_period"] = float(
        np.mean([len(r["holdings"]) for r in rebalance_log])
    )
    port_metrics["variant"] = "equal_weight_baseline"
    port_metrics["_port_series"] = port_series
    return port_metrics


# ── Kill criteria evaluation ─────────────────────────────────────────────────

def evaluate_kill_criteria(
    result: dict,
    baseline: dict,
    pre_checks: dict,
) -> list[dict]:
    """Evaluate all H004 kill criteria. Returns list of result dicts."""
    port_series = result["_port_series"]
    base_series = baseline["_port_series"]

    port_monthly = port_series.resample("ME").apply(lambda r: (1 + r).prod() - 1)
    base_monthly = base_series.resample("ME").apply(lambda r: (1 + r).prod() - 1)
    aligned = pd.DataFrame({"vol": port_monthly, "base": base_monthly}).dropna()
    ret_corr = float(aligned.corr().loc["vol", "base"]) if len(aligned) > 5 else float("nan")

    return [
        {
            "criterion": "Sharpe < 0.3",
            "value": result.get("sharpe", float("nan")),
            "threshold": SHARPE_KILL,
            "triggered": result.get("sharpe", 1.0) < SHARPE_KILL,
        },
        {
            "criterion": "Max DD > 20%",
            "value": abs(result.get("max_drawdown", 0.0)),
            "threshold": DD_KILL,
            "triggered": abs(result.get("max_drawdown", 0.0)) > DD_KILL,
        },
        {
            "criterion": "Alpha vs VFV < 0%",
            "value": result.get("alpha_vs_benchmark", float("nan")),
            "threshold": 0.0,
            "triggered": result.get("alpha_vs_benchmark", 1.0) < 0.0,
        },
        {
            "criterion": "Corr(vol-targeted returns, baseline) > 0.70",
            "value": ret_corr,
            "threshold": CORR_KILL,
            "triggered": ret_corr > CORR_KILL if not np.isnan(ret_corr) else False,
        },
        {
            "criterion": "H004: leverage effect absent (majority Corr(fwd_ret,RV) > 0)",
            "value": pre_checks.get("leverage_corr_positive_count", 0),
            "threshold": len(EQUITY_TICKERS) / 2,
            "triggered": pre_checks.get("leverage_corr_positive_count", 0) > len(EQUITY_TICKERS) / 2,
        },
        {
            "criterion": "H004: Corr(vol_regime_score, portfolio_RV) > 0.85",
            "value": pre_checks.get("regime_overlap_corr", float("nan")),
            "threshold": REGIME_OVERLAP_KILL,
            "triggered": abs(pre_checks.get("regime_overlap_corr", 0.0)) > REGIME_OVERLAP_KILL,
        },
    ]


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("H004 -- Volatility Targeting Backtest (Moreira-Muir Scaling)")
    print("=" * 70)

    print("\n[1/5] Loading price data...")
    prices = load_prices()
    print(f"  Loaded: {sorted(prices.keys())}")

    rv_21d = {t: compute_monthly_rv(prices[t]) for t in EQUITY_TICKERS if t in prices}
    rv_ewma = {t: compute_ewma_variance(prices[t]) for t in EQUITY_TICKERS if t in prices}

    end_date = date.today()
    start_date = date(end_date.year - BACKTEST_YEARS, end_date.month, end_date.day)
    print(f"  Backtest window: {start_date} to {end_date}")

    # ── PRE-BACKTEST CHECK 1: Leverage effect ─────────────────────────────────
    print("\n[2/5] Pre-check 1 -- Leverage effect: Corr(equity_return_{t+1}, RV_t)")
    leverage_corrs = check_leverage_effect(prices)
    positive_count = sum(1 for v in leverage_corrs.values() if not np.isnan(v) and v > 0)

    print(f"  {'Ticker':<10} {'Corr(fwd_ret, RV)':<22} Direction")
    print(f"  {'-'*60}")
    for ticker, corr in leverage_corrs.items():
        direction = "POSITIVE (leverage effect ABSENT)" if corr > 0 else "negative (leverage effect present)"
        corr_str = f"{corr:+.4f}" if not np.isnan(corr) else "  nan"
        print(f"  {ticker:<10} {corr_str:<22} {direction}")

    print(f"\n  Tickers with positive Corr(fwd_ret, RV): {positive_count}/{len(EQUITY_TICKERS)}")
    leverage_kill = positive_count > len(EQUITY_TICKERS) / 2
    print(f"  Kill criterion (majority positive): {'[KILL]' if leverage_kill else '[PASS]'}")

    # ── PRE-BACKTEST CHECK 2: Regime signal overlap ───────────────────────────
    print("\n[3/5] Pre-check 2 -- Corr(vol_regime_score, portfolio_RV)")
    regime_corr = check_regime_signal_overlap(prices)
    print(f"  Corr(vol_regime_score, portfolio_RV): {regime_corr:+.4f}")
    print(f"  Kill threshold: |corr| > {REGIME_OVERLAP_KILL}")
    regime_kill = abs(regime_corr) > REGIME_OVERLAP_KILL
    print(f"  Kill criterion: {'[KILL]' if regime_kill else '[PASS]'}")

    pre_checks = {
        "leverage_corrs": leverage_corrs,
        "leverage_corr_positive_count": positive_count,
        "regime_overlap_corr": regime_corr,
    }

    # ── WALK-FORWARD BACKTESTS ─────────────────────────────────────────────────
    print("\n[4/5] Running walk-forward backtests...")
    print("  Running equal-weight baseline...")
    baseline = run_equal_weight_baseline(prices, start_date, end_date)

    print("  Running vol-targeted (21d RV)...")
    result_rv21 = run_vol_targeted_backtest(prices, rv_21d, start_date, end_date, "vol_target_rv21")

    print("  Running vol-targeted (EWMA lambda=0.94)...")
    result_ewma = run_vol_targeted_backtest(prices, rv_ewma, start_date, end_date, "vol_target_ewma")

    # ── PRE-BACKTEST CHECK 3: RV estimator comparison ─────────────────────────
    sharpe_rv21 = result_rv21.get("sharpe", float("nan"))
    sharpe_ewma = result_ewma.get("sharpe", float("nan"))
    sharpe_delta = sharpe_ewma - sharpe_rv21
    ewma_wins = sharpe_delta > EWMA_ADVANTAGE_THRESHOLD
    print(f"\n  Pre-check 3 -- 21d RV vs EWMA Sharpe delta: {sharpe_delta:+.4f} (EWMA minus 21d RV)")
    print(f"  Kill criterion (EWMA wins by >{EWMA_ADVANTAGE_THRESHOLD}): {'[KILL]' if ewma_wins else '[PASS]'}")
    pre_checks["sharpe_rv21"] = sharpe_rv21
    pre_checks["sharpe_ewma"] = sharpe_ewma
    pre_checks["ewma_advantage"] = sharpe_delta

    # ── RESULTS TABLE ─────────────────────────────────────────────────────────
    print("\n[5/5] Results")
    print("=" * 70)

    def _row(label: str, key: str, fmt: str = "+.4f") -> None:
        b = baseline.get(key, float("nan"))
        r = result_rv21.get(key, float("nan"))
        e = result_ewma.get(key, float("nan"))
        bfmt = format(b, fmt) if isinstance(b, float) and not np.isnan(b) else "--"
        rfmt = format(r, fmt) if isinstance(r, float) and not np.isnan(r) else "--"
        efmt = format(e, fmt) if isinstance(e, float) and not np.isnan(e) else "--"
        print(f"  {label:<30} {bfmt:<18} {rfmt:<18} {efmt}")

    print(f"\n  {'Metric':<30} {'Baseline (EW)':<18} {'Vol-Target RV21':<18} {'Vol-Target EWMA'}")
    print(f"  {'-'*80}")
    _row("Ann. Return", "annualized_return")
    _row("Ann. Vol", "annualized_vol", ".4f")
    _row("Sharpe", "sharpe", ".4f")
    _row("Sortino", "sortino", ".4f")
    _row("Max Drawdown", "max_drawdown")
    _row("Calmar", "calmar", ".4f")
    _row("Alpha vs VFV", "alpha_vs_benchmark")
    _row("Beta", "beta_vs_benchmark", ".4f")
    _row("Avg holdings/period", "avg_holdings_per_period", ".1f")

    # ── KILL CRITERIA EVALUATION ──────────────────────────────────────────────
    print("\n  Kill Criteria Evaluation (vol_target_rv21):")
    print(f"  {'-'*60}")
    kills = evaluate_kill_criteria(result_rv21, baseline, pre_checks)
    any_kill = False
    for k in kills:
        val = k["value"]
        val_str = f"{val:+.4f}" if isinstance(val, float) and not np.isnan(val) else str(val)
        status = "[KILL]" if k["triggered"] else "[PASS]"
        print(f"  {k['criterion']}")
        print(f"    Value: {val_str}  |  Threshold: {k['threshold']}  |  {status}")
        if k["triggered"]:
            any_kill = True

    print(f"\n  {'='*60}")
    triggered_count = sum(1 for k in kills if k["triggered"])
    if any_kill:
        print(f"  VERDICT: KILL -- {triggered_count} kill criterion/criteria triggered")
    else:
        print("  VERDICT: ALL KILL CRITERIA PASS -- promote to BACKTESTED")
    print(f"  {'='*60}")

    # ── SUMMARY for hypothesis file ───────────────────────────────────────────
    print("\n  Raw numbers for H004_vol_targeting.md:")
    print(f"  Baseline Sharpe:          {baseline.get('sharpe', float('nan')):.4f}")
    print(f"  Vol-Target RV21 Sharpe:   {result_rv21.get('sharpe', float('nan')):.4f}")
    print(f"  Vol-Target EWMA Sharpe:   {result_ewma.get('sharpe', float('nan')):.4f}")
    print(f"  Baseline Ann. Return:     {baseline.get('annualized_return', float('nan')):+.4f}")
    print(f"  Vol-Target RV21 Return:   {result_rv21.get('annualized_return', float('nan')):+.4f}")
    print(f"  Baseline Max DD:          {baseline.get('max_drawdown', float('nan')):+.4f}")
    print(f"  Vol-Target RV21 Max DD:   {result_rv21.get('max_drawdown', float('nan')):+.4f}")
    print(f"  Baseline Alpha:           {baseline.get('alpha_vs_benchmark', float('nan')):+.4f}")
    print(f"  Vol-Target RV21 Alpha:    {result_rv21.get('alpha_vs_benchmark', float('nan')):+.4f}")
    print(f"  Corr(regime, port_RV):    {regime_corr:+.4f}")
    print(f"  Leverage positive count:  {positive_count}/{len(EQUITY_TICKERS)}")
    print(f"  Per-ticker leverage corrs: {leverage_corrs}")


if __name__ == "__main__":
    main()
