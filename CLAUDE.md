# CLAUDE.md — Quant Engine

> **For Claude Code working on this project.** Read this fully before any change. This is real money.

---

## Mission

Build a personal systematic investing engine that operates like a small quant fund — math-heavy, news-light, persistent. Generate signals daily, recommend trades only when expected edge clears cost thresholds, execute manually through Wealthsimple TFSA. The system informs decisions; the operator pulls the trigger.

**This is not a toy project. Every recommendation will move real capital.**

---

## Operator Profile

- **Name**: Arsh
- **Account**: Wealthsimple TFSA (no public trading API — manual execution only)
- **Starting capital**: ~$500–1000 CAD
- **Contributions**: $300–400/month (monthly cycle, even though paycheques are biweekly)
- **TFSA contribution room**: $35,000
- **Horizon**: 3–7 years
- **Drawdown ceiling**: 20% soft, monitored continuously
- **Benchmark**: VBAL (interim), VFV (S&P 500 CAD) as stretch goal
- **Communication style**: direct, blunt, no hedging, push back when math doesn't support the request

---

## Hard Constraints (Non-Negotiable)

1. **CRA day-trading rule on TFSA**
   The Canada Revenue Agency can reclassify TFSA gains as business income if trading frequency and intent indicate a business. System defaults to **monthly execution**. Intra-month trades require: (a) signal strength above strong threshold, (b) logged justification, (c) annual trade count stays well under day-trading territory.

2. **Asset universe lock**
   Canadian-listed ETFs only at current capital tier. No US-listed instruments (FX drag 1.5%). No individual stocks. No options. No leverage. No crypto.

3. **Cost-aware signals**
   No trade fires unless `expected_return ≥ 2 × bid_ask_spread + 0.5% profit_floor`. Every recommendation must justify it cleared this gate.

   **Exception — drift-triggered SELL.** A rebalancing trim that brings a bucket back inside its tolerance band is risk-control, not alpha-capture, so it is **not** gated on the profit-floor. It is gated on the `min_rebalance_trade` ($50) dollar floor + MIN_HOLD + CRA cap instead. Its `cost_estimate` still records the honest spread cost (`2 × spread`) for audit. Code: the drift branch in `generate_trade_cards` (`sell_reason="DRIFT"`). Ratified 2026-05-30 (v1.2.0, F5).

4. **No LLM in the signal path**
   Models are deterministic: momentum, mean reversion, volatility regime, factor exposure, correlation breakdown. No GPT/Claude/any LLM in the trade decision loop. LLMs may be used for: code generation, doc writing, post-hoc analysis, dashboard prose. Never for signals.

5. **Capital-tier scaling** (intended progression — Tier 1 enforced today)
   - Tier 1 ($0–$10k): Canadian ETFs only, 6–9 tickers
   - Tier 2 ($10k–$25k): + Canadian dividend stocks (blue chips)
   - Tier 3 ($25k–$50k): + US-listed ETFs (FX cost worth it at scale)
   - Tier 4 ($50k+): + individual large-cap stocks, sector rotation

   **What is actually enforced today (Tier 1):** the universe lock is enforced by `universe.yaml` membership + the universe check in `execute_command` — a trade on any ticker outside the configured universe is refused. `capital_tier` in `config/portfolio.yaml` is a **declared-but-inert** value: no module branches on it yet. Runtime tier-transition machinery (NAV ≥ $10k detection, automatic universe widening) is a **Tier 2 deliverable**, not built. The `region:` fields in `universe.yaml` are descriptive metadata, not enforced filters. Corrected 2026-05-30 (v1.2.0, F7) — the prior "all modules read capital_tier / scale automatically" claim overstated the implementation.

6. **Persistence**
   All state in SQLite at `data/quant.db`. Nothing lives in memory only. Every signal, trade recommendation, executed trade, rebalance, and metric snapshot logged with timestamp.

7. **Three-bucket guardrails** (Hybrid allocation policy)
   - Growth: 60% (±10%) — VFV, XIC, HXQ, XEF
   - Stable: 25% (±5%) — VAB, ZAG, HSAV
   - Dividend: 15% (±5%) — CDZ, VDY
   Optimizer optimizes *within* buckets; bucket weights themselves only shift on regime change signals.

