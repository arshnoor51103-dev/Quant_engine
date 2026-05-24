# Quant Research Skill Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-agent web search in the quant-research skill with a parallel four-agent pipeline (Academic, Practitioner, Replication, Synthesis) sourcing from verified curated databases, and expand the DEEPER_LEARNING.md entry format to carry the richer evidence structure.

**Architecture:** Three parallel research sub-agents (Academic hits 7 academic databases, Practitioner hits 10 verified quant/HF sites, Replication hunts independent confirmation/critique of the canonical source) produce structured findings packages. A Synthesis agent consolidates them into one Research Brief before the Council deliberates. DEEPER_LEARNING entries gain three new sections: Source Coverage, Replication Evidence, Practitioner Consensus.

**Tech Stack:** Markdown skill files only — no Python, no tests, no git commits in the skill directory. Two files rewritten, one file deleted.

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Delete | `~/.claude/skills/quant-research/templates/DEEPER_LEARNING_SEED.md` | Superseded — seeding is complete |
| Rewrite | `~/.claude/skills/quant-research/SKILL.md` | Full replacement: 5-step pipeline, 4 agent specs, curated source lists, output formats |
| Rewrite | `~/.claude/skills/quant-research/templates/deeper_learning_entry.md` | Add Evidence Quality field + 3 new sections (Source Coverage, Replication Evidence, Practitioner Consensus) |

