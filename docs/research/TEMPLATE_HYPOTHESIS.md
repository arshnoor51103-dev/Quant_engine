# H[NNN] — [Descriptive Title]

**Status:** PROPOSED | COUNCIL_REVIEWED | BACKTESTED | PROMOTED | KILLED | SHELVED
**Created:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD
**Source:** [Where this idea came from — paper citation, market observation, backtest anomaly, etc.]

---

## Thesis

[One paragraph maximum. What do you believe, and why? Be specific and falsifiable. A thesis that can't be falsified isn't a thesis — it's a preference.]

---

## Proposed Math

[The signal formula, weighting scheme, or structural change. Pseudocode or LaTeX-style notation. If you can't write the math, the idea isn't concrete enough yet. Don't start implementation until this section is filled in.]

---

## Preconditions

- **Universe required:** [Tier 1 (9 ETFs) / Tier 2 (+ CA stocks) / Tier 3 (+ US ETFs) / Tier 4 (+ individual stocks)]
- **Regime dependency:** [Does this only work in certain vol regimes? Which ones?]
- **Data requirements:** [How much history? Any special data beyond daily OHLCV?]
- **Rebalance frequency:** [Monthly / weekly / other — must be compatible with CRA 24-trade limit]

---

## Kill Criteria

[Use global defaults from PIPELINE.md unless overriding. If overriding, write the justification here.]

- Sharpe < 0.3 in 5-year walk-forward backtest
- Max drawdown > 20%
- Correlation with existing live signals > 0.70
- Alpha vs VFV.TO < 0%
- Requires rebalance frequency faster than monthly
- Requires universe beyond current tier → SHELVED instead of KILLED

**Overrides from global defaults:** [None — or justify each override]

---

## Council Review

**Date reviewed:**
**Council verdict:** [APPROVED_TO_BACKTEST / REJECTED_BEFORE_BACKTEST / NEEDS_REVISION]
**Key pushback:** [What did the Skeptic or Risk Manager flag? What was the strongest objection?]
**Modifications post-review:** [What changed in the thesis or math after the Council session?]

---

## Backtest Results

**Date run:**
**Parameters:** [years, top-N, rebalance freq, benchmark, walk-forward or in-sample]

| Metric | Strategy | VFV Benchmark | Pass/Fail |
|--------|----------|--------------|-----------|
| Annualized return | | | — |
| Annualized vol | | | — |
| Sharpe | | | < 0.3 → KILL |
| Sortino | | | — |
| Max drawdown | | | > 20% → KILL |
| Calmar | | | — |
| Alpha vs VFV | | | < 0% → KILL |
| Beta | | | — |
| Monthly win rate | | | — |
| Corr vs momentum signal | | | > 0.70 → KILL |
| Corr vs other live signals | | | > 0.70 → KILL |

---

## Decision

**Outcome:** PROMOTED / KILLED / SHELVED
**Reasoning:** [1–3 sentences. Which criteria passed, which failed, what tipped the decision.]

---

## Autopsy (if KILLED or SHELVED)

**Why it failed:**
[Be specific. Which kill criterion triggered? What was the mechanism — was it the universe, the frequency, the signal construction, or all three?]

**What this teaches:**
[The transferable lesson. What does this failure tell you about signal design, universe constraints, or the cost of assumptions?]

**Structural vs parameter issue:**
[Was the idea fundamentally wrong (structural), or was it wrong for this universe/constraint set (parameter)? This distinction determines whether the idea is dead forever or just deferred.]

**Revisit conditions:**
[Under what future conditions should this be re-examined? E.g., "Revisit at Tier 2 with 30+ stocks for cross-sectional dispersion" or "Revisit if CRA rules clarify weekly rebalance is acceptable."]
