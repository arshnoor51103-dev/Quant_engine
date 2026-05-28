# H004 -- Portfolio-Level Volatility Targeting (Moreira-Muir Scaling)

**Status:** KILLED
**Created:** 2026-05-28
**Last updated:** 2026-05-28
**Killed:** 2026-05-28
**Source:** Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." Journal of Finance, 72(4), 1611-1644. Routed from Council session DL-007 (2026-05-24).

---

## Thesis

Realized variance is negatively correlated with expected equity returns (leverage effect). A portfolio that scales position sizes inversely proportional to last month's realized variance should improve risk-adjusted returns by reducing exposure during high-vol drawdown periods and increasing exposure during low-vol recovery periods. Applied at the portfolio weight construction step -- after signal ranking selects the top-N tickers -- and restricted to the equity bucket only (Growth + Dividend). Stable bucket (VAB.TO, HSAV.TO) is excluded: HISA returns have no return-variance relationship; bond vol may correlate positively with returns. The critical empirical question is whether this adds anything beyond what the existing vol_regime signal already does.

---

## Proposed Math

**Moreira-Muir inverse-variance scaling (portfolio weights, not signal scores):**

```
RV_{t-1} = sum of squared daily returns over prior month
c = E[RV_{t-1}]                           # unconditional mean of RV (preserves overall vol)
scale_t = c / RV_{t-1}                    # scalar: >1 in low-vol months, <1 in high-vol months
```

**Application at weight construction time:**

```
# Step 1: signal ranking selects top-N tickers (unchanged)
selected = top_n_by_signal_score(equity_tickers)

# Step 2: equal-weight baseline
w_i = 1 / len(selected)

# Step 3: vol-target adjustment (EQUITY BUCKET ONLY)
w_i_managed = w_i x scale_t              # scale by prior month's realized variance ratio
w_i_managed = clip(w_i_managed, 0, 1)   # no shorting
w_i_managed = normalize(w_i_managed)    # re-normalize so equity weights sum to bucket target

# Step 4: stable bucket unchanged (equal-weight, no scaling)
```

The signal score rank order is preserved. Scaling is a weight modifier, not a score modifier.

---

## Preconditions

- **Universe required:** Tier 1 (9 ETFs). Applied to equity bucket: VFV.TO, XIC.TO, HXQ.TO, XEF.TO, CHPS.TO, CDZ.TO, VDY.TO. Stable bucket (VAB.TO, HSAV.TO) not scaled.
- **Regime dependency:** None at the signal level -- scaling is mechanical (RV-based), not regime-conditional.
- **Data requirements:** Minimum 22 daily bars of prior-month returns per ticker. Daily OHLCV already available.
- **Rebalance frequency:** Monthly (no change).

---

## Kill Criteria

**Global defaults (PIPELINE.md) -- all apply:**

| Criterion | Threshold | Action |
|-----------|-----------|--------|
| Sharpe (walk-forward, 5yr) | < 0.3 | KILL |
| Max drawdown | > 20% | KILL |
| Correlation with existing live signals (monthly returns) | > 0.70 | KILL |
| Alpha vs VFV.TO | < 0% | KILL |
| Rebalance frequency | Faster than monthly | KILL |

**H004-specific kill criteria (from DL-007 Council mandate):**

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Corr(vol_regime_score, RV_t) across equity ETFs | > 0.85 | Vol targeting redundant with existing vol_regime signal |
| Corr(equity_return_{t+1}, RV_t) majority positive | > 50% of tickers | Leverage effect absent -- Moreira-Muir formula has no theoretical basis |
| 21-day RV vs EWMA Sharpe delta | EWMA wins by > 0.1 | Estimation noise dominates; wrong vol estimator |

---

## Council Review

**Date reviewed:** 2026-05-24
**Council verdict:** CONTESTED_RESOLVED (3-2 CANDIDATE). Mathematician, Empiricist, Engineer voted CANDIDATE. Skeptic and Risk Manager voted THEORETICAL.
**DL entry:** DL-007
**Key pushback:**
- **Skeptic:** 21-day realized variance has ~31% standard error. Scaling portfolio weights by a noisy estimate may introduce more variance than it removes.
- **Risk Manager:** Double-counting risk -- vol_regime signal already modulates signal strength. Stacking vol targeting may over-penalize high-vol periods.
- **Mathematician (affirmative):** Monthly rebalance reduces transaction cost objection. Leverage effect likely holds for equity ETFs.
- **Chair resolution:** CANDIDATE subject to three mandatory pre-backtest checks.

---

## Backtest Results

**Date run:** 2026-05-28
**Code:** `docs/research/scratch/H004_vol_targeting_backtest.py`
**Parameters:** 5-year walk-forward (2021-05-28 to 2026-05-28), top-4 equity selection, monthly rebalance (21 trading days), vol-scaled weights vs equal-weight baseline, long-only, VFV.TO benchmark.

### Pre-Backtest Checks