Paths use `~` shorthand. Full path: `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\`.

No changes to:
- `~/.claude/skills/the-council/SKILL.md`
- `D:\Quant_engine\docs\DEEPER_LEARNING.md` (new format applies to future entries only)
- Any Python source file

---

## Task 1: Delete the Superseded Seed Template

**Files:**
- Delete: `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\templates\DEEPER_LEARNING_SEED.md`

- [ ] **Step 1: Confirm the file exists**

  Run: `Test-Path "C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\templates\DEEPER_LEARNING_SEED.md"`
  Expected: `True`

- [ ] **Step 2: Delete it**

  Run: `Remove-Item "C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\templates\DEEPER_LEARNING_SEED.md"`

- [ ] **Step 3: Verify deletion**

  Run: `Test-Path "C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\templates\DEEPER_LEARNING_SEED.md"`
  Expected: `False`

---

## Task 2: Rewrite SKILL.md — Complete Replacement

**Files:**
- Rewrite: `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\SKILL.md`

- [ ] **Step 1: Write the complete new SKILL.md**

  Write this exact content to `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\SKILL.md`:

````markdown
---
name: quant-research
description: >
  Systematic research engine for the Quant Engine project. Use this skill when the user wants to:
  research a new algorithm or signal, evaluate a quantitative strategy, understand a mathematical
  concept for potential implementation, check whether an existing signal's math is sound, explore
  factor models or portfolio optimization techniques, or find new strategies from academic literature.
  Also trigger when the user says "research", "find me an algorithm", "what strategies exist for",
  "is there a better way to calculate", "study this", "deep dive into", "explore [quant concept]",
  or "add this to deeper learning". This skill orchestrates: classify → parallel research agents
  (Academic + Practitioner + Replication) → synthesis → Council deliberation (Config G) → recursive
  reconvene if contested → validated write to DEEPER_LEARNING.md. Always trigger this over a basic
  web search when the topic is quantitative finance, signal design, portfolio math, or risk modeling.
---

# Quant Research Engine

A structured research pipeline that finds, validates, and persists quantitative knowledge for the
Quant Engine project. Every piece of knowledge that enters the system goes through the same pipeline:
classify → parallel multi-source research → synthesize → Council deliberate → persist.

Nothing gets written to DEEPER_LEARNING.md without surviving all three source domains and Council
deliberation.

---

## Prerequisites

This skill depends on **the-council** skill (specifically Configuration G — Quantitative Research).
Read `the-council/SKILL.md` if not already in context. The recursive reconvene protocol defined
there is the convergence mechanism used here.

This skill uses parallel sub-agents. Use the `superpowers:dispatching-parallel-agents` skill to
fire the Academic Agent and Practitioner Agent simultaneously in Step 2.

---

## Step 1: Classify the Research Request

Before doing anything, classify what the user is asking for. This determines the workflow depth.

| Type | Description | Example | Depth |
|------|-------------|---------|-------|
| **NEW_ALGORITHM** | Researching a strategy/signal not yet in the system | "What about pairs trading?" | Full pipeline |
| **ALGO_CHECK** | Validating math or assumptions in an existing signal | "Is our momentum signal's lookback period optimal?" | Council + targeted research |
| **CONCEPT_DEEP_DIVE** | Understanding a mathematical concept for potential use | "Explain Kelly criterion for position sizing" | Research + Council + DEEPER_LEARNING |
| **LITERATURE_SCAN** | Surveying what exists in a domain | "What mean reversion signals exist for ETFs?" | Broad search + summary + Council on top candidates |
| **IMPLEMENTATION_EVAL** | Can this algorithm work in our stack/constraints? | "Can we run Markowitz optimization with 9 ETFs in SQLite?" | Engineering-focused Council |

State the classification explicitly before proceeding:
```
📋 Research Classification: [TYPE]
Topic: [one-line summary]
Relevance to Quant Engine: [which phase/component this could affect]
```

---

## Step 2: Parallel Research Phase

Fire three research sub-agents. Academic and Practitioner fire simultaneously. The Replication
Agent fires after Academic finishes — it receives the canonical source list and targets it.

**Execution order:**
1. Fire Academic Agent and Practitioner Agent simultaneously (dispatching-parallel-agents)
2. When Academic Agent finishes, fire Replication Agent with its canonical source list as input
3. Wait for all three to complete
4. Proceed to Step 3 (Synthesis)

Each agent produces a structured findings package in the exact format specified below. Agents
must follow the format precisely — the Synthesis Agent depends on consistent structure.

---

### 2a. Academic Agent

**Mission:** Find the canonical and secondary academic literature. Extract verified math. Do not
evaluate or opine — retrieve and structure only.

**Sources to search (work through all 7):**

| Database | What to search |
|----------|----------------|
| SSRN (ssrn.com) | Full-text search for the topic |
| arXiv q-fin (arxiv.org/search — Quantitative Finance section) | Topic keyword search |
| NBER (nber.org/papers) | Working papers search |
| Google Scholar (scholar.google.com) | Citation counts, canonical source confirmation, related papers |
| Journal of Portfolio Management (pm-research.com) | Topic search |
| Financial Analysts Journal — CFA Institute (cfainstitute.org/research/financial-analysts-journal) | Topic search |
| Journal of Finance (onlinelibrary.wiley.com/journal/15406261) | Abstract search |

**Structured findings package — output exactly this format:**

```
ACADEMIC RESEARCH FINDINGS
Topic: [name]
Sources checked: [list all 7 — include those with no results]

CANONICAL SOURCE(S):
  Author, Year, Title, Journal
  Core findings: [2–3 sentences]
  Mathematical specification: [key equations, all variables defined]
  Sample: [geography, time period, asset class tested on]

SECONDARY SOURCES:
  [Author, Year] — [1-line finding]
  [Author, Year] — [1-line finding]

REPLICATION PAPERS (found in academic literature):
  [Author, Year] — Geography: [x], Period: [x], Result: confirmed/failed/mixed

MATHEMATICAL GAPS:
  [Free parameters, implementation choices the papers leave unspecified]

SOURCE GAPS:
  [Which of the 7 databases returned no relevant results]
