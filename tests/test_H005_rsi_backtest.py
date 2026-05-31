"""
H005 Backtest: RSI(21) > 50 as Momentum Confirmation Filter.

Council-mandated protocol (DL-012):
  1. Empirical correlation — RSI gates vs momentum direction
  2. Divergence sub-period — forward returns when RSI/momentum disagree
  3. Portfolio comparison — baseline vs RSI-monthly vs RSI-daily vs EMA(12)
  4. t-statistic for incremental alpha (Harvey et al. threshold: t > 3.0)
  5. Verdict: additive or redundant?

Two windows:
  - Full 9-ETF (incl. CHPS.TO): 2023-07 to 2026-04 (~33 months — tight)
  - Extended 8-ETF (no CHPS.TO): 2017-06 to 2026-04 (~106 months — wider)

Run:  pytest -s tests/test_H005_rsi_backtest.py
      python tests/test_H005_rsi_backtest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Allow running directly as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows cp1252 can't encode U+2500 box-drawing chars used in print separators
sys.stdout.reconfigure(encoding="utf-8")

from src.data.storage import get_connection

# Research backtests read the REAL historical DB, independent of the test-suite
# $QUANT_DB isolation (conftest.py). This is read-only replication against live
# price history, not a unit test, so it must not see the empty throwaway DB.
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "quant.db"

# ── Universe ──────────────────────────────────────────────────────────────────

ALL_TICKERS = [
    "VFV.TO", "XIC.TO", "HXQ.TO", "XEF.TO",  # growth
    "CDZ.TO", "VDY.TO",                         # dividend
    "VAB.TO", "HSAV.TO",                         # stable
    "CHPS.TO",                                   # growth (added 2021)
]
STABLE = {"VAB.TO", "HSAV.TO"}
BENCHMARK = "VFV.TO"
TOP_N = 4  # top growth/dividend tickers by momentum rank each month

# Momentum formation: 252 trading days lookback + 21-day skip
FORM_DAYS = 252
SKIP_DAYS = 21
RSI_MONTHLY_PERIOD = 21   # H005 proposed: 21 monthly bars
RSI_DAILY_PERIOD = 14     # Canonical Wilder daily spec
EMA_MONTHLY_PERIOD = 12   # Comparison gate: price > EMA(12 months)


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_daily_prices() -> dict[str, pd.Series]:
    if not DB_PATH.exists():
        return {}
    conn = get_connection(DB_PATH)
    result: dict[str, pd.Series] = {}
    for ticker in ALL_TICKERS:
        rows = conn.execute(
            "SELECT trade_date, adj_close FROM prices WHERE ticker=? ORDER BY trade_date",
            (ticker,),
        ).fetchall()
        if rows:
            dates = pd.to_datetime([r[0] for r in rows])
            vals = pd.Series([float(r[1]) for r in rows], index=dates, name=ticker)
            result[ticker] = vals.dropna()
    conn.close()
    return result


# ── Signal helpers ────────────────────────────────────────────────────────────

def _rsi(prices: pd.Series, period: int) -> pd.Series:
    """Wilder RSI series on prices. Uses SMMA: ewm(alpha=1/period, adjust=False)."""
    delta = prices.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    avg_gain = gains.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100.0 - (100.0 / (1.0 + rs))).rename(f"rsi_{period}")


def _build_signal_panel(
    daily: dict[str, pd.Series],
    tickers: list[str],
) -> pd.DataFrame:
    """
    Build a (ticker × month) panel with all signals and next-month returns.

    Signals computed for each month-end:
        momentum_raw    : 12-1 month price return
        rsi21_monthly   : RSI(21) on monthly-resampled prices
        rsi14_daily     : RSI(14) on daily prices at month-end
        ema12_gate      : 1 if price > EMA(12 months), else 0
        next_ret        : forward 1-month return (label)
    """
    records = []
    bench_monthly = daily[BENCHMARK].resample("ME").last()
    month_ends = bench_monthly.index

    for ticker in tickers:
        if ticker not in daily:
            continue
        d = daily[ticker]
        monthly = d.resample("ME").last().dropna()

        # Pre-compute RSI on daily and monthly bars
        rsi_daily_series = _rsi(d, RSI_DAILY_PERIOD)
        rsi_monthly_series = _rsi(monthly, RSI_MONTHLY_PERIOD)
        ema12_monthly = monthly.ewm(span=EMA_MONTHLY_PERIOD, adjust=False).mean()

        for me in month_ends:
            d_to_me = d[d.index <= me].dropna()
            m_to_me = monthly[monthly.index <= me].dropna()

            # ── Momentum (12-1 month on daily bars) ──────────────────────────
            needed = FORM_DAYS + SKIP_DAYS
            if len(d_to_me) < needed + 10:
                continue
            p_skip = d_to_me.iloc[-SKIP_DAYS - 1]
            p_form = d_to_me.iloc[-(FORM_DAYS + SKIP_DAYS) - 1]
            if p_form <= 0:
                continue
            momentum_raw = float(p_skip / p_form) - 1.0

            # ── RSI(21) on monthly bars ───────────────────────────────────────
            rsi21_m = rsi_monthly_series.get(me, np.nan)
            if pd.isna(rsi21_m) and me in rsi_monthly_series.index:
                rsi21_m = float(rsi_monthly_series[me])

            # ── RSI(14) on daily bars at month-end ────────────────────────────
            rsi14_d = rsi_daily_series.get(me, np.nan)
            if pd.isna(rsi14_d) and me in rsi_daily_series.index:
                rsi14_d = float(rsi_daily_series[me])

            # ── EMA(12) gate on monthly bars ──────────────────────────────────
            if me in ema12_monthly.index and me in monthly.index:
                ema12_gate = 1.0 if float(monthly[me]) > float(ema12_monthly[me]) else 0.0
            else:
                ema12_gate = np.nan

            # ── Next-month return (label, no lookahead) ───────────────────────
            future = d[d.index > me]
            if future.empty or d_to_me.empty:
                next_ret = np.nan
            else:
                next_me = (me + pd.offsets.MonthEnd(1))
                future_in = future[future.index <= next_me]
                if future_in.empty:
                    next_ret = np.nan
                else:
                    next_ret = float(future_in.iloc[-1] / d_to_me.iloc[-1]) - 1.0

            records.append({
                "month_end": me,
                "ticker": ticker,
                "momentum_raw": momentum_raw,
                "rsi21_monthly": rsi21_m,
                "rsi14_daily": rsi14_d,
                "ema12_gate": ema12_gate,
                "next_ret": next_ret,
            })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Cross-sectional momentum rank (1 = strongest) per month, non-stable only
    non_stable = df[~df["ticker"].isin(STABLE)].copy()
    non_stable["mom_rank"] = non_stable.groupby("month_end")["momentum_raw"].rank(
        ascending=False, method="first"
    )
    stable = df[df["ticker"].isin(STABLE)].copy()
    stable["mom_rank"] = np.nan
    df = pd.concat([non_stable, stable]).sort_values(["month_end", "ticker"])

    # Binary gate columns
    df["mom_positive"] = (df["momentum_raw"] > 0).astype(int)
    df["rsi21_m_gate"] = (df["rsi21_monthly"] > 50).astype(float)
    df["rsi14_d_gate"] = (df["rsi14_daily"] > 50).astype(float)

    return df.dropna(subset=["momentum_raw", "next_ret"]).reset_index(drop=True)


# ── Portfolio simulation ──────────────────────────────────────────────────────

def _monthly_portfolio_returns(
    panel: pd.DataFrame,
    gate_col: str | None = None,
) -> pd.Series:
    """
    Equal-weight monthly portfolio returns.

    Each month:
      - Non-stable: select top TOP_N by momentum rank where momentum > 0.
        If gate_col given, also require gate_col == 1.
      - Stable: always included, equal-weight.
    Falls back to stable-only if no active tickers qualify.
    """
    monthly_returns: list[tuple] = []

    for me, grp in panel.groupby("month_end"):
        stable_rows = grp[grp["ticker"].isin(STABLE)].dropna(subset=["next_ret"])
        active_rows = grp[~grp["ticker"].isin(STABLE)].dropna(
            subset=["next_ret", "mom_rank"]
        )

        # Filter active: positive momentum
        eligible = active_rows[active_rows["mom_positive"] == 1].copy()

        # Apply additional gate if requested
        if gate_col is not None:
            eligible = eligible[eligible[gate_col].fillna(0) == 1]

        # Top N by momentum rank
        selected_active = eligible.nsmallest(TOP_N, "mom_rank")
        selected = pd.concat([selected_active, stable_rows])

        if selected.empty:
            continue

        monthly_returns.append((me, float(selected["next_ret"].mean())))

    if not monthly_returns:
        return pd.Series(dtype=float)

    idx, rets = zip(*monthly_returns)
    return pd.Series(rets, index=idx, name=gate_col or "baseline").dropna()


def _sharpe(returns: pd.Series, annualize: int = 12) -> float:
    """Monthly returns to annualised Sharpe (0 risk-free for simplicity)."""
    if len(returns) < 2 or returns.std() == 0:
        return np.nan
    return float(returns.mean() / returns.std() * np.sqrt(annualize))


def _t_stat(incremental: pd.Series) -> float:
    """t-statistic: H0 = mean incremental return is zero."""
    n = len(incremental)
    if n < 3:
        return np.nan
    se = incremental.std() / np.sqrt(n)
    return float(incremental.mean() / se) if se > 0 else np.nan


def _annualised_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() ** (12 / len(returns)) - 1)


# ── Correlation and divergence analysis ──────────────────────────────────────

def _correlation_analysis(panel: pd.DataFrame) -> dict:
    """
    Measure correlation between gate columns and momentum direction.
    Also measures forward return in divergence sub-periods.
    """
    non_stable = panel[~panel["ticker"].isin(STABLE)].copy()

    results = {}
    for gate_col, label in [
        ("rsi21_m_gate", "RSI(21) monthly"),
        ("rsi14_d_gate", "RSI(14) daily"),
        ("ema12_gate",   "EMA(12) monthly"),
    ]:
        sub = non_stable.dropna(subset=["mom_positive", gate_col, "next_ret"]).copy()
        sub[gate_col] = sub[gate_col].astype(float)

        n = len(sub)
        if n < 10:
            results[label] = {"n": n, "insufficient_data": True}
            continue

        # Pearson correlation (treating binary vars as continuous)
        corr = float(sub["mom_positive"].corr(sub[gate_col]))

        # Agreement rate: fraction of (ticker, month) pairs where gate == mom_positive
        agreement = float((sub[gate_col] == sub["mom_positive"]).mean())

        # Divergence: momentum says yes, gate says no (gate would filter valid signal)
        div_filter = sub[(sub["mom_positive"] == 1) & (sub[gate_col] == 0)]
        # Divergence: gate says yes, momentum says no (gate creates noise)
        div_noise = sub[(sub["mom_positive"] == 0) & (sub[gate_col] == 1)]

        # Forward return in divergence cases
        div_filter_ret = float(div_filter["next_ret"].mean()) if not div_filter.empty else np.nan
        div_noise_ret = float(div_noise["next_ret"].mean()) if not div_noise.empty else np.nan
        agree_ret = float(sub[
            (sub["mom_positive"] == 1) & (sub[gate_col] == 1)
        ]["next_ret"].mean())

        results[label] = {
            "n": n,
            "pearson_corr_mom_vs_gate": corr,
            "agreement_rate": agreement,
            "n_diverge_filter": len(div_filter),
            "n_diverge_noise": len(div_noise),
            "mean_ret_agree_both_on": agree_ret,
            "mean_ret_diverge_mom_yes_gate_no": div_filter_ret,
            "mean_ret_diverge_gate_yes_mom_no": div_noise_ret,
        }

    return results


# ── Main analysis ─────────────────────────────────────────────────────────────

def _run_analysis(tickers: list[str], label: str, panel: pd.DataFrame) -> None:
    if panel.empty:
        print(f"\n[{label}] No data — skipping.")
        return

    months = panel["month_end"].nunique()
    print(f"\n{'='*65}")
    print(f"  H005 BACKTEST - {label}")
    print(f"  Universe: {sorted(tickers)}")
    print(f"  Period:   {panel['month_end'].min().strftime('%Y-%m')} to "
          f"{panel['month_end'].max().strftime('%Y-%m')}  ({months} months)")
    print(f"{'='*65}")

    # ── 1. Correlation analysis ──────────────────────────────────────────
    print("\n── 1. Gate / Momentum Correlation ──────────────────────────────")
    print(f"  {'Gate':<20} {'Corr(mom,gate)':<16} {'Agreement%':<12} "
          f"{'N_filter':<10} {'N_noise':<10}")
    corr = _correlation_analysis(panel)
    for lbl, r in corr.items():
        if r.get("insufficient_data"):
            print(f"  {lbl:<20} insufficient data (n={r['n']})")
            continue
        print(
            f"  {lbl:<20} {r['pearson_corr_mom_vs_gate']:>+.3f}          "
            f"{r['agreement_rate']*100:>6.1f}%      "
            f"{r['n_diverge_filter']:>6}    {r['n_diverge_noise']:>6}"
        )

    # ── 2. Divergence sub-period returns ─────────────────────────────────
    print("\n── 2. Forward Returns in Divergence Cases ───────────────────────")
    print(f"  {'Gate':<20} {'Both=ON':<10} {'Mom=ON Gate=OFF':<18} {'Gate=ON Mom=OFF':<16}")
    for lbl, r in corr.items():
        if r.get("insufficient_data"):
            continue
        both_on = f"{r['mean_ret_agree_both_on']*100:+.2f}%"
        mom_yes_gate_no = (
            f"{r['mean_ret_diverge_mom_yes_gate_no']*100:+.2f}%"
            if not np.isnan(r["mean_ret_diverge_mom_yes_gate_no"])
            else "  N/A"
        )
        gate_yes_mom_no = (
            f"{r['mean_ret_diverge_gate_yes_mom_no']*100:+.2f}%"
            if not np.isnan(r["mean_ret_diverge_gate_yes_mom_no"])
            else "  N/A"
        )
        print(f"  {lbl:<20} {both_on:<10} {mom_yes_gate_no:<18} {gate_yes_mom_no:<16}")
    print("  (Mom=ON, Gate=OFF: cases the gate would suppress — "+
          "positive = gate removing valid signal)")

    # ── 3. Portfolio performance ──────────────────────────────────────────
    print("\n── 3. Portfolio Performance (monthly rebalance, top-4 non-stable) ─")
    strategies = {
        "Baseline (no gate)": None,
        "+ RSI(21) monthly":  "rsi21_m_gate",
        "+ RSI(14) daily":    "rsi14_d_gate",
        "+ EMA(12) monthly":  "ema12_gate",
    }

    bench_daily = _load_daily_prices().get(BENCHMARK)
    bench_rets: pd.Series | None = None
    if bench_daily is not None:
        bench_monthly = bench_daily.resample("ME").last().pct_change().dropna()
        month_range = (panel["month_end"].min(), panel["month_end"].max())
        bench_rets = bench_monthly[
            (bench_monthly.index >= month_range[0]) &
            (bench_monthly.index <= month_range[1])
        ]

    results: dict[str, pd.Series] = {}
    print(f"  {'Strategy':<24} {'Ann.Ret':>8} {'Sharpe':>8} {'MaxDD':>8} "
          f"{'N_months':>9}")
    print(f"  {'-'*24} {'-'*8} {'-'*8} {'-'*8} {'-'*9}")

    for name, gate in strategies.items():
        port = _monthly_portfolio_returns(panel, gate_col=gate)
        if len(port) < 3:
            print(f"  {name:<24} insufficient data")
            continue
        ann_ret = _annualised_return(port)
        sharpe = _sharpe(port)
        max_dd = float(((1 + port).cumprod() / (1 + port).cumprod().cummax() - 1).min())
        print(f"  {name:<24} {ann_ret*100:>+7.1f}% {sharpe:>8.2f} "
              f"{max_dd*100:>7.1f}% {len(port):>9}")
        results[name] = port

    if bench_rets is not None and not bench_rets.empty:
        ann_b = _annualised_return(bench_rets)
        sharpe_b = _sharpe(bench_rets)
        max_dd_b = float(
            ((1 + bench_rets).cumprod() / (1 + bench_rets).cumprod().cummax() - 1).min()
        )
        print(f"  {'Benchmark (VFV.TO)':<24} {ann_b*100:>+7.1f}% {sharpe_b:>8.2f} "
              f"{max_dd_b*100:>7.1f}% {len(bench_rets):>9}")

    # ── 4. Incremental alpha t-statistics ────────────────────────────────
    print("\n── 4. Incremental Alpha vs Baseline (Harvey et al. bar: t > 3.0) ─")
    baseline = results.get("Baseline (no gate)")
    if baseline is None or len(baseline) < 3:
        print("  Baseline unavailable — cannot compute t-statistics.")
    else:
        print(f"  {'Gate strategy':<24} {'t-stat':>8} {'n_overlap':>10} {'Verdict':>16}")
        print(f"  {'-'*24} {'-'*8} {'-'*10} {'-'*16}")
        for name, gate in [
            ("+ RSI(21) monthly", "rsi21_m_gate"),
            ("+ RSI(14) daily",   "rsi14_d_gate"),
            ("+ EMA(12) monthly", "ema12_gate"),
        ]:
            port = results.get(name)
            if port is None or len(port) < 3:
                continue
            shared_idx = baseline.index.intersection(port.index)
            if len(shared_idx) < 3:
                continue
            incremental = port.loc[shared_idx] - baseline.loc[shared_idx]
            t = _t_stat(incremental)
            verdict = (
                "ADDITIVE (t > 3.0)" if not np.isnan(t) and abs(t) > 3.0
                else "REDUNDANT (t ≤ 3.0)" if not np.isnan(t)
                else "N/A"
            )
            print(
                f"  {name:<24} {t:>+8.2f} {len(shared_idx):>10}   {verdict:<16}"
            )

    # ── 5. Verdict ────────────────────────────────────────────────────────
    print("\n── 5. Verdict ───────────────────────────────────────────────────")
    baseline = results.get("Baseline (no gate)")
    rsi_m = results.get("+ RSI(21) monthly")
    ema = results.get("+ EMA(12) monthly")

    if baseline is None or rsi_m is None:
        print("  INCONCLUSIVE — insufficient data for verdict.")
        return

    shared = baseline.index.intersection(rsi_m.index)
    if len(shared) < 3:
        print("  INCONCLUSIVE — too few overlapping months.")
        return

    incr = rsi_m.loc[shared] - baseline.loc[shared]
    t_rsi21 = _t_stat(incr)

    incr_ema: pd.Series | None = None
    t_ema = np.nan
    if ema is not None:
        shared_ema = baseline.index.intersection(ema.index)
        if len(shared_ema) >= 3:
            incr_ema = ema.loc[shared_ema] - baseline.loc[shared_ema]
            t_ema = _t_stat(incr_ema)

    print(f"  RSI(21) monthly gate t-stat: {t_rsi21:+.2f}  "
          f"(threshold: |t| > 3.0 required)")
    if not np.isnan(t_ema):
        print(f"  EMA(12) monthly gate t-stat: {t_ema:+.2f}  (comparison arm)")

    if not np.isnan(t_rsi21) and abs(t_rsi21) > 3.0:
        print("\n  >>> RESULT: RSI(21) gate CLEARS t > 3.0 — potential ADDITIVE value.")
        print("  >>> Update H005 status to ACTIVE candidate for production testing.")
    else:
        t_str = f"{t_rsi21:.2f}" if not np.isnan(t_rsi21) else "N/A"
        print(f"\n  >>> RESULT: RSI(21) gate does NOT clear t > 3.0 (t = {t_str}).")
        print("  >>> VERDICT: REDUNDANT — recommend REJECT H005.")
        print("  >>> RSI(21) gate adds no statistically credible value beyond")
        print("      the existing momentum signal at the Harvey et al. bar.")
        if not np.isnan(t_ema) and abs(t_ema) > abs(t_rsi21 or 0):
            print(f"  >>> EMA(12) gate (t={t_ema:.2f}) performed {'better' if abs(t_ema) > abs(t_rsi21 or 0) else 'similarly'} —")
            print("      consistent with Council recommendation of EMA as preferred alternative.")


# ── Pytest entry point ────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="quant.db not found — run `quant ingest` first",
)
def test_H005_rsi_backtest():
    """
    H005 Council-mandated backtest. Results printed to stdout.
    Run with:  pytest -s tests/test_H005_rsi_backtest.py
    """
    daily = _load_daily_prices()
    assert len(daily) >= 5, "Need at least 5 tickers loaded"

    # ── Window 1: Full 9-ETF universe ────────────────────────────────────
    # CHPS.TO needs 22 months warmup for RSI(21) monthly to start 2023-07
    nine_etf_tickers = [t for t in ALL_TICKERS if t in daily]
    nine_start = pd.Timestamp("2023-07-01")
    panel_full = _build_signal_panel(daily, nine_etf_tickers)
    panel_full = panel_full[panel_full["month_end"] >= nine_start]

    _run_analysis(nine_etf_tickers, "Full 9-ETF Universe (2023-07 to present)", panel_full)

    # ── Window 2: Extended 8-ETF (no CHPS.TO) ────────────────────────────
    eight_etf_tickers = [t for t in ALL_TICKERS if t != "CHPS.TO" and t in daily]
    eight_start = pd.Timestamp("2017-06-01")
    panel_8 = _build_signal_panel(daily, eight_etf_tickers)
    panel_8 = panel_8[panel_8["month_end"] >= eight_start]

    _run_analysis(eight_etf_tickers, "Extended 8-ETF (no CHPS.TO, 2017-06 to present)", panel_8)

    # ── Data integrity assertions (always run) ───────────────────────────
    if not panel_8.empty:
        assert panel_8["momentum_raw"].notna().any(), "No valid momentum values"
        assert panel_8["rsi21_monthly"].notna().any(), "No valid RSI(21) monthly values"
        assert panel_8["rsi14_daily"].notna().any(), "No valid RSI(14) daily values"
        assert panel_8["ema12_gate"].notna().any(), "No valid EMA(12) values"
        assert panel_8["next_ret"].notna().any(), "No valid forward returns"
        months_8 = panel_8["month_end"].nunique()
        assert months_8 >= 20, (
            f"Extended window has only {months_8} months — insufficient for analysis"
        )


# ── Direct script execution ───────────────────────────────────────────────────

if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"ERROR: quant.db not found at {DB_PATH}")
        print("Run: python -m src.cli.main ingest")
        sys.exit(1)

    daily = _load_daily_prices()
    print(f"Loaded {len(daily)} tickers from quant.db")
    for t, s in daily.items():
        print(f"  {t}: {len(s)} days ({s.index[0].date()} to {s.index[-1].date()})")

    nine_etf = [t for t in ALL_TICKERS if t in daily]
    panel_full = _build_signal_panel(daily, nine_etf)
    panel_full = panel_full[panel_full["month_end"] >= pd.Timestamp("2023-07-01")]
    _run_analysis(nine_etf, "Full 9-ETF Universe (2023-07 to present)", panel_full)

    eight_etf = [t for t in ALL_TICKERS if t != "CHPS.TO" and t in daily]
    panel_8 = _build_signal_panel(daily, eight_etf)
    panel_8 = panel_8[panel_8["month_end"] >= pd.Timestamp("2017-06-01")]
    _run_analysis(eight_etf, "Extended 8-ETF (no CHPS.TO, 2017-06 to present)", panel_8)