| Check | Result | Kill triggered? |
|-------|--------|----------------|
| Corr(equity_return_{t+1}, RV_t) -- leverage effect | 7/7 equity ETFs positive (+0.03 to +0.30) | **YES** -- all positive, majority threshold triggered |
| Corr(vol_regime_score, portfolio_RV) -- signal overlap | -0.3478 | No (|corr| < 0.85 threshold) |
| 21-day RV vs EWMA Sharpe delta | -0.024 (EWMA loses marginally) | No (delta < 0.1 threshold) |

Per-ticker leverage correlations: VFV.TO +0.299, XIC.TO +0.283, HXQ.TO +0.226, XEF.TO +0.157, CHPS.TO +0.028, CDZ.TO +0.209, VDY.TO +0.073

### Walk-Forward Results

| Metric | Vol-Targeted (21d RV) | Equal-Weight Baseline | VFV Benchmark | Pass/Fail |
|--------|----------------------|----------------------|--------------|-----------|
| Annualized return | +18.78% | +18.89% | -- | -- |
| Annualized vol | 13.44% | 14.73% | -- | -- |
| Sharpe | 1.0623 | 0.9768 | -- | PASS (> 0.3) |
| Sortino | 1.4115 | 1.3145 | -- | -- |
| Max drawdown | -17.28% | -18.20% | -- | PASS (< 20%) |
| Calmar | 1.0865 | 1.0380 | -- | -- |
| Alpha vs VFV | +4.94% | +4.05% | -- | PASS (> 0%) |
| Beta | 0.7521 | 0.8319 | -- | -- |
| Avg holdings/period | 3.8 | 3.8 | -- | -- |
| Corr vs baseline (monthly returns) | 0.9862 | -- | -- | **KILL** (> 0.70) |

**Kill criteria triggered: 2 of 6** (leverage effect absent; returns correlation)

---

## Decision

**Outcome:** KILLED

**Reasoning:** Two kill criteria triggered. Leverage effect is absent in this universe -- all 7 equity ETFs show positive Corr(fwd_return, RV), invalidating Moreira-Muir's mathematical precondition. Monthly return correlation with equal-weight baseline is 0.9862, confirming near-zero portfolio-level differentiation. The apparent metric improvements (Sharpe +0.086, max DD -0.9pp) exist but are theoretically unjustified and within estimation noise on a 5-year window.

---

## Autopsy

**Why it failed:**

Two independent failures, one theoretical and one empirical:

1. **Leverage effect absent in Canadian ETF universe (structural -- theoretical basis fails).**
   Moreira-Muir's Sharpe improvement requires Corr(E[r_{t+1}], sigma^2_t) < 0. All 7 equity ETFs
   show the opposite: high-vol months are followed by higher, not lower, returns over the
   2021-2026 window. The period includes COVID recovery and the AI/semiconductor boom where
   high-vol episodes preceded strong rallies. When the mathematical precondition fails, the
   formula has no theoretical justification regardless of in-sample metrics.

2. **Near-identical portfolio to equal-weight baseline (empirical redundancy).**
   Monthly return correlation = 0.9862. Moreira-Muir scaling shifts weights within the same
   top-4 tickers without changing which tickers are held (rank order is preserved by design).
   With 4-5 tickers per period and scale clipped to [0.25, 4.0] x equal-weight, the resulting
   portfolio is operationally indistinguishable from equal-weight in monthly return space.
   This mirrors H005's finding: adding a modifier on top of the existing signal does not
   change the portfolio when the modifier and the existing signal rank the same tickers.

**Interesting nuance:** Vol targeting marginally improves all three pass-criteria metrics
(Sharpe, DD, alpha) despite being killed. The mechanical weight reduction in high-vol months
does reduce drawdown slightly. But the improvement exists for the wrong reason (the formula
should theoretically hurt performance when the leverage effect is absent, yet it helps slightly
because weight reduction in high-vol months still reduces risk, just not via the stated mechanism).
A strategy that appears to work for the wrong reason on a short sample is not a promotable
finding.

**Structural vs parameter issue:**

Structural on the leverage effect. The problem is not the RV window, the EWMA lambda, or
clip bounds. The leverage effect is primarily documented in US individual equities (Black 1976
mechanism). ETFs with creation/redemption arbitrage buffer price-vol dynamics differently.
The 2021-2026 window may also be atypical -- a longer sample including 2008-2009 might show
a different result, but this is speculation, not evidence.

Parametric on the correlation kill. A wider universe (30+ individual equities at Tier 2+)
might produce meaningful weight dispersion from vol scaling across a larger selection.

**Revisit conditions:**

1. **Tier 2+ with individual Canadian equities.** Test Corr(fwd_ret, RV) on a 30+ stock universe.
   If leverage effect is present (majority negative), revisit Moreira-Muir as a position-sizing
   modifier. This is the single gating condition -- no parameter tuning helps if the precondition fails.
2. **Longer sample.** 10-15 years including 2008-2009 to verify leverage effect directionally.
3. **Fixed-target formulation** (sigma_target / sigma_hat_t) if Tier 2+ conditions met -- simpler
   and used by Research Affiliates for multi-asset portfolios.
