# H001 — Mean Reversion Standalone Signal (9-ETF Universe)

**Status:** KILLED
**Created:** 2026-05-22
**Killed:** 2026-05-22
**Source:** Academic literature (Jegadeesh 1990, Lehmann 1990) + natural counterpart to the existing momentum signal.

> **This is the graveyard copy.** The full hypothesis is at `docs/research/hypotheses/H001_mean_reversion_standalone.md`.
> This file exists for fast autopsy lookup — graveyard entries are never removed.

---

## Kill Summary

**Kill criteria triggered: 4 of 5**

| Kill Criterion | Result | Value |
|----------------|--------|-------|
| Sharpe < 0.3 | **TRIGGERED** | −0.027 |
| Max drawdown > 20% | **TRIGGERED** | −24.18% |
| Alpha vs VFV < 0% | **TRIGGERED** | −6.59% |
| Correlation with momentum > 0.70 | **TRIGGERED** | +0.836 |
| Requires frequency faster than monthly | Passed | Monthly (same as live system) |

---

## Autopsy

**Why it failed:**

Three independent structural failures, not one:

1. **Universe too small for cross-sectional dispersion.** 9 ETFs with 5 equity positions. The "losers" in any month are often structurally different assets (bonds in a rate-hike year, regional ETF lagging on currency) — not mean-reverting equities temporarily below fair value. The signal buys the wrong thing systematically.

2. **Monthly rebalance too slow for the 20-day z-score window.** Jegadeesh/Lehmann reversals operate at 1-week horizons. By the time the monthly rebalance fires, the reversal has resolved or deepened into a real trend.

3. **Both signals are cross-sectional ranking signals on the same 9 tickers.** Top-4 equal-weight selection from 9 names produces nearly identical portfolios whether ranked by momentum or mean reversion — hence 0.836 monthly return correlation. No ensemble diversification possible at this coarseness.

**What this teaches:**

Signal design can be mathematically correct and structurally incompatible with trading constraints simultaneously. The formula is sound. The constraint set (monthly rebalance, 9-ticker universe) is the problem. Backtest is the only arbiter. No mathematical elegance substitutes for empirical validation on the actual universe and constraints.

**Structural vs parameter issue:**

**Structural** — the constraint set is the problem, not the signal math. The z-score formula, tanh normalization, and regime-conditional blending are all principled. They require an operating environment the current system cannot provide.

**Revisit conditions:**

1. **Tier 2+ universe (25–40 individual CA stocks):** genuine idiosyncratic reversals exist in individual equities; stock-level cross-sectional dispersion is well-documented.
2. **Weekly rebalance:** if CRA constraints clarify or non-registered account opens (trigger: 24 trades/year OR NAV ≥ $5k).
3. **As position-sizing modifier only:** use `tanh(z_ts)` as a weight-modifier on momentum-selected tickers rather than a standalone selection signal. Strongly negative z_ts = caution flag. No high frequency required.

---

## Signal Code (preserved, not deployed)

Signal is complete and tested in the codebase:
- **Module:** `src/signals/mean_reversion.py`
- **Tests:** `tests/test_mean_reversion.py` — 16 tests passing
- **CLI access:** `quant signals --signal-type mean_reversion`
- **Integration status:** NOT wired into recommendation engine. Not in signal path. Code-complete but inactive.
