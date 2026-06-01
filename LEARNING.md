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

### 2026-05-30 — v1.2.0 Guardrails: 22-finding Tier 1 code-review cleanup before any Tier 2 work

**Context**: A Tier 1 code review (`docs/reviews/2026-05-29-tier1-code-review.md`) surfaced 22 findings spanning real-money safety, signal-contract correctness, persistence robustness, and stale docs. Closed on branch `fix/v1.2.0-guardrails`, TDD, one atomic commit per finding. Operator decisions locked before execution (no relitigation mid-flight).

**Real-money safety (operator-locked):**
- **F1 (CRA 24-cap)** — `execute_command` now hard-blocks at `≥ max_trades_per_year`; `--force --justification "..."` is the only override, and it is logged to `run_log`. Warn-at-20 unchanged. The cap is a legal boundary (day-trade reclassification risk on a TFSA), not a soft preference.
- **F2 (drawdown ceiling)** — soft-halt: at `current_dd ≥ risk.max_drawdown` (0.20) new BUY cards are suppressed (→ SKIP / `DRAWDOWN_HALT`); SELL/HOLD/WARN still flow (risk reduction must never be blocked). Pure fn `apply_drawdown_halt`, config toggle `risk.drawdown_halt_enabled`, RISK HALT banner, and a distinct ceiling note folded into the drawdown ntfy alert.
- **F3/F4 (fail-loud)** — `fetch` retries with backoff and exits non-zero past `data.fetch_max_failures`; `signals` exits non-zero on unknown type / empty data / 0-row save. Silent partial-data runs were the worst latent failure mode.
- **F5 (drift-SELL exemption)** — *ratified, not changed*: a rebalancing trim stays exempt from the profit-floor gate (it is risk-control, not alpha) but now populates `cost_estimate = 2 × spread` for audit, and the exemption is documented in CLAUDE.md Hard Constraint 3 so code and policy agree.

**Contract / persistence consolidation:**
- **F6/F10/F20/F14** — `SignalResult.ticker_metadata` is now an allow-list (`_PER_TICKER_KEYS` + rename map): structural dicts like `regime_weights` are preserved, per-ticker keys renamed to singular (`z_ts`, `rsi_value`), run-level lists dropped from per-row persistence. `STABLE_TICKERS` is derived from `universe.yaml` (`_derive_stable_tickers`) — one bucket-truth source, no second hardcoded list to drift.
- **F15** — replaced `migrate_recommendations_v2/v3` + a module-global `_migrated` guard with a `schema_version`-tracked `run_migrations()` runner. Each migration applies exactly once; v2/v3 kept as back-compat shims. This is the pattern any future schema change must use.
- **F11** — daily run dropped the redundant standalone `signals --save` steps; `recommend --save` already re-persists momentum + vol_regime under one `run_id`, so a date's signal_scores no longer fragment across run_ids.

**F7 (doc honesty)** — corrected the CLAUDE.md "all modules read capital_tier / scale automatically" claim: `capital_tier` is declared-but-inert today; the Tier 1 universe lock is what's actually enforced (universe.yaml membership + `execute_command` check); runtime tier-switching is a Tier 2 deliverable, deliberately **not** built now.

**Outcome**: 204 → 234 tests, all green. Tag `v1.2.0-guardrails`. F18 was moot (review referenced a `db_path` param `DailyRunner.__init__` never had). This was the cost of velocity in Phase 3 — the guardrails were specified in CLAUDE.md but the enforcement and the docs had drifted from each other; v1.2.0 reconciles them before capital scales.

---

### 2026-05-28 — Tier 1 Complete: system declared production-ready, v1.0.0-tier1 tagged

**Context**: All seven originally planned Tier 1 subsystems shipped. The engine has been running for ~9 days (first commit 2026-05-19). Every subsystem has targeted test coverage and has been validated against real data.

**What production-ready means for this system:**
- **Daily auto-run**: `DailyRunner` + Windows Task Scheduler (P3.6) runs `fetch → momentum signal → vol_regime signal → recommend --optimize --save --notify` every morning without operator intervention. Step failures are reported via ntfy.sh.
- **Persistence**: All state in SQLite — prices, holdings, trades, recommendations, signal_scores, alerts_log, run_log, metrics_snapshots. Nothing lives only in memory. Daily runs persist every signal score and trade card.
- **Phone alerts**: Three triggers wired: NEW_RECOMMENDATION, REGIME_CHANGE, DRAWDOWN (>15% threshold). DRAWDOWN state machine fires once on crossing, logs a RECOVERED row on exit — prevents alert spam on repeated crossings.
- **BUY/SELL/rebalance**: Full recommendation lifecycle. Signal-driven full exit (negative signal). Drift-triggered partial trim (bucket tolerance exceeded). `sell_reason` field distinguishes the two. All routed through the same `quant recommend` + `quant execute` pipeline.
- **Within-bucket optimizer**: Ledoit-Wolf covariance + SLSQP. `quant recommend --optimize` produces Markowitz-weighted trade cards. Equal-weight fallback preserved on solver failure.
- **Hypothesis pipeline**: Council-validated research pipeline at `docs/research/`. Four hypotheses entered, all resolved: H001 (KILLED, parameter failure — 9-ETF universe too small for MR), H004 (KILLED, structural failure — leverage effect absent 7/7 ETFs), H005 (KILLED, structural failure — RSI/momentum mathematical redundancy), H006 (SHELVED, ETF structural incompatibility). 14 DEEPER_LEARNING entries written (DL-001 through DL-014).
- **Test suite**: 204 tests across 14 files, all passing. Every subsystem has targeted coverage.

**Tags**: v0.3.0-signal-persistence → v0.4.0-alerts → v0.5.0-daily-run → v0.6.0-test-coverage → v0.7.0-hypothesis-cleanup → **v1.0.0-tier1**

**Tier 2 trigger**: NAV reaches $10,000 CAD.

---

### 2026-05-28 — H004 (vol targeting) and H005 (RSI filter) hypothesis cleanup: both KILLED

**Context**: Two hypotheses at CANDIDATE status with mandatory backtests pending. H004 (Moreira-Muir portfolio-level vol scaling, DL-007) had no hypothesis file yet. H005 (RSI(21) > 50 momentum gate, DL-012) was already KILLED with backtest results recorded but two deliverables missing: LEARNING.md result table and DL-012 supersession.

