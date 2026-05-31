# PROJECT STATUS — Quant Engine
> **Fresh-session onboarding doc.** Read this + CLAUDE.md before touching anything.
> Last updated: 2026-05-30 (v1.2.0-guardrails — Tier 1 code-review cleanup, all 22 findings closed, 234 tests passing). Prior: v1.0.0-tier1 (2026-05-28).

---

## What This System Is

A personal systematic investing engine for Arsh's Wealthsimple TFSA. Math-driven, news-free, persistent. It generates momentum and volatility regime signals daily, validates them against walk-forward backtests, and surfaces BUY/SELL/rebalance trade recommendations. Arsh pulls the trigger manually in Wealthsimple — the system never executes.

**Capital**: ~$500–1000 CAD starting, $300–400/month contributions. 3–7 year horizon. 20% soft drawdown ceiling. Benchmark: VBAL (interim), VFV (stretch).

---

## Repository

- **GitHub**: `https://github.com/arshnoor51103-dev/Quant_engine`
- **Branch**: `main`
- **Git initialized**: 2026-05-19
- **Python**: 3.11+ (running on 3.14.3 locally)
- **Venv**: `.venv/` at project root (not committed)

---

## Current State: v1.0.0 — Tier 1 Complete

| Phase | Status | Tag | What It Delivers |
|-------|--------|-----|-----------------|
| Phase 1 — Foundation | ✅ Complete | — | Data pipeline, portfolio model, risk metrics, CLI |
| Phase 2 — Signal Engine | ✅ Complete | — | Momentum + vol regime signals, walk-forward backtester, FastAPI dashboard |
| Phase 3 P0 — Recommendations | ✅ Complete | — | Signal-proportional weights, trade cards, cost/CRA/min-hold gates, execute workflow |
| Phase 3 P1 — Mean Reversion | ✅ Complete | — | Regime-conditional MR signal + backtest validation (not viable standalone on 9-ETF universe) |
| Phase 3 P2 — Optimizer | ✅ Complete (2026-05-23) | — | Ledoit-Wolf covariance, Markowitz within-bucket optimizer, `--optimize` flag |
| Phase 3 P3.3 — Signal Persistence | ✅ Complete (2026-05-26) | v0.3.0-signal-persistence | `signal_scores` table, `persist_signals()`, `query_signal_history()`, `quant signal-history` |
| Phase 3 SELL / Rebalance | ✅ Complete (2026-05-26) | — | Signal-driven full exit + drift-triggered partial trim, `sell_reason` field, schema migration |
| Phase 3 P3.5 — Phone Alerts | ✅ Complete (2026-05-27) | v0.4.0-alerts | ntfy.sh, 3 triggers, DRAWDOWN state machine, `alerts_log` table, `quant alert-test` |
| Phase 3 P3.6 — Scheduled Daily Run | ✅ Complete (2026-05-28) | v0.5.0-daily-run | DailyRunner class, `quant daily-run`, Task Scheduler scripts |
| Phase 3 P3.7 — Test Coverage | ✅ Complete (2026-05-28) | v0.6.0-test-coverage | `BacktestResult.summary_str()`, test_backtest.py, test_integration.py, 204/204 |
| Research Pipeline | ✅ Integrated | — | quant-research skill + Council Config G + `docs/DEEPER_LEARNING.md` |
| Research Pipeline (Structured) | ✅ Structured (2026-05-23) | — | `docs/research/` — hypothesis lifecycle tracker, kill criteria, graveyard, watchlist |
| Hypothesis Queue | ✅ Cleared | v0.7.0-hypothesis-cleanup | H004 KILLED (Moreira-Muir), H005 KILLED (RSI redundancy), H006 SHELVED (ETF incompatibility) |
| **Tier 1** | **✅ Production-ready** | **v1.0.0-tier1** | **All subsystems shipped. Daily auto-run live. 204/204 tests.** |
| v1.2.0 — Guardrails Cleanup | ✅ Complete (2026-05-30) | v1.2.0-guardrails | 22 Tier-1 review findings closed: CRA hard-block (F1), drawdown soft-halt (F2), fail-loud fetch/signals (F3/F4), drift-SELL exemption ratified (F5), ticker_metadata allow-list (F6/F10/F20), STABLE_TICKERS single-source (F14), schema_version migration runner (F15), DB-backed E2E test (F13). 234 tests. |

---

## v1.2.0 Guardrails — what changed for the operator

- **Execution is now hard-blocked at the CRA 24-trade/year cap.** `quant execute` refuses trade #25; the only way past is `--force --justification "reason"`, which is logged to `run_log`. This is a legal boundary on a TFSA, not a soft warning.
- **New BUYs are soft-halted at the 20% drawdown ceiling.** When the portfolio is at/below the ceiling, `quant recommend` converts BUY cards to SKIP (`DRAWDOWN_HALT`) and prints a RISK HALT banner; SELL/rebalance still flow. Toggle: `risk.drawdown_halt_enabled` in `portfolio.yaml`.
- **`quant fetch` and `quant signals` now fail loud** (non-zero exit) instead of silently producing partial data — fetch retries with backoff first.
- **Capital-tier reality check (F7):** `capital_tier` is declared-but-inert today. Tier 1 is enforced by the `universe.yaml` lock + `execute_command`'s universe check. Automatic tier-switching (NAV ≥ $10k → widen universe) is a **Tier 2 deliverable, not built**. See CLAUDE.md Hard Constraint 5.
- **Test claim correction (F13):** the end-to-end pipeline is now covered by a real DB-backed round-trip test (`TestEndToEndDB` in `test_integration.py`: seed prices → save recommendation → record trade → mark executed → assert persistence), not only the in-memory pure-function pipeline test.

