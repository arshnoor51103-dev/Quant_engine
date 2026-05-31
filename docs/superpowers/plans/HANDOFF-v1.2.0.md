# HANDOFF — v1.2.0 Guardrails Cleanup (fresh session resume)

**Written:** 2026-05-30, mid-execution. Prior session hit context limit + intermittent tool-output corruption.

## TL;DR for the fresh session

You are executing `docs/superpowers/plans/2026-05-30-v1.2.0-guardrails.md` (the full plan — read it). It closes 22 findings from `docs/reviews/2026-05-29-tier1-code-review.md`. **12 of 22 are done and committed; 9 remain; F18 is moot.** Resume at **Task 10**.

- **Branch:** `fix/v1.2.0-guardrails` (do NOT work on main)
- **HEAD at handoff:** `88eb354`
- **Tests at handoff:** `229 passed` (was 204 baseline + 25 new). Working tree clean.
- **Execution mode:** inline, TDD, one atomic commit per finding. Skill: `superpowers:executing-plans`.

## START HERE (do this first in the fresh session)
```bash
git branch --show-current        # must be fix/v1.2.0-guardrails
git --no-pager log -1 --format="%h %s"   # must be 88eb354 fix(F14)...
python -m pytest -q | tail -3    # must be 229 passed
```
If any of those three don't match, STOP and reconcile before editing.

## DONE (committed, do not redo)
| Finding | Commit | What |
|---|---|---|
| F8, F16 | 0622a0f | spread_override `is None` check; deleted dead `cost_threshold` |
| F5 | bc0e4ab | drift-SELL sets `cost_estimate=2*spread` (exemption ratified) |
| F2 | 5a76de7, fc9ccaf, 9f81678 | `apply_drawdown_halt` pure fn + `GateStatus.DRAWDOWN_HALT` + config `risk.drawdown_halt_enabled`; wired into `recommend_command` (RISK HALT banner); ceiling note folded into the drawdown ntfy alert |
| F1, F12 | 65e8126 | `execute_command` hard-blocks at CRA cap; `--force --justification` logged override |
| F3 | abd05be | `ingest_universe` retries+backoff; `quant fetch` exits non-zero past `data.fetch_max_failures` |
| F4 | 2f22435 | `signals` exits non-zero on unknown type / empty data / 0-row save |
| F6, F10, F20 | 706f7a8 | `ticker_metadata` allow-list (`_PER_TICKER_KEYS`); structural dicts preserved; z_ts_raw/rsi_values renamed; lists dropped per-row |
| F14 | 88eb354 | `STABLE_TICKERS` derived from universe.yaml via `_derive_stable_tickers()` |
| F18 | — | MOOT: `DailyRunner.__init__` has no `db_path` param; review ref was stale. Note in closeout, no code change. |