**H004 — Volatility Targeting (Moreira-Muir Scaling). KILLED. 2 of 6 kill criteria triggered.**

Backtest: 5yr walk-forward 2021-05-28 to 2026-05-28, top-4 equity selection, monthly rebalance. Vol scaling applied to portfolio weights after signal ranking (not to signal scores — rank order preserved). Equity bucket only (7 tickers: VFV/XIC/HXQ/XEF/CHPS/CDZ/VDY).

Pre-backtest checks:
| Check | Result |
|-------|--------|
| Leverage effect: Corr(fwd_ret, RV) sign | All 7/7 equity ETFs POSITIVE (+0.03 to +0.30). Kill criterion triggered. |
| Corr(vol_regime_score, portfolio_RV) | -0.3478. PASS (threshold |corr| > 0.85). |
| 21d RV vs EWMA Sharpe delta | -0.024 (EWMA loses marginally). PASS (threshold > 0.10). |

Walk-forward results:
| Metric | Vol-Target (RV21) | Equal-Weight Baseline | Pass/Fail |
|--------|-------------------|-----------------------|-----------|
| Sharpe | 1.0623 | 0.9768 | PASS |
| Max DD | -17.28% | -18.20% | PASS |
| Alpha vs VFV | +4.94% | +4.05% | PASS |
| Corr vs baseline (monthly returns) | 0.9862 | -- | **KILL** |

Kill criteria triggered:
1. **Leverage effect absent (7/7 positive)**: Moreira-Muir's precondition is Corr(E[r_{t+1}], sigma^2_t) < 0. All equity ETFs show the opposite on 2021-2026 data. COVID recovery + AI boom produced high-vol months followed by rallies, not drawdowns. Formula has no theoretical basis when the leverage effect is inverted.
2. **Returns correlation 0.9862**: Vol-targeted strategy is operationally indistinguishable from equal-weight baseline. Scaling within the same top-4 tickers without changing selection produces near-zero portfolio-level differentiation.

Structural failure on leverage effect (not parameter issue). Revisit at Tier 2+ if Corr(fwd_ret, RV) turns negative on Canadian individual equities.

Files: `docs/research/hypotheses/H004_vol_targeting.md` (KILLED), `docs/research/graveyard/H004_vol_targeting.md` (autopsy), `docs/research/scratch/H004_vol_targeting_backtest.py` (research script).

---

**H005 — RSI(21) > 50 Momentum Filter. KILLED. 3 of 3 kill criteria triggered.** (Backtest run 2026-05-26; deliverables completed 2026-05-28.)

Backtest results (from `tests/test_H005_rsi_backtest.py`, code `src/signals/rsi.py`):

Window 1 — 9-ETF universe (2023-07 to 2026-04, 34 months):
| Metric | Baseline (no gate) | + RSI(21) monthly | + EMA(12) monthly | Pass/Fail |
|--------|-------------------|-------------------|-------------------|-----------|
| Sharpe | 1.86 | 1.86 | 1.86 | -- |
| t-stat (incremental alpha) | -- | **NaN** (zero variance) | -1.09 | **KILL** (need > 3.0) |
| Agreement rate (mom vs gate) | -- | 96.2% | 92.0% | **KILL** (< 0.81 means gate matters; > means redundant) |

Window 2 -- 8-ETF extended (no CHPS.TO, 2017-06 to 2026-04, 107 months):
| Metric | Baseline (no gate) | + RSI(21) monthly | + EMA(12) monthly | Pass/Fail |
|--------|-------------------|-------------------|-------------------|-----------|
| Sharpe | 1.11 | 1.11 | 1.10 | -- |
| t-stat (incremental alpha) | -- | **-1.00** | -1.53 | **KILL** |
| Agreement rate | -- | 83.5% | 83.8% | **KILL** |

Divergence analysis (8-ETF extended) -- when momentum says BUY but gate says NO:
| Gate | Mom=ON, Gate=OFF forward return | Both=ON forward return |
|------|--------------------------------|------------------------|
| RSI(21) monthly | **+7.30%** | +1.02% |
| EMA(12) monthly | +2.08% | +1.00% |

Kill criteria triggered: (1) t-stat NaN/−1.00 (need > 3.0); (2) gate suppresses valid signals (+7.30% forward return when blocked); (3) 96.2%/83.5% agreement rate (mathematical redundancy confirmed empirically).

Structural failure: RSI(21) at monthly frequency is a bounded monotonic transform of the same positive-drift construct as 12-1 momentum. Marshall et al. 0.81-0.91 correlation prediction confirmed. No parameter tuning (period or threshold) fixes this -- the mathematical equivalence is structural.

Files: `docs/research/hypotheses/H005_rsi_momentum_filter.md` (KILLED), `docs/research/graveyard/H005_rsi_momentum_filter.md` (autopsy), `src/signals/rsi.py` (preserved, not in signal path), `tests/test_rsi_signal.py`, `tests/test_H005_rsi_backtest.py`.

---

### 2026-05-28 — Phase 3 P3.7: Test coverage pass

**Context**: Three known gaps in the test suite since Phase 2: (1) no test asserting the backtest engine actually holds tickers (avg_holdings_per_period > 0), only that it runs without error; (2) no test for BacktestResult.summary_str(), which didn't exist yet; (3) no integration test joining all three pipeline layers (signal → backtest → recommend). Additionally, two DRAWDOWN/REGIME_CHANGE alert state-machine paths were untested: the first-run case where get_last_alert() returns None.

**Decision**: Added BacktestResult.summary_str() to engine.py (returns formatted multi-line string with all key metrics). Created tests/test_backtest.py (8 tests: avg_holdings_per_period assertion, summary_str() content/dates/signal-name, insufficient-data ValueError, rebalance_log non-empty, metrics keys present). Created tests/test_integration.py (11 tests across three classes: TestSignalLayer verifies momentum scores; TestBacktestLayer verifies holdings and rebalances; TestRecommendLayer verifies BUY cards produced and ValueError on zero capital). Added test_regime_change_fires_on_first_run_no_prior_alert and test_drawdown_warning_first_run_fires_when_exceeds_threshold to test_alerts.py.