---

## File Structure

```
quant_engine/
├── CLAUDE.md                        ← hard constraints + coding conventions (READ FIRST)
├── LEARNING.md                      ← append-only log: decisions, bugs, concepts
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   ├── PROJECT_STATUS.md            ← this file
│   ├── PHASE_1_ROADMAP.md
│   ├── ARCHITECTURE.md
│   ├── DEEPER_LEARNING.md           ← Council-validated quant knowledge base (append-only, DL-001–DL-014)
│   └── research/
│       ├── PIPELINE.md              ← master hypothesis lifecycle rules
│       ├── TEMPLATE_HYPOTHESIS.md
│       ├── hypotheses/              ← active/killed hypothesis files (H001–H006)
│       ├── graveyard/               ← H001, H004, H005 autopsy files (permanent, append-only)
│       ├── watchlist/               ← passive background research (H006, ai_semiconductor, canadian_energy)
│       ├── findings/                ← promoted signals (empty — none promoted yet)
│       └── scratch/                 ← research scripts (H004_vol_targeting_backtest.py)
├── config/
│   ├── portfolio.yaml               ← buckets, tiers, risk config, trade thresholds, optimizer block, rebalance block
│   └── universe.yaml                ← 9 ETF definitions with metadata + spread_override hook
├── src/
│   ├── data/
│   │   ├── ingest.py                ← yfinance → SQLite, incremental OHLCV pull
│   │   └── storage.py               ← SQLite schema + helpers; recommendations CRUD, signal persistence, alerts log
│   ├── portfolio/
│   │   ├── model.py                 ← holdings, NAV, bucket allocation, price_series
│   │   ├── metrics.py               ← Sharpe, Sortino, Calmar, max DD, beta, alpha, rolling
│   │   ├── recommendations.py       ← combined signals, target weights, BUY/SELL/drift trade cards
│   │   └── optimizer.py             ← BucketOptimizer: Ledoit-Wolf covariance + SLSQP within-bucket weights
│   ├── signals/
│   │   ├── base.py                  ← Signal ABC + SignalResult dataclass
│   │   ├── momentum.py              ← 12-1 month momentum (Jegadeesh-Titman 1993)
│   │   ├── vol_regime.py            ← realized vol percentile → regime classification
│   │   ├── mean_reversion.py        ← regime-conditional z-score MR (not wired into recommendation engine)
│   │   └── rsi.py                   ← RSI(21) signal (H005 graveyard artifact; not in signal path)
│   ├── backtest/
│   │   └── engine.py                ← walk-forward backtester, BacktestConfig, BacktestResult, summary_str()
│   ├── api/
│   │   └── server.py                ← FastAPI server, 5 REST endpoints + HTML dashboard
│   ├── alerts/
│   │   └── ntfy.py                  ← ntfy.sh HTTP transport, fire-and-forget, never raises
│   ├── dashboard/
│   │   ├── styles.py                ← Streamlit CSS + layout constants
│   │   ├── data.py                  ← data-loading helpers for dashboard
│   │   └── components.py            ← reusable Streamlit component functions
│   └── cli/
│       ├── main.py                  ← typer app, all commands registered
│       ├── phase2_commands.py       ← signals, backtest, dashboard commands
│       ├── phase3_commands.py       ← recommend, execute, pending, skip, alert-test commands
│       └── daily_run_command.py     ← DailyRunner class + quant daily-run command
├── scripts/
│   ├── daily_run.py                 ← Task Scheduler entry point; writes dated log to logs/
│   ├── daily_run.bat                ← .bat wrapper for Task Scheduler (activates venv, runs daily_run.py)
│   └── setup_scheduler.ps1          ← registers daily_run.bat as a Windows Task Scheduler task
├── tests/
│   ├── test_metrics.py              ← 11 tests — portfolio/metrics.py
│   ├── test_signals.py              ← 11 tests — MomentumSignal, ShortTermMomentum, VolRegimeSignal, edge cases
│   ├── test_recommendations.py      ← 21 tests — combined signals, target weights, all gate types, cold-start math
│   ├── test_mean_reversion.py       ← 16 tests — MeanReversionSignal shape, bounds, sign convention, warmup
│   ├── test_optimizer.py            ← 31 tests — BucketOptimizer constraints, LW PD check, 2-ticker, fallbacks
│   ├── test_storage.py              ← 23 tests — SQLite schema, CRUD, VWAP, trade count, min-hold, alerts log
│   ├── test_sell_logic.py           ← 16 tests — signal-SELL gate, drift-SELL gate, sell_reason, partial vs full exit
│   ├── test_signal_persistence.py   ←  9 tests — ticker_metadata(), persist_signals(), query_signal_history()
│   ├── test_alerts.py               ← 14 tests — ntfy transport, 3 alert triggers, DRAWDOWN state machine, first-run
│   ├── test_daily_run.py            ←  9 tests — DailyRunner steps, timeout-as-failure, cash flag, log branching
│   ├── test_rsi_signal.py           ← 24 tests — RSI math, Wilder SMMA, gate logic, metadata, edge cases
│   ├── test_H005_rsi_backtest.py    ←  1 test  — H005 backtest regression (graveyard artifact)
│   ├── test_backtest.py             ←  8 tests — avg_holdings > 0, summary_str(), metrics keys, ValueError
│   └── test_integration.py          ← 10 tests — full pipeline: signal layer → backtest layer → recommend layer
└── data/                            ← SQLite db + parquet cache (gitignored)
```

