# Quant Research Skill Upgrade — Design Spec
**Date:** 2026-05-24
**Topic:** Deep multi-source research pipeline for quant-research skill
**Status:** Approved — proceed to implementation plan

---

## Problem Statement

The current `quant-research` skill produces Research Briefs sourced from 1–3 generic web searches. The result is one canonical paper deep — sufficient to identify what a strategy is, insufficient to verify:

1. Whether it **replicates out-of-sample** (international evidence, post-publication performance)
2. Whether **major quant practitioners** (AQR, Man Institute, etc.) have independently published on it
3. Whether **failure modes are independently documented** beyond the original authors

DL-003 (52-week high momentum) is the clearest example: canonical source identified (George & Hwang 2004), but no secondary citations, no AQR replication, no independent critique literature.

---

## Design Goals

- Every research session verifies all three dimensions above before the Council sees the Brief
- Sources are verified/curated — no open-ended "hedge fund commentary" searches that return noise
- Research runs in parallel across source domains — context isolation per agent, quality over speed
- DEEPER_LEARNING entries expand to carry the richer evidence structure
- Council role unchanged — deliberation only, never source evaluation

---

## Architecture

### Pipeline Overview

```
Step 1:  Classify request (unchanged — same 5 types)
Step 2:  Fire Academic Agent + Practitioner Agent simultaneously
Step 2b: Fire Replication Agent (takes Academic Agent output as input — targeted)
Step 3:  Synthesis Agent reads all 3 findings packages → Consolidated Research Brief
Step 4:  Council Deliberation — Config G, 5 members (unchanged)
Step 4b: Recursive Reconvene if contested (unchanged)
Step 5:  Write to DEEPER_LEARNING.md (expanded format)
Step 6:  Post-Research Actions (unchanged)
```

### Agent Execution Order

- **Academic Agent** fires first (solo)
- **Practitioner Agent** fires simultaneously with Academic Agent
- **Replication Agent** fires after Academic Agent finishes — it receives the Academic Agent's canonical source list and hunts specifically for papers that challenged, replicated, or failed to replicate those exact claims
- **Synthesis Agent** fires after all three finish

The Practitioner Agent and Replication Agent overlap in time. Total wall-clock time is: `max(Academic, Practitioner) + Replication + Synthesis` rather than the sum of all four.

---

## Sub-Agent Specifications

### Academic Agent

**Mission:** Find the canonical and secondary academic literature. Extract verified math. Do not evaluate — just retrieve and structure.

**Sources to hit (in order):**
1. SSRN — full-text search for the topic
2. arXiv q-fin section — search for the topic
3. NBER working papers — search for the topic
4. Google Scholar — search for citation counts, confirm canonical source, find related papers
5. Journal of Portfolio Management — search for the topic
6. Financial Analysts Journal (CFA Institute) — search for the topic
7. Journal of Finance — search abstracts for the topic

**Output format (structured findings package):**
```
ACADEMIC RESEARCH FINDINGS
Topic: [name]
Sources checked: [list]

CANONICAL SOURCE(S):
  Author, Year, Title, Journal
  Core findings: [2–3 sentences]
  Mathematical specification: [key equations, all variables defined]
  Sample: [geography, time period, asset class tested on]

SECONDARY SOURCES:
  [Author, Year] — [1-line finding]
  [Author, Year] — [1-line finding]
  ...

REPLICATION PAPERS (found in academic literature):
  [Author, Year, geography, result: confirmed/failed/mixed]
  ...

MATHEMATICAL GAPS:
  [What the academic literature does not specify — free parameters, implementation choices]

SOURCE GAPS:
  [Which databases returned no results for this topic]
```

---

### Practitioner Agent

**Mission:** Find what verified quant practitioners have independently published on this strategy. Extract practitioner consensus and any divergence from academic findings.

**Verified source list (hit all that have content):**

