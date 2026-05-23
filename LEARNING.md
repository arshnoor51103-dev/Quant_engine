# LEARNING.md — Quant Engine Autoprogression Log

> Append-only log of decisions, mistakes, concepts learned, and open questions.
> **Never delete entries.** Corrections go as new entries that reference the original.

---

## How To Use This File

Every entry follows one of five templates below. Add new entries at the **top of each section** (newest first within section). Date format: `YYYY-MM-DD`.

When Claude Code makes an architectural decision, finds a bug, learns something non-obvious, or hits an open question — it appends here before/after the code change.

When Arsh learns a concept (factor models, regime detection, etc.), he appends a Concept entry.

---

## 📐 Decisions Log

> Architectural and design choices with rationale. The "why" behind the code.

### 2026-05-22 — Research pipeline integrated: quant-research skill + the-council Config G + DEEPER_LEARNING.md
**Context**: Needed a structured, repeatable way to research new algorithms and persist validated knowledge across sessions. Raw web search → implementation was error-prone and produced no institutional memory.
**Decision**: Integrated three components into a formal research pipeline:
1. **`quant-research` skill** — orchestrates the full pipeline: classify request → research (web/literature) → Council deliberation → recursive reconvene if contested → write to DEEPER_LEARNING.md.
2. **`the-council` Config G (Quantitative Research)** — 5-member deliberation panel: Mathematician, Empiricist, Skeptic, Engineer, Risk Manager. The only 5-member default config because quant research needs all five lenses — the gap between "mathematically elegant" and "implementable-profitable-survivable" is too wide for 4.
3. **`docs/DEEPER_LEARNING.md`** — append-only knowledge base. Every entry carries a convergence level (UNANIMOUS / STRONG_CONSENSUS / CONTESTED_RESOLVED / CONTESTED_UNRESOLVED) and a lifecycle status (THEORETICAL → CANDIDATE → ACTIVE / REJECTED). DL-001 (cross-sectional momentum) seeded from existing backtest validation.
**Recursive Reconvene Protocol**: When the Council Chair detects genuine unresolved tension, contested claims are narrowed and re-deliberated (max 3 rounds, aperture shrinks each round). Prevents infinite loops while ensuring real disagreements get resolution attempts.
**Convergence rules**: CONTESTED_UNRESOLVED entries still land in DEEPER_LEARNING.md with a minority report — disagreement is logged, not buried.
**What triggered this**: Mean reversion backtest results (Phase 3 P1) demonstrated that "understood" ≠ "validated." A 5-member Council would have flagged the 0.836 cross-sectional correlation with momentum before the build, not after.
**Files changed**: `docs/DEEPER_LEARNING.md` (created), CLAUDE.md (research pipeline section added), LEARNING.md (this entry). Skills installed globally to `~/.claude/skills/`.

### 2026-05-22 — Universe swap: ZAG.TO removed, CHPS.TO added to growth bucket
**Context**: Council session evaluating AI-boom ETF additions. Engine was at 9-ticker Tier 1 max. Adding required removing. ZAG.TO identified as the weakest link: 0.97 correlation with VAB.TO (same Canadian aggregate bond exposure, same MER, smaller AUM). Removing it costs zero diversification.
**Decision**: Replace ZAG.TO (stable, redundant) with CHPS.TO.TO (Global X AI Semiconductor Index ETF, growth bucket).
**CHPS.TO rationale**:
- TSX-listed, CAD-denominated — passes Tier 1 constraints
- 1,234 trading days of history (June 2021) — well above 252-day momentum lookback minimum
- MER 0.65% (management fee 0.45%) — confirmed via globalx.ca, no fee waiver
- Average daily volume ~32k shares — adequate liquidity for sub-$10k positions
- Holdings (NVDA 20.6%, TSMC 16.1%, Broadcom 15.2%, ASML 11.4%, AMD 7.2%) — includes TSMC and ASML not present in HXQ.TO/VFV.TO at meaningful weights; genuine incremental semiconductor exposure
- Momentum rank #1 (+1.000) on first live signal run (2026-05-22) — AI semiconductor boom already in the data
**STABLE_TICKERS change**: frozenset shrinks from 3 → 2 (VAB.TO, HSAV.TO). Stable equal-weight goes from 1/3 → 1/2 per ticker. Test updated to `1.0 / len(STABLE_TICKERS)` to stay dynamic.
**Rejected candidates this session**: CIAI.TO (0.68% MER, same top-5 as HXQ.TO), INAI.TO (good MER but heavy overlap with HXQ.TO), MTRX.TO (Jan 2025 launch — insufficient history), AIQ.TO / ARTI.TO (too new). TEC.TO deferred — XEF.TO still provides geographic diversification not in TEC.TO.
**Lesson**: Redundancy in the stable bucket is a quiet drag. Two correlated tickers that both track Canadian aggregate bonds consume a universe slot for zero diversification benefit. Audit for ticker-level correlation, not just bucket-level balance.