---

## CLI Commands

Run from project root with: `python -m src.cli.main <command>`
Or if installed as `quant`: `quant <command>`

**Windows note**: Set `$env:PYTHONUTF8 = "1"` before running CLI commands or Unicode bar characters crash the console:
```powershell
$env:PYTHONUTF8 = "1"; python -m src.cli.main signals --signal-type momentum
```

### Phase 1 Commands
| Command | What it does |
|---------|-------------|
| `quant init` | Create SQLite schema at `data/quant.db` |
| `quant fetch [--years N] [--full]` | Pull OHLCV for all 9 tickers via yfinance. Default 20yr. Incremental by default. |
| `quant universe` | Print the 9-ETF universe with bucket, MER, region |
| `quant status` | Portfolio NAV, holdings table, bucket drift vs targets |
| `quant metrics [--ticker X] [--lookback N]` | Risk/return metrics. Default lookback 1260 days (5yr). |
| `quant trade TICKER SIDE UNITS PRICE` | Record a manually executed trade, update holdings |

### Phase 2 Commands
| Command | What it does |
|---------|-------------|
| `quant signals --signal-type [momentum\|momentum_short\|vol_regime\|mean_reversion] [--save]` | Generate signal scores. `--save` persists to `signal_scores` table with a `run_id`. |
| `quant signal-history TICKER [--records N] [--signal-type TYPE]` | Show persisted signal score history. Pivoted table: date, scores, regime, raw return. Default last 12 records. |
| `quant backtest --signal-type X --years N --top-n N` | Walk-forward backtest. Default: momentum, 5yr, top-4. Prints metrics + `summary_str()` vs VFV benchmark. |
| `quant dashboard [--port N]` | Launch FastAPI server at localhost:8501. Serves `/api/universe`, `/api/metrics`, `/api/signals`, `/api/status` + HTML dashboard. |

### Phase 3 Commands
| Command | What it does |
|---------|-------------|
| `quant recommend [--cash N] [--save] [--optimize] [--notify]` | Full recommendation pipeline. `--optimize`: Ledoit-Wolf Markowitz weights. `--save`: persists signals + trade cards. `--notify`: fires ntfy.sh alerts on BUY/SELL, regime change, drawdown. |
| `quant execute <ID> --price X --units Y [--date YYYY-MM-DD]` | Mark recommendation as executed. Atomically updates rec status + creates trade record. |
| `quant pending` | List all pending recommendations with rec IDs. |
| `quant skip <ID>` | Mark a pending recommendation as skipped. |
| `quant alert-test` | Fire a test ntfy.sh notification to verify the alert pipeline is wired. |
| `quant daily-run [--cash N]` | Run the full daily pipeline interactively (fetch → momentum → vol_regime → recommend --optimize --save --notify). Stdout only — use `scripts/daily_run.py` for scheduled runs with file logging. |

---

## Asset Universe (Tier 1)

| Ticker | Name | Bucket | Asset Class | MER | Notes |
|--------|------|--------|-------------|-----|-------|
| VFV.TO | Vanguard S&P 500 Index ETF | Growth | Equity (US) | 0.09% | Core US large-cap, unhedged |
| XIC.TO | iShares S&P/TSX Capped Composite | Growth | Equity (CA) | 0.06% | TSX broad market |
| HXQ.TO | Horizons NASDAQ-100 ETF | Growth | Equity (US) | 0.28% | Swap structure, tax-efficient in TFSA |
| XEF.TO | iShares Core MSCI EAFE IMI | Growth | Equity (Dev ex-NA) | 0.22% | Developed markets ex North America |
| CHPS.TO | Global X AI Semiconductor Index ETF | Growth | Equity (Global Semi) | 0.65% | Added 2026-05-22; replaced ZAG.TO; NVDA/TSMC/Broadcom/ASML/AMD top holdings |
| VAB.TO | Vanguard Canadian Aggregate Bond | Stable | Fixed income (CA) | 0.09% | Broad Canadian bonds, intermediate duration |
| HSAV.TO | Horizons High Interest Savings ETF | Stable | Cash equivalent | 0.11% | HISA wrapper, swap structure. STABLE_TICKERS = {VAB.TO, HSAV.TO} |
| CDZ.TO | iShares S&P/TSX Dividend Aristocrats | Dividend | Equity-div (CA) | 0.66% | 5+ yr dividend growth companies |
| VDY.TO | Vanguard FTSE Canadian High Dividend | Dividend | Equity-div (CA) | 0.22% | Bank/energy heavy, low MER |

**Data loaded** (as of first pull 2026-05-19, universe updated 2026-05-22):
- VFV.TO: 3,393 rows | XIC.TO: 5,018 | HXQ.TO: 2,528 | XEF.TO: 3,286
- VAB.TO: 3,593 | HSAV.TO: 1,573 | CDZ.TO: 4,942 | VDY.TO: 3,393 | CHPS.TO: ~1,234
- HSAV shortest history (~6yr, launched 2019). CHPS launched June 2021 (~1,234 trading days).
- ZAG.TO removed 2026-05-22 (0.97 correlation with VAB.TO, zero diversification benefit).

