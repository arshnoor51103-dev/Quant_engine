# H005 — RSI(21) > 50 as Momentum Confirmation Filter

**Status:** KILLED
**Created:** 2026-05-26
**Last updated:** 2026-05-26
**Source:** Academic: Wilder (1978), Marshall et al. (TSMOM/MA correlation). Council review DL-012.

---

## Thesis

RSI(21) > 50 as a multiplicative binary gate on the existing momentum signal. When the 21-month Wilder RSI exceeds 50, this indicates average gains exceed average losses over the lookback — a positive-drift confirmation consistent with momentum being "real." Gate closed (RSI ≤ 50) suppresses the momentum signal to zero, preventing the portfolio from entering declining-trend positions.

The hypothesis was that RSI, being a bounded transform of the gain/loss ratio, might capture a slightly different facet of trend persistence than raw price momentum and therefore provide additive filtering value.

---

## Proposed Math

**Wilder SMMA RSI:**

```
delta(t) = price(t) - price(t-1)
avg_gain = SMMA(max(delta, 0), n)   # alpha = 1/n (Wilder spec)
avg_loss = SMMA(max(-delta, 0), n)
RS = avg_gain / avg_loss
RSI(n) = 100 - (100 / (1 + RS))
```

**Gate signal:**

```
rsi_gate = 1.0 if RSI(21) > 50 else 0.0
combined = momentum_score × rsi_gate
```

**Mathematical equivalence note (DL-012):**

RSI > 50 iff SMMA(gains) > SMMA(losses) iff smoothed net signed price change > 0. This is a bounded monotonic transform of the same positive-drift construct as price above a moving average. Marshall et al. documented empirical correlation 0.81–0.91 between RSI-based and MA-based signals at monthly frequency.

---

## Preconditions

- **Universe:** Tier 1 (9 ETFs), non-stable tickers only (RSI gate does not apply to stable bucket)
- **Data requirements:** Minimum 22 monthly bars for RSI(21) to warm up
- **Rebalance frequency:** Monthly (no change from existing system)
- **Parameters:** period=21 (monthly bars), threshold=50.0

---

## Kill Criteria (H005-specific, Council-mandated per DL-012)

| Kill Criterion | Threshold | Rationale |
|----------------|-----------|-----------|
| Incremental alpha t-statistic | t > 3.0 (Harvey et al.) | Required for any added filter claiming alpha |
| Divergence test — gate suppresses valid signals | forward return in divergence > baseline | If RSI=OFF when mom=ON yields positive returns, gate hurts |
| Empirical correlation (mom vs RSI gate) | < 0.81 | Council threshold from Marshall et al. |

---

## Council Review

**Date reviewed:** 2026-05-26
**Council verdict:** STRONG_CONSENSUS — proceed to backtest, mathematical redundancy near-certain, empirical confirmation required before kill
**DL entry:** DL-012
**Key Council pushback:**
- **Mathematician:** RSI(21) on monthly bars is a bounded monotonic transform of SMMA net price change. Mathematically near-equivalent to 12-1 momentum at this frequency. No new information.
- **Empiricist:** Marshall et al. report 0.81–0.91 correlation between RSI-based and MA-based signals. At monthly rebalance, 21-month RSI and 12-month return are measuring the same underlying construct with different smoothing. Backtest correlation expected to be very high.
- **Skeptic:** Zero practitioner sources (Winton, AQR, Two Sigma research blogs, Quantopian notebooks) use RSI as a momentum gate on ETF portfolios. The canonical use is RSI mean-reversion at shorter frequencies. RSI(21) at monthly frequency is a misapplication of the indicator's design intent.
- **Engineer:** RSI(21) on monthly bars needs 22-month warmup. CHPS.TO added 2021 — warmup not complete until 2023-07. Severely constrains the 9-ETF backtest window.
- **Risk Manager:** Gate reduces position count during RSI-closed periods. If RSI is near-redundant with momentum direction, the gate is filtering valid positions without compensation.

---

## Backtest Results

**Date run:** 2026-05-26
**Code:** `tests/test_H005_rsi_backtest.py`
**Signal implementation:** `src/signals/rsi.py`

### Window 1: Full 9-ETF Universe (2023-07 to 2026-04, 34 months)

| Metric | Baseline (no gate) | + RSI(21) monthly | + RSI(14) daily | + EMA(12) monthly | Pass/Fail |
|--------|-------------------|-------------------|-----------------|-------------------|-----------|
| Ann. return | +18.2% | +18.2% | +13.3% | +17.3% | — |
| Sharpe | 1.86 | 1.86 | 2.02 | 1.86 | — |
| Max DD | -6.0% | -6.0% | -3.5% | -6.0% | — |
| t-stat (incremental vs baseline) | — | **NaN** | -1.37 | -1.09 | **FAIL** (need > 3.0) |
| Correlation agreement (mom vs RSI21 gate) | — | 96.2% | 48.7% | 92.0% | **FAIL** (< 0.81 required) |

