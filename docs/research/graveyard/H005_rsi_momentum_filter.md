# H005 — RSI(21) > 50 as Momentum Confirmation Filter (GRAVEYARD)

**Status:** KILLED
**Created:** 2026-05-26
**Killed:** 2026-05-26
**Source:** Wilder (1978), Marshall et al. (TSMOM/MA correlation). Council review DL-012.

> **This is the graveyard copy.** The full hypothesis is at `docs/research/hypotheses/H005_rsi_momentum_filter.md`.
> This file exists for fast autopsy lookup — graveyard entries are never removed.

---

## Kill Summary

**Kill criteria triggered: 3 of 3**

| Kill Criterion | Result | Value |
|----------------|--------|-------|
| Incremental alpha t-stat > 3.0 (Harvey et al.) | **TRIGGERED** | t=NaN (9-ETF, zero variance); t=-1.00 (8-ETF extended) |
| Divergence test: gate suppresses valid signals | **TRIGGERED** | +7.30% forward return when mom=ON, RSI=OFF — gate hurts |
| Empirical correlation (agreement rate) | **TRIGGERED** | 96.2% agreement (9-ETF); 83.5% (8-ETF extended) |

---

## Autopsy

**Why it failed:**

Two independent structural failures:

1. **Mathematical near-equivalence proved empirically.** RSI(21) > 50 and momentum_raw > 0 agree in 83.5–96.2% of (ticker, month) observations. Both signals measure the same underlying construct — positive price drift — with different smoothing. At monthly frequency, the RSI cannot express anything beyond what raw momentum already measures. The Council's Marshall et al. prediction (0.81–0.91 correlation) was confirmed.

2. **Gate actively harms by filtering valid momentum signals.** When momentum says BUY but RSI gate says NO, forward returns are +7.30% (extended window) — higher than the baseline. The gate is suppressing valid signals, not noise. RSI(21) SMMA is slower to recover from drawdowns than raw 12-month return; it blocks positions at exactly the moment they should be entered.

**Structural vs parameter issue:**

Structural. RSI at monthly frequency on a momentum-sorted portfolio is near-redundant with the momentum signal. No RSI period or threshold fixes this.

**What to use instead:**

The baseline momentum signal without any gate is the correct current spec. EMA(12) was tested as a comparison arm — also failed t > 3.0 (t=-1.53), though it is structurally simpler if a gate is ever revisited.

---

## Signal Code

- **Module:** `src/signals/rsi.py` — Wilder RSI implementation, complete and tested
- **Tests:** `tests/test_rsi_signal.py` (24 passing), `tests/test_H005_rsi_backtest.py`
- **Integration status:** NOT in signal path. Code preserved for reference only.
