# DEEPER LEARNING

Validated quantitative knowledge base for the Quant Engine project.

**Rules:**
1. Every entry has survived Council deliberation (Config G — Quantitative Research)
2. Append-only — never modify past entries; add new entries that reference and supersede
3. Convergence level is always stated — the reader knows if this is settled or contested
4. Math is the validated version, not raw research output
5. Status tracks lifecycle: THEORETICAL → CANDIDATE → ACTIVE (or REJECTED)

**Entry ID format:** DL-001, DL-002, ... (sequential, never reused)

---

## DL-001: Cross-Sectional Momentum (12-1 Month)

**Date:** 2026-05-22
**Classification:** NEW_ALGORITHM
**Status:** ACTIVE
**Council Convergence:** N/A — pre-dates Council system, validated via backtest
**Relevant Phase:** Phase 2 — Signal Generation

### Source
Canonical reference: Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling
Losers: Implications for Stock Market Efficiency." Journal of Finance, 48(1), 65-91.

### Mathematical Specification

R_i(t) = (P_i(t) - P_i(t-12)) / P_i(t-12)  — skip most recent month

Signal_i(t) = rank_normalize(R_i(t)) → [-1, +1]

Where:
- P_i(t) = adjusted close price of asset i at month t
- 12-month lookback with 1-month skip (avoids short-term reversal)
- Cross-sectional rank normalization across the ETF universe
- Top-N assets by rank are selected for equal-weight allocation

### Intuition
Assets that have outperformed over the past year (excluding the most recent month) tend to continue
outperforming in the near term. The 1-month skip avoids the well-documented short-term reversal
effect. This is one of the most robust anomalies in finance — documented across decades, geographies,
and asset classes.

### Assumptions
1. Momentum effect persists in Canadian-listed ETFs (less studied than US equities)
2. Monthly rebalance frequency is sufficient to capture the signal
3. The 12-1 lookback is appropriate for the current ETF universe (originally calibrated on stocks)
4. Transaction costs don't eat the alpha at our trade frequency

### Known Failure Modes
- Momentum crashes: sharp, violent reversals (e.g., March 2009) where winners become losers overnight
- Low-volatility regimes: signal strength weakens when cross-sectional dispersion is low
- Small universe: with only 9 ETFs, rank discrimination is coarse — limited cross-sectional spread

### Council Deliberation Summary
This entry pre-dates the Council system. Validation was performed via walk-forward backtest:
5-year period, top-4 selection, monthly rebalance, equal-weight. Results: +1.19% alpha vs VFV,
max drawdown -15.9% (within 20% ceiling), beta 0.685, Sortino 1.03. Strategy confirmed viable.

**Key Agreement:** N/A (backtest-validated)
**Key Tension:** N/A

### Quant Engine Integration
**Module affected:** src/signals/momentum.py
**Dependencies:** None beyond current stack (pandas, numpy)
**Implementation complexity:** Low — already implemented and running
**Interaction with existing signals:** Primary signal. Vol regime detector modulates position sizing.

### Cross-References
- Related DEEPER_LEARNING entries: None yet
- Related LEARNING.md entries: Phase 2 integration bugs (5 bugs found and fixed)
- Supersedes: N/A

---
