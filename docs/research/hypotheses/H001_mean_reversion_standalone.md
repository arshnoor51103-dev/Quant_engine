# H001 — Mean Reversion Standalone Signal (9-ETF Universe)

**Status:** KILLED
**Created:** 2026-05-22
**Last updated:** 2026-05-22
**Source:** Academic literature (Jegadeesh 1990, Lehmann 1990) + natural counterpart to the existing momentum signal. Idea: if momentum captures trend-followers, mean reversion captures the correction after overextension.

---

## Thesis

Assets that have deviated significantly from their recent return distribution tend to revert toward their historical mean. A dual-window z-score of daily log returns (20-day short-term, 60-day intermediate) captures this oversold/overbought deviation. On a universe of 9 Canadian-listed ETFs with monthly rebalancing, selecting the most oversold tickers should produce positive returns as prices revert. The signal should complement momentum: when momentum chases winners, mean reversion bets on losers recovering — in theory, low correlation and potential ensemble benefit.

---

## Proposed Math

**Time-series component:**

```
z_N(i, t) = (r_i(t) - μ_N(i, t)) / σ_N(i, t)
```

where `r_i(t)` is the daily log return of ticker i at day t,  
`μ_N` and `σ_N` are the rolling mean and standard deviation over N trading days.

```
z_ts(i, t) = 0.5 × z_20(i, t) + 0.5 × z_60(i, t)
```

**TS normalization:** `tanh(z_ts)` — smooth compression to (−1, +1), handles outliers gracefully.

**Cross-sectional component:**

```
z_cs(i, t) = rank_normalize(z_ts(i, t)) across universe → [−1, +1]
```

**Regime-conditional blend:**

```
combined(i, t) = w_ts × tanh(z_ts(i, t)) + w_cs × z_cs(i, t)
```

Regime weights (TS/CS):
- CRISIS: 0.70 / 0.30 — tickers decorrelate in crisis, idiosyncratic TS dominates
- HIGH_VOL: 0.60 / 0.40
- NORMAL: 0.50 / 0.50
- LOW_VOL: 0.35 / 0.65 — high correlation regime, relative positioning more informative

**Sign flip:** Multiply combined by −1. Oversold (negative z) → positive score (buy signal).

**Final:** Rank-normalize across universe → [−1, +1]. Warmup: 60 rows minimum; else score = 0.0 (neutral).

**References:** Jegadeesh (1990), Lehmann (1990), Asness/Moskowitz/Pedersen (2013) — cross-asset momentum/reversion evidence.

---

## Preconditions

- **Universe required:** Tier 1 (9 ETFs is the minimum tested; hypothesis is that Tier 2+ would help)
- **Regime dependency:** TS/CS weight blend shifts by regime. Signal runs in all regimes.
- **Data requirements:** Minimum 60 trading days of daily OHLCV. 252+ preferred for stable z-score statistics.
- **Rebalance frequency:** Monthly (top-4 equal-weight, same structure as momentum backtest)

---

## Kill Criteria

Global defaults applied with no overrides.

- Sharpe < 0.3 in 5-year walk-forward backtest
- Max drawdown > 20%
- Correlation with existing live signals > 0.70
- Alpha vs VFV.TO < 0%
- Requires rebalance frequency faster than monthly

---

## Council Review

**Date reviewed:** 2026-05-22 (post-facto — signal was built before the Council system was formalized)
**Council verdict:** Not formally reviewed pre-build. Backtest results render the verdict moot — three independent kill criteria triggered.
**Key pushback (reconstructed):** The Skeptic would have flagged: "9 ETFs has insufficient cross-sectional dispersion for a ranking signal. The 'losers' in any given month are structurally different assets (e.g., bonds in a rate-hike year), not mean-reverting equities. And your 20-day window requires weekly or daily rebalancing to capture the reversal before it resolves — monthly rebalancing is structurally incompatible with the signal's time horizon."
**Modifications post-review:** N/A — the backtest confirmed the skeptical case.

---

## Backtest Results

**Date run:** 2026-05-22
**Parameters:** 5-year walk-forward, top-4 selection, monthly rebalance (21 trading days), equal-weight, long-only, VFV.TO benchmark. Identical configuration to the momentum baseline for direct comparison.