## REMAINING (9 findings, Tasks 10–18 in the plan)
- **Task 10 — F9 (small):** Only the REGIME_CHANGE `json.loads` in `_run_alert_triggers` (phase3_commands.py ~line 317) is still unguarded. The DRAWDOWN read was already guarded during F2. phase2 `signal_history` json.loads is ALREADY guarded (test_signal_persistence confirms) — no change there. Add try/except + a malformed-row test in test_alerts.py.
- **Task 11 — F15 (BIGGEST/RISKIEST):** Replace `migrate_recommendations_v2/v3` + `_migrated` global with a `schema_version`-keyed `run_migrations()` runner. **MUST keep compat shims** — `tests/test_storage.py:27` imports `migrate_recommendations_v2` and calls it at lines ~187/199/217/239; `storage.py:141-142` calls both in `initialize()`. Shim: `def migrate_recommendations_v2(db_path=DB_PATH): run_migrations(db_path)`. Do this one carefully with a full-suite check.
- **Task 12 — F11 (small):** `daily_run_command.py` `_STEPS` → drop the two `signals --save` steps, leaving `[fetch, recommend]` (recommend re-persists momentum+vol_regime under one run_id). Update test_daily_run.py (a test asserts the 4-step list).
- **Task 13 — F17 (small):** In `recommend_command` save loop, replace `target_weight=0.0,` with `(optimized_weights or equal_weights).get(card.ticker, 0.0)`.
- **Task 14 — F19+F22 (small):** F19: `pending_command` `if r.get("expected_ret")` → `is not None`. F22: docstring on `max_drawdown` documenting NaN-on-empty contract + 2 metrics tests.
- **Task 15 — F13 (medium):** Add DB-backed E2E test in test_integration.py (temp DB → upsert_prices → save_recommendation → record_trade → mark_executed → assert). Keep existing in-memory test.
- **Task 16 — F7 + F5-docs + docs sync (medium, no code risk):** Correct CLAUDE.md `capital_tier` claim (it's inert; tier machinery is Tier 2 work; `region:` fields are descriptive). Document drift-SELL exemption in Hard Constraint 3. Append LEARNING.md decision entry. Update PROJECT_STATUS.md. (Optional NAV tripwire in `status` — skip if it expands scope.)
- **Task 17 — F21 (small):** Remove stale `.claude/worktrees/phase-3-p35-ntfy-alerts/`. Inspect first (`git worktree list`); if uncommitted unique work, STOP and surface. It pollutes repo-wide greps.
- **Task 18 — Finalize:** Full `pytest`, append a finding→resolution closeout section to the review doc (append-only, don't edit original), `git tag -a v1.2.0-guardrails`, report to operator + ask about merge to main.

## LOCKED DECISIONS (operator, 2026-05-30 — do not relitigate)
- **F2:** soft-halt — at `current_dd >= risk.max_drawdown` (0.20) suppress BUYs→SKIP/DRAWDOWN_HALT, keep SELL/HOLD/WARN, banner + alert note. Toggle `risk.drawdown_halt_enabled`.
- **F5:** ratify exemption — drift-SELL stays off the profit-floor gate (risk-control), keeps $50 floor, but shows `cost_estimate`. Document in CLAUDE.md (Task 16).
- **F1:** hard block at cap + logged `--force --justification`; warn at 20.
- **F11:** drop redundant daily-run signal steps (don't thread run_id across subprocesses).
- **F7:** correct the doc claim; do NOT build tier-switching now.

## ENVIRONMENT GOTCHAS (these cost the prior session a lot of time)
1. **A PostToolUse hook (`.claude/hooks/run_tests_on_src_change.py`) auto-runs the full suite with `-x` after every src/test edit.** Its RED/GREEN is real free verification — but it fires on the *first* edit of a multi-edit change, so mid-sequence RED is expected and not necessarily a real failure. Always confirm with your own explicit `pytest -q | tail -3` after a logical unit.
2. **Tool output was intermittently truncated/garbled/stale** — at one point fabricated test content appeared and caused ~15 wasted cycles. Mitigation: trust `git show HEAD:<path>` and direct `python -c`/probe output over large Read/tail dumps; verify HEAD with `git --no-pager log -1 --format="%h %s"` (single line, hard to corrupt). If output looks wrong, re-run ONE clean command rather than re-reading.
3. **`tail` on pytest sometimes hid the summary line** — a `2 failed` prefix got masked once, and a regression rode through 2 commits before being caught (fixed in 9f81678). After each commit, run a clean full `pytest -q | tail -3` and read the PASS/FAIL count explicitly.
4. **LF→CRLF git warnings are harmless** (Windows). Ignore.
5. **Read-before-edit is enforced** — Read (or `git show`) a file in-session before Edit or the call is rejected.
6. **`config/portfolio.yaml` already has the new keys** added this session: `risk.drawdown_halt_enabled: true` and a `data:` block (`fetch_retries`, `fetch_backoff_seconds`, `fetch_max_failures`).

## Test files created this session
- `tests/test_phase3_cli.py` (F2 halt wiring + F1/F12 CRA execute) — 5 tests
- `tests/test_phase2_cli.py` (F4) — 2 tests
- `tests/test_ingest.py` (F3) — 4 tests
- New tests appended to: test_recommendations.py (spread, drift-cost, drawdown-halt, F14), test_storage.py (TickerMetadataContract), test_alerts.py (ceiling note)