### 2026-05-22 — Mean reversion signal design (Phase 3 P1)
**Context**: Mean reversion is the classic counterpart to momentum — buy recent losers, sell recent winners. Built it to test whether a 9-ETF Canadian universe has enough cross-sectional dispersion for the signal to show edge.
**Key design decisions** (grill-me session before any code):
- **Interface**: `generate(prices)` only — regime computed internally via `VolRegimeSignal` so the `Signal` ABC interface stays clean. No extended signature, no constructor injection.
- **Z-score formula**: Rolling z-score of **daily log returns** at 20d (short-term reversal, Jegadeesh/Lehmann 1990) and 60d (intermediate reversion). `z_ts = 0.5 × z_20 + 0.5 × z_60`. This asks "was today's return extreme relative to recent history?" — not a cumulative window z-score.
- **TS normalization**: `tanh(z_ts)` compresses raw z-scores to (−1, 1) while preserving rank ordering and handling outliers smoothly. Rejected: clip/3 (linear, less elegant), per-ticker rolling rank (adds second window, heavier).
- **CS component**: Rank-normalize z_ts across all tickers at run_date → [-1,+1]. Same `_rank_normalize()` method as momentum.
- **Regime-conditional blend**: `combined = w_ts × tanh(z_ts) + w_cs × z_cs`. Weights: CRISIS (0.70/0.30), HIGH_VOL (0.60/0.40), NORMAL (0.50/0.50), LOW_VOL (0.35/0.65). In CRISIS, idiosyncratic TS signal dominates (tickers decorrelate). In LOW_VOL, cross-sectional rank is more informative (high correlation = relative positioning matters).
- **Sign flip**: Multiply combined by −1 before final rank-normalize. Oversold (negative z) → positive (buy) signal.
- **Warmup**: <60 rows → score 0.0 (neutral), same pattern as momentum.
- **Dashboard**: CLI-only for now. `render_signal_scorecard()` is hardwired for momentum; plugging MR in would require signature changes across 3 files. Deferred until signal proves standalone value.
**Files**: `src/signals/mean_reversion.py`, `tests/test_mean_reversion.py`, `src/cli/phase2_commands.py`
**Tests**: 16 unit tests, all passing.