```

---

### 2b. Practitioner Agent

**Mission:** Find what verified quant practitioners have independently published on this strategy.
Do not search beyond this list — open-ended practitioner searches return noise. Hit all 10 sources
and report findings or absence for each.

**Verified source list — search all 10:**

| Source | URL |
|--------|-----|
| AQR Capital Research | aqr.com/insights/research |
| Man Institute | man.com/maninstitute |
| Verdad Capital Research | verdadcap.com/research |
| Alpha Architect | alphaarchitect.com/blog |
| Research Affiliates | researchaffiliates.com/publications |
| Flirting with Models / Newfound Research | flirtingwithmodels.com |
| Robeco Insights | robeco.com/en/insights |
| NAAIM Research | naaim.org/research |
| Vanguard Research | advisors.vanguard.com/insights/research |
| Bank of Canada Working Papers | bankofcanada.ca/publications |

**Structured findings package — output exactly this format:**

```
PRACTITIONER RESEARCH FINDINGS
Topic: [name]
Sources checked: all 10

FINDINGS BY SOURCE:
  AQR: [key insight] OR [no content found]
  Man Institute: [key insight] OR [no content found]
  Verdad: [key insight] OR [no content found]
  Alpha Architect: [key insight] OR [no content found]
  Research Affiliates: [key insight] OR [no content found]
  Flirting with Models: [key insight] OR [no content found]
  Robeco: [key insight] OR [no content found]
  NAAIM: [key insight] OR [no content found]
  Vanguard: [key insight] OR [no content found]
  Bank of Canada: [key insight] OR [no content found]

PRACTITIONER CONSENSUS:
  [Where ≥3 sources agree — state the claim and which sources]

DIVERGENCE FROM ACADEMIC CONSENSUS:
  [Where practitioners say something different from the papers — or "none identified"]

SOURCE GAPS:
  [Which sites had no content — a meaningful signal that practitioners have not engaged]
```

---

### 2c. Replication/Criticism Agent

**Mission:** Hunt specifically for independent evidence that confirms or challenges the canonical
claims from the Academic Agent. This is targeted, not a general search — use the Academic Agent's
canonical source list to drive every query.

**Input received:** Academic Agent's canonical source list (author, year, title, core claims)

**Mandatory searches — run all 9:**

1. `"[factor/strategy name]" replication out-of-sample`
2. `"[factor/strategy name]" international evidence`
3. `"[factor/strategy name]" fails [market OR period]`
4. `"[factor/strategy name]" data mining OR p-hacking`
5. Fetch Hou, Xue & Zhang (2017) "Replicating Anomalies" — does this factor appear?
6. Fetch McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?" — does this factor appear? Is post-publication decay documented?
7. Fetch Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns" (the factor zoo paper) — does this factor appear? Is the t-statistic threshold flagged?
8. Search Alpha Architect replication series specifically for this factor/strategy
9. Search for any paper directly challenging a claim from the Academic Agent's canonical source

**Structured findings package — output exactly this format:**

```
REPLICATION & CRITICISM FINDINGS
Topic: [name]
Targeting canonical claims from: [Academic Agent canonical source(s)]

OUT-OF-SAMPLE REPLICATION EVIDENCE:
  [Author, Year] — Geography: [x], Period: [x], Result: confirmed/failed/mixed
  Notes: [1 sentence on methodology or key finding]

FACTOR ZOO / DATA MINING FLAGS:
  Hou et al (2017): [appears in study] / [does not appear] / [not applicable]
  McLean & Pontiff (2016): [appears — post-publication decay documented?] / [does not appear]
  Harvey et al (2016): [appears — t-stat flagged?] / [does not appear]

INDEPENDENT FAILURE MODE DOCUMENTATION:
  [Failure modes documented by non-original authors, with citation and conditions]

CRITIQUES OF SPECIFIC CLAIMS:
  [Any source that directly challenges a claim from the canonical paper]

REPLICATION SUMMARY:
  Overall replication status: Strong / Mixed / Weak / No independent evidence found
  Confidence basis: [1–2 sentences explaining the rating]
