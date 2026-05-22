# PROJECT STATUS — Quant Engine
> **Fresh-session onboarding doc.** Read this + CLAUDE.md before touching anything.
> Last updated: 2026-05-22 (mean reversion signal + backtest validation complete).

---

## What This System Is

A personal systematic investing engine for Arsh's Wealthsimple TFSA. Math-driven, news-free, persistent. It generates momentum, volatility regime, and mean reversion signals daily, validates them against walk-forward backtests, and surfaces trade recommendations. Arsh pulls the trigger manually in Wealthsimple — the system never executes.

**Capital**: ~$500–1000 CAD starting, $300–400/month contributions. 3–7 year horizon. 20% soft drawdown ceiling. Benchmark: VBAL (interim), VFV (stretch).

---

## Repository

- **GitHub**: `https://github.com/arshnoor51103-dev/Quant_engine`
- **Branch**: `main`
- **Git initialized**: 2026-05-19
- **Python**: 3.11+ (running on 3.14.3 locally)
- **Venv**: `.venv/` at project root (not committed)

---

## Current State: Phase 2 Complete

| Phase | Status | What It Delivers |
|-------|--------|-----------------|
| Phase 1 — Foundation | ✅ Complete | Data pipeline, portfolio model, risk metrics, CLI |
| Phase 2 — Signal Engine | ✅ Complete | Momentum + vol regime signals, walk-forward backtester, FastAPI dashboard |
| Phase 3 P0 — Recommendations | ✅ Complete | Signal-proportional weights, trade cards, cost/CRA/min-hold gates, execute workflow |
| Phase 3 P2 — Optimizer | 🔲 Not started | Ledoit-Wolf covariance, Markowitz within-bucket optimizer |
| Phase 3 P1 — Mean Reversion | ✅ Complete | Regime-conditional mean reversion signal + backtest validation |
| Phase 4 — Automation | 🔲 Not started | ntfy.sh phone alerts, scheduled daily runs |

---

## File Structure

```
quant_engine/
├── CLAUDE.md                   ← hard constraints + coding conventions (READ FIRST)
├── LEARNING.md                 ← append-only log: decisions, bugs, concepts
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   ├── PROJECT_STATUS.md       ← this file
│   ├── PHASE_1_ROADMAP.md
│   └── ARCHITECTURE.md
├── config/
│   ├── portfolio.yaml          ← buckets, tiers, risk config, trade thresholds + spread_proxy/anchor_return
│   └── universe.yaml           ← 9 ETF definitions with metadata + spread_override hook
├── src/
│   ├── data/
│   │   ├── ingest.py           ← yfinance → SQLite, incremental OHLCV pull
│   │   └── storage.py          ← SQLite schema + helpers; Phase 3 adds recommendation CRUD
│   ├── portfolio/
│   │   ├── model.py            ← holdings, NAV, bucket allocation, price_series
│   │   ├── metrics.py          ← Sharpe, Sortino, Calmar, max DD, beta, alpha, rolling
│   │   └── recommendations.py  ← Phase 3 P0: combined signals, target weights, trade cards
│   ├── signals/
│   │   ├── base.py             ← Signal ABC + SignalResult dataclass
│   │   ├── momentum.py         ← 12-1 month momentum (Jegadeesh-Titman 1993)
│   │   ├── vol_regime.py       ← realized vol percentile → regime classification
│   │   └── mean_reversion.py   ← regime-conditional z-score MR (Jegadeesh/Lehmann 1990)
│   ├── backtest/
│   │   └── engine.py           ← walk-forward backtester, BacktestConfig, BacktestResult
│   ├── api/
│   │   └── server.py           ← FastAPI server, 5 REST endpoints + HTML dashboard
│   └── cli/
│       ├── main.py             ← typer app, all commands registered
│       ├── phase2_commands.py  ← signals, backtest, dashboard commands
│       └── phase3_commands.py  ← recommend, execute, pending, skip commands
├── tests/
│   ├── test_metrics.py         ← 11 unit tests for portfolio/metrics.py
│   ├── test_signals.py         ← 11 unit tests for momentum + vol_regime signals
│   ├── test_recommendations.py ← 22 unit tests for Phase 3 P0 recommendation engine
│   └── test_mean_reversion.py  ← 16 unit tests for MeanReversionSignal
└── data/                       ← SQLite db + parquet cache (gitignored)
```