8. **Test before merge**
   Every metric, every signal, every optimizer change ships with a unit test. Financial math bugs are silent killers.

---

## Architecture

```
quant_engine/
├── CLAUDE.md              ← you are here
├── LEARNING.md            ← rolling log: decisions, mistakes, concepts
├── README.md              ← setup + run instructions
├── requirements.txt
├── .gitignore
├── config/
│   ├── portfolio.yaml     ← buckets, tiers, constraints
│   └── universe.yaml      ← ETF universe with metadata
├── src/
│   ├── data/
│   │   ├── ingest.py      ← yfinance → SQLite, daily OHLCV
│   │   └── storage.py     ← SQLite schema + helpers
│   ├── portfolio/
│   │   ├── model.py       ← portfolio state, holdings, NAV
│   │   └── metrics.py     ← Sharpe, Sortino, max DD, beta, vol
│   ├── signals/           ← (Phase 2) momentum, MR, regime
│   └── cli/
│       └── main.py        ← typer entry point
├── tests/
├── docs/
│   ├── PHASE_1_ROADMAP.md
│   ├── ARCHITECTURE.md
│   └── DEEPER_LEARNING.md ← Council-validated quant knowledge base (append-only)
├── data/                  ← SQLite db, cached parquet (gitignored)
└── logs/                  ← daily run logs (gitignored)
```

---

## Coding Conventions

- **Python 3.11+**. Type hints on every function signature.
- **Pure functions** in `metrics.py` and `signals/`. Side effects isolated to `data/` and `cli/`.
- **No silent failures.** Every exception is logged with context. No bare `except:`.
- **Reproducibility**: seed every random number generator. Backtest results must be deterministic.
- **Docstrings on every public function** — what it does, args, returns, math reference if applicable.
- **No magic numbers.** All thresholds in `config/`.
- **Imports**: stdlib → third-party → local, separated by blank lines.

---

## Workflow Rules

- **Before adding a feature**: append a "Decision" entry to `LEARNING.md` with rationale.
- **After a bug or bad signal**: append a "Mistake & Correction" entry to `LEARNING.md`.
- **Every Friday** (or after major change): commit and tag.
- **Branch naming**: `phase-N/feature-name` for new work, `fix/short-description` for bugs.
- **When in doubt about a financial calculation**: cite the source (textbook, paper, Wikipedia equation) in the docstring.

---

## What Claude Code Should Do Proactively

1. When asked to add a metric, add it to `metrics.py`, write a unit test, log decision in `LEARNING.md`.
2. When asked to add a signal model, scaffold it under `src/signals/`, write a backtest in `tests/`, document the math.
3. When data fetching fails, log to `logs/`, retry with backoff, never silently return stale data.
4. When optimizer outputs violate constraints, raise — never quietly clip.
5. When asked to research a quant concept, signal, or algorithm — invoke the `quant-research` skill. It runs: classify → parallel 4-agent research (Academic Agent across 7 databases + Practitioner Agent across 10 verified sites fire in Wave 1; Replication/Criticism Agent runs 9 targeted searches + 3 mandatory factor zoo checks in Wave 2) → inline Synthesis → Council deliberation (Config G, 5 members) → recursive reconvene if contested → write validated entry to `docs/DEEPER_LEARNING.md`. Do not shortcut this pipeline with a bare web search. Every entry now carries Evidence Quality, Source Coverage, Replication Evidence table, and Practitioner Consensus sections.

## Research Knowledge Base

`docs/DEEPER_LEARNING.md` is the persistent, Council-validated knowledge base for this project. Rules:
- **Append-only.** Never modify past entries. Supersede with new entries that reference the old.
- **No entry without Council deliberation.** Raw research findings do not go in directly.
- **Every entry carries a convergence level**: UNANIMOUS / STRONG_CONSENSUS / CONTESTED_RESOLVED / CONTESTED_UNRESOLVED.
- **Entry IDs are sequential and never reused**: DL-001, DL-002, ...
- **Status lifecycle**: THEORETICAL → CANDIDATE → ACTIVE (or REJECTED)

## Structured Research Pipeline

`docs/research/` is the hypothesis lifecycle tracker. Separate from DEEPER_LEARNING.md (concept knowledge base) — this is where strategy ideas live from proposal through backtest to promotion or death.

