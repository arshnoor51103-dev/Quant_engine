# H004 -- Portfolio-Level Volatility Targeting (GRAVEYARD)

**Status:** KILLED
**Created:** 2026-05-28
**Killed:** 2026-05-28
**Source:** Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." JF 72(4). Council DL-007.

> **Graveyard copy.** Full hypothesis at `docs/research/hypotheses/H004_vol_targeting.md`.
> Graveyard entries are never removed.

---

## Kill Summary

**Kill criteria triggered: 2 of 6**

| Kill Criterion | Result | Value |
|----------------|--------|-------|
| Sharpe < 0.3 | PASS | 1.0623 |
| Max DD > 20% | PASS | -17.28% |
| Alpha vs VFV < 0% | PASS | +4.94% |
| Corr(vol-targeted returns, baseline) > 0.70 | **TRIGGERED** | 0.9862 |
| H004-specific: leverage effect absent (majority Corr(fwd_ret,RV) > 0) | **TRIGGERED** | 7/7 positive |
| H004-specific: Corr(vol_regime_score, portfolio_RV) > 0.85 | PASS | -0.3478 |

---

## Pre-Backtest Check Results

| Check | Result | Kill triggered? |
|-------|--------|----------------|
| Corr(equity_return, RV_{t-1}) -- leverage effect | All 7/7 equity ETFs positive | YES -- majority positive |
| Corr(vol_regime_score, RV_t) -- signal overlap | -0.3478 | No (threshold 0.85) |
| 21-day RV vs EWMA Sharpe delta | -0.024 (EWMA loses marginally) | No |

---

## Walk-Forward Results (2021-05-28 to 2026-05-28, 5yr)

| Metric | Vol-Targeted (RV21) | Equal-Weight Baseline | VFV Benchmark | Pass/Fail |
|--------|--------------------|-----------------------|--------------|-----------|
| Annualized return | +18.78% | +18.89% | -- | -- |
| Annualized vol | 13.44% | 14.73% | -- | -- |
| Sharpe | 1.0623 | 0.9768 | -- | PASS |
| Sortino | 1.4115 | 1.3145 | -- | -- |
| Max drawdown | -17.28% | -18.20% | -- | PASS |
| Calmar | 1.0865 | 1.0380 | -- | -- |
| Alpha vs VFV | +4.94% | +4.05% | -- | PASS |
| Beta | 0.7521 | 0.8319 | -- | -- |
| Corr vs baseline (monthly returns) | 0.9862 | -- | -- | **KILL** |

Per-ticker leverage effect correlations:
- VFV.TO: +0.299, XIC.TO: +0.283, HXQ.TO: +0.226, XEF.TO: +0.157
- CHPS.TO: +0.028, CDZ.TO: +0.209, VDY.TO: +0.073

---

## Autopsy

**Why it failed:**

Two independent kill criteria, one theoretical and one empirical:

1. **Leverage effect absent in Canadian ETF universe (structural -- theoretical basis fails).**
   Moreira-Muir's formula improves Sharpe if and only if Corr(E[r_{t+1}], sigma^2_t) < 0 -- i.e.,
   high-vol months must PRECEDE lower returns. In US equity markets, this negative leverage effect
   is well-documented (vol spikes during drawdowns; return recovers after). On this 9-ETF Canadian
   universe over 2021-2026, the correlation is inverted: ALL 7 equity ETFs show positive
   Corr(fwd_return, RV), ranging from +0.028 (CHPS) to +0.299 (VFV). The 2021-2026 window includes
   COVID recovery and the AI/semiconductor boom -- periods where high-vol months were often followed
   by strong rallies, not drawdowns. When the mathematical precondition fails, the formula has no
   theoretical justification even if in-sample metrics happen to look marginally better.

2. **Vol targeting produces near-identical portfolio to equal-weight baseline (empirical redundancy).**
   Monthly return correlation between vol-targeted strategy and equal-weight baseline is 0.9862.
   This is structurally similar to H005's finding (96.2% momentum agreement rate). Moreira-Muir
   scaling shifts weights within the same top-4 tickers but does not change which tickers are
   held -- momentum signal rank order is preserved by design. With only 4-5 tickers per period
   each receiving weight adjustments within a narrow range (clipped to [0.25, 4.0] x equal-weight),
   the resulting portfolio is nearly indistinguishable from equal-weight in monthly return space.

**Interesting nuance -- metrics improve despite KILL:**
Despite being killed, vol targeting marginally improves Sharpe (0.977 -> 1.062), reduces max DD
(-18.2% -> -17.3%), and slightly increases alpha. These improvements exist because the scaling
mechanically reduces exposure during high-vol months. But: (a) the improvement is within
estimation noise given the short backtest window; (b) the theoretical foundation is invalid
(leverage effect absent); (c) the strategy is operationally indistinguishable from baseline
(0.9862 correlation). A strategy that improves metrics for the wrong reason, on a small sample,
should not be promoted -- this is precisely what the kill criteria prevent.

**Structural vs parameter issue:**

Structural on the leverage effect failure. The problem is not the RV window (21d), the
EWMA parameter (lambda=0.94), or the clip bounds. The problem is that the mathematical
condition for Sharpe improvement does not hold for Canadian-listed equity ETFs in the
studied period. The leverage effect is primarily documented in US individual equities
under the Black (1976) leverage mechanism; its applicability to ETFs (where creation/
redemption arbitrage buffers price-vol dynamics) and non-US markets was already flagged
as uncertain in DL-007's Council deliberation.

Parametric on the correlation kill. The 0.9862 monthly return correlation might improve at
Tier 2+ with a wider universe (30+ tickers) where vol scaling creates meaningful dispersion
across the selection rather than minor weight adjustments within the same 4 ETFs.

**Revisit conditions:**

1. **Leverage effect test at Tier 2+ (Canadian individual equities).** Individual stocks exhibit
   stronger leverage effect than ETFs -- the Black (1976) mechanism operates at the firm level.
   If Corr(fwd_ret, RV) turns negative for a basket of 30+ Canadian stocks, revisit Moreira-Muir
   as a position-sizing modifier (not as a strategy alone). This is the single most important
   condition: if the theoretical precondition is not met, no parameter tuning helps.

2. **Longer sample period.** The 2021-2026 window is dominated by post-COVID recovery dynamics.
   A 10-15 year sample including 2008-2009 or 2015-2016 vol episodes might show the leverage
   effect more clearly. Revisit when sufficient history is available for the full Canadian ETF
   universe.

3. **Fixed-target formulation (sigma_target / sigma_hat_t) with wider universe.** The
   fixed-target variant is more tractable than inverse-variance scaling and is used by
   Research Affiliates for multi-asset portfolios. If Tier 2+ conditions are met, test
   fixed-target first before inverse-variance.

---

## Research Script

- **Code:** `docs/research/scratch/H004_vol_targeting_backtest.py`
- **Integration status:** NOT in signal path. Research artifact only.