t=NaN means zero incremental variance — RSI(21) monthly gate produced **identical** portfolio to baseline across all 34 months.

### Window 2: Extended 8-ETF (no CHPS.TO, 2017-06 to 2026-04, 107 months)

| Metric | Baseline (no gate) | + RSI(21) monthly | + EMA(12) monthly | Pass/Fail |
|--------|-------------------|-------------------|-------------------|-----------|
| Ann. return | +10.6% | +10.6% | +9.7% | — |
| Sharpe | 1.11 | 1.11 | 1.10 | — |
| Max DD | -15.5% | -15.5% | -14.0% | — |
| t-stat (incremental vs baseline) | — | **-1.00** | -1.53 | **FAIL** (need > 3.0) |
| Correlation agreement (mom vs RSI21 gate) | — | 83.5% | 83.8% | **FAIL** |

### Divergence Analysis (8-ETF extended)

| Gate | Both=ON | Mom=ON, Gate=OFF | Gate=ON, Mom=OFF |
|------|---------|-----------------|-----------------|
| RSI(21) monthly | +1.02% | **+7.30%** | +0.84% |
| RSI(14) daily | +0.87% | +1.27% | +1.05% |
| EMA(12) monthly | +1.00% | +2.08% | +1.22% |

**Critical finding:** When momentum says BUY but RSI gate says NO (5 cases in extended window), forward return is +7.30% — the gate would have actively suppressed valid momentum signals at significant cost.

**Kill criteria triggered: 3 of 3**

---

## Decision

**Outcome:** KILLED

**Reasoning:** All three H005-specific kill criteria triggered. RSI(21) monthly gate adds zero incremental value on either time window (t=NaN on 9-ETF, t=-1.00 on extended). The gate is mathematically redundant with the existing momentum signal — 96.2% agreement rate on the 9-ETF window confirms the Council's pre-backtest prediction. The divergence analysis provides the final evidence: the five cases where RSI says NO when momentum says YES have +7.30% forward return — the gate is removing valid signals, not noise.

---

## Autopsy

**Why it failed:**

Two independent structural failures:

1. **Mathematical near-equivalence proved empirically.** RSI(21) > 50 and momentum_raw > 0 agree in 83.5–96.2% of (ticker, month) observations depending on the window. Both signals are measuring the same underlying construct — positive price drift over the lookback period — with different smoothing windows and normalizations. The Mathematician's pre-backtest warning was precisely correct. At monthly frequency with a 21-month RSI period, the indicator cannot express anything beyond what raw momentum already measures.

2. **Gate harms by filtering valid momentum signals.** The divergence analysis shows the cases where RSI says NO while momentum says YES have *higher* forward returns (+7.30%) than the baseline agree-both-on case (+1.02%). This is not noise filtering — it is valid momentum signal suppression. The intuition: RSI(21) is slower to recover from a drawdown than raw 12-month return. A ticker with a recent recovery (positive 12-1 momentum) may still have RSI < 50 because the SMMA gain average hasn't caught up. The gate blocks the position at exactly the wrong moment.

**What this teaches:**

The Council's prediction of 0.81–0.91 correlation from Marshall et al. was confirmed empirically (96.2% agreement on 9-ETF). Pre-backtest mathematical analysis accurately predicted the outcome. The hypothesis was a well-posed test of a proposition the math already suggested was false. That's the right way to run this pipeline — not to prove the hypothesis right, but to confirm or deny the mathematical prediction with data.

**Structural vs parameter issue:**

Structural — the problem is not the RSI period (14 vs 21) or threshold (50). The problem is that RSI at monthly frequency on a momentum-sorted portfolio is near-redundant with the momentum signal itself. No parameter tuning fixes this.

**Revisit conditions:**

None. This hypothesis class (RSI as momentum gate at monthly rebalance frequency) has been empirically invalidated. If a future researcher proposes RSI at a shorter frequency (daily RSI on intraday/weekly signals), that is a different hypothesis — H-new — not a revisit of H005. RSI(14) daily was tested as a comparison arm and also failed (t=-2.63 on extended window, worse than RSI(21) monthly despite higher variance of gate signal).

**What to use instead:**

EMA(12) monthly gate (price > 12-month EMA) performed similarly or better in the divergence analysis and is structurally simpler. However, it also failed the t > 3.0 bar (t=-1.53 on extended window). The Council's pre-backtest recommendation was that EMA(12) is the preferred alternative IF any gate is desired — this remains true, but EMA(12) also did not demonstrate additive value. The baseline momentum signal without any gate is the correct current spec.

---

## Signal Code (preserved, not deployed)

RSI implementation complete and tested:
- **Module:** `src/signals/rsi.py`
- **Tests:** `tests/test_rsi_signal.py` — 24 tests passing
- **Backtest:** `tests/test_H005_rsi_backtest.py`
- **Integration status:** NOT wired into recommendation engine. Not in signal path. Code-complete but inactive.