```

---

## Step 3: Synthesis Agent → Consolidated Research Brief

Read all three structured findings packages. Produce one Consolidated Research Brief. Do not add
new research — only integrate what the three agents found. Flag convergence and divergence explicitly.

**Consolidated Research Brief format:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 CONSOLIDATED RESEARCH BRIEF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic: [name]
Classification: [type]
Source coverage: Academic ([N] papers), Practitioner ([N]/10 sites with content), Replication ([N] studies)

MATHEMATICAL SPECIFICATION:
  [From Academic Agent — all variables defined]

ASSUMPTIONS:
  [Consolidated from all three agents — attributed to source where possible]

REPLICATION EVIDENCE:
  | Study | Geography | Period | Result |
  |-------|-----------|--------|--------|
  | [Author, Year] | [x] | [x] | Confirmed / Failed / Mixed |

PRACTITIONER CONSENSUS:
  [From Practitioner Agent — what verified sites say, with source attribution]

FAILURE MODES:
  [Consolidated from all three — each attributed to its source]
  [Distinguish: original-author-documented vs. independently-documented]

CONVERGENCE SUMMARY:
  All three domains agree on: [...]
  Academic and Practitioner agree but Replication is weak: [...]
  Disputed or absent in one domain: [...]

EVIDENCE QUALITY RATING:
  [Strong / Mixed / Weak / Insufficient]
  Basis: [2–3 sentences]

OPEN QUESTIONS FOR COUNCIL:
  [3–5 specific questions informed by all three source domains]
  [Required: at least one question on replication strength or out-of-sample performance]
  [Required: at least one question on Canadian ETF / TFSA monthly-rebalance applicability]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 4: Council Deliberation

Send the Consolidated Research Brief to The Council using **Configuration G — Quantitative Research**.

The 5 members (Mathematician, Empiricist, Skeptic, Engineer, Risk Manager) evaluate the findings
from their perspective. Each member must address the Open Questions from the Brief explicitly.
They can raise additional concerns, but the Open Questions are mandatory — not optional.

The richer Brief produces richer deliberation. The Council's role is unchanged: deliberation only,
never source quality evaluation.

**Interpreting the Chair's output:**
- **UNANIMOUS or STRONG_CONSENSUS** → proceed to Step 5
- **CONTESTED_RESOLVED** → proceed to Step 5, flag the resolution path in the entry
- **CONTESTED_UNRESOLVED** → trigger Recursive Reconvene (Step 4b)

---

## Step 4b: Recursive Reconvene (if contested)

Follow the Recursive Reconvene Protocol from the-council skill:

1. Extract the contested claims from the Chair's "Genuine Tension" section
2. Narrow the scope — reconvene ONLY on the contested points, not the whole topic
3. Each dissenting member provides: (a) their strongest evidence or math, (b) what specific data or proof would change their mind (falsification criteria)
4. Reconvene (max 3 total rounds)
5. After final round: Chair issues ruling with convergence level and confidence

**The key rule: narrow the aperture each round.** Round 1 might be "is pairs trading viable for
Canadian ETFs?" Round 2 becomes "does cointegration hold for VFV/XIC over rolling 3-year windows?"
Round 3 becomes "is the Engle-Granger test appropriate for this sample size or do we need Johansen?"

Each round must be more specific than the last. If it is not getting more specific, the
disagreement is genuinely unresolvable with available information — say so and document it.

---

## Step 5: Write to DEEPER_LEARNING.md

Once the Council has reached a conclusion (any convergence level), append a structured entry to
`D:\Quant_engine\docs\DEEPER_LEARNING.md`.

Use the template at `templates/deeper_learning_entry.md`. The expanded template includes three
new sections (Source Coverage, Replication Evidence, Practitioner Consensus) and an Evidence
Quality field in the header. See the template for the exact format.

**DEEPER_LEARNING.md rules (unchanged):**
1. Append-only. Never modify past entries. Supersede with new entries referencing the old.
2. Math must be Council-validated. No raw research findings go in directly.
3. Every entry links back to related entries, LEARNING.md items, and relevant modules.
4. Convergence level is always stated.
5. Implementation status is tracked: THEORETICAL / CANDIDATE / ACTIVE / REJECTED.

---

## Step 6: Post-Research Actions

1. **Summarize** — 2–3 sentences: what was learned, where it landed, what the evidence quality was
2. **Connect forward** — if this has implications for the Phase 3 roadmap or current signals, say so explicitly
3. **Suggest next research** — 1–2 natural follow-up questions the user might want to research next

---

## Quality Standards

**A good research session:**
- All 10 practitioner sites were checked (even if most return "no content found" — gaps are signal)
- Factor zoo papers explicitly checked (Hou et al, McLean & Pontiff, Harvey et al)
- At least one replication study found, or explicitly states "no independent replication found"
- DEEPER_LEARNING entry carries Source Coverage, Replication Evidence, and Practitioner Consensus
- Council Open Questions included at least one replication question and one Canadian ETF question
- Math was actually challenged and defended, not rubber-stamped
- Entry is self-contained — a future reader with no session context can understand it fully

**A bad research session:**
- Council rubber-stamps the first paper found (zombie consensus — sign the Brief was too thin)
- Practitioner sources skipped ("not relevant for this topic" is not valid — check and document gaps)
- Factor zoo check skipped
- Failure modes sourced only from the original authors
- Evidence Quality Rating left as "Strong" without documented basis

---

## Reference Files

- `templates/deeper_learning_entry.md` — exact template for DEEPER_LEARNING.md entries (expanded format)
- `the-council/SKILL.md` — Council framework (Config G and Recursive Reconvene Protocol)
````

- [ ] **Step 2: Verify key sections are present**

  Open `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\SKILL.md` and confirm all of these are present:
  - [ ] Frontmatter `name: quant-research` unchanged
  - [ ] Step 2 shows execution order (Academic + Practitioner simultaneous, Replication after Academic)
  - [ ] Academic Agent table has all 7 databases
  - [ ] Practitioner Agent table has all 10 sites with URLs
  - [ ] Replication Agent lists all 9 mandatory searches including the three factor zoo papers
  - [ ] Synthesis Agent output format includes the replication evidence table
  - [ ] Open Questions mandate replication question and Canadian ETF question
  - [ ] Quality Standards section retained

---

## Task 3: Rewrite deeper_learning_entry.md — Add Three New Sections

**Files:**
- Rewrite: `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\templates\deeper_learning_entry.md`

- [ ] **Step 1: Write the complete updated template**

  Write this exact content to `C:\Users\Arshnoor singh sidhu\.claude\skills\quant-research\templates\deeper_learning_entry.md`:

````markdown
# DEEPER_LEARNING.md Entry Template

Use this exact structure for every entry appended to `docs/DEEPER_LEARNING.md`.
Fields marked [REQUIRED] must always be filled. Fields marked [IF APPLICABLE] can be omitted.

---

```markdown
---