---

## Portfolio Configuration

**Bucket targets** (from `config/portfolio.yaml`):
- Growth: 60% ± 10% (range: 50–70%)
- Stable: 25% ± 5% (range: 20–30%)
- Dividend: 15% ± 5% (range: 10–20%)

**Risk config**:
- Max drawdown: 20% soft ceiling, alert fires at 15%
- Risk-free rate: 4.5% (1yr GoC, refresh quarterly)
- Benchmark primary: VBAL.TO (interim) | Benchmark stretch: VFV.TO

**Trade thresholds**: Signal must clear `expected_return ≥ 2 × bid-ask + 0.5%`. Max 24 trades/year (CRA day-trade buffer). Min hold 14 days.

**Capital tier**: Tier 1 ($0–$10k) — Canadian ETFs only. Tier 2 unlocks at $10k NAV. Tier 3 at $25k. Tier 4 at $50k.

**Optimizer block** (from `config/portfolio.yaml`):
- `max_position_weight`: 0.40 (40% of bucket max per ticker)
- `min_position_weight`: 0.05 (5% floor if included)
- `rebalance_threshold`: 0.02 (weight changes < 2% → BELOW_THRESHOLD HOLD, not a trade)

**Rebalance block**:
- `min_rebalance_trade`: $50 (dollar floor for drift-SELL; prevents burning a trade slot on a trivial trim)

---

## Current Signal Readings (reference snapshot, 2026-05-19/2026-05-22)

### Momentum Signal (12-1 month, Jegadeesh-Titman 1993)

| Rank | Ticker | Score | Raw 12-1 Return |
|------|--------|-------|----------------|
| 1 | CHPS.TO | +1.000 | — (first run 2026-05-22) |
| 2 | VDY.TO | +0.750 | +50.25% |
| 3 | XIC.TO | +0.500 | +45.94% |
| 4 | HXQ.TO | +0.250 | +43.81% |
| 5 | VFV.TO | +0.000 | +33.98% |
| 6 | XEF.TO | -0.250 | +31.50% |
| 7 | CDZ.TO | -0.500 | +26.13% |
| 8 | HSAV.TO | -0.750 | +2.85% |
| 9 | VAB.TO | -1.000 | +2.24% |

Scores are cross-sectional rank-normalized to [-1, +1]. CHPS.TO ranked #1 on first live run — AI semiconductor boom already in the data.

### Vol Regime Signal (realized vol percentile, XIC.TO benchmark)

| Metric | Value |
|--------|-------|
| **Regime** | **NORMAL** |
| Vol percentile | 62.5% (of 5yr history) |
| Current annualized vol | 12.67% |
| Interpretation | Mild risk-on. Growth ETFs +0.30, stable ETFs -0.30. No defensive action warranted. |

Regime thresholds: LOW_VOL (<25th pct) = +1.0, NORMAL (25–75th) = +0.3, HIGH_VOL (75–95th) = -0.5, CRISIS (>95th) = -1.0.

---

## Backtest Results

### Momentum Strategy (2026-05-19)

**Configuration**: Momentum signal, 5-year walk-forward, equal-weight top-4, monthly rebalance, long-only, VFV.TO benchmark.

| Metric | Strategy | VFV Benchmark |
|--------|----------|--------------|
| Ann. Return | +13.98% | +16.60% |
| Ann. Vol | 11.75% | — |
| Sharpe | 0.807 | 0.812 |
| Sortino | 1.035 | — |
| Max Drawdown | -15.9% | -22.2% |
| Calmar | 0.879 | — |
| Alpha vs VFV | +1.19% | — |
| Beta vs VFV | 0.685 | — |
| Rebalances | 60 | — |
| Avg holdings/period | 4.0 | — |

**Interpretation**: Strategy trails VFV on raw return (+13.98% vs +16.60%) but achieves meaningfully lower drawdown (-15.9% vs -22.2%), lower beta (0.685), and Sortino of 1.03. Alpha +1.19% modest but positive. Captures ~69% of market upside with ~72% of market downside — reasonable risk-adjusted profile for a TFSA with 20% drawdown ceiling.

---

### Mean Reversion Signal (2026-05-22) — STANDALONE NOT VIABLE

**Configuration**: MeanReversionSignal (20d/60d z-score, regime-conditional TS/CS), 5-year walk-forward, equal-weight top-4, monthly rebalance, VFV.TO benchmark.

| Metric | Strategy | VFV Benchmark | vs Momentum |
|--------|----------|--------------|-------------|
| Ann. Return | +4.24% | +16.51% | −9.74pp |
| Sharpe | **−0.027** | 0.805 | −0.834 |
| Max Drawdown | **−24.18%** | −22.19% | −8.28pp |
| Alpha vs VFV | **−6.59%** | — | — |
| Monthly corr vs momentum | **+0.836** | — | — |

**Verdict**: Standalone MR fails on this universe. DD violates 20% ceiling, Sharpe near-zero, 0.84 correlation with momentum means no ensemble diversification benefit. Signal preserved in codebase — not wired into recommendation engine. Re-evaluate at Tier 2+ with individual equities (20+ names for cross-sectional dispersion).

---