---

## CLI Commands

Run from project root with: `python -m src.cli.main <command>`
Or if installed as `quant`: `quant <command>`

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
| `quant signals --signal-type [momentum\|momentum_short\|vol_regime\|mean_reversion]` | Generate signal scores for universe. Prints ranked table + raw returns or regime metadata. |
| `quant backtest --signal-type X --years N --top-n N` | Walk-forward backtest. Default: momentum, 5yr, top-4. Prints metrics vs VFV benchmark. |
| `quant dashboard [--port N]` | Launch FastAPI server at localhost:8501. Serves `/api/universe`, `/api/metrics`, `/api/signals`, `/api/status` + HTML dashboard. |

### Phase 3 P0 Commands
| Command | What it does |
|---------|-------------|
| `quant recommend [--cash N] [--save]` | Run full recommendation pipeline. Prints trade cards with gate status. `--cash` required when NAV=0. `--save` persists cards to DB and assigns rec IDs. |
| `quant execute <ID> --price X --units Y [--date YYYY-MM-DD]` | Mark recommendation as executed. Atomically updates rec status + creates trade record with actual fill. |
| `quant pending` | List all pending (unsaved/unexecuted) recommendations with rec IDs. |
| `quant skip <ID>` | Mark a pending recommendation as skipped (not executed). |

**Windows note**: Set `$env:PYTHONUTF8 = "1"` before running CLI commands or the Unicode bar characters crash the console. Example:
```powershell
$env:PYTHONUTF8 = "1"; python -m src.cli.main signals --signal-type momentum
```

---

## Asset Universe (Tier 1)

| Ticker | Name | Bucket | Asset Class | MER | Notes |
|--------|------|--------|-------------|-----|-------|
| VFV.TO | Vanguard S&P 500 Index ETF | Growth | Equity (US) | 0.09% | Core US large-cap, unhedged |
| XIC.TO | iShares S&P/TSX Capped Composite | Growth | Equity (CA) | 0.06% | TSX broad market |
| HXQ.TO | Horizons NASDAQ-100 ETF | Growth | Equity (US) | 0.28% | Swap structure, tax-efficient in TFSA |
| XEF.TO | iShares Core MSCI EAFE IMI | Growth | Equity (Dev ex-NA) | 0.22% | Developed markets ex North America |
| VAB.TO | Vanguard Canadian Aggregate Bond | Stable | Fixed income (CA) | 0.09% | Broad Canadian bonds, intermediate duration |
| ZAG.TO | BMO Aggregate Bond Index | Stable | Fixed income (CA) | 0.09% | Alternative to VAB |
| HSAV.TO | Horizons High Interest Savings ETF | Stable | Cash equivalent | 0.11% | HISA wrapper, swap structure |
| CDZ.TO | iShares S&P/TSX Dividend Aristocrats | Dividend | Equity-div (CA) | 0.66% | 5+ yr dividend growth companies |
| VDY.TO | Vanguard FTSE Canadian High Dividend | Dividend | Equity-div (CA) | 0.22% | Bank/energy heavy, low MER |

**Data loaded** (as of 2026-05-19 first pull):
- VFV.TO: 3,393 rows | XIC.TO: 5,018 | HXQ.TO: 2,528 | XEF.TO: 3,286
- VAB.TO: 3,593 | ZAG.TO: 4,094 | HSAV.TO: 1,573 | CDZ.TO: 4,942 | VDY.TO: 3,393
- HSAV shortest history (~6yr, launched 2019) — expected.

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