| Source | URL | Why verified |
|--------|-----|-------------|
| AQR Capital Research | aqr.com/insights/research | Academic-quality, Cliff Asness, peer-reviewed internally |
| Man Institute | man.com/maninstitute | Publishes in academic journals, top-tier |
| Verdad Capital Research | verdadcap.com/research | Chris Schindler, rigorous quant |
| Alpha Architect | alphaarchitect.com/blog | Wes Gray PhD, systematically replicates academic papers |
| Research Affiliates | researchaffiliates.com/publications | Rob Arnott, canonical factor research |
| Flirting with Models / Newfound Research | flirtingwithmodels.com | Corey Hoffstein, rigorous quant practitioner |
| Robeco Insights | robeco.com/en/insights | Academic-quality European quant |
| NAAIM Research | naaim.org/research | Dow Award / NAAIM Award papers (source of Giordano MVCT) |
| Vanguard Research | advisors.vanguard.com/insights/research | ETF/index specific, directly relevant to our universe |
| Bank of Canada Working Papers | bankofcanada.ca/publications | Canadian market mechanics, relevant to our ETF universe |

**Output format (structured findings package):**
```
PRACTITIONER RESEARCH FINDINGS
Topic: [name]
Sources checked: [all 10 listed above]

FINDINGS BY SOURCE:
  AQR: [key insight or "no content found"]
  Man Institute: [key insight or "no content found"]
  Verdad: [key insight or "no content found"]
  Alpha Architect: [key insight or "no content found"]
  Research Affiliates: [key insight or "no content found"]
  Flirting with Models: [key insight or "no content found"]
  Robeco: [key insight or "no content found"]
  NAAIM: [key insight or "no content found"]
  Vanguard: [key insight or "no content found"]
  Bank of Canada: [key insight or "no content found"]

PRACTITIONER CONSENSUS:
  [Where ≥3 sources agree — state the claim and which sources agree]

DIVERGENCE FROM ACADEMIC CONSENSUS:
  [Where practitioners say something different from the papers — state the divergence clearly]

SOURCE GAPS:
  [Which sites had no content — important signal that practitioners have not engaged with this]
```

---

### Replication/Criticism Agent

**Mission:** Hunt specifically for independent evidence that either confirms or challenges the canonical claims from the Academic Agent. Targeted — not a general literature search.

**Inputs received:** Academic Agent's canonical source list (author, year, title, core claims)

**Search strategy (run all of these):**
1. `"[factor/strategy name]" replication out-of-sample [geography variants]`
2. `"[factor/strategy name]" fails [market/period]`
3. `"[factor/strategy name]" data mining p-hacking`
4. `"[factor/strategy name]" international evidence`
5. Explicit check: Hou, Xue & Zhang (2017) "Replicating Anomalies" — does this factor appear?
6. Explicit check: McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?" — does this factor appear?
7. Explicit check: Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns" (factor zoo paper) — does this factor appear?
8. Alpha Architect replication series — search for their coverage of this factor
9. Targeted search for critiques of specific claims from the Academic Agent

**Output format (structured findings package):**
```
REPLICATION & CRITICISM FINDINGS
Topic: [name]
Targeting claims from: [Academic Agent canonical source(s)]

OUT-OF-SAMPLE REPLICATION EVIDENCE:
  [Author, Year] — Geography: [x], Period: [x], Result: [confirmed/failed/mixed], Notes: [1 sentence]
  ...

FACTOR ZOO / DATA MINING FLAGS:
  Hou et al (2017): [appears / does not appear / not tested]
  McLean & Pontiff (2016): [appears / does not appear / post-publication decay documented?]
  Harvey et al (2016): [appears / does not appear / t-statistic threshold met?]

INDEPENDENT FAILURE MODE DOCUMENTATION:
  [Failure modes documented by authors other than the original paper]
  [Each entry: who documented it, what the failure mode is, under what conditions]

CRITIQUES OF SPECIFIC CLAIMS:
  [Any paper or source that directly challenges a claim from the Academic Agent's canonical source]

REPLICATION SUMMARY:
  Overall replication status: [Strong / Mixed / Weak / No independent evidence found]
  Confidence basis: [1–2 sentences]
```

---

## Synthesis Agent

**Mission:** Read all three structured findings packages. Produce one Consolidated Research Brief. Do not add new research — only integrate what the three agents found. Flag convergence and divergence explicitly.

**Output format — Consolidated Research Brief:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 CONSOLIDATED RESEARCH BRIEF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic: [name]
Classification: [type]
Source coverage: Academic ([N] papers), Practitioner ([N]/10 sites with content), Replication ([N] studies)

MATHEMATICAL SPECIFICATION:
  [From Academic Agent — the validated version]