### H004 — Volatility Targeting / Moreira-Muir (2026-05-28) — KILLED

**Configuration**: 5yr walk-forward, vol-scaled portfolio weights on top-4 equity tickers, monthly rebalance. Vol scaling applied after signal ranking using 21-day realized variance.

| Metric | Vol-Target (RV21) | Equal-Weight Baseline | Verdict |
|--------|-------------------|-----------------------|---------|
| Sharpe | 1.0623 | 0.9768 | PASS |
| Max DD | -17.28% | -18.20% | PASS |
| Alpha vs VFV | +4.94% | +4.05% | PASS |
| Corr vs baseline (monthly returns) | **0.9862** | — | **KILL** |
| Leverage effect Corr(fwd_ret, RV) | +0.03 to +0.30 all 7 ETFs | — | **KILL** |

**Kill criteria triggered**: (1) Leverage effect absent — Moreira-Muir requires Corr(E[r], σ²) < 0; all 7 equity ETFs show the opposite on 2021-2026 data (COVID recovery + AI boom = high-vol months followed by rallies). (2) Monthly return corr 0.9862 with equal-weight baseline — operationally indistinguishable. Structural failure, not parameter failure. Graveyard: `docs/research/graveyard/H004_vol_targeting.md`.

---

### H005 — RSI(21) Momentum Filter (2026-05-26) — KILLED

**Configuration**: RSI(21) > 50 gate on top of existing momentum signal. Two windows tested: 9-ETF (34 months) and 8-ETF extended (107 months, no CHPS.TO).

| Window | t-stat (incremental α) | Agreement rate | Verdict |
|--------|------------------------|----------------|---------|
| 9-ETF (34m) | NaN (zero variance) | 96.2% | KILL |
| 8-ETF (107m) | -1.00 | 83.5% | KILL |

Divergence: when momentum says BUY but RSI gate says NO, forward return = **+7.30%** — the gate suppressed valid signals. RSI(21) is a bounded monotonic transform of the same positive-drift construct as 12-1 momentum; mathematical redundancy is structural, not a parameter issue. Graveyard: `docs/research/graveyard/H005_rsi_momentum_filter.md`. Code preserved at `src/signals/rsi.py` (not in signal path).

---

## Architectural Decisions (from LEARNING.md)

### 2026-05-17 — Manual execution (Wealthsimple, no IBKR automation)
CRA day-trade reclassification risk on TFSA. $0 Wealthsimple commission vs $1 IBKR minimum. Manual circuit breaker against bugs. Revisit at Tier 3 ($25k+).

### 2026-05-17 — Three-bucket hybrid guardrails
Optimizer works *within* buckets (Growth/Stable/Dividend). Bucket weights only shift on regime signals. Pure Markowitz overconcentrates on a 9-ticker universe.

### 2026-05-17 — Horizon 3–7 years
Original 1–3yr horizon conflicted mathematically with 20% drawdown ceiling (~30% breach probability). Extended to 3–7yr. Unlocks growth allocation without breaking risk math.

### 2026-05-22 — Universe swap: ZAG.TO removed, CHPS.TO added to growth bucket
ZAG.TO had 0.97 correlation with VAB.TO — zero diversification benefit. CHPS.TO (Global X AI Semiconductor, TSX-listed, 1234d history, MER 0.65%) replaced it. STABLE_TICKERS shrinks to {VAB.TO, HSAV.TO}.

### 2026-05-22 — Research pipeline integrated: quant-research skill + Council Config G
Validated concept before implementation. quant-research skill runs 4-agent parallel pipeline → Council deliberation → DEEPER_LEARNING.md entry. Mean reversion backtest demonstrated the failure mode this pipeline catches: a signal that the factor zoo literature would have flagged before the build.

### 2026-05-23 — Structured hypothesis lifecycle tracker at docs/research/
Markdown-only. PROPOSED → COUNCIL_REVIEWED → BACKTESTED → PROMOTED/KILLED/SHELVED workflow. Graveyard entries distinguish structural failures (idea is wrong) from parameter failures (idea is wrong for this constraint set) — determines whether to revisit at Tier 2.

### 2026-05-23 — Ledoit-Wolf + SLSQP within-bucket optimizer
Sample covariance becomes unreliable as N approaches T. LW shrinkage toward structured target with analytically computed intensity — no hyperparameter tuning. SLSQP handles equality + inequality constraints natively. Stable bucket always equal-weight (HSAV near-zero vol would cause ~95/5 concentration). Falls back to equal-weight on solver failure.

### 2026-05-24 — quant-research skill upgrade: 4-agent parallel pipeline
Academic Agent (7 databases) + Practitioner Agent (10 verified sites) fire in parallel (Wave 1). Replication/Criticism Agent (9 targeted searches + 3 mandatory factor zoo checks) fires after Academic returns (Wave 2). Synthesis inline. Quality floor: all 10 practitioner sites checked, factor zoo papers explicitly consulted, at least one Council question addresses replication strength and one addresses Canadian ETF applicability.

### 2026-05-26 — Signal persistence: signal_scores table and --save contract
Signals computed on-the-fly are unauditable. `signal_scores.run_id = recommendations.run_id` is the audit path — when a trade card fires, the signal scores that drove it are retrievable. `--save` gates all persistence; no silent DB writes from read-only commands. `SignalResult.ticker_metadata()` is the two-tier extraction contract — per-ticker dicts rename keys via `_PER_TICKER_KEY_MAP`; broadcast scalars pass through verbatim. `storage.py` knows nothing about signal internals.

