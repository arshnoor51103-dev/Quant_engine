# Tier 1 Code Review — Quant Engine

**Date:** 2026-05-29
**Reviewed at:** `v1.1.0-tooling` (HEAD = eea698f)
**Baseline:** 204/204 tests passing (confirmed green before review)
**Scope:** Cross-phase consistency audit of the full Tier 1 build (Phase 1 → P3.7 + tooling). Read-only. No `src/`, `tests/`, or `config/` changes. This document is the only artifact.
**Method:** Six review domains. Domains 1–2 (hard-constraint compliance, cross-phase contract drift) executed by parallel subagents with full reports. Domains 3–6 (persistence/migration, silent-failure, test coverage, documentation) executed inline after a session interruption truncated those subagents — same files, same checks, evidence cited.

---

## Executive Summary

Tier 1 is in good structural health: the no-LLM-in-signal-path constraint is **airtight**, the cost gate math is correct, MIN_HOLD genuinely blocks, the SQLite schema is fully idempotent, the metrics layer is NaN-safe on empty input, the optimizer logs every fallback, and every documented config value matches code. The test suite is green and the documentation is unusually faithful to the code.

The biggest concern is a cluster of **silent-success-on-failure paths feeding the real-money recommendation engine**: `quant fetch` and `quant signals` exit 0 even on total failure, so the automated daily run can report "0 steps failed" while recommending trades on stale or empty data — and the 20% drawdown ceiling and the 24-trade/year CRA cap are both documented hard limits that **nothing in code actually enforces**. None of these break Tier 1 functionally (hence no BLOCKER), but they are exactly the kind of guardrail you want solid before adding capital and instruments.

The biggest pleasant surprise: the `GateStatus` enum discipline is perfect (no path anywhere returns a bare bool/string where a gate decision belongs), and `run_id` propagation within `recommend --save` is exactly correct — the audit JOIN holds. Drift was found mostly in the *later* additions (mean-reversion / RSI metadata, drift-SELL gating) bolting onto contracts written earlier, which is the predictable shape of staged builds.

---

## Findings Table

Severity key: **BLOCKER** = fix before any Tier 2 work · **MAJOR** = fix in Tier 1 cleanup before Tier 2 · **MINOR** = fix opportunistically · **NIT** = polish, no action required.