ASSUMPTIONS:
  [Consolidated from all three agents — attributed by source]

REPLICATION EVIDENCE:
  [From Replication Agent — table format: Study / Geography / Period / Result]

PRACTITIONER CONSENSUS:
  [From Practitioner Agent — what the verified sites say, with attribution]

FAILURE MODES:
  [Consolidated from all three — each failure mode attributed to its source]
  [Distinguishes: original-author-documented vs. independently-documented]

CONVERGENCE SUMMARY:
  All three source domains agree on: [...]
  Academic and Practitioner agree but Replication is weak: [...]
  Disputed or absent: [...]

EVIDENCE QUALITY RATING:
  [Strong / Mixed / Weak / Insufficient]
  Basis: [2–3 sentences explaining the rating]

OPEN QUESTIONS FOR COUNCIL:
  [3–5 specific questions — now informed by all three source domains]
  [At least one question must address replication strength]
  [At least one question must address Canadian ETF applicability specifically]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Council Interaction (Config G — Unchanged Role, Richer Input)

The five Council members (Mathematician, Empiricist, Skeptic, Engineer, Risk Manager) receive the Consolidated Research Brief. Their roles are unchanged — they deliberate, they do not evaluate source quality. The richer brief produces richer deliberation naturally.

**One addition:** The Open Questions in the Brief now mandate at least one replication question and one Canadian ETF applicability question. The Council must address all Open Questions explicitly (already required by the skill — this just tightens what the questions must cover).

The Recursive Reconvene Protocol is unchanged.

---

## Expanded DEEPER_LEARNING.md Entry Format

Two new sections added to every entry. Existing sections unchanged.

**New section: Source Coverage**
```
### Source Coverage
**Academic databases checked:** SSRN, arXiv, NBER, Google Scholar, JPM, FAJ, JF
**Practitioner sites with content:** [list which of the 10 had relevant content]
**Replication studies found:** [N]
**Factor zoo check:** Hou et al / McLean & Pontiff / Harvey et al — [appears / does not appear / N/A]
```

**New section: Replication Evidence** (replaces the current single-paragraph failure modes section — failure modes stay, replication becomes its own section)
```
### Replication Evidence
| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| [Author, Year] | [market] | [dates] | Confirmed / Failed / Mixed |
...

**Overall replication status:** [Strong / Mixed / Weak / No independent evidence]
```

**New section: Practitioner Consensus**
```
### Practitioner Consensus
**Sources with content:** [list]
**Summary:** [2–4 sentences — what the verified practitioner literature says]
**Divergence from academic consensus:** [any, or "none identified"]
```

**Evidence Quality Rating** added to the header block (alongside Status and Council Convergence):
```
**Evidence Quality:** Strong / Mixed / Weak / Insufficient
```

---

## Files to Change

| File | Change |
|------|--------|
| `~/.claude/skills/quant-research/SKILL.md` | Full rewrite — new pipeline, agent specs, output formats |
| `~/.claude/skills/quant-research/templates/deeper_learning_entry.md` | Add 3 new sections |

No changes to `the-council/SKILL.md` — Council is unchanged.
No changes to `DEEPER_LEARNING.md` itself — new format applies to future entries only.

---

## What This Does NOT Change

- Classification step (Step 1) — same 5 types
- Council Config G — same 5 members, same roles, same Recursive Reconvene Protocol
- DEEPER_LEARNING.md append-only rule
- Entry ID sequence (DL-001, DL-002, ...)
- Status lifecycle (THEORETICAL → CANDIDATE → ACTIVE / REJECTED)
- Convergence levels (UNANIMOUS / STRONG_CONSENSUS / CONTESTED_RESOLVED / CONTESTED_UNRESOLVED)
- The research pipeline (PIPELINE.md) — hypothesis lifecycle is separate from the knowledge base

---

## Success Criteria

A research session succeeds under this design if:
- All 10 practitioner sites were checked (even if most return "no content found")
- Replication evidence section has at least one entry (or explicitly states "no independent replication found")
- Factor zoo papers were explicitly checked
- DEEPER_LEARNING entry carries Source Coverage, Replication Evidence, and Practitioner Consensus sections
- Council Open Questions include at least one replication question and one Canadian ETF question