**Capital tier**: Tier 1 ($0–$10k) — Canadian ETFs only. Tier 2 unlocks at $10k NAV (+ CA dividend stocks). Tier 3 at $25k (+ US-listed ETFs). Tier 4 at $50k (+ large-cap stocks).

---

## Current Signal Readings (2026-05-19)

### Momentum Signal (12-1 month, Jegadeesh-Titman 1993)

| Rank | Ticker | Score | Raw 12-1 Return |
|------|--------|-------|----------------|
| 1 | VDY.TO | +1.000 | +50.25% |
| 2 | XIC.TO | +0.750 | +45.94% |
| 3 | HXQ.TO | +0.500 | +43.81% |
| 4 | VFV.TO | +0.250 | +33.98% |
| 5 | XEF.TO | +0.000 | +31.50% |
| 6 | CDZ.TO | -0.250 | +26.13% |
| 7 | HSAV.TO | -0.500 | +2.85% |
| 8 | ZAG.TO | -0.750 | +2.38% |
| 9 | VAB.TO | -1.000 | +2.24% |

Scores are cross-sectional rank-normalized to [-1, +1]. Bonds score lowest because fixed income momentum trails equity in the current environment.

### Vol Regime Signal (realized vol percentile, XIC.TO benchmark)

| Metric | Value |
|--------|-------|
| **Regime** | **NORMAL** |
| Vol percentile | 62.5% (of 5yr history) |
| Current annualized vol | 12.67% |
| Interpretation | Mild risk-on. Growth ETFs +0.30, stable ETFs -0.30. No defensive action warranted. |

Regime thresholds: LOW_VOL (<25th pct) = +1.0, NORMAL (25–75th) = +0.3, HIGH_VOL (75–95th) = -0.5, CRISIS (>95th) = -1.0.

---

## Backtest Results (2026-05-19)

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

**Last 3 rebalance picks**:
- 2026-02-27: XIC.TO, VDY.TO, XEF.TO, CDZ.TO
- 2026-03-30: XIC.TO, VDY.TO, XEF.TO, CDZ.TO
- 2026-04-29: VDY.TO, XIC.TO, CDZ.TO, HXQ.TO

**Interpretation**: Strategy slightly trails VFV on raw return (+13.98% vs +16.60%) but achieves this with meaningfully lower drawdown (-15.9% vs -22.2%), lower beta (0.685), and a Sortino of 1.03 indicating well-controlled downside risk. Alpha of +1.19% is modest but positive. The strategy captures ~69% of market upside with ~72% of market downside — a reasonable risk-adjusted profile for a TFSA with a 20% drawdown ceiling.

---

### Mean Reversion Signal (2026-05-22)

**Configuration**: MeanReversionSignal (20d/60d z-score, regime-conditional TS/CS), 5-year walk-forward, equal-weight top-4, monthly rebalance, VFV.TO benchmark.

| Metric | Strategy | VFV Benchmark | vs Momentum |
|--------|----------|--------------|-------------|
| Ann. Return | +4.24% | +16.51% | −9.74pp |
| Ann. Vol | 9.93% | — | −1.82pp |
| Sharpe | −0.027 | 0.805 | −0.834 |
| Sortino | −0.038 | — | −1.073 |
| Max Drawdown | **−24.18%** | −22.19% | −8.28pp |
| Calmar | 0.175 | — | −0.704 |
| Alpha vs VFV | **−6.59%** | — | −7.78pp |
| Beta | 0.527 | — | −0.158 |
| Monthly win rate | 55.7% (34/61) | — | — |
| Monthly corr vs momentum | **+0.836** | — | — |

**Verdict: standalone mean reversion is not viable on this universe.**
- Max drawdown −24.18% violates the 20% soft ceiling.
- Sharpe −0.027: barely beats cash. Momentum: 0.807.
- Alpha −6.59%: deeply negative.
- Monthly return correlation with momentum is 0.836 — nearly the same signal, no ensemble diversification benefit.