**Master rules:** `docs/research/PIPELINE.md` — read this before proposing any new signal.
**Template:** `docs/research/TEMPLATE_HYPOTHESIS.md` — every hypothesis uses this structure.

Workflow: `PROPOSED → COUNCIL_REVIEWED → BACKTESTED → PROMOTED / KILLED / SHELVED`

Key rules:
- Every strategy idea — from papers, observations, or anomalies — enters as a hypothesis file in `hypotheses/`.
- No hypothesis skips Council review (`/quant-research` skill). No implementation before Council approval.
- No hypothesis touches the live codebase until all kill criteria are cleared by backtest.
- Killed hypotheses move to `graveyard/` with autopsy filled in. The graveyard is permanent and append-only.
- The watchlist (`watchlist/`) is passive background research for future tiers — zero interaction with live system.

**Current hypothesis count:** H001 (graveyard — mean reversion standalone, KILLED 2026-05-22) · H005 (graveyard — RSI(21) momentum filter, KILLED 2026-05-26) · H006 (SHELVED — volume spike regime indicator, re-evaluate Tier 2+)

## What Claude Code Should Never Do

1. **Never recommend live trading without a backtest behind the signal.**
2. **Never inject any LLM call into the signal generation path.** Even for "natural language signals" — no.
3. **Never widen the asset universe past the current capital tier** without a config update.
4. **Never delete `LEARNING.md` entries.** Append-only. Corrections go as new entries.
5. **Never assume the operator has tested something.** If it isn't in `tests/`, it isn't tested.
6. **Never write to `docs/DEEPER_LEARNING.md` without Council deliberation.** The `quant-research` skill enforces this — use it.

---

## Current Phase

**Phase 3 P0 — Trade Recommendation Engine. Complete.**
**Dashboard + CLI redesign. Complete (2026-05-20).**
**Phase 3 P1 — Mean Reversion Signal. Complete (2026-05-22). Backtest: standalone not viable on 9-ETF universe (Sharpe −0.03, DD −24.2%, alpha −6.6%). Signal in codebase, not in recommendation engine.**
**Phase 3 P2 — Within-Bucket Optimizer (Ledoit-Wolf). Complete (2026-05-23). `quant recommend --optimize` flag. 31 new tests. 109/109 passing.**
**quant-research skill upgrade (2026-05-24). 4-agent parallel pipeline (Academic + Practitioner + Replication/Criticism + inline Synthesis). Expanded DEEPER_LEARNING entry template with Evidence Quality, Source Coverage, Replication Evidence, Practitioner Consensus sections.**
**Phase 3 P3.3 — Signal Persistence. Complete (2026-05-26). `signal_scores` table. `persist_signals()` + `query_signal_history()` in `storage.py`. `quant signals --save`, `quant recommend --save` write signal evidence before trade cards. `quant signal-history` command. 9 new tests. v0.3.0-signal-persistence.**
**Phase 3 SELL / Rebalance Logic. Complete (2026-05-26). Signal-driven full exit + drift-triggered partial trim. `sell_reason` field on `TradeCard` and `recommendations` table. `migrate_recommendations_v3()` schema migration. 16 new tests.**
**H005 — RSI(21) > 50 momentum filter (2026-05-26). KILLED. Backtest confirmed mathematical near-redundancy: 96.2% agreement with momentum (9-ETF), t=NaN incremental alpha. Divergence analysis: gate suppressed +7.30% forward-return signals. All 3 kill criteria triggered. DL-012. Autopsy: `docs/research/graveyard/H005_rsi_momentum_filter.md`.**
**H006 — Volume spike as regime indicator (2026-05-26). SHELVED. Council: STRONG_CONSENSUS. Three ETF failure modes: creation/redemption noise contamination, absent visibility mechanism, Baker & Stein direction inversion at portfolio-aggregate level. 93% factor zoo failure rate for liquidity signals. Re-evaluate at Tier 2+ with individual equities. DL-013.**
**Phase 3 P3.5 — ntfy.sh Phone Alerts. Complete (2026-05-27). Three triggers: NEW_RECOMMENDATION, REGIME_CHANGE, DRAWDOWN (>15% threshold, state machine prevents spam). `alerts_log` table. `--notify` flag on `quant recommend`. `quant alert-test` command. 14 tests. v0.4.0-alerts.**
**Phase 3 P3.6 — Scheduled Daily Run. Complete (2026-05-28). `DailyRunner` class in `src/cli/daily_run_command.py`. `quant daily-run` command. Windows Task Scheduler scripts: `scripts/daily_run.py`, `scripts/daily_run.bat`, `scripts/setup_scheduler.ps1`. 9 tests. v0.5.0-daily-run.**
**Phase 3 P3.7 — Test Coverage Closure. Complete (2026-05-28). `BacktestResult.summary_str()` added to `engine.py`. `tests/test_backtest.py` (8 tests). `tests/test_integration.py` (10 tests). Alert first-run gap tests added to `test_alerts.py`. 204/204 passing. v0.6.0-test-coverage.**
**H004 — Volatility targeting / Moreira-Muir scaling (2026-05-28). KILLED. 2 of 6 kill criteria triggered: (1) leverage effect absent — all 7 equity ETFs show positive Corr(fwd_ret, RV) on 2021-2026 data, invalidating Moreira-Muir's mathematical precondition; (2) monthly return correlation with equal-weight baseline = 0.9862, near-zero portfolio differentiation. Graveyard: `docs/research/graveyard/H004_vol_targeting.md`. Research script: `docs/research/scratch/H004_vol_targeting_backtest.py`.**