**Key design choice — integration test avoids real VolRegimeSignal**: VolRegimeSignal requires 1291 rows of XIC.TO history. Constructing that in a test fixture would be slow and couple the integration test to a specific signal's data requirement. Instead the regime SignalResult is constructed directly — the regime signal is already unit-tested in test_signals.py. The integration test focuses on layer connectivity, not signal correctness.

**Result**: 184 → 204 tests, all passing. Tagged v0.6.0-test-coverage. Known test gaps section in PROJECT_STATUS.md cleared.

**Files**: `src/backtest/engine.py` (summary_str), `tests/test_backtest.py`, `tests/test_integration.py`, `tests/test_alerts.py`, `docs/PROJECT_STATUS.md`.

### 2026-05-28 — Phase 3 P3.6: Scheduled daily run
**Context**: Engine signals and recommendations were only generated when the operator manually ran `quant recommend`. No automation existed — daily data fetch and signal generation required manual CLI invocation.
**Decision**: DailyRunner class in `src/cli/daily_run_command.py` orchestrates four CLI steps (fetch → momentum signal → vol_regime signal → recommend --optimize --save --notify) via subprocess. Runs all steps regardless of individual failures (fail-fast would skip the recommend step if a signal step errored). Error alerts via ntfy.sh at priority=5 on any step failure. Two callers: `scripts/daily_run.py` (Task Scheduler entry point, writes dated log) and `quant daily-run` (interactive manual trigger, stdout only). Windows Task Scheduler registered via `scripts/setup_scheduler.ps1` with dual triggers: daily at configurable time (morning or post-close, commented variable at top) and at-logon fallback. `-WakeToRun ON`, `-StartWhenAvailable ON` so laptop (plugged in, lid open at home) wakes for the scheduled run. `logs/bat.log` overwritten each run (startup failures only); `logs/YYYY-MM-DD.log` appended (DailyRunner owns signal output and trade cards).
**Key invariant**: All state persisted via `--save` flags on signals and recommend. DailyRunner never bypasses the CRA 24-trade/year cap or 14-day min-hold gate — those remain in `quant recommend`.
**Files**: `src/cli/daily_run_command.py`, `scripts/daily_run.py`, `scripts/daily_run.bat`, `scripts/setup_scheduler.ps1`, `tests/test_daily_run.py` (9 tests), `src/cli/main.py`, `config/portfolio.yaml`.

### 2026-05-27 — Phase 3 P3.5: ntfy.sh phone alert pipeline
**Context**: `quant recommend` was purely a terminal tool. No notification fires when signals trigger while the operator is away from the computer.
**Decision**: ntfy.sh one-way push alerts (confirmed from 2026-05-20 decision). Three triggers wired into `recommend_command --notify`:
- `NEW_RECOMMENDATION`: fires when ≥1 gate-passing BUY or SELL card is produced.
- `REGIME_CHANGE`: fires when the vol regime value shifts from the last persisted row in `alerts_log`.
- `DRAWDOWN` (config key `DRAWDOWN_WARNING`): transition detector — fires once on first crossing above 15% alert threshold; logs a RECOVERED row (no POST) when portfolio returns below threshold, enabling re-fire on the next crossing.
**Implementation**: `src/alerts/ntfy.py` (HTTP transport only, fire-and-forget); `alerts_log` SQLite table + `get_last_alert` / `log_alert` in `storage.py`; `_run_alert_triggers()` private helper in `phase3_commands.py`; `--notify` flag on `quant recommend`; `quant alert-test` command. `requests>=2.31.0` added. 16 new tests (4 transport + 4 storage + 8 trigger).
**Key invariant**: `send_alert` never raises — network failure logs a WARNING and returns. Recommendation pipeline integrity is not conditional on ntfy.sh availability.

### 2026-05-26 — Phase 3 SELL and Rebalance Logic
**Context**: Phase 3 P0 shipped BUY-only recommendations. The portfolio could accumulate positions that turned negative (signal-driven exits) or let bucket weights drift past tolerance bands (drift-triggered trims) without any way to reduce them. Lifted the BUY-only constraint.
**Design decisions locked (grill-me session 2026-05-26)**:
1. **Drift trigger — reuses `needs_rebalance` from `bucket_allocation()`**: A drift fires when `bucket_actual > target + tolerance` (the same boolean the bucket allocation table already computes). No separate `drift_threshold` config field — deleted from `portfolio.yaml`. One truth source, no synchronization risk.
2. **Signal-SELL cost gate**: `|combined_signal| × anchor_return ≥ 2 × spread + profit_floor`. Symmetric with the BUY gate. The direction check (signal < 0) is separate from the cost check — both must pass. A strong negative signal with a sub-threshold dollar impact still fires HOLD, not SELL.
3. **Drift-SELL cost gate**: `|delta_dollars| ≥ min_rebalance_trade` (new config field, default $50, under `rebalance:` block in `portfolio.yaml`). Dollar-based because drift is a percentage deviation but the cost penalty is in dollars; comparing percentages to a dollar floor was confusing. $50 floor prevents burning a trade slot on a 0.1-unit trim.
4. **Single `action="SELL"` with `sell_reason` field**: One action type, not two (`SELL_SIGNAL` / `SELL_DRIFT`). The CLI and execute workflow treat all SELLs identically; the distinction is logged as `sell_reason: "SIGNAL" | "DRIFT"` on the `TradeCard` and persisted in the `recommendations` table. Avoids branching in execute logic, keeps the card schema minimal.
5. **Signal-SELL = full exit, drift-SELL = partial trim**: Signal-SELL exits all held units (the signal has gone negative — no reason to hold any). Drift-SELL trims only the excess weight (`round(delta / price, 2)` units), not the entire position. This asymmetry is intentional: signal is conviction-based, drift is mechanical rebalancing.
6. **Tax-loss harvesting skipped**: TFSA has no capital gains tax. TLH is a taxable-account optimization only. Not applicable here.
7. **Same `quant recommend` + `quant execute` pipeline**: BUY-only guard dropped. SELL cards appear in the same `quant recommend` output, are stored in the same `recommendations` table, and are marked executed via the same `quant execute <ID>` command. No new commands needed.
**Schema change**: `sell_reason TEXT` column added to `recommendations` table. `migrate_recommendations_v3()` added for databases created before this change — `ALTER TABLE` adds the column with NULL default, no data loss.
**Tests**: 16 new tests in `tests/test_sell_logic.py`. 159/159 passing.
**Files**: `config/portfolio.yaml`, `src/data/storage.py`, `src/portfolio/recommendations.py`, `src/cli/phase3_commands.py`, `tests/test_sell_logic.py` (new).