**Why it fails on 9 ETFs**: Too few tickers for cross-sectional dispersion. Monthly rebalance is too slow for the 20d z-score window (reversals resolve within 1 week). Both MR and momentum are cross-sectional ranking signals on the same universe and end up selecting mostly the same 4 tickers.

**Signal status**: Code complete, tests passing, CLI accessible (`quant signals --signal-type mean_reversion`). **Not wired into the recommendation engine.** Potential value: (a) position-sizing modifier in ensemble at higher tiers, (b) revisit when universe expands to 20+ individual stocks, (c) intraweek rebalance experiment.

---

## Architectural Decisions (from LEARNING.md)

### 2026-05-19 — Phase 2 components landed together
Signals, backtester, and API dashboard built simultaneously. Rationale: signals without backtests are dangerous. Dashboard without signals has nothing to show.

### 2026-05-17 — Manual execution (Wealthsimple, no IBKR automation)
CRA day-trade reclassification risk on TFSA. $0 Wealthsimple commission vs $1 IBKR minimum. Manual circuit breaker against bugs. Revisit at Tier 3 ($25k+).

### 2026-05-17 — Three-bucket hybrid guardrails
Optimizer works *within* buckets (Growth/Stable/Dividend). Bucket weights only shift on regime signals. Pure Markowitz overconcentrates on a 9-ticker universe.

### 2026-05-17 — Horizon 3–7 years
Original 1–3yr horizon mathematically conflicted with 20% drawdown ceiling (~30% breach probability). Extended to 3–7yr. Unlocks growth allocation without breaking risk math.

### 2026-05-17 — Canadian ETFs only at Tier 1
Avoid 1.5% Wealthsimple FX drag. Universe expands automatically at capital tier breaks.

---

## Bugs Found and Fixed (Phase 2)

### Bug 1: Backtest top-N slice selected bottom-N tickers
- **File**: `src/backtest/engine.py`
- **Root cause**: `result.ranked()` returns descending (highest first). `ranked[-top_n:]` selects the *last* N = lowest-scored tickers (bonds). The `if s > 0` guard filtered all of them out → cash every period → 0.0 return, NaN Sharpe.
- **Fix**: Changed `ranked[-config.top_n:]` to `ranked[:config.top_n]` in both branches.
- **Lesson**: Always comment sort direction when slicing ranked lists.

### Bug 2: Vol regime lookback insufficient
- **File**: `src/cli/phase2_commands.py`
- **Root cause**: Prices loaded with hardcoded `lookback_days=1260` but `VolRegimeSignal.lookback_days = 1291`. Benchmark check failed → all scores 0.0, regime "unknown".
- **Fix**: Select signal first, then load `max(sig.lookback_days, 1260)` days.

### Bug 3: Format string crash on missing metadata
- **File**: `src/cli/phase2_commands.py`
- **Root cause**: `:.1%` format spec applied to string `'n/a'` when metadata absent (unknown regime path).
- **Fix**: Guard with `if value is not None` before formatting.

### Bug 4: Empty Series RangeIndex crash in momentum signal
- **File**: `src/signals/momentum.py`
- **Root cause**: `pd.Series(dtype=float)` has `RangeIndex(int64)`. Comparing `int64 index <= Timestamp` raises `TypeError`.
- **Fix**: Early guard — skip ticker if `series.empty` or index is int64.

### Bug 5: Flaky test fixture (weak random drift)
- **File**: `tests/test_signals.py`
- **Root cause**: Mock prices used stochastic data with ±0.001 daily drift, swamped by 0.01 vol. Rank ordering not guaranteed.
- **Fix**: Replaced with deterministic `np.linspace`/`np.full` series.

---

## Test Suite

```
tests/test_metrics.py           11 tests — all portfolio/metrics.py functions
tests/test_signals.py           11 tests — MomentumSignal, ShortTermMomentum, VolRegimeSignal, edge cases
tests/test_recommendations.py  22 tests — combined signals, target weights, all gate types, cold-start math
tests/test_mean_reversion.py    16 tests — MeanReversionSignal shape, bounds, sign convention, warmup, regime weights
```

