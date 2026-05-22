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

4. **No LLM in the signal path**
   Models are deterministic: momentum, mean reversion, volatility regime, factor exposure, correlation breakdown. No GPT/Claude/any LLM in the trade decision loop. LLMs may be used for: code generation, doc writing, post-hoc analysis, dashboard prose. Never for signals.

5. **Capital-tier scaling**
   All modules read `capital_tier` from `config/portfolio.yaml`. Universe and constraints scale automatically at thresholds:
   - Tier 1 ($0–$10k): Canadian ETFs only, 6–9 tickers
   - Tier 2 ($10k–$25k): + Canadian dividend stocks (blue chips)
   - Tier 3 ($25k–$50k): + US-listed ETFs (FX cost worth it at scale)
   - Tier 4 ($50k+): + individual large-cap stocks, sector rotation

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
│   └── ARCHITECTURE.md
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

## What Claude Code Should Never Do

1. **Never recommend live trading without a backtest behind the signal.**
2. **Never inject any LLM call into the signal generation path.** Even for "natural language signals" — no.
3. **Never widen the asset universe past the current capital tier** without a config update.
4. **Never delete `LEARNING.md` entries.** Append-only. Corrections go as new entries.
5. **Never assume the operator has tested something.** If it isn't in `tests/`, it isn't tested.

---

## Current Phase

**Phase 3 P0 — Trade Recommendation Engine. Complete.**
**Dashboard + CLI redesign. Complete (2026-05-20).**
**Phase 3 P1 — Mean Reversion Signal. Complete (2026-05-22). Backtest: standalone not viable on 9-ETF universe (Sharpe −0.03, DD −24.2%, alpha −6.6%). Signal in codebase, not in recommendation engine.**
**Phase 3 P2 — Within-Bucket Optimizer (Ledoit-Wolf). Not started.**

### Phase 3 P0 decisions locked in CLAUDE.md:
- **Spread proxy**: Flat 0.05% universal for all ETFs. `spread_override` field in `universe.yaml` for per-ETF override (Tier 3+). Revisit when portfolio size makes 6bp differentials worth modeling.
- **Cost gate order**: Compute target weights first → diff holdings → gate each resulting trade. Gate is in dollar terms (delta × expected_return ≥ delta × cost_threshold).
- **BUY-only in P0**: No SELL recommendations until NAV is large enough that drift correction justifies a trade slot.
- **Combined signal**: `momentum × max(regime_score, 0)` for growth/dividend. Stable bucket uses equal weight (1/3 each) — regime does not gate bond allocation.
- **CRA discipline**: Hard MIN_HOLD gate (14 days). Max 24 trades/year from `trades` table. Warn at 20. Legal boundary holds until professional account justified (trigger: 24 trades hit OR NAV ≥ $5k).

For a full picture of what's built, what's tested, all architectural decisions, all bugs found, current signal readings, backtest results, and the Phase 3 roadmap — read:

**`docs/PROJECT_STATUS.md`** ← start here for any new session.

---

*Last updated: Phase 3 P1 (mean reversion signal + backtest) complete, 2026-05-22.*