### 2026-05-26 — SELL / Rebalance logic: 7 design decisions
1. **Drift trigger reuses `needs_rebalance`** from `bucket_allocation()` — one truth source, no synchronization risk.
2. **Signal-SELL cost gate**: `|combined_signal| × anchor_return ≥ 2 × spread + profit_floor` — symmetric with BUY gate.
3. **Drift-SELL cost gate**: `|delta_dollars| ≥ min_rebalance_trade` ($50 floor) — dollar-based because drift is a percentage deviation but cost penalty is in dollars.
4. **Single `action="SELL"` with `sell_reason`**: CLI and execute workflow treat all SELLs identically; distinction logged as `"SIGNAL"` or `"DRIFT"` on `TradeCard`. Avoids branching in execute logic.
5. **Signal-SELL = full exit, drift-SELL = partial trim** — signal is conviction-based, drift is mechanical.
6. **Tax-loss harvesting skipped** — TFSA has no capital gains tax.
7. **Same `quant recommend` + `quant execute` pipeline** — no new commands needed.
Schema change: `sell_reason TEXT` column + `migrate_recommendations_v3()` for existing DBs.

### 2026-05-27 — ntfy.sh alert pipeline: state machine for DRAWDOWN trigger
ntfy.sh confirmed over Telegram (single HTTP POST, no bot setup). DRAWDOWN trigger uses a state machine: fires once on first crossing above 15% threshold, logs a RECOVERED row (no POST) when portfolio returns below, re-arms for the next crossing. `send_alert` never raises — network failure logs a WARNING and returns. Recommendation pipeline integrity is not conditional on ntfy.sh availability.

### 2026-05-28 — DailyRunner: fail-forward, not fail-fast
Four steps: fetch → momentum signal → vol_regime signal → recommend --optimize --save --notify. Runs all steps regardless of individual failures — fail-fast would skip `recommend` if a signal step errored, defeating the purpose of automation. Error alerts via ntfy.sh priority=5 on any step failure. Two callers: `scripts/daily_run.py` (Task Scheduler, writes dated log) and `quant daily-run` (interactive, stdout only). `-WakeToRun ON`, `-StartWhenAvailable ON` in Task Scheduler so laptop wakes for the scheduled run.

### 2026-05-28 — Integration test avoids real VolRegimeSignal
VolRegimeSignal requires 1291 rows of XIC.TO history. Constructing that in a test fixture would be slow and couple the integration test to a specific signal's data requirement. The regime `SignalResult` is constructed directly — the signal is already unit-tested in test_signals.py. Integration test focuses on layer connectivity, not signal correctness.

---

## Bugs Found and Fixed

### Bug 1 (2026-05-19): Backtest top-N slice selected bottom-N tickers
- **File**: `src/backtest/engine.py`
- **Root cause**: `result.ranked()` returns descending. `ranked[-top_n:]` = lowest-scored tickers. `if s > 0` guard filtered all of them → cash every period → 0.0 return, NaN Sharpe.
- **Fix**: Changed `ranked[-config.top_n:]` to `ranked[:config.top_n]`.

### Bug 2 (2026-05-19): Vol regime lookback insufficient
- **File**: `src/cli/phase2_commands.py`
- **Root cause**: Prices loaded with hardcoded 1260-day window; VolRegimeSignal needs 1291 days. Signal silently returned regime=unknown, scores=0.0.
- **Fix**: Instantiate signal first, then load `sig.lookback_days` days.

### Bug 3 (2026-05-19): Format string crash on missing metadata
- **Root cause**: `:.1%` format spec applied to string `'n/a'` when metadata absent.
- **Fix**: Guard with `if value is not None` before formatting.

### Bug 4 (2026-05-19): Empty Series RangeIndex crash in momentum signal
- **Root cause**: `pd.Series(dtype=float)` has int64 RangeIndex. `series.index <= Timestamp` raises TypeError.
- **Fix**: Early guard — skip ticker if series.empty or index is int64.

### Bug 5 (2026-05-19): Flaky test fixture (weak random drift)
- **Root cause**: ±0.001 daily drift swamped by 0.01 vol over 231-day window. Rank ordering not guaranteed.
- **Fix**: Deterministic `np.linspace`/`np.full` price series.

---

## Test Suite

```
tests/test_metrics.py              11 tests — portfolio/metrics.py: Sharpe, Sortino, Calmar, max DD, beta, alpha
tests/test_signals.py              11 tests — MomentumSignal, ShortTermMomentum, VolRegimeSignal, edge cases
tests/test_recommendations.py      21 tests — combined signals, target weights, all gate types, cold-start math
tests/test_mean_reversion.py       16 tests — MeanReversionSignal shape, bounds, sign convention, warmup, regime weights
tests/test_optimizer.py            31 tests — BucketOptimizer constraints, LW PD check, 2-ticker, fallbacks, integration
tests/test_storage.py              23 tests — SQLite schema, CRUD, VWAP, annual trade count, min-hold, alerts log
tests/test_sell_logic.py           16 tests — signal-SELL gate, drift-SELL gate, sell_reason, partial vs full exit
tests/test_signal_persistence.py    9 tests — ticker_metadata(), persist_signals(), query_signal_history()
tests/test_alerts.py               14 tests — ntfy transport, 3 alert triggers, DRAWDOWN state machine, first-run paths
tests/test_daily_run.py             9 tests — DailyRunner steps, timeout-as-failure, cash flag, log branching
tests/test_rsi_signal.py           24 tests — RSI math, Wilder SMMA, gate logic, metadata, edge cases
tests/test_H005_rsi_backtest.py     1 test  — H005 backtest regression (graveyard artifact)
tests/test_backtest.py              8 tests — avg_holdings > 0, summary_str(), metrics keys, ValueError
tests/test_integration.py          10 tests — full pipeline: signal layer → backtest layer → recommend layer
─────────────────────────────────────────────────────────────────────────────
TOTAL                             204 tests — 204/204 passing as of v1.0.0-tier1 (2026-05-28)
```