### 2026-05-22 — Mean reversion backtest results: standalone signal not viable on 9-ETF universe
**Context**: Ran 5-year walk-forward backtest (top-4, monthly rebalance, VFV benchmark) against mean reversion signal.
**Results**:
| Metric | Mean Reversion | Momentum baseline |
|---|---|---|
| Ann. return | +4.24% | +13.98% |
| Ann. vol | 9.93% | 11.75% |
| Sharpe | −0.027 | 0.807 |
| Sortino | −0.038 | 1.035 |
| Max drawdown | **−24.18%** | −15.9% |
| Calmar | 0.175 | 0.879 |
| Alpha vs VFV | **−6.59%** | +1.19% |
| Beta | 0.527 | 0.685 |
| Monthly win rate | 55.7% | — |
| Monthly corr vs momentum | **+0.836** | — |
**Verdict**: Standalone mean reversion fails on this universe. Three disqualifying findings:
1. Max drawdown −24.18% **violates the 20% soft ceiling** — the system's core risk constraint.
2. Sharpe −0.027 — the strategy barely beats cash after adjusting for vol. Momentum delivers 0.807.
3. Monthly return correlation with momentum is 0.836 — nearly identical signal. No ensemble diversification benefit. Blending two 0.84-correlated signals produces negligible covariance reduction.
**Why does MR struggle on this universe?**
- 9 ETFs is too few for cross-sectional dispersion. Most are highly correlated equity ETFs (growth×4, dividend×2); the "loser" in any given month is often structurally different (bonds in a rate-hike year), not a mean-reverting equity.
- Monthly rebalance is too slow for the 20d z-score window. Jegadeesh/Lehmann short-term reversals operate at 1-week horizons, not 1-month. By the time the monthly rebalance fires, the reversal has already resolved (or deepened into a real trend).
- Both MR and momentum are cross-sectional ranking signals on the same 9-ticker universe. With equal portfolio construction (top-4 equal-weight), they end up holding mostly the same tickers but in different order — hence 0.836 correlation.
**Decision**: Mean reversion signal is **complete and tested as built**, but removed from the active Phase 3 roadmap as a primary portfolio construction signal. Potential future uses:
1. **Position sizing modifier** in the recommendation engine: very negative z_ts = caution flag before adding to a position, even if momentum is positive.
2. **Revisit at Tier 2+** when universe expands to individual stocks — cross-sectional dispersion is much higher with 20–40 names, and stock-level reversals are well-documented.
3. **Intraweek rebalance experiment**: if rebalance frequency drops to 5d, the 20d window may show edge.
**No action needed**: Signal lives in the codebase, tests pass, CLI accessible via `quant signals --signal-type mean_reversion`. Not wired into the recommendation engine.

### 2026-05-20 — Phase 3 P0: Trade Recommendation Engine
**Context**: Phase 2 complete (signals, backtester, dashboard). Building the first actionable output: trade cards that survive cost, CRA, and min-hold gates.
**Decision**: Built signal-proportional weight engine + full recommendation pipeline. 11 design decisions resolved before a line was written (grill-me session).
**Key choices**:
- Signal-proportional weights within buckets (no Markowitz optimizer). Optimizer added in P3.2 when NAV justifies covariance estimation precision.
- Combined signal = momentum × max(regime_score, 0). Clamping to 0 in HIGH_VOL/CRISIS prevents sign-flip artifacts (neg × neg = pos) that would otherwise buy anti-momentum tickers in bad regimes.
- Stable bucket uses equal weight (1/3 each). Regime does not gate stable allocation — bonds are always needed for diversification; momentum is not the right signal for fixed income selection.
- Cost gate operates on delta (after weight assignment), not on raw signal. Gate in dollar terms: expected_return ≥ 2×spread + 0.5% floor.
- BUY-only in P0. Sells deferred until NAV is large enough that drift correction is worth a trade slot.
- Flat 0.05% spread proxy. spread_override hook added to universe.yaml for Tier 3+ per-ETF calibration.
- --cash required when NAV=0. Raises clear error (not silent zero-card output). Optional when NAV>0.
- CRA gate: warn at 20 trades, show CRA_LIMIT at 24 — pipeline always runs, Arsh decides.
- MIN_HOLD hard gate: 14 days, from trades table. Legal boundary until professional account justified.
- quant execute <rec_id> is atomic: updates recommendation + creates trade record in one command.
**Files**: src/portfolio/recommendations.py, src/cli/phase3_commands.py
**Tests**: 22 unit tests, all passing.

### 2026-05-20 — Professional account trigger conditions (future decision)
**Context**: MIN_HOLD and CRA max-trade constraints currently enforce legal boundary for TFSA.
**Decision**: Revisit opening a non-registered/professional account when either (a) annual trade count approaches 24, or (b) NAV reaches $5k first threshold.
**Rationale**: At sub-$5k NAV the tax sheltering of TFSA outweighs the trading flexibility of a margin account. Once NAV grows, the calculus changes.

### 2026-05-20 — Phone alert pipeline: ntfy.sh for Phase 3 P2
**Context**: Phase 3 P2 will introduce scheduled daily auto-runs that push a phone notification when a signal fires or a trade card is ready. Options evaluated: Telegram bot, ntfy.sh, email.
**Decision**: ntfy.sh for one-way push alerts. Revisit Telegram only if/when two-way interactive trade approval (inline buttons, `/approve trade_id`) is needed.
**Rationale**: ntfy.sh is a single HTTP POST — no bot creation, no token, no chat_id storage, no rate-limit games. Free public instance is sufficient for now; self-hostable on a $5 VPS later if privacy matters. Both ntfy.sh and Telegram are HTTP under the hood, so the alert dispatch module can add a second backend without a rewrite. Email ruled out for delivery latency.
**Revisit when**: Interactive trade approval is needed (Phase 4+).