## DL-[NNN]: [Topic Title]

**Date:** [YYYY-MM-DD]
**Classification:** [NEW_ALGORITHM | ALGO_CHECK | CONCEPT_DEEP_DIVE | LITERATURE_SCAN | IMPLEMENTATION_EVAL]
**Status:** [THEORETICAL | CANDIDATE | ACTIVE | REJECTED]
**Council Convergence:** [UNANIMOUS | STRONG_CONSENSUS | CONTESTED_RESOLVED | CONTESTED_UNRESOLVED]
**Evidence Quality:** [Strong | Mixed | Weak | Insufficient]
**Relevant Phase:** [Phase N — component name]

### Source
[REQUIRED]
Canonical reference: [Author(s), Title, Year, DOI/URL if available]
Secondary sources: [Other references consulted]

### Mathematical Specification
[REQUIRED]
[Full mathematical formulation. All variables defined. This is the Council-validated version —
any modifications from the original source are noted with rationale.]

[Example format:]
Signal_i(t) = (P_i(t) - P_i(t-k)) / P_i(t-k)

Where:
- P_i(t) = adjusted close price of asset i at time t
- k = lookback period in trading days
- Signal output is rank-normalized to [-1, +1] cross-sectionally

### Intuition
[REQUIRED]
[2-4 sentences explaining WHY this works in plain language. Not the math — the economic or
statistical reasoning. A smart non-quant should understand this paragraph.]