### 2026-05-26 — H005 and H006 Council-validated research: RSI(21) momentum filter and volume spike regime indicator
**Context**: Two hypothesis candidates entered the quant-research pipeline. H005 asked whether RSI(21) > 50 adds measurable signal on top of the existing `momentum × regime` composite (ALGO_CHECK). H006 asked whether academic backing exists for volume spikes as a leading regime indicator in ETF markets (LITERATURE_SCAN).
**Research pipeline run**: Full 4-agent parallel pipeline — Academic Agent (7 databases each), Practitioner Agent (10 verified sites, both topics simultaneously), Replication/Criticism Agent (9 searches + 3 factor zoo checks each), inline Synthesis, Config G Council deliberation.
**H005 outcome — CANDIDATE (mandatory backtest gate)**: RSI(21) > 50 is mathematically near-redundant with the existing `momentum_score`. Both measure positive price drift; Marshall et al. (2017) found TSMOM/MA signal correlations of 0.81–0.91, and RSI is in the same mathematical family. Zero of 10 practitioner sources use RSI as a momentum gate; NAAIM explicitly categorizes RSI as "overbought/oversold," not momentum. Parameter RSI(21) has no academic grounding at monthly bar frequency (Wilder used 14 for daily bars). Factorzoo: RSI absent from all three major studies (Harvey et al. 2016, McLean & Pontiff 2016, Hou et al. 2020). Before any implementation: must measure empirical correlation of RSI(21) > 50 vs. momentum_score on this dataset, test the ~20% disagreement cases, clear Harvey et al. t > 3.0 bar, and compare against price > EMA(12) as a better-grounded alternative. Skeptic minority: file as SHELVED unless backtest is committed to this cycle.
**H006 outcome — SHELVED (Tier 2+ re-evaluation)**: The High-Volume Return Premium is real for individual developed-market equities (replicated in 41 countries, Kaniel et al. 2012) but three independent failure mechanisms block ETF application: (1) creation/redemption arbitrage flows contaminate ETF volume with non-informational noise (Ben-David et al. 2018); (2) the Gervais et al. visibility mechanism requires individual-stock investor attention dynamics absent in ETFs; (3) at portfolio-aggregate level, Baker & Stein (2004) show high turnover predicts LOWER returns — the opposite of H006's stated hypothesis direction. Monthly frequency destroys spike resolution. Factor zoo base rate for liquidity/trading-frictions signals: 93% failure (Hou et al. 2017). If volume signal is ever pursued, Baker & Stein's aggregate-turnover bearish read is the academically grounded direction, not a bullish spike flag. Mathematician and Skeptic minority: KILLED status preferred — direction conflict plus 7% base rate is sufficient.
**DEEPER_LEARNING entries added**: DL-012 (H005, CANDIDATE), DL-013 (H006, SHELVED).

### 2026-05-24 — quant-research skill upgrade: 4-agent parallel pipeline + expanded DEEPER_LEARNING template
**Context**: The original quant-research skill ran a single-threaded research path — one web search sweep → Council deliberation. There was no systematic separation of academic literature, practitioner evidence, and independent replication checks. The Council was receiving thin Briefs with only one source domain, which risks rubber-stamp consensus and misses the factor zoo literature entirely.
**Decision**: Full rewrite of `quant-research/SKILL.md` into a 4-agent parallel pipeline with structured execution phases:
1. **Academic Agent** — 7 databases: SSRN, arXiv q-fin, NBER, Google Scholar, Journal of Portfolio Management, Financial Analysts Journal, Journal of Finance. Extracts canonical source, secondary sources, mathematical specification, and replication papers from academic literature.
2. **Practitioner Agent** — 10 verified sites: AQR, Man Institute, Verdad, Alpha Architect, Research Affiliates, Flirting with Models, Robeco, NAAIM, Vanguard, Bank of Canada. Fires simultaneously with Academic Agent (Wave 1).
3. **Replication/Criticism Agent** — 9 targeted searches + 3 mandatory factor zoo checks (Hou/Xue/Zhang 2017, McLean/Pontiff 2016, Harvey/Liu/Zhu 2016). Fires after Academic Agent returns (Wave 2) because it depends on the canonical source list to drive targeted queries.
4. **Synthesis Agent** — Inline (no sub-agent dispatch). Integrates all three packages into a Consolidated Research Brief with Evidence Quality Rating and structured Open Questions for Council.
**Wave ordering rationale**: Academic and Practitioner are independent — parallel is safe. Replication is not independent: it needs the canonical claim list to target searches correctly. Firing it in Wave 1 would waste it on a generic query. Wave 2 after Academic returns means Replication hunts for evidence that either corroborates or challenges the specific claims from the primary papers.
**Template expansion**: `quant-research/templates/deeper_learning_entry.md` expanded with three new sections: Source Coverage (which of the 17 sources were checked), Replication Evidence (table: author, geography, period, result), Practitioner Consensus (what verified practitioners have said). Plus an Evidence Quality field in the entry header (Strong / Mixed / Weak / Insufficient).
**Deleted**: `quant-research/templates/DEEPER_LEARNING_SEED.md` — superseded by the expanded template.
**Quality floor raised**: A research session is only considered complete when all 10 practitioner sites are checked, factor zoo papers explicitly consulted, and at least one Council Open Question addresses replication strength and one addresses Canadian ETF applicability. "No content found" is a valid and meaningful result — gaps in practitioner engagement are informative.
**Why this matters**: The mean reversion build (P1) demonstrated the failure mode — a signal with sound math, well-known in academic literature, that the factor zoo literature would have flagged as crowded and academically arbitraged. The upgraded pipeline makes this catch mandatory before any implementation decision. The Replication Agent's three factor zoo checks are the specific fix for that failure mode.