### 2026-05-20 — Covariance estimation: Ledoit-Wolf shrinkage, not raw sample covariance
**Context**: Phase 3 optimizer needs a covariance matrix. The naive choice is the sample covariance of daily returns.
**Decision**: Use `sklearn.covariance.LedoitWolf` with constant-correlation target throughout the optimizer. Sample covariance fallback only if N ≤ 5 (degenerate case). Re-evaluate at Tier 4 if N approaches 50+ (may need Ledoit-Wolf 2020 non-linear shrinkage at that scale).
**Rationale**: Sample covariance becomes unreliable as N (assets) approaches T (observations). At Tier 1 (9 ETFs × 1260 obs) the ratio is safe, but at Tier 2/3 (20–40 names) estimation error dominates. Markowitz puts its biggest bets on the most extreme covariance entries — exactly the ones that are most noise-contaminated. Ledoit-Wolf pulls extreme correlations toward a structured target with analytically computed shrinkage intensity; no hyperparameter tuning, no cross-validation. Building Phase 3 with raw sample covariance would produce a working Tier 1 backtest and a numerical instability rewrite at Tier 2.
**Implementation note**: `sklearn.covariance.LedoitWolf().fit(returns).covariance_` is 4 lines. `skfolio.moments.LedoitWolf` adds a force-positive-definite option worth using in the optimizer.

### 2026-05-19 — Phase 2: Signal engine + backtesting + API dashboard
**Context**: Phase 1 complete (data pipeline, metrics, CLI). Moving to signal generation.
**Decision**: Built three components simultaneously: (1) momentum + vol regime signals, (2) walk-forward backtesting framework, (3) FastAPI server for web dashboard.
**Rationale**: Signals without backtests are dangerous. Dashboard without signals has nothing to show. All three needed to land together for Phase 2 to be useful.

### 2026-05-17 — Manual execution architecture chosen over IBKR automation
**Context**: Considered switching from Wealthsimple TFSA to Interactive Brokers Canada for API-driven automated execution.
**Decision**: Stay with Wealthsimple TFSA. Manual execution. System generates trade cards, operator executes via Wealthsimple app.
**Rationale**:
1. CRA day-trading rule reclassifies TFSA gains as taxable business income. Automated execution amplifies that risk.
2. At current capital tier ($500–1000), API speed offers zero edge — signals operate at weekly-monthly timescales.
3. Wealthsimple has $0 commission on Canadian ETFs vs IBKR's $1 minimum.
4. Manual execution adds a human circuit breaker against runaway bugs.
**Revisit when**: Capital reaches Tier 3 ($25k+) AND a real intraday strategy is validated by backtest.

### 2026-05-17 — Three-bucket framework retained as hybrid guardrails
**Context**: Choice between (a) keep buckets fixed, (b) let optimizer override, (c) hybrid.
**Decision**: Hybrid. Bucket weights (60/25/15) are guardrails with ±10/±5/±5 tolerance. Optimizer works *within* buckets. Bucket weights themselves only shift on regime signals.
**Rationale**: Pure Markowitz on a small universe overconcentrates. Operator's existing mental model is buckets — preserving it reduces friction. Math still gets to optimize within the structure.

### 2026-05-17 — Horizon set to 3–7 years (Path C)
**Context**: Original ask was 1–3 year horizon with 20% drawdown ceiling and S&P 500 benchmark. These conflicted mathematically (~30% probability of breaching 20% DD over 1–3yr horizon).
**Decision**: Extend horizon to 3–7 years. Keep 20% soft drawdown ceiling. Interim benchmark VBAL, stretch benchmark VFV.
**Rationale**: Operator's true exit is decades away, not 2027. Horizon honesty unlocks the growth allocation without breaking the risk math.

### 2026-05-17 — Canadian-listed ETFs only at Tier 1
**Context**: Asset universe scope.
**Decision**: Lock to 9 Canadian-listed ETFs: VFV, XIC, HXQ, XEF, VAB, ZAG, HSAV, CDZ, VDY.
**Rationale**: Avoid 1.5% Wealthsimple FX drag. Optimizer has enough degrees of freedom without overfitting risk. Universe expands automatically at capital tier breaks.