| # | Sev | Domain | File:Line | Description | Recommended Action |
|---|-----|--------|-----------|-------------|--------------------|
| F1 | MAJOR | Constraints | `src/cli/phase3_commands.py:471` (execute_command) | The "24 trades/year" CRA cap is **not enforced**. `_cra_gate` (`recommendations.py:225-238`) only colours the card `CRA_LIMIT` at ≥24; `execute_command` records trade #25, #26… with no trade-count check. CLAUDE.md frames 24 as a hard legal boundary. | Add a blocking (or hard-confirm) check in `execute_command`: refuse execution when `get_annual_trade_count() >= max_trades`. |
| F2 | MAJOR | Constraints | `config/portfolio.yaml:21` (`risk.max_drawdown: 0.20`) | The 20% drawdown ceiling is read by **no code**. Only the 15% `drawdown_alert` fires (ntfy). At 20% the system keeps emitting normal BUY cards. Grep confirms `max_drawdown` config key has zero consumers. | Add a distinct ceiling-breach alert (priority 5) and/or suppress BUY cards at ≥20% in `_run_alert_triggers`/`recommend_command` (`phase3_commands.py:319`). |
| F3 | MAJOR | Contract drift | `src/cli/main.py:51-70` (fetch) → `src/data/ingest.py:101-104` | `ingest_universe` swallows every per-ticker exception (sets `-1`, "Don't raise") and `fetch` returns normally → **exit 0 even if all 9 tickers fail**. DailyRunner logs it `OK`; recommend then runs on stale prices. Also violates CLAUDE.md "never silently return stale data / retry with backoff." | Make `fetch` exit non-zero when all (or a threshold of) tickers fail. Add retry/backoff per CLAUDE.md. |
| F4 | MAJOR | Contract drift | `src/cli/phase2_commands.py:52-63` (signals) | `signals` exits 0 when signal-type is unknown (`return` at :52-53) and when price data is empty (persists 0 rows, exits 0). DailyRunner records `OK`; a run that persisted no signals is indistinguishable from success. | Exit non-zero on unknown signal-type and on empty/zero-row persistence. |
| F5 | MAJOR | Contract drift | `src/portfolio/recommendations.py:318-366` (drift-SELL branch) | Drift-driven SELL **bypasses the cost gate entirely** — it gates only on the `$50` `min_rebalance_trade` floor, min-hold, and CRA, never on `exp_ret ≥ 2×spread+profit_floor`. The card also never sets `cost_estimate` (stays `None`, then persisted as NULL). CLAUDE.md Hard Constraint 3 + the module docstring claim symmetric gating. | Decide intent: either document that drift-SELL is dollar-floor-gated by design (and populate `cost_estimate` for audit), or add the percentage cost gate to the drift path. |
| F6 | MAJOR | Contract drift | `src/signals/base.py:64-72` (`ticker_metadata`) | The two-tier extraction treats **any dict** as ticker-keyed. `mean_reversion.py:190-195` puts a structural dict `regime_weights={"w_ts",...}` in metadata → silently dropped from every persisted row (no real ticker is a key). This is the "silently broken in signal-history" failure mode. Dormant only because MR isn't in the live pipeline. | Make `ticker_metadata()` distinguish ticker-keyed dicts from structural dicts (explicit allow-list, or a `per_ticker=` wrapper). Critical before adding any Tier 2 signal. |
| F7 | MINOR | Constraints | `config/portfolio.yaml:4`; all of `src/` | `capital_tier` is read by **no code**. CLAUDE.md claims "All modules read `capital_tier`… universe and constraints scale automatically." False — the Tier 1 universe lock holds only because `universe.yaml` happens to contain Canadian ETFs and `execute_command:509-511` rejects off-universe tickers. `region: US` fields are decorative. | Either implement a runtime `capital_tier`-aware universe filter, or correct the CLAUDE.md claim. Required for the Tier 2 transition regardless. |
| F8 | MINOR | Silent failure | `src/portfolio/recommendations.py:61` | `spread = meta.get("spread_override") or spread_proxy` — a deliberate `spread_override: 0` is falsy and silently falls back to the proxy. A real zero-spread override is impossible to set. | Use `meta.get("spread_override")` with an explicit `is None` check. |
| F9 | MINOR | Persistence | `phase2_commands.py:225`; `phase3_commands.py:305,325` | All three `json.loads` calls on JSON-as-TEXT columns are **not** wrapped in try/except. A single malformed row crashes the whole `signal-history` query / alert trigger. Low likelihood today (the system controls all writes) but no defensive guard. | Wrap each `json.loads` in try/except, log + skip the bad row. |
| F10 | MINOR | Contract drift | `src/signals/base.py:27-30` (`_PER_TICKER_KEY_MAP`) | `rsi.py` `rsi_values` and `mean_reversion.py` `z_ts_raw` are per-ticker dicts with **no map entry** → persisted un-renamed (e.g. `rsi_values` instead of `rsi_value`). Value survives but the convention documented at `base.py:26` was not honoured when those signals were added. | Add map entries when those signals enter the live path (or fold into the F6 fix). |
| F11 | MINOR | Contract drift / Persistence | `phase2_commands.py:67-70` vs `phase3_commands.py:435`; `storage.py:485` | The daily run writes `signal_scores` under multiple `run_id`s (one per `signals --save` subprocess, plus recommend's own). It "works" only because `INSERT OR REPLACE` on PK `(run_date,ticker,signal_type)` lets the recommend-run overwrite earlier rows for the same date. If signal-type sets ever diverge, orphan non-joining rows persist. | Have the daily run generate one `run_id` and thread it through all steps, or drop the redundant `signals --save` steps (recommend re-persists anyway). |
| F12 | MINOR | Test coverage | `tests/test_recommendations.py:206-214` | `test_cra_limit_threshold` asserts the gate *shows* `CRA_LIMIT` at 24, but there is **no test that trade #25 is blocked** from execution — because (per F1) no blocking exists. Negative test is absent. | Add the negative test alongside the F1 fix. |
| F13 | MINOR | Test coverage | `tests/test_integration.py:70-90` | The "full pipeline" integration test exercises signal → in-memory `compute_combined_scores`/`generate_trade_cards` only. It does **not** call `fetch`, `execute`, or touch the DB; regime is a hand-built `SignalResult`. The "fetch → signal → recommend → execute" claim (PROJECT_STATUS) is overstated. | Either add a real end-to-end test (temp DB, fetch stub, execute round-trip) or downgrade the doc claim. |
| F14 | MINOR | Architecture / drift | `config/universe.yaml`; `config/portfolio.yaml:6-18`; `src/signals/vol_regime.py:36` | Bucket membership has **three sources of truth**: `universe.yaml` (the live `universe_map`), `portfolio.yaml` `buckets.*.tickers`, and the hardcoded `STABLE_TICKERS` frozenset in `vol_regime.py`. A ticker re-bucket must update all three in sync or signals/recommendations silently diverge. Painful at 40 tickers. | Consolidate to one source (load stable set from `universe_map`); remove the hardcoded frozenset. |
| F15 | MINOR | Persistence | `storage.py:285-316` vs `319-333` | `migrate_recommendations_v2` is guarded by a module-global `_migrated` set; `migrate_recommendations_v3` is not. Both are idempotent (column-existence checked), so harmless, but the inconsistency is a trap when a v4 migration is added. | Pick one pattern. A real migration runner keyed on a `schema_version` row would scale better for Tier 2. |
| F16 | NIT | Constraints | `recommendations.py:196` | Dead variable `cost_threshold` (uses global `spread_proxy`); live gating uses per-ticker `gate_threshold` at `:245`. | Delete. |
| F17 | NIT | Contract drift | `phase3_commands.py:444`; `storage.py:66` | `save_recommendation` always called with `target_weight=0.0` hardcoded; the `recommendations.target_weight` column is dead (TradeCard has no such field). | Remove the column or populate it. |
| F18 | NIT | Silent failure | `daily_run_command.py:52` | `DailyRunner.__init__` accepts `db_path` but never stores/uses it. | Remove the param or wire it. |
| F19 | NIT | Contract drift | `phase3_commands.py:558,568` | `pending` renders a legitimate `0.0` expected-return as "—" (`if r.get("expected_ret")` is falsy on 0.0); inconsistent with the `is not None` check used for `combined_signal`. | Use `is not None`. |
| F20 | NIT | Persistence | `base.py:71-72` via momentum/MR/RSI metadata | `skipped_tickers` (a list) broadcasts verbatim into *every* ticker's persisted `signal_scores.metadata` — storage bloat, not a correctness bug. | Drop list-typed metadata from per-row persistence, or store once per run. |
| F21 | NIT | Hygiene | `.claude/worktrees/phase-3-p35-ntfy-alerts/` (untracked) | A stale duplicate `src/`+`config/` tree pollutes repo-wide greps with an older code state. | Remove the worktree. |
| F22 | MINOR | Silent failure | `src/portfolio/metrics.py:115-116` | `max_drawdown` on an **empty** series returns `float("nan")`, not `0.0`. In the drawdown-alert path (`phase3_commands.py:322`) a NaN compares `False` against the 15% threshold, so an empty NAV series silently no-ops (no alert, no crash) — functionally safe but via NaN, not a clean `0.0`. The same NaN-on-empty applies to all metrics. | If a clean `0.0` is wanted for the no-holdings case, special-case it in the alert path; otherwise document the NaN contract. |

---

## What Is Correct (silence is not signal — these were checked and pass)

- **No LLM in the signal path.** Exhaustive import scan of all `src/`: zero `anthropic`/`openai`/`langchain`/`cohere`/`transformers`. `requests` appears only in `src/alerts/ntfy.py:10` (the legitimate ntfy transport, off the signal path, and it never raises into the pipeline — `ntfy.py:50-51`). Airtight.
- **Cost gate formula.** `2×spread + 0.5% floor` computed correctly (`recommendations.py:244-245`, threshold = 0.006) and applied to **every BUY** (`:416`) and **every signal-SELL** (`:263`). Per-ETF `spread_override` honoured. (Drift-SELL is the exception — see F5.)
- **MIN_HOLD (14d) genuinely blocks** all three paths (`recommendations.py:429-440` BUY, `:278-290` signal-SELL, `:342-355` drift-SELL) via `continue`/`MIN_HOLD` — a true suppression, not a warning.
- **`GateStatus` enum discipline is clean.** Every gate decision returns a `GateStatus` member; no path returns a bare bool/string. `_cra_gate` always returns an enum; `.value` access at persistence is therefore safe.
- **`run_id` within `recommend --save` is consistent.** One UUID (`phase3_commands.py:435`) flows to `persist_signals` and every `save_recommendation` in the same run — the `signal_scores.run_id = recommendations.run_id` JOIN holds.
- **`sell_reason` populated and rendered correctly** across BUY (`None`), signal-SELL (`"SIGNAL"`), drift-SELL (`"DRIFT"`), round-tripping through the DB and `pending` output.
- **Schema fully idempotent.** Every `CREATE TABLE` and `CREATE INDEX` uses `IF NOT EXISTS` (`storage.py:26-121`). `quant init` on an existing DB will not error. Both migrations check column existence before `ALTER`, add with NULL default — no data loss.
- **Metrics module never crashes on degenerate input.** Every function guards short/empty input and returns `float("nan")` (`annualized_return:41-42`, `annualized_volatility:53-54`, `max_drawdown:115-116`, `beta:142-143`, etc.) — no exceptions, no division-by-zero. (Note: it returns **NaN, not 0.0** — see F22.)
- **Optimizer fallbacks all log at WARNING** (`optimizer.py:84-87, 102-106, and all-below-min path`) — no silent equal-weight fallback.
- **All config values match documentation/constraints.** `portfolio.yaml`: 60/25/15 ±10/5/5, min-hold 14, max-trades 24, spread 0.0005, profit-floor 0.005, multiplier 2.0, max_dd 0.20, alert 0.15 — all match CLAUDE.md and PROJECT_STATUS.
- **DEEPER_LEARNING.md numbering** is sequential DL-001 → DL-014, 14 entries, no gaps, no reuse.
- **Signal docstring citations present and matching the math:** momentum → Jegadeesh-Titman 1993 (`momentum.py:14`), vol_regime → Kritzman-Page-Turkington 2012 (`vol_regime.py:18`), mean_reversion → Jegadeesh/Lehmann 1990 (`mean_reversion.py:16`), rsi → Wilder 1978 (`rsi.py:13`).
- **Test count matches docs:** 204 collected, 204 passing.
- **`STABLE_TICKERS = {VAB.TO, HSAV.TO}`** exists as claimed (`vol_regime.py:36`).
- **`send_alert` never raises** — network failure logs a WARNING and returns; pipeline integrity is not conditional on ntfy availability.

---

## Observations (interesting, not problems)

- **PRAGMA `foreign_keys = ON` is set** (`storage.py:128`) but **no table declares any FOREIGN KEY constraint** — `run_id` and `trades.signal_id` are plain columns. So FK enforcement is moot today: the PRAGMA is on, but there are no FKs to enforce. The `run_id` linkage is application-enforced only. Not a bug at Tier 1; worth knowing before relying on referential integrity at Tier 2.
- **`signal_scores` has nullable columns today** (`metadata`, `run_id`); `score` and the PK are NOT NULL. The single write path (`persist_signals`) always supplies all six columns, so `INSERT OR REPLACE` loses nothing now. The risk the code comment anticipates (a future write path omitting a column under `INSERT OR REPLACE`) is real but not yet triggered.
- **Stable bucket intentionally bypasses regime + optimizer** — fixed `1/n` weight (`recommendations.py:97-98`, `optimizer.py:92-95`), matching the locked P0/P2 design. The cost gate still applies to stable via `exp_ret`.
- **Insufficient benchmark history fails *open*, not safe.** `_clamped_regime_score` (`recommendations.py:64-77`) catches `Regime("unknown")` → falls back to `Regime.NORMAL` (score 0.3, buys allowed). On a bad/empty XIC.TO pull the system tilts to "mild risk-on" rather than suppressing buys. Adjacent to F3/F4's stale-data theme; arguably should fail to a neutral/zero tilt.
- **Dashboard broad excepts** (`components.py:104,132,188,332,366`) surface errors to the UI via `st.error(...)` rather than swallowing them silently. Acceptable for a display layer, off the signal path. The two justified non-display broad excepts are `ingest.py:101` (per-ticker isolation, logged) and `daily_run_command.py:45,193` (fail-forward, logged) — both intentional, both `# noqa`-marked or logged.
- **`recommend` correctly exits 0 on a zero-actionable-card run** — an empty recommendation set is not a failure, and DailyRunner treating it as `OK` is right.

---

## Risk Assessment for Tier 2

What in the current code will likely break when the universe expands past 9 ETFs, individual stocks are added, or NAV crosses $10k:

1. **No tier-transition machinery exists (F7).** `capital_tier` is inert. There is no code path that detects NAV ≥ $10k, updates the tier, or widens the universe. The "auto-scaling" described in CLAUDE.md is aspirational. Tier 2 starts with building this from zero — and until it exists, the universe lock is enforced only by `execute_command` rejecting tickers absent from `universe.yaml`.
2. **Three sources of truth for bucket membership (F14)** become a live correctness hazard at 20–40 names. The hardcoded `STABLE_TICKERS` frozenset in `vol_regime.py` will silently disagree with `universe.yaml` the first time someone forgets to update both.
3. **`ticker_metadata()`'s dict-is-ticker-keyed assumption (F6)** breaks any new Tier 2 signal that carries structural metadata. Mean-reversion already trips it; it's shelved for Tier 2 revival, so this bites on arrival.
4. **Silent fetch/signal failure (F3, F4)** scales badly: with 40 tickers, partial download failures are far more likely, and the daily run will keep reporting success while feeding incomplete cross-sections into the ranking — exactly when cross-sectional dispersion (the whole Tier 2 thesis) matters most.
5. **Covariance estimation (already flagged in PROJECT_STATUS Open Q2).** Ledoit-Wolf is fine for 9 ETFs; the N/T ratio degrades toward 40 names. Not a *current* bug — noted because the optimizer's `ledoit_wolf_cov` (`optimizer.py:36-55`) is unchanged and will need re-evaluation, not a rewrite.
6. **CRA cap non-enforcement (F1)** matters more at Tier 2: more instruments and rebalancing pressure mean more trades; the only thing between the operator and day-trade reclassification is a yellow label.
7. **Migration fragility (F15)** surfaces at the first Tier 2 schema change (e.g. adding `tier` or `sector` to `recommendations`). The ad-hoc `migrate_*` pattern works but has no version ledger; existing rows get NULLs silently.

---

## Three Recommendations Before Tier 2 (priority order)

1. **Close the silent-failure / unenforced-guardrail cluster (F1, F2, F3, F4).** These are the real-money safety gaps: data-fetch and signal steps must fail loudly, the CRA cap must block at execution, and the 20% ceiling must do *something*. This is the core of the v1.2.0 cleanup. Cheap to fix, highest payoff.
2. **Fix the metadata contract before any new signal (F6, F10, F14).** `ticker_metadata()` must handle structural dicts, and bucket membership must collapse to one source of truth. Doing this now is far cheaper than after a 40-ticker universe and a revived mean-reversion signal are both in flight.
3. **Resolve the drift-SELL gating intent and harden persistence (F5, F9, F15).** Decide whether drift-SELL is contractually cost-gated or dollar-floor-gated and make code + docs agree; wrap the JSON reads; and replace the ad-hoc migrations with a `schema_version`-keyed runner before the first Tier 2 column lands.

---

*Read-only review. No source, test, or config files were modified. Triage these findings to scope the v1.2.0 cleanup; do not begin cleanup from this document alone.*

---

## Closeout — v1.2.0 Guardrails (2026-05-30, append-only)

> Resolution record for the cleanup executed on branch `fix/v1.2.0-guardrails` per `docs/superpowers/plans/2026-05-30-v1.2.0-guardrails.md`. **The findings table above is NOT modified** (append-only convention). All 22 findings resolved; F18 moot. Test suite 204 → 238, all green. Tag: `v1.2.0-guardrails`.

| # | Sev | Resolution | Commit |
|---|-----|------------|--------|
| F1 | MAJOR | `execute_command` hard-blocks at `≥ max_trades_per_year`; `--force --justification` logged override; warn-at-20 kept. Negative test (#25 blocked) added. | `65e8126` |
| F2 | MAJOR | Soft-halt: pure fn `apply_drawdown_halt` + `GateStatus.DRAWDOWN_HALT` + config `risk.drawdown_halt_enabled`; wired into `recommend_command` (RISK HALT banner); ceiling note folded into the drawdown ntfy alert. | `5a76de7`, `fc9ccaf`, `9f81678` |
| F3 | MAJOR | `ingest_universe` retries with exponential backoff; `quant fetch` exits non-zero past `data.fetch_max_failures`. New `tests/test_ingest.py`. | `abd05be` |
| F4 | MAJOR | `signals` exits non-zero on unknown type / empty data / 0-row save. New `tests/test_phase2_cli.py`. | `2f22435` |
| F5 | MAJOR | Exemption **ratified** (drift-SELL is risk-control, stays off the profit-floor gate, keeps $50 floor) + now populates `cost_estimate = 2×spread`; documented in CLAUDE.md Hard Constraint 3. | `bc0e4ab` (code), `4ff80c9` (docs) |
| F6 | MAJOR | `ticker_metadata` rewritten as allow-list (`_PER_TICKER_KEYS`); structural dicts (e.g. `regime_weights`) preserved, not dropped. | `706f7a8` |
| F7 | MINOR | CLAUDE.md claim corrected: `capital_tier` is declared-but-inert; Tier 1 enforced by `universe.yaml` lock + `execute_command` check; tier-switching is a Tier 2 deliverable (not built). `region:` noted as descriptive. **Doc-only** per locked decision (tier machinery not built now). | `4ff80c9` |
| F8 | MINOR | `spread_override` uses explicit `is None` check — a deliberate `0.0` override is honoured. | `0622a0f` |
| F9 | MINOR | All `json.loads` in alert triggers guarded (REGIME_CHANGE this session; DRAWDOWN guarded during F2). phase2 `signal_history` loads were **already guarded** — verified, no change. Malformed-row test added. | `ebca279` |
| F10 | MINOR | `z_ts_raw → z_ts`, `rsi_values → rsi_value` rename map honoured in the F6 allow-list. | `706f7a8` |
| F11 | MINOR | Daily run drops the two redundant `signals --save` steps; `recommend --save` re-persists momentum + vol_regime under one `run_id`. Pipeline now `fetch → recommend`. | `6364cdd` |
| F12 | MINOR | Negative test `test_execute_blocks_at_cra_cap` (trade #25 blocked before `record_trade`) shipped with F1. | `65e8126` |
| F13 | MINOR | DB-backed E2E `TestEndToEndDB.test_recommend_persist_execute_roundtrip` (temp DB: upsert_prices → save_recommendation → record_trade → mark_executed → assert). In-memory pipeline test kept. PROJECT_STATUS claim corrected. | `e7c1b0b` |
| F14 | MINOR | `STABLE_TICKERS` derived from `universe.yaml` via `_derive_stable_tickers()` — one bucket-truth source, hardcoded frozenset removed. | `88eb354` |
| F15 | MINOR | `schema_version`-tracked `run_migrations()` runner replaces `migrate_recommendations_v2/v3` + `_migrated` global; v2/v3 kept as back-compat shims. | `185a4bf` |
| F16 | NIT | Dead `cost_threshold` variable deleted. | `0622a0f` |
| F17 | NIT | `save_recommendation` persists real `target_weight` = `(optimized_weights or equal_weights).get(ticker, 0.0)` instead of hardcoded 0.0. | `69390c7` |
| F18 | NIT | **MOOT** — the review referenced `DailyRunner.__init__(db_path=...)`; current code has no such param (only `log_target, default_cash, step_timeout_seconds`). Stale reference, no code change. | — |
| F19 | NIT | `pending_command` uses `is not None` so a real `0.0` expected-return renders correctly. | `c0aa5da` |
| F20 | NIT | List-typed metadata (e.g. `skipped_tickers`) dropped from per-row persistence in the F6 allow-list. | `706f7a8` |
| F21 | NIT | Stale worktree deregistered (`git worktree remove`) and its fully-merged branch `worktree-phase-3-p35-ntfy-alerts` deleted; duplicate source tree contents removed (no longer pollutes greps). The now-empty `.claude/worktrees/` dir was held by a Windows process lock at cleanup time — untracked, contents gone, clears on session restart. No commit (untracked path). | — |
| F22 | MINOR | `max_drawdown` NaN-on-empty contract documented on the function + 2 guard tests; the alert/halt paths already rely on NaN-compares-False. | `c0aa5da` |

*Closeout appended by the v1.2.0 execution session. Append-only — see LEARNING.md (2026-05-30 Decision) for the rationale narrative.*