### 2026-05-23 — Structured research pipeline: hypothesis lifecycle tracker at docs/research/
**Context**: The existing research system (quant-research skill + Council Config G + DEEPER_LEARNING.md) validates quant concepts and builds the knowledge base, but there was no formal system for tracking strategy hypotheses from proposal through backtest to promotion or death. Ideas were scattered across LEARNING.md entries and PROJECT_STATUS.md tables with no enforced workflow or kill criteria.
**Decision**: Built `docs/research/` as a documentation-only hypothesis lifecycle tracker. No Python, no database, no automation — just disciplined Markdown with an enforced workflow.
**Why structured over flat**: A flat notes file (LEARNING.md entries) doesn't enforce that a hypothesis reaches Council before implementation, doesn't require a kill criteria table before a backtest runs, and doesn't produce a reusable autopsy when an idea dies. The structured pipeline enforces the discipline at the file creation level — you can't fill in the template halfway and call it done.
**Why graveyard matters**: A killed hypothesis with a thorough autopsy is more valuable than a vague "we tried mean reversion, it didn't work" note. The autopsy distinguishes structural failures (the idea is wrong) from parameter failures (the idea is wrong for this universe/constraint set). H001 is a parameter failure — the signal math is sound, the operating environment isn't. That distinction determines whether the idea gets revisited at Tier 2 or abandoned permanently.
**Why no LLM strategy generation**: The Council stress-tests human hypotheses — it does not generate signal math. All ideas originate from academic papers, market observations, or backtest anomalies. The Council's value is adversarial pressure on an idea that already has a thesis and math. Asking an LLM to invent a strategy and then having it review its own idea is circular.
**Files created**: `docs/research/PIPELINE.md` (master rules), `docs/research/TEMPLATE_HYPOTHESIS.md`, `docs/research/hypotheses/H001_mean_reversion_standalone.md` (backfill), `docs/research/graveyard/H001_mean_reversion_standalone.md` (first graveyard resident), `docs/research/watchlist/README.md`, `docs/research/watchlist/ai_semiconductor.md`, `docs/research/watchlist/canadian_energy.md`, `docs/research/findings/` (empty, awaiting first promotion).
**CLAUDE.md updated**: Research pipeline section added linking to PIPELINE.md and stating the workflow rules.

### 2026-05-23 — Phase 3 P2: Within-bucket Markowitz optimizer with Ledoit-Wolf shrinkage
**Context**: Signal-proportional equal-weight allocation (P0) ignores covariance structure within buckets. With 5 growth ETFs, CHPS.TO would receive 34% of the portfolio when ranked #1 — a single-ticker concentration well above the 40%-of-bucket cap.
**Decision**: Implemented `BucketOptimizer` in `src/portfolio/optimizer.py`. Key design choices:
1. **Ledoit-Wolf covariance (sklearn)**: Added `scikit-learn>=1.4.0`. Sample covariance on 2–5 assets over 252 days is near-singular. LW shrinkage toward the structured target is analytically optimal with no hyperparameter tuning — 3-line implementation vs ~25 lines for the closed-form formula. Battle-tested.
2. **Expected return proxy: signal_i × annualized_vol_i**: Signal scores are rank-normalized to [-1, +1]. Multiplying by annualized vol gives return-like units calibrated to each ticker's volatility. Avoids historical mean returns which are noise-dominated at monthly frequency on 9 ETFs. This is the signal as the return forecast.
3. **Stable bucket always equal-weight**: HSAV.TO is a cash-equivalent (near-zero vol). Running the optimizer on stable would produce ~95% HSAV / 5% VAB — mathematically optimal but operationally wrong. P0 decision stands: stable always 1/n per ticker.
4. **SLSQP solver (scipy)**: Handles equality + inequality constraints natively. Constraints: sum(w)=1, w_i≥0, w_i≥5% if included, w_i≤40%. Falls back to equal-weight on solver failure — pipeline never crashes.
5. **Rebalance threshold (2%)**: Weight changes < 2% produce BELOW_THRESHOLD HOLD cards instead of BUY. With 24 trades/year limit, can't burn slots on trivial rebalances. Gate added as GateStatus.BELOW_THRESHOLD.
6. **Integration**: Optimizer is opt-in via `--optimize` flag on `quant recommend`. Equal-weight path unchanged. `generate_trade_cards` accepts optional `optimized_weights` dict — zero breaking changes to P0 tests.
**Live demo result (2026-05-23, NORMAL regime, $800 capital)**:
- CHPS.TO: 34.3% → 24.0% (optimizer caps at 40% of 60% growth = 24% portfolio)
- HXQ.TO: 17.1% → 24.0% (risk-adjusted; lower vol than CHPS, same bucket constraint)
- XIC.TO: 8.6% → 12.0% (captured redistributed weight)
- Stable: 12.5%/12.5% unchanged ✓
**Backtester integration**: `engine.py` is equal-weight only. Running a weights-comparison backtest would require passing a weight function to `run_backtest` — deferred to a future phase. The within-bucket optimizer's value shows in realized portfolio Sharpe over time, not in the existing equal-weight backtester.
**Tests**: 31 new tests in `tests/test_optimizer.py`, 109/109 passing.
**Files**: `src/portfolio/optimizer.py` (new), `src/portfolio/recommendations.py` (extended), `src/cli/phase3_commands.py` (extended), `config/portfolio.yaml` (optimizer block), `requirements.txt` (scikit-learn).

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
*(Tier 1 complete — no active items. Awaiting Tier 2 trigger: NAV ≥ $10,000 CAD.)*

### Backlog (Tier 2)
- [ ] Capital tier transition logic: detect NAV ≥ $10k, auto-update `capital_tier` in `config/portfolio.yaml`, notify via ntfy.sh
- [ ] Canadian dividend large-cap stock additions: screen TSX-listed, 5+ yr dividend growth, AUM > $100M (Tier 2 universe expansion)
- [ ] Covariance estimation review: Ledoit-Wolf re-tuning with 20–40 assets; evaluate non-linear shrinkage if N/T ratio degrades
- [ ] H001 mean-reversion re-evaluation at Tier 2 (individual equities — 20+ names provide cross-sectional dispersion the 9-ETF universe lacks)
- [ ] Tier 2 code review: full pass on all `src/` before first Tier 2 feature ships