---

## 🐛 Mistakes & Corrections

> Bugs, bad signals, misjudgments. Post-mortem format. Pain teaches.

### 2026-05-19 — Backtest engine sliced bottom-N instead of top-N tickers
**What happened**: `quant backtest` showed 0.0 return, 0.0 vol, NaN Sharpe — strategy held cash every single period.
**Root cause**: `result.ranked()` returns scores descending (highest first). `ranked[-top_n:]` slices the *last* N items — the lowest-scored tickers (bonds at -1.0 to -0.25). The `if s > 0` guard then filtered all of them out → empty holdings → cash.
**Impact**: Every backtest run since Phase 2 landed would have returned zeros. No bad trade fired, but the backtest was useless.
**Fix**: Changed `ranked[-config.top_n:]` to `ranked[:config.top_n]` in both the long-only and short-allowed branches of `engine.py`.
**Guardrail added**: When slicing a ranked list, always comment the sort direction. `ranked()` is descending by default — `[:N]` = top N, `[-N:]` = bottom N.
**Test added**: Need a backtest unit test that asserts `avg_holdings_per_period > 0` on a universe with known positive signals. (TODO Phase 2 test gap.)

### 2026-05-19 — Flaky test fixture: weak random drift doesn't guarantee momentum rank ordering
**What happened**: `test_momentum_ranks_correctly` and `test_momentum_downtrend_is_negative` failed intermittently. Mock DOWN.TO ticker (seed 3, drift -0.001/day) produced higher 12-1 momentum than FLAT.TO in the specific random realization.
**Root cause**: Daily drift of ±0.001 is swamped by 0.01 volatility over a 231-day window. The expected direction of cumulative return is not guaranteed with small samples.
**Impact**: False test failure — signal logic was correct, fixture was wrong.
**Fix**: Replaced stochastic fixture with deterministic `np.linspace`/`np.full` price series that guarantee the expected rank ordering by construction.
**Guardrail added**: Use deterministic data in signal unit tests. Reserve stochastic fixtures for stress/randomized tests, not assertion of specific ordering.
**Test added**: `mock_prices` fixture now uses linspace(100→200), full(100), linspace(100→50) for UP/FLAT/DOWN tickers.

### 2026-05-19 — Empty Series with RangeIndex crashes momentum signal on Timestamp comparison
**What happened**: `MomentumSignal.generate()` raised `TypeError: '<=' not supported between instances of 'numpy.ndarray' and 'Timestamp'` when passed `pd.Series(dtype=float)` (empty, RangeIndex).
**Root cause**: Empty series created without an explicit index defaults to `RangeIndex(dtype=int64)`. Filtering `series[series.index <= pd.Timestamp(run_date)]` fails because int64 index can't compare to Timestamp.
**Impact**: Any caller passing an empty or non-datetime-indexed series would crash the entire signal run.
**Fix**: Added early guard in the per-ticker loop: skip and mark as neutral if series is empty or has int64 index.
**Guardrail added**: Check `price_series.empty` before any index-based filtering in signal models.
**Test added**: `test_momentum_handles_empty_series` — confirms empty series returns score 0.0 (neutral) without raising.

**Template**:
```
### YYYY-MM-DD — [Short description]
**What happened**:
**Root cause**:
**Impact**:
**Fix**:
**Guardrail added**:
**Test added**:
```

---

## 📚 Concepts Learned

> Quant finance concepts as Arsh internalizes them. Building the mental model.

*Add entries as concepts click. Format: concept name → one-line definition → why it matters here → reference.*

**Template**:
```
### YYYY-MM-DD — [Concept name]
**Definition (in own words)**:
**Why it matters for this project**:
**Reference**:
**Code where it's used**:
```

---

## ❓ Open Questions

> Things we don't know yet. Triaged when answered (move to Decisions log).

### 2026-05-17 — How do we estimate covariance with only 1–2 years of history before relying on backtest signals?
~~Shrinkage estimators (Ledoit-Wolf)? Just trust 5+ years of ETF history?~~
**Answered 2026-05-20** → See Decision: "Covariance estimation: Ledoit-Wolf shrinkage, not raw sample covariance."