**Run**: `python -m pytest tests/ -v`
**Status**: 59/59 passing as of 2026-05-22.

**Known test gaps** (TODO for Phase 3 P1+):
- Backtest engine needs a test asserting `avg_holdings_per_period > 0` on known-positive signals.
- No tests for `BacktestResult.summary_str()`.
- No integration test covering full pipeline: fetch → signal → backtest → recommend.

---

## SQLite Schema

**Database**: `data/quant.db` (gitignored, regenerable via `quant init` + `quant fetch`)

| Table | Purpose |
|-------|---------|
| `prices` | Daily OHLCV per ticker. PK: (ticker, trade_date). |
| `holdings` | Current positions. PK: ticker. Updated atomically on each trade. |
| `trades` | Executed trade log with rationale field. |
| `recommendations` | Signal-generated recommendations (not all become trades). |
| `metrics_snapshots` | Periodic risk/return snapshots per scope/metric/window. |
| `run_log` | System event log with component + level. |

**Signal scores are not yet persisted** — they're computed on the fly. Phase 3 should write `signal_scores` to the DB or to the `recommendations` table.

---

## Signal Math Reference

### MomentumSignal (src/signals/momentum.py)
- **Algorithm**: 12-1 month cross-sectional momentum
- **Formula**: `raw = (P_{t-21} / P_{t-273}) - 1` per ticker, then rank-normalized to [-1, +1]
- **Skip month**: 21 trading days skipped to avoid short-term reversal
- **Reference**: Jegadeesh & Titman (1993). *Returns to Buying Winners and Selling Losers.* Journal of Finance, 48(1), 65–91.
- **Variants**: `ShortTermMomentum` (3-1 month, 63/21 days), `LongTermMomentum` (18-1 month, 378/21 days)

### VolRegimeSignal (src/signals/vol_regime.py)
- **Algorithm**: 21-day realized vol of XIC.TO, percentile-ranked against 5yr history
- **Thresholds**: <25th pct = LOW_VOL (+1.0), 25–75th = NORMAL (+0.3), 75–95th = HIGH_VOL (-0.5), >95th = CRISIS (-1.0)
- **Broadcast**: Growth/dividend tickers get raw regime score. Stable tickers (VAB, ZAG, HSAV) get inverse (crisis = buy bonds).
- **Reference**: Kritzman et al. (2012). *Regime Shifts: Implications for Dynamic Strategies.* Financial Analysts Journal.

### MeanReversionSignal (src/signals/mean_reversion.py)
- **Algorithm**: Regime-conditional dual-window z-score mean reversion
- **TS component**: `z_ts = 0.5 × z_20 + 0.5 × z_60` where each `z_N` = rolling z-score of daily log returns at N days
- **TS normalization**: `tanh(z_ts)` — smooth compression to (−1, 1) per ticker
- **CS component**: Rank-normalize `z_ts` across all tickers at run_date → [−1, +1]
- **Combination**: `combined = w_ts × tanh(z_ts) + w_cs × z_cs`, sign-flipped, then final rank-normalize
- **Regime weights**: CRISIS (0.70/0.30 TS/CS) → HIGH_VOL (0.60/0.40) → NORMAL (0.50/0.50) → LOW_VOL (0.35/0.65)
- **Sign convention**: Positive score = oversold = buy pressure (matches momentum convention)
- **Warmup**: 60 trading days minimum; insufficient data → 0.0 neutral
- **References**: Jegadeesh (1990), Lehmann (1990), Asness/Moskowitz/Pedersen (2013)
- **Backtest verdict**: Standalone not viable on 9-ETF universe (Sharpe −0.03, DD −24%, alpha −6.6%, 0.84 corr with momentum)

### Backtest Engine (src/backtest/engine.py)
- **Method**: Walk-forward, monthly rebalance (21 trading days), equal-weight top-N by signal score
- **Long-only**: Only holds tickers with positive signal scores (TFSA constraint)
- **No lookahead**: Signals at time t use only data available at t
- **Benchmark**: Buy-and-hold VFV.TO