### Assumptions
[REQUIRED]
[Numbered list of what this math assumes to be true about markets, data, or distributions.]

1. [Assumption 1]
2. [Assumption 2]

### Known Failure Modes
[REQUIRED]
[When and where this breaks down. Specific conditions, not vague hand-waving.
Distinguish: original-author-documented failure modes vs. independently-documented ones.]

- [Failure mode 1: condition → consequence] (Source: [original authors / independent: Author, Year])
- [Failure mode 2: condition → consequence] (Source: [original authors / independent: Author, Year])

### Source Coverage
[REQUIRED — filled by the research pipeline]
**Academic databases checked:** SSRN, arXiv q-fin, NBER, Google Scholar, Journal of Portfolio Management, Financial Analysts Journal, Journal of Finance
**Practitioner sites with content:** [list which of the 10 returned relevant content]
**Practitioner sites with no content:** [list which returned nothing — this is signal]
**Replication studies found:** [N total]
**Factor zoo check:**
  - Hou, Xue & Zhang (2017) "Replicating Anomalies": [appears / does not appear / not applicable]
  - McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?": [appears / does not appear]
  - Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns": [appears / does not appear]

### Replication Evidence
[REQUIRED — "No independent replication found" is a valid entry and must be stated explicitly]

| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| [Author, Year] | [market] | [dates] | Confirmed / Failed / Mixed |

**Overall replication status:** [Strong / Mixed / Weak / No independent evidence found]
**Notes:** [1–2 sentences on what the replication landscape looks like — or why evidence is absent]

### Practitioner Consensus
[REQUIRED — "No practitioner coverage found" is a valid entry and must be stated explicitly]
**Sources with content:** [list from the 10 verified sites]
**Summary:** [2–4 sentences — what the verified practitioner literature says about this factor/strategy]
**Divergence from academic consensus:** [any divergence, or "none identified"]

### Council Deliberation Summary
[REQUIRED]
[3-5 sentences capturing the key points of agreement and disagreement from the Council session.
Not a transcript — a distillation. The Council received the full Consolidated Research Brief
including replication evidence and practitioner consensus before deliberating.]

**Key Agreement:** [What the Council converged on]
**Key Tension:** [What was contested, and how it was resolved (or not)]

### Minority Report
[IF APPLICABLE — only if convergence was CONTESTED_RESOLVED or CONTESTED_UNRESOLVED]
[Which member dissented, their core argument, and their falsification criteria.]

**Member:** [Name]
**Position:** [Their argument in 2-3 sentences]
**Falsification:** [What evidence would change their mind]

### Quant Engine Integration
[REQUIRED]
**Module affected:** [src/signals/, src/portfolio/, src/backtest/, etc.]
**Dependencies:** [New libraries, data sources, or capabilities needed]
**Implementation complexity:** [Low / Medium / High — with one-line reason]
**Interaction with existing signals:** [How this relates to current momentum, vol_regime signals]

### Implementation Notes
[IF APPLICABLE — only if Status is CANDIDATE or ACTIVE]
[Pseudocode, parameter choices, or key implementation decisions. Should be enough for a
developer to start coding without re-reading the full research.]

### Cross-References
[REQUIRED]
- Related DEEPER_LEARNING entries: [DL-NNN, DL-NNN]
- Related LEARNING.md entries: [entry references if any]
- Supersedes: [DL-NNN if this updates a prior entry]