### Done
- [x] Phase 1 Milestone 1: Data pipeline — 20yr daily OHLCV for 9 ETFs into SQLite (2026-05-19)
- [x] Phase 1 Milestone 2: Portfolio model + holdings ledger (2026-05-19)
- [x] Phase 1 Milestone 3: Core risk metrics module with unit tests (2026-05-19)
- [x] Phase 1 Milestone 4: CLI dashboard — `quant status`, `quant metrics`, `quant fetch` (2026-05-19)
- [x] Phase 1 Milestone 5: First end-to-end run (2026-05-19)
- [x] Phase 2: Momentum + vol regime signals, walk-forward backtester, FastAPI dashboard (2026-05-19)
- [x] Phase 3 P0: Trade recommendation engine, cost/CRA/min-hold gates, `quant execute` (2026-05-20)
- [x] Dashboard + CLI redesign: Streamlit 4-file architecture (2026-05-20)
- [x] Phase 3 P1: Mean reversion signal — standalone not viable, signal in codebase (2026-05-22)
- [x] Universe swap: ZAG.TO → CHPS.TO in growth bucket (2026-05-22)
- [x] Research pipeline: quant-research skill + Council Config G + DEEPER_LEARNING.md (2026-05-22)
- [x] Structured research pipeline: `docs/research/` hypothesis lifecycle tracker (2026-05-23)
- [x] Phase 3 P2: Within-bucket Markowitz optimizer, Ledoit-Wolf, `--optimize` flag (2026-05-23)
- [x] quant-research skill upgrade: 4-agent parallel pipeline (2026-05-24)
- [x] Phase 3 P3.3: Signal persistence — `signal_scores` table, `quant signal-history` (2026-05-26)
- [x] Phase 3 SELL/Rebalance: signal-driven exit + drift-triggered trim, `sell_reason` field (2026-05-26)
- [x] H005: RSI(21) filter KILLED — mathematical redundancy with momentum confirmed (2026-05-26)
- [x] H006: Volume spike indicator SHELVED — ETF structural failure modes (2026-05-26)
- [x] Phase 3 P3.5: ntfy.sh phone alerts — 3 triggers, `alerts_log`, `--notify` flag (2026-05-27)
- [x] Phase 3 P3.6: Scheduled daily run — DailyRunner, Task Scheduler, `quant daily-run` (2026-05-28)
- [x] Phase 3 P3.7: Test coverage closure — `summary_str()`, integration tests, 204/204 (2026-05-28)
- [x] H004: Volatility targeting KILLED — leverage effect absent 7/7 ETFs, corr 0.9862 (2026-05-28)
- [x] v1.0.0-tier1 tagged — Tier 1 production-ready (2026-05-28)

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

---

### 2026-05-26 — P3.3 Signal Persistence

**Decision:** Added `signal_scores` SQLite table. `persist_signals()` and
`query_signal_history()` in `storage.py`. `--save` flag on `quant signals`
persists scores for that signal type. `quant recommend --save` persists both
momentum + vol_regime scores before saving trade cards. New `quant
signal-history TICKER [--records N] [--signal-type TYPE]` command shows
pivoted score history.

**Rationale:** Signals computed on-the-fly are unauditable. When a trade
recommendation is generated, there must be a record of which signal scores
drove it. The `signal_scores.run_id = recommendations.run_id` JOIN is the
audit path.

**Key design choices:**
- `SignalResult.ticker_metadata()` extracts per-ticker metadata slices —
  `storage.py` calls this method and knows nothing about signal internals.
  Two-tier contract: per-ticker dicts extract per-ticker values (key renamed
  via explicit `_PER_TICKER_KEY_MAP`); broadcast scalars pass through verbatim.
- `--save` gates all persistence. No silent DB writes from read-only commands.
  Daily scheduler (`daily_run.py`) MUST always pass `--save` to
  `quant recommend`.
- `signal-history` uses last-N-records semantics (default 12), not calendar
  days. More useful for a monthly system with sparse persisted data.
- Schema uses `INSERT OR REPLACE` upsert. Revisit to `ON CONFLICT DO UPDATE`
  if nullable columns are added to `signal_scores` in future.

**Lesson:** Silent neutral fallback (`score=0.0`) on insufficient data is correct behavior for signal integrity, but callers must actively use `sig.lookback_days` to size the fetch window. Never hardcode a lookback constant that could silently undercut a signal's required history.

---

**Mistake & Correction — 2026-05-31**

**Bug cluster: `recommend --notify` died silently, and so did the alert about it (3 root causes + 1 systemic)**

A `recommend --notify` smoke run failed with `OperationalError: no such table: alerts_log`, and the daily-run alert meant to report that failure *also* failed with `'latin-1' codec can't encode character '—'`. Net effect on a real-money system: the daily pipeline broke and the operator was never notified — a doubly-silent failure.

**Root causes (all distinct):**
1. **Stale live DB (Bug A).** `data/quant.db` predated the `alerts_log` + `schema_version` DDL; `quant init` had not been re-run. Schema in code was correct — the live DB was simply un-synced. Fix: ran idempotent `quant init` (additive `CREATE TABLE IF NOT EXISTS` + `run_migrations()`); 63 recs preserved, tables added, `schema_version=[1,2]`.
2. **Unguarded alert side-effect (Bug C).** `_run_alert_triggers` was called from `recommend_command` with no guard, and `log_alert`/`get_last_alert` do DB I/O that can raise — so an alerting failure crashed the *primary* recommendation pipeline. This violated the ntfy.py contract ("the recommendation pipeline must not fail because an alert failed") and the function's own false "never raises" docstring. Fix: split into a guarded wrapper `_run_alert_triggers` (logs + console-warns on any failure, never raises) over an inner `_evaluate_alert_triggers`.
3. **Non-latin-1 HTTP header (Bug B).** `send_alert` puts the title in the `X-Title` header; `requests` encodes header values as latin-1. The daily-run error title `Quant Engine — {step} FAILED` carries an em-dash (U+2014) at position 13. `UnicodeEncodeError` is a `ValueError`, *not* caught by `except (RequestException, OSError)`. Fix: `_latin1_header()` maps common Unicode punctuation (—, –, →, …, curly quotes) to ASCII and `encode("latin-1", "replace")`s the rest, applied to `X-Title` and `X-Tags`. Body is unaffected (sent as UTF-8 bytes).
4. **Systemic Windows-console crash (Bug D), discovered while applying the fix.** `quant init` crashed on its own `✓` success message: `'charmap' codec can't encode '✓'`. Python <3.15 on Windows defaults console output to cp1252, so *every* CLI command printing a non-cp1252 glyph (`✓ — → █ ─`) crashes when run directly in a terminal (it survived the smoke harness only because subprocess PIPEs default to UTF-8). Fix: `_force_utf8_output()` reconfigures stdout/stderr to UTF-8 at CLI entry in `main.py`.