---

## Phase 3 Roadmap

Phase 3 goal: **within-bucket weight optimization + trade recommendation engine**. Signals generate scores; optimizer converts scores to target weights; recommendation engine applies cost gate and fires trade cards.

### P3.1 — Mean Reversion Signal ✅ COMPLETE (2026-05-22)
- File: `src/signals/mean_reversion.py` — 16 tests passing
- Regime-conditional dual-window z-score (20d/60d), tanh TS + CS rank, sign-flip
- **Backtest result**: standalone not viable (Sharpe −0.03, DD −24.2%, alpha −6.6%, corr 0.84 vs momentum)
- Signal complete in codebase; not wired into recommendation engine; revisit at Tier 2+ or with intraweek rebalance

### P3.2 — Within-Bucket Optimizer
- File: `src/portfolio/optimizer.py`
- Input: signal scores + current holdings + bucket constraints from `portfolio.yaml`
- Method: Markowitz mean-variance with Ledoit-Wolf shrinkage covariance (addresses the open question from LEARNING.md about short history)
- Constraint: weights stay within bucket tolerances; no shorting; sum = 1 within bucket
- Output: target weights per ticker

### P3.3 — Signal Persistence
- Write signal scores to SQLite at each run (extend `recommendations` table or add `signal_scores` table)
- Enable historical signal tracking and regime-change audit trail

### P3.4 — Trade Recommendation Engine
- File: `src/portfolio/recommendations.py`
- Input: target weights (optimizer output) + current holdings + prices
- Cost gate: `expected_return ≥ 2 × bid_ask_spread + 0.5%` (already in `portfolio.yaml`)
- CRA gate: check annual trade count < 24 before firing
- Output: trade cards persisted to `recommendations` table, surfaced via `quant recommend`

### P3.5 — Phone Alert Pipeline
- Open question from LEARNING.md: Telegram bot vs ntfy.sh vs email
- Trigger: new trade recommendation, drawdown alert (>15%), regime change
- Lean toward ntfy.sh (dead simple, no bot setup)

### P3.6 — Scheduled Daily Run
- Windows Task Scheduler or a simple `.bat` wrapper
- Run: `quant fetch --incremental && quant signals --signal-type momentum && quant signals --signal-type vol_regime`
- Log output to `logs/YYYY-MM-DD.log`

### P3.7 — Backtest Test Coverage
- Unit test: `avg_holdings_per_period > 0` on known-positive universe
- Unit test: `VolRegimeSignal` with synthetic price series
- Integration test: full pipeline fetch → signal → backtest

---

## Open Questions (from LEARNING.md)

1. **Covariance estimation with short history**: Use Ledoit-Wolf shrinkage for the optimizer. Short ETF histories (HSAV: ~6yr) mean sample covariance is noisy. Shrinkage pulls toward identity matrix.
2. **Phone alerts**: Telegram bot vs ntfy.sh. ntfy.sh leans simpler — evaluate in Phase 3.5.
3. **Regime detection method**: Simple vol thresholds (current) vs hidden Markov model vs VIX-based. Current vol-percentile approach is live and working. Compare HMM in Phase 3 backtest.

---

## How to Resume in a Fresh Session

1. Read `CLAUDE.md` for hard constraints (never violate these).
2. Read this file (`docs/PROJECT_STATUS.md`) for current state.
3. Check `LEARNING.md` for any decisions or bugs logged since this doc was last updated.
4. Run `python -m pytest tests/ -v` to confirm baseline is green before any change.
5. Run `quant signals --signal-type momentum` to confirm live signals are working.
6. The next task is Phase 3 — start with P3.1 (mean reversion signal) or P3.2 (optimizer), per Arsh's direction.

---

*Last updated: 2026-05-22. Phase 3 P1 (mean reversion signal) complete. 59/59 tests passing. Committed on `main`.*