---
```

## DEEPER_LEARNING.md File Header

The file itself starts with this header (written once, on first creation — do not rewrite):

```markdown
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
```
````

- [ ] **Step 2: Verify the three new sections are present**

  Open the file and confirm all of these are present:
  - [ ] `**Evidence Quality:**` field in the header block (after `**Council Convergence:**`)
  - [ ] `### Source Coverage` section with academic databases list, practitioner sites with/without content fields, and factor zoo check for all three papers
  - [ ] `### Replication Evidence` section with the markdown table format and Overall replication status field
  - [ ] `### Practitioner Consensus` section with Sources with content, Summary, and Divergence fields
  - [ ] `### Known Failure Modes` updated to distinguish original-author-documented vs. independently-documented
  - [ ] `### Council Deliberation Summary` note that Council received the full Consolidated Research Brief
  - [ ] Existing sections (Source, Mathematical Specification, Intuition, Assumptions, Minority Report, Quant Engine Integration, Implementation Notes, Cross-References) all preserved unchanged

---

## Task 4: Spot-Check Against Design Spec

**Files:** Read-only verification — no changes

- [ ] **Step 1: Verify SKILL.md covers all spec requirements**

  Read `D:\Quant_engine\docs\superpowers\specs\2026-05-24-quant-research-upgrade-design.md` and
  check each requirement is addressed in the new SKILL.md:

  | Spec requirement | Covered by |
  |-----------------|------------|
  | Academic Agent hits all 7 databases | Step 2a table in SKILL.md |
  | Practitioner Agent hits all 10 sites | Step 2b table in SKILL.md |
  | Replication Agent receives Academic output as input | Step 2 execution order + 2c mission statement |
  | Replication Agent checks the 3 factor zoo papers | Step 2c mandatory searches 5–7 |
  | Synthesis Agent produces Consolidated Research Brief | Step 3 with full format |
  | Open Questions mandate replication + Canadian ETF questions | Step 3 format |
  | Council role unchanged — deliberation only | Step 4 |
  | DEEPER_LEARNING entry has Source Coverage section | Template Task 3 |
  | DEEPER_LEARNING entry has Replication Evidence table | Template Task 3 |
  | DEEPER_LEARNING entry has Practitioner Consensus section | Template Task 3 |
  | Evidence Quality field in entry header | Template Task 3 |
  | DEEPER_LEARNING_SEED.md deleted | Task 1 |

- [ ] **Step 2: Confirm no placeholder text remains**

  Grep both updated files for: `TBD`, `TODO`, `fill in`, `implement later`, `similar to`
  Expected: zero matches

- [ ] **Step 3: Confirm skill name is unchanged**

  Check SKILL.md frontmatter. `name: quant-research` must be present exactly.

---

## Self-Review Against Spec

**Spec coverage check:**
- Architecture (4 agents, execution order) → Task 2 SKILL.md Step 2
- All 7 academic databases → Task 2 Step 2a table
- All 10 practitioner sites with URLs → Task 2 Step 2b table
- 9 mandatory replication searches including 3 factor zoo papers → Task 2 Step 2c
- Synthesis Agent output format with replication table → Task 2 Step 3
- Mandatory Open Questions (replication + Canadian ETF) → Task 2 Step 3
- Council unchanged → Task 2 Step 4
- Evidence Quality field → Task 3 header block
- Source Coverage section → Task 3
- Replication Evidence section with table → Task 3
- Practitioner Consensus section → Task 3
- DEEPER_LEARNING_SEED.md deleted → Task 1
- No Python code changes → confirmed, not in plan

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" references. All file content is written in full.

**Consistency check:** The output formats in SKILL.md (Academic Agent produces `ACADEMIC RESEARCH FINDINGS`, Practitioner produces `PRACTITIONER RESEARCH FINDINGS`, Replication produces `REPLICATION & CRITICISM FINDINGS`) feed cleanly into the Synthesis Agent's Consolidated Research Brief format, which feeds into the Council, which produces the Council Deliberation Summary that goes into the expanded template. Chain is consistent end-to-end.