### 2026-05-17 — Phone alert pipeline: Telegram bot vs ntfy.sh vs email?
~~Telegram has bot API + push notifications free. ntfy.sh is dead simple. Email has delivery latency. Decide before Phase 2.~~
**Answered 2026-05-20** → See Decision: "Phone alert pipeline: ntfy.sh for Phase 3 P2."

### 2026-05-17 — Regime detection method: hidden Markov model, simple vol thresholds, or VIX-based?
Test all three on backtest in Phase 2.

---

## 📊 Performance Log

> System performance snapshots. Filled in once Phase 1 is running.

### 2026-05-19 — First data pipeline run (pre-trade baseline)
**Portfolio NAV**: $0.00 (no holdings yet — first trade pending)
**MTD return**: n/a
**YTD return**: n/a
**Sharpe (rolling 1yr)**: n/a
**Max drawdown (rolling 1yr)**: n/a
**Benchmark (VBAL) return YTD**: n/a
**Alpha YTD**: n/a
**Notes**: Phase 1 data pipeline operational. `python -m src.cli.main fetch --years 20` completed
successfully for all 9 tickers. Row counts: VFV.TO 3393, XIC.TO 5018, HXQ.TO 2528, XEF.TO 3286,
VAB.TO 3593, ZAG.TO 4094, HSAV.TO 1573, CDZ.TO 4942, VDY.TO 3393. HSAV has shortest history
(~6yr) due to 2019 launch date — expected. YAML parse bug fixed (unquoted colon in VFV name field).
Metrics module confirmed running. Ready for first manual buy via `trade` command.

**Template**:
```
### YYYY-MM-DD — Monthly snapshot
**Portfolio NAV**:
**MTD return**:
**YTD return**:
**Sharpe (rolling 1yr)**:
**Max drawdown (rolling 1yr)**:
**Benchmark (VBAL) return YTD**:
**Alpha YTD**:
**Notes**:
```

---

## 🎯 Next Steps (Rolling)

> Top of mind. Reordered as priorities shift. Items move to "Done" when complete.

### Active
- [ ] Phase 1 Milestone 1: Data pipeline pulling 20yr daily OHLCV for 9 ETFs into SQLite
- [ ] Phase 1 Milestone 2: Portfolio model + holdings ledger
- [ ] Phase 1 Milestone 3: Core risk metrics module with unit tests
- [ ] Phase 1 Milestone 4: CLI dashboard (`quant status`, `quant metrics`, `quant fetch`)
- [ ] Phase 1 Milestone 5: First end-to-end run — fetch data, compute metrics, print dashboard

### Backlog (Phase 2)
- [ ] Momentum factor signal
- [ ] Mean reversion signal
- [ ] Volatility regime detection
- [ ] Backtesting framework
- [ ] Phone alert pipeline (Telegram bot)

### Done
*(items move here on completion)*

---

*Last edited: 2026-05-19, Bug #6 fix.*

---

**Mistake & Correction — 2026-05-19**

**Bug #6: VolRegimeSignal silently degraded to regime=unknown due to insufficient lookback**

`VolRegimeSignal.lookback_days` = 1291 (history_window 1260 + vol_window 21 + padding 10). Two callers loaded prices with a hardcoded 1260-day window:
- `src/api/server.py` `/api/signals` endpoint called `_load_prices()` with no argument, using the 1260 default.
- `src/portfolio/model.py` `price_series()` default was `252*5 = 1260`.

The signal's `generate()` guard (`len(prices[benchmark]) < self.lookback_days`) silently returned `regime=unknown, scores=0.0` — no exception, no warning to the caller.

**Fix:**
1. `server.py` `/api/signals`: instantiate the signal first, then call `_load_prices(sig.lookback_days)`.
2. `model.py`: bumped `price_series()` default from `252*5` to `252*6` (1512 days) as a safety margin.
3. `phase2_commands.py`: removed the redundant `max(..., 1260)` floor — `sig.lookback_days` is already the correct minimum.

**Lesson:** Silent neutral fallback (`score=0.0`) on insufficient data is correct behavior for signal integrity, but callers must actively use `sig.lookback_days` to size the fetch window. Never hardcode a lookback constant that could silently undercut a signal's required history.