**Current hypothesis count:** H001 (graveyard — mean reversion standalone, KILLED 2026-05-22) · H004 (graveyard — vol targeting / Moreira-Muir, KILLED 2026-05-28) · H005 (graveyard — RSI(21) momentum filter, KILLED 2026-05-26) · H006 (SHELVED — volume spike regime indicator, re-evaluate Tier 2+)

**Tier 1 Complete. v1.0.0-tier1 tagged (2026-05-28). All Phase 3 subsystems shipped and tested. System is production-ready: daily auto-run, full BUY/SELL/rebalance pipeline, within-bucket optimizer, full persistence, phone alerts, Council-validated hypothesis pipeline, 204/204 tests. Next milestone trigger: NAV ≥ $10,000 CAD (Tier 2).**

### Phase 3 P0 decisions locked in CLAUDE.md:
- **Spread proxy**: Flat 0.05% universal for all ETFs. `spread_override` field in `universe.yaml` for per-ETF override (Tier 3+). Revisit when portfolio size makes 6bp differentials worth modeling.
- **Cost gate order**: Compute target weights first → diff holdings → gate each resulting trade. Gate is in dollar terms (delta × expected_return ≥ delta × cost_threshold).
- **BUY-only in P0**: No SELL recommendations until NAV is large enough that drift correction justifies a trade slot.
- **Combined signal**: `momentum × max(regime_score, 0)` for growth/dividend. Stable bucket uses equal weight (1/n_stable each) — regime does not gate bond allocation.
- **CRA discipline**: Hard MIN_HOLD gate (14 days). Max 24 trades/year from `trades` table. Warn at 20. Legal boundary holds until professional account justified (trigger: 24 trades hit OR NAV ≥ $5k).
- **Universe swap (2026-05-22)**: ZAG.TO removed (redundant with VAB.TO, 0.97 corr), CHPS.TO added to growth bucket (Global X AI Semiconductor, TSX-listed, 1234d history, MER 0.65%). `STABLE_TICKERS` is now `{VAB.TO, HSAV.TO}`. Rejected candidates this session: CIAI.TO, INAI.TO (HXQ.TO overlap), MTRX.TO/AIQ.TO/ARTI.TO (insufficient history). TEC.TO deferred.

For a full picture of what's built, what's tested, all architectural decisions, all bugs found, current signal readings, backtest results, and the Phase 3 roadmap — read:

**`docs/PROJECT_STATUS.md`** ← start here for any new session.

---

*Last updated: 2026-05-28. v1.0.0-tier1 — Tier 1 complete. All Phase 3 subsystems (P3.3 signal persistence, SELL/rebalance, P3.5 alerts, P3.6 daily run, P3.7 test coverage) shipped. H004 (vol targeting) + H005 (RSI filter) KILLED. H006 SHELVED. 204/204 tests passing.*