| Metric | Mean Reversion | VFV Benchmark | Momentum Baseline | Pass/Fail |
|--------|---------------|--------------|-------------------|-----------|
| Annualized return | +4.24% | +16.51% | +13.98% | — |
| Annualized vol | 9.93% | — | 11.75% | — |
| Sharpe | **−0.027** | 0.805 | 0.807 | **FAIL** (< 0.3) |
| Sortino | −0.038 | — | 1.035 | — |
| Max drawdown | **−24.18%** | −22.19% | −15.9% | **FAIL** (> 20%) |
| Calmar | 0.175 | — | 0.879 | — |
| Alpha vs VFV | **−6.59%** | — | +1.19% | **FAIL** (< 0%) |
| Beta | 0.527 | — | 0.685 | — |
| Monthly win rate | 55.7% (34/61) | — | — | — |
| Corr vs momentum (monthly returns) | **+0.836** | — | — | **FAIL** (> 0.70) |

**Kill criteria triggered: 4 of 5** (Sharpe, max drawdown, alpha, correlation with momentum).

---

## Decision

**Outcome:** KILLED

**Reasoning:** All four quantitative kill criteria triggered simultaneously. The signal is not marginally below threshold — it is deeply negative on alpha (−6.6%), violates the 20% drawdown ceiling (−24.18%), and produces nearly identical monthly returns to momentum (r = 0.836), eliminating any ensemble benefit. Standalone mean reversion on this universe, at this trade frequency, does not work.

---

## Autopsy

**Why it failed:**

Three independent structural failures, not one:

1. **Universe too small for cross-sectional dispersion.** 9 ETFs, 5 of which are equity (2 growth, 2 dividend, 1 semiconductor). In any given month, the "losers" are often structurally different assets — bonds underperforming in a rate-hike year, or a specific regional ETF lagging due to currency moves. These are not mean-reverting equities being temporarily pushed below fair value. They are assets responding correctly to regime changes. The signal systematically buys the wrong thing.

2. **Monthly rebalance too slow for the 20-day z-score window.** Jegadeesh/Lehmann short-term reversals operate at 1-week horizons. By the time the monthly rebalance fires, the reversal has already resolved (best case) or deepened into a real trend (worst case). The 20-day z-score is stale at the point of execution.

3. **Both signals are cross-sectional ranking signals on the same 9-ticker universe.** With equal-weight top-4 portfolio construction, momentum and mean reversion end up selecting mostly the same 4 tickers in different order — 4 out of 9 is too coarse a selection to produce portfolio-level divergence. Hence 0.836 monthly return correlation.

**What this teaches:**

Signal design can be mathematically correct and structurally incompatible with trading constraints at the same time. The z-score formula is sound. The tanh normalization is elegant. The regime-conditional blending is principled. None of that matters when the universe is too small to express cross-sectional dispersion and the execution frequency is too low to capture the reversal window. **Backtest is the only arbiter.** No amount of mathematical elegance substitutes for empirical validation on the actual universe and constraints.

**Structural vs parameter issue:**

Structural. The constraint set is the problem — monthly rebalance and 9-ticker universe — not the signal math. If the universe expands to 30+ individual stocks (Tier 2) where genuine idiosyncratic reversals exist, and if a weekly rebalance becomes possible (requires CRA constraint clarification or non-registered account), the signal math may show edge. The formula itself is not wrong. Its operating environment is wrong for this configuration.

**Revisit conditions:**

1. **Tier 2+ universe** with 25–40 individual Canadian stocks. Cross-sectional dispersion is much higher with individual equities — stock-level reversals (earnings disappointments, temporary liquidity shocks) are well-documented and don't require cross-asset comparison.
2. **Weekly rebalance** if CRA constraints ever clarify that systematic monthly contributions do not constitute day-trading intent when rebalancing weekly. Or when a non-registered/margin account is opened (capital trigger: 24 trades/year hit OR NAV ≥ $5k).
3. **Position-sizing modifier** use case: don't use MR as a standalone selection signal, use `tanh(z_ts)` as a weight-modifier on momentum selections. Strongly negative z_ts = caution flag on a momentum-positive ticker. This doesn't require high trade frequency and doesn't depend on cross-sectional dispersion.