**Tests:** `tests/test_alerts.py` (+3: em-dash title, non-latin-1 tag, ASCII unchanged; +1: `_run_alert_triggers` never raises on DB error — reproduces the exact `no such table: alerts_log` crash and proves it is now swallowed). `tests/test_cli_encoding.py` (+3: cp1252 baseline, reconfigure makes glyphs safe, no-op on non-reconfigurable streams). 261/261 passing.

**Lessons:**
- A "fire-and-forget" side effect is only fire-and-forget if it is *wrapped*. A docstring promising "never raises" is a comment, not a guarantee — the guarantee must be a `try/except` at the call boundary. Log loudly (no silent failures), drop, continue.
- HTTP header values are latin-1, not UTF-8. Rich body text ≠ header text. Sanitize at the transport boundary so no caller can ever crash a header.
- Green tests against temp DBs do not prove the *live* DB is in sync. Schema drift between `SCHEMA`-in-code and `data/quant.db` is invisible until a command touches the missing table. (See `docs/runbooks/TIER1_OPERATIONALIZATION.md` Step 1.)
- On Windows + Python <3.15, force UTF-8 stdout at entry or every glyph is a latent crash. Subprocess capture hides it; the operator's terminal will not.

---

**Mistake & Correction — 2026-05-31 (follow-up audit: "if we missed those, what else?")**

After the alert/encoding cluster, ran a full read-only audit across three fronts (every `except` clause for type-coverage gaps; every process entry point for UTF-8 coverage; every "never raises / must not fail" contract for a failure-path test) plus a live read-only execution pass of all 8 read-only CLI commands. All 8 exited 0; DailyRunner was found genuinely encoding-correct (UTF-8 log file + `PYTHONUTF8=1` subprocess). Seven findings; five fixed this pass:

1. **F1 — real-money trade commands leaked DB errors.** `quant execute` wrapped `record_trade` in **no** try/except; `quant trade` caught **only `ValueError`**. `record_trade` does DB I/O, so a `sqlite3.OperationalError`/`IntegrityError` (or a SELL-too-many `ValueError` on `execute`) escaped as a raw traceback. Same shape as the latin-1 bug: narrow except, body raises an uncaught type. Fix: both paths now catch `(ValueError, sqlite3.Error)` → clean `Trade rejected: …` + Exit(1).
2. **F2 — `execute` did two non-atomic writes** (`record_trade` then `mark_recommendation_executed`). A failure between them = a recorded trade with a still-pending rec → possible double-execution. Fix (shared-connection): both functions take an optional `conn`; `execute_command` runs them in one `with get_connection() as conn:` transaction, so either both commit or both roll back. Verified by a storage test that forces a mid-transaction failure and asserts zero rows persisted.
3. **F3 — `_clamped_regime_score` fell back to NORMAL silently.** Added `logger.warning` (module logger, matching optimizer.py) so a bad regime string is never swallowed unlogged.
4. **F4 — daily-run "alert failure must never abort the run" was untested.** Added a failure-path test: `send_alert` raising → run still completes with the correct failure count.
5. **F7 — `DB_PATH` was hardcoded**, so write-commands could only be exercised against the live DB — a root reason these paths were never run. Added `$QUANT_DB` override (`_default_db_path()`). This unlocked a real end-to-end write-path check: BUY → oversell (clean `Cannot sell …` Exit 1) → SELL, against a throwaway DB, live DB untouched.