**Run**: `python -m pytest tests/ -v`
**Known test gaps**: None — all Phase 3 subsystems have targeted coverage.

---

## SQLite Schema

**Database**: `data/quant.db` (gitignored, regenerable via `quant init` + `quant fetch`)

| Table | Purpose |
|-------|---------|
| `prices` | Daily OHLCV per ticker. PK: (ticker, trade_date). |
| `holdings` | Current positions. PK: ticker. Updated atomically on each trade. |
| `trades` | Executed trade log with rationale field. |
| `recommendations` | Signal-generated trade cards (BUY/SELL, all statuses). Includes `sell_reason` field. |
| `metrics_snapshots` | Periodic risk/return snapshots per scope/metric/window. |
| `run_log` | System event log with component + level. |
| `signal_scores` | Persisted signal scores per ticker per run. PK: (run_date, ticker, signal_type). JOIN to `recommendations` via `run_id`. |
| `alerts_log` | Alert event log: alert_type, payload, timestamp. Used by DRAWDOWN state machine to detect crossings and recoveries. |

**Signal scores** are persisted via `quant signals --save` or `quant recommend --save`. JOIN path: `signal_scores.run_id = recommendations.run_id`.

**Schema migration**: `migrate_recommendations_v3()` in `storage.py` adds `sell_reason TEXT` to existing databases with NULL default (no data loss).

---

## Signal Math Reference

### MomentumSignal (src/signals/momentum.py)
- **Algorithm**: 12-1 month cross-sectional momentum
- **Formula**: `raw = (P_{t-21} / P_{t-273}) - 1` per ticker, then rank-normalized to [-1, +1]
- **Skip month**: 21 trading days skipped to avoid short-term reversal
- **Reference**: Jegadeesh & Titman (1993). *Returns to Buying Winners and Selling Losers.* JF 48(1).
- **Variants**: `ShortTermMomentum` (3-1 month, 63/21 days), `LongTermMomentum` (18-1 month, 378/21 days)

### VolRegimeSignal (src/signals/vol_regime.py)
- **Algorithm**: 21-day realized vol of XIC.TO, percentile-ranked against 5yr history
- **Thresholds**: <25th pct = LOW_VOL (+1.0), 25–75th = NORMAL (+0.3), 75–95th = HIGH_VOL (-0.5), >95th = CRISIS (-1.0)
- **Broadcast**: Growth/dividend tickers get raw regime score. Stable tickers get inverse (crisis = buy bonds).
- **Reference**: Kritzman et al. (2012). *Regime Shifts: Implications for Dynamic Strategies.* FAJ.

### MeanReversionSignal (src/signals/mean_reversion.py) — not in recommendation engine
- **Algorithm**: Regime-conditional dual-window z-score
- **Formula**: `z_ts = 0.5 × z_20 + 0.5 × z_60`, normalized via `tanh()`, blended with cross-sectional rank
- **Regime weights**: CRISIS (0.70/0.30 TS/CS) → NORMAL (0.50/0.50) → LOW_VOL (0.35/0.65)
- **Status**: Complete and tested. Not wired into recommendation engine. Re-evaluate at Tier 2+.

### Combined Signal (src/portfolio/recommendations.py)
- **Formula**: `momentum × max(regime_score, 0)` for growth/dividend. Stable bucket: equal weight (1/n_stable).
- **Rationale**: Clamping regime to 0 prevents sign-flip artifacts (neg × neg = pos) that would buy anti-momentum tickers in bad regimes.

### BucketOptimizer (src/portfolio/optimizer.py)
- **Covariance**: Ledoit-Wolf shrinkage (`sklearn.covariance.LedoitWolf`). Analytically optimal shrinkage intensity, no hyperparameter tuning.
- **Expected return proxy**: `signal_i × annualized_vol_i` — signal scores in return-like units calibrated to each ticker's vol.
- **Solver**: SLSQP (scipy). Constraints: sum(w)=1, w≥0, w≥5% if included, w≤40%.
- **Fallback**: Equal-weight on solver failure — pipeline never crashes.
- **Stable bucket**: Always equal-weight (HSAV near-zero vol causes degenerate concentration).
- **Rebalance gate**: Weight changes < 2% → BELOW_THRESHOLD HOLD (preserves trade budget).

### Backtest Engine (src/backtest/engine.py)
- **Method**: Walk-forward, monthly rebalance (21 trading days), equal-weight top-N by signal score
- **Long-only**: Only holds tickers with positive signal scores (TFSA constraint)
- **No lookahead**: Signals at time t use only data available at t
- **Benchmark**: Buy-and-hold VFV.TO
- **Output**: `BacktestResult` with `summary_str()` method for formatted multi-line metric display

