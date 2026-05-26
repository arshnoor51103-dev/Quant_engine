# Research Pipeline — Quant Engine

> The discipline that separates quant research from guesswork.
> Every idea enters as a hypothesis. It either survives the gauntlet or it dies with an autopsy.
> The graveyard teaches more than the successes.

---

## Workflow Stages

```
PROPOSED → COUNCIL_REVIEWED → BACKTESTED → PROMOTED
                                          → KILLED (→ graveyard/)
                                          → SHELVED (universe/tier gate)
```

**PROPOSED**: Hypothesis file created in `hypotheses/` using the template. Thesis and math written down.

**COUNCIL_REVIEWED**: `/quant-research` skill invoked with Council Config G (5 members: Mathematician, Empiricist, Skeptic, Engineer, Risk Manager). No implementation work before this step.

**BACKTESTED**: Walk-forward backtest run with the parameters specified in the hypothesis. Kill criteria evaluated.

**PROMOTED**: All kill criteria cleared AND all promotion criteria met. Validated findings move to `findings/`. Hypothesis file stays in `hypotheses/` marked PROMOTED as cross-reference.

**KILLED**: One or more kill criteria triggered. Hypothesis file moves to `graveyard/` with autopsy filled in.

**SHELVED**: Kill criteria not triggered, but requires universe or tier capabilities not yet available. Hypothesis stays in `hypotheses/` marked SHELVED with the unlock condition noted. Not killed — revisit when conditions change.

---

## Rules

1. **Any idea enters as a hypothesis file.** From papers, market observations, Council sessions, backtest anomalies — all go through the template. No exception.

2. **No hypothesis skips Council review.** Run it through `/quant-research` with Council Config G before any implementation work. The Council stress-tests human hypotheses — it does not generate them. Strategy ideas come from academic papers, your own observations, and anomalies you notice in backtest data. NOT from asking an LLM to invent math.

3. **No hypothesis touches the live codebase until it passes backtest with ALL kill criteria cleared.** Full stop.

4. **Killed hypotheses move to `graveyard/` with a mandatory autopsy section filled in.** The autopsy is the most valuable output of this pipeline. Write it carefully.

5. **Promoted hypotheses move their validated findings to `findings/` under the appropriate subcategory.** The hypothesis file stays in `hypotheses/` marked PROMOTED as a cross-reference.

6. **The watchlist is passive background research for future tiers.** Zero interaction with the live trading system. Research storage, not a buy list.

7. **No LLM in the signal path.** The Council reviews human hypotheses — it does not generate signal math. Ideas come from you, from papers, from data. The Council's job is adversarial stress-testing.

---

## Kill Criteria (Global Defaults)

These apply to every hypothesis unless explicitly overridden with written justification in the hypothesis file.

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Sharpe ratio | < 0.3 in 5-year walk-forward backtest | Below this, noise explains the return as well as signal |
| Max drawdown | > 20% | Hard TFSA constraint — violates the system's core risk rule |
| Correlation with existing live signals | > 0.70 | No ensemble diversification benefit at this correlation |
| Alpha vs VFV.TO benchmark | < 0% | Underperforms passive — why not just hold VFV? |
| Rebalance frequency | Faster than monthly | Violates CRA 24-trade/year limit |
| Universe requirement | > current tier's eligible assets | SHELVED, not killed — revisit at higher tier |

---

## Promotion Criteria

**All must pass.** Not a checklist to partially satisfy.

| Criterion | Threshold |
|-----------|-----------|
| Sharpe | > 0.5 in walk-forward backtest (not in-sample — walk-forward only) |
| Max drawdown | < 18% (2% buffer inside the 20% ceiling) |
| Correlation with all existing live signals | < 0.50 |
| Alpha vs VFV.TO | Positive |
| Implementability | Within current constraints: trade frequency, universe, cost gate |

---

## Directory Layout

```
docs/research/
├── PIPELINE.md                         ← this file — master rules and workflow
├── TEMPLATE_HYPOTHESIS.md              ← template for all new hypotheses
├── hypotheses/                         ← all hypotheses (all statuses)
│   └── H001_mean_reversion_standalone.md
├── findings/                           ← promoted, validated research
│   ├── strategies/                     ← signal strategies that cleared all gates
│   ├── sectors/                        ← sector/thematic research validated for use
│   └── market_mechanics/               ← structural market knowledge (costs, liquidity, etc.)
├── watchlist/                          ← passive future-tier research
│   ├── README.md
│   ├── ai_semiconductor.md
│   └── canadian_energy.md
└── graveyard/                          ← killed hypotheses with autopsies
    └── H001_mean_reversion_standalone.md
```

---

## Hypothesis Numbering

Sequential: H001, H002, H003, ...
Never reused. Even if a hypothesis is killed, its ID is retired with it.
The graveyard preserves killed hypotheses permanently — their IDs don't recycle.

**Current count**: H001 (graveyard) · H005 (graveyard)

---

## Relationship to `docs/DEEPER_LEARNING.md`

`DEEPER_LEARNING.md` is the Council-validated quant knowledge base (concepts, math, frameworks).
This research pipeline is the hypothesis lifecycle tracker (ideas → backtest → promote/kill).

They are complementary, not redundant:
- A promoted hypothesis in `findings/` may cite a DL entry as its mathematical foundation.
- A DL entry may be created during the Council review of a hypothesis (new concept validated along the way).
- They are separate append-only artifacts with different scopes.

---

*Pipeline established: 2026-05-23. First resident: H001 (mean reversion standalone, KILLED).*