Deferred as documented/theoretical: F5 (`scripts/daily_run.py` bypasses `_force_utf8_output`, but DailyRunner is internally UTF-8-safe) and F6 (`send_alert`'s narrow except, now moot post-sanitization).

**Tests:** +9 (2 F7, 1 F3, 1 F4, 3 F2-atomicity, 2 F1-CLI). 270/270 passing.

**Lessons:**
- The audit's highest-yield finding wasn't a bug — it was that **write paths had never been executed** because the DB path was unmockable. Hardcoded resources don't just hurt testing; they guarantee the untested path ships. Make the resource injectable (`$QUANT_DB`) and the smoke gate writes itself.
- "Narrow `except`, body raises a wider type" is a *pattern*, not a one-off. After finding it once (latin-1), grep every `except (...)` and ask "what else can the body throw?" — F1 was the same bug in two more real-money commands.
- Two sequential writes that must agree belong in one transaction. "It'll basically never fail between them" is how a double-booked real trade happens.

---

**Mistake & Correction — 2026-05-31 (DB discrepancy fix + a test that corrupted the live DB)**

Full DB audit of `data/quant.db` came back structurally clean (schema migrated, holdings/trades reconcile, prices fresh, 0 NaN, 0 run_log errors) with **one real discrepancy**: 63 `pending` recommendations accumulated across 7 `recommend --save` runs with **no supersession**, so `quant pending` showed up to **7 duplicate BUY cards per ticker** (43 "actionable") plus a zombie BUY ZAG.TO from before ZAG was dropped from the universe. Executing two cards for one ticker = an accidental double-buy.

**Fix (snapshot model):** new `supersede_pending_recommendations(keep_run_id)` (no schema migration — `status` has no CHECK constraint; added a `superseded` status that drops out of the pending view but stays in the append-only log). `recommend --save` calls it after persisting so the newest run is the only pending one. One-time cleanup left 9 pending (latest run) + 54 superseded.

**The bite — a unit test corrupted the live database.** Wiring supersession into `recommend_command` meant the *pre-existing* `test_recommend_save_persists_real_target_weight` (which calls `recommend_command(save=True)` and mocked `save_recommendation` but, of course, not the brand-new supersede call) ran the **real** `supersede_pending_recommendations` against the **default DB_PATH = the live `data/quant.db`** during the suite — silently flipping all 63 pending recs to superseded. Caught only because the follow-up cleanup query found 0 pending where 63 were expected.

**Root-cause fix:** added `conftest.py` that sets `$QUANT_DB` to a throwaway temp DB **before any test imports storage**, so the module-level `DB_PATH` binds to the throwaway and **no test can ever touch the live DB by default**. This is the systemic form of F7. One read-only research test (`test_H005_rsi_backtest`) legitimately needs live price history, so it now pins the real repo `data/quant.db` path explicitly (read-only). 274/274 passing; verified the suite leaves the live DB byte-unchanged.

**Lessons:**
- Adding a DB **write** to a code path silently widens the blast radius of every existing test that exercises it. A test that was "safe" because the old writes were mocked becomes a live-DB mutator the moment you add an unmocked one.
- Test isolation must be enforced at the *infrastructure* layer (a conftest that redirects the default DB), not per-test discipline. Per-test mocking is opt-in and therefore eventually forgotten — as it was here.
- The blast radius was invisible until a state-counting query disagreed with expectation. When a number "should be 63" and is 0, stop and find out *who wrote it* before doing anything else.

---

**Decision — 2026-05-31 — `quant db-audit`: codify the manual DB health check into a re-runnable command**

The 2026-05-31 pending pile-up (63 unsuperseded recs + zombie ZAG.TO) was found by a *manual* DB audit. Manual audits don't re-run, so the next drift would again be invisible until something broke. Codifying the sweep as `quant db-audit`.

**Contract (operator-approved):**
- **Exit code:** 0 when clean or WARN-only; **1 on any ERROR finding** — so `daily-run` / Task Scheduler can gate on real corruption while tolerating benign warnings (weekend-stale prices).
- **Read-only.** Never mutates `prices/holdings/trades/recommendations`. Remediation stays in the existing commands (`quant init` for schema, `recommend --save` for supersession); the audit *names* the fix in its finding message. The one permitted write is a single summary row to `run_log` (component=`db_audit`) — `run_log` is the system event log, not a domain table.
- **Output:** human severity-grouped table by default, `--json` for machine/scheduler consumption.

**Architecture:** read-only compute is separated from command I/O so the audit is unit-testable without stdout/exit/writes.
- `src/data/audit.py` — `AuditFinding`/`AuditReport` dataclasses + check-function registry + `run_audit(conn, universe_tickers, today, thresholds) -> AuditReport`. Everything injected for determinism. `AuditReport.exit_code = 1 if any ERROR else 0`.
- `src/cli/db_audit_command.py` — loads universe + thresholds, opens conn, calls `run_audit`, renders/prints, writes the `run_log` summary, raises `typer.Exit(report.exit_code)`.
- `scripts/db_audit.py` — thin Task-Scheduler entry mirroring `scripts/daily_run.py`.

**Check catalog (severity):**
1. `schema` (ERROR) — every `SCHEMA` table exists; `recommendations` has all migration-added columns. (Catches Bug A: a live DB predating `alerts_log`/`schema_version`.)
2. `migrations` (ERROR) — every `_MIGRATIONS` version recorded in `schema_version`.
3. `holdings_reconciliation` (ERROR) — holding `units` == Σ(BUY) − Σ(SELL); `avg_cost` == VWAP; no holding without backing trades; no net-positive ticker missing a holding row.
4. `pending_supersession` (ERROR) — all `pending` recs share one (latest) `run_id`; no duplicate ticker+action among pending. (Catches the pile-up.)
5. `universe_integrity` — off-universe **pending rec** → WARN (zombie); off-universe **holding** → ERROR (universe-lock breach, Hard Constraint 2).
6. `price_coverage` (ERROR) — every universe ticker has ≥1 price row.
7. `price_freshness` (WARN/ERROR) — freshest price age vs `staleness_warn_days`/`staleness_error_days` (business days via `numpy.busday_count`); a ticker lagging the freshest by > `per_ticker_lag_warn_days` → WARN.
8. `price_quality` (ERROR) — no NULL or ≤0 `close`/`adj_close`.

**Thresholds:** new `db_audit:` block in `config/portfolio.yaml` (`price_staleness_warn_days: 5`, `price_staleness_error_days: 15`, `per_ticker_lag_warn_days: 3`); sensible defaults if absent.

**Deliberate scope calls:** no `--fix` (read-only); not auto-wired into `daily-run` this pass (chaining a non-zero-exit audit changes that pipeline's failure semantics — its own decision).

**Build:** TDD, one check at a time. Tests seed a temp DB from `SCHEMA`, insert clean + broken states, assert findings/severity; CLI tests monkeypatch the command's injected deps (conn, universe, config, run_log) against an in-memory DB. Live DB never touched (conftest isolation).

---

**Decision — 2026-05-31 — Test isolation: close the network class, not just the DB instance**

Follow-up to the conftest `$QUANT_DB` DB isolation. Audited every test for real network / live-resource use: `test_ingest.py` mocks `fetch_ticker` (yfinance) + `upsert_prices`; `test_alerts.py` mocks `requests.post`; `test_daily_run.py` mocks `subprocess.run` in every `runner.run()` test; `test_H005_rsi_backtest.py` reads the live `data/quant.db` **read-only** by design (`skipif(not DB_PATH.exists())`). **No test makes a real network call today.**

But that is per-test discipline — the exact thing the 2026-05-31 DB-isolation lesson says is "opt-in and therefore eventually forgotten." The DB class was closed at the infrastructure layer; the network class was not. Closed it: `conftest.py` now installs a socket guard (`socket.create_connection` + `socket.socket.connect`/`connect_ex`) that raises a loud `RuntimeError` on any outbound connection to a non-loopback host, naming the fix. Loopback (`127.0.0.1`/`::1`/`localhost`/`0.0.0.0`) stays allowed for a future in-process server test. Mocked transports never reach a socket, so the existing suite is unaffected.

**Tests:** `tests/test_network_isolation.py` (+3: external `create_connection` blocked, external raw `connect` blocked, loopback passes through to the OS). 321/321 passing. The RED run confirmed the environment has live network access (the unguarded `create_connection("example.com", 80)` succeeded) — i.e. the guard closes a real, open door.

**Lesson:** "No test hits the network" is a property to *enforce*, not to *audit once*. An audit is a snapshot; a conftest guard is a ratchet. Same shape as the DB fix — redirect/deny the resource at the session layer so the next forgotten mock fails loudly instead of silently calling out.