---

## Phase 3 Roadmap

### P3.1 — Mean Reversion Signal ✅ COMPLETE (2026-05-22)
Signal complete in codebase; not viable standalone (Sharpe −0.03, DD −24.2%, corr 0.84 vs momentum). Not wired into recommendation engine.

### P3.2 — Within-Bucket Optimizer ✅ COMPLETE (2026-05-23)
`src/portfolio/optimizer.py`. Ledoit-Wolf + SLSQP. `--optimize` flag on `quant recommend`. 31 tests.

### P3.3 — Signal Persistence ✅ COMPLETE (2026-05-26)
`signal_scores` table. `persist_signals()` + `query_signal_history()` in `storage.py`. `quant signal-history` command. 9 tests. v0.3.0-signal-persistence.

### P3.4 — SELL / Rebalance ✅ COMPLETE (2026-05-26)
Signal-driven full exit + drift-triggered partial trim. `sell_reason` field. Schema migration. 16 tests.

### P3.5 — Phone Alert Pipeline ✅ COMPLETE (2026-05-27)
ntfy.sh. Three triggers: NEW_RECOMMENDATION, REGIME_CHANGE, DRAWDOWN. `alerts_log` table. `--notify` flag. `quant alert-test`. 14 tests. v0.4.0-alerts.

### P3.6 — Scheduled Daily Run ✅ COMPLETE (2026-05-28)
`DailyRunner` in `src/cli/daily_run_command.py`. `quant daily-run`. `scripts/daily_run.py`, `scripts/daily_run.bat`, `scripts/setup_scheduler.ps1`. 9 tests. v0.5.0-daily-run.

### P3.7 — Test Coverage Closure ✅ COMPLETE (2026-05-28)
`BacktestResult.summary_str()`. `tests/test_backtest.py` (8 tests). `tests/test_integration.py` (10 tests). Alert first-run gap tests. 204/204 passing. v0.6.0-test-coverage.

---

## Hypothesis Tracker

| ID | Hypothesis | Status | Outcome | Reference |
|----|-----------|--------|---------|-----------|
| H001 | Mean reversion standalone signal | KILLED (2026-05-22) | Parameter failure — 9-ETF universe too small, monthly rebalance too slow for 20d window | `graveyard/H001_mean_reversion_standalone.md` |
| H004 | Volatility targeting / Moreira-Muir scaling | KILLED (2026-05-28) | Structural failure — leverage effect absent 7/7 ETFs, corr 0.9862 with baseline | `graveyard/H004_vol_targeting.md` |
| H005 | RSI(21) > 50 momentum gate | KILLED (2026-05-26) | Structural failure — 96.2% agreement, t=NaN, gate suppresses +7.30% valid signals | `graveyard/H005_rsi_momentum_filter.md` |
| H006 | Volume spike as regime indicator | SHELVED | ETF structural incompatibility (creation/redemption noise, Baker & Stein inversion) | `hypotheses/H006_volume_spike_regime.md` |

**No active candidates.** Next hypothesis requires a new file through `/quant-research` pipeline.

**DEEPER_LEARNING entries**: DL-001 through DL-014 (14 entries). See `docs/DEEPER_LEARNING.md`.

---

## Open Questions (Tier 2)

1. **Capital tier transition automation**: When NAV hits $10k, what does a clean tier transition look like? Auto-update `capital_tier` in YAML? Notify and prompt? Freeze recommendations until operator confirms?

2. **Covariance estimation at Tier 2**: Ledoit-Wolf is well-suited for 9 ETFs. With 20–40 assets (Tier 2 individual stocks), the N/T ratio degrades. Evaluate non-linear shrinkage (Ledoit-Wolf 2020) vs Oracle Approximating Shrinkage before first Tier 2 optimizer run.

3. **Regime detection comparison**: Hidden Markov Model vs current vol-percentile approach vs VIX-based. Current approach is live and working. Compare HMM in a Phase 4 backtest when Tier 2 data is available.

4. **H001 mean-reversion re-evaluation at Tier 2**: Parameter failure (small universe, monthly rebalance too slow) — revisit once universe expands to 20+ individual equities with meaningful cross-sectional dispersion.

---

## How to Resume in a Fresh Session

1. Read `CLAUDE.md` for hard constraints (never violate these).
2. Read this file (`docs/PROJECT_STATUS.md`) for current state.
3. Check `LEARNING.md` for any decisions or bugs logged since this doc was last updated.
4. Run `python -m pytest tests/ -v` to confirm baseline is green before any change.
5. Run `quant signals --signal-type momentum` to confirm live signals are working.
6. **No active hypothesis candidates.** Any new signal idea requires a new hypothesis file through `/quant-research`. Research pipeline is live. Watchlist: H006 (volume spike, SHELVED Tier 2+).
7. **Next milestone trigger**: NAV ≥ $10,000 CAD unlocks Tier 2.

---

*Last updated: 2026-05-28. v1.0.0-tier1 — Tier 1 complete. All Phase 3 subsystems shipped (P3.3 signal persistence, SELL/rebalance, P3.5 alerts, P3.6 daily run, P3.7 test coverage). H004 + H005 KILLED. H006 SHELVED. 204/204 tests passing. Next milestone: NAV ≥ $10k (Tier 2).*
