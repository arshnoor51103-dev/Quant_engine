# Tier 1 Operationalization Runbook

> **What this is:** the step-by-step to take Tier 1 from *coded-and-tested* to *actually operating with real money*. This is a **runbook, not a feature** — it ships no code, so it does **not** earn a version bump. The current merged state is marked by the metadata tag `v1.2.0-guardrails-merged`. The next version bump (v1.2.1 / v1.3.0) is whatever the **first real trade** reveals needs fixing.
>
> **Audience:** Arsh (operator). Run these in order. Each step has a verification you must see before moving on.

---

## Why this runbook exists — the gap it closes

v1.2.0 closed all 22 code-review findings and the suite is 238/238 green. But green tests are against **mocks and temp DBs**. A DB + config audit on 2026-05-31 found the live system has never actually operated:

| Reality (live `data/quant.db`, 2026-05-31) | Implication |
|---|---|
| **0 trades, 0 holdings**, 36 recommendations all `pending` | The BUY/SELL/execute/CRA-cap path — including every v1.2.0 guardrail — has **never run on real money**. NAV ≈ $0. |
| `alerts_log` table **does not exist** in the live DB | `--notify` / daily-run has never written an alert here. The alerts subsystem is a unit-tested shell, never activated. |
| `schema_version` table **does not exist** in the live DB | The live DB predates the F15 migration runner; `quant init` has not been run since. |
| `alerts.ntfy_topic = "quant-arsh-7k2m9x"` with `# change before first use` | Placeholder topic. No device is subscribed. No real push has ever been delivered. |

The transport (`send_alert`) and trigger logic are real and correct — they have simply never been pointed at a live DB or a subscribed phone. This runbook does that.

---

## Definition of "operational" (exit checklist)

Tier 1 is operational when **all** of these are true:

- [ ] A real ntfy push notification has been **received on the phone** (not just sent).
- [ ] `alerts_log` **and** `schema_version` tables exist in `data/quant.db`.
- [ ] At least **one executed trade** exists in the `trades` table (real Wealthsimple fill, recorded via `quant execute`).
- [ ] `quant status` reflects the resulting holding and NAV.
- [ ] `quant daily-run` completes against the live DB with **no missing-table / no silent-failure** errors.

Until every box is checked, "the system works" means "the tests pass," not "the system works."

---

## Step 1 — Sync the live database schema

The live DB is missing `alerts_log` and `schema_version`. Anything that writes an alert (`--notify`, `daily-run`) will fail or no-op until these exist. `quant init` is idempotent (`CREATE TABLE IF NOT EXISTS` + the F15 `run_migrations()` runner), so this is safe on the existing DB — it adds the missing tables and records schema versions without touching existing data.

```powershell
quant init
```

**Verify** (must see both tables + schema versions 1,2; existing 36 recs untouched):

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/quant.db'); print('tables:', sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"))); print('schema_version:', [r[0] for r in c.execute('SELECT version FROM schema_version')]); print('recs still present:', c.execute('SELECT COUNT(*) FROM recommendations').fetchone()[0])"
```

Expected: `alerts_log` and `schema_version` now appear in `tables`; `schema_version: [1, 2]`; `recs still present: 36`.

---

## Step 2 — Activate phone alerts (make the shell real)

**2a. Pick a real, private topic.** ntfy.sh public topics are readable by **anyone who knows the name** — and this name lives in a committed config file. Generate a fresh, long, unguessable topic and replace the placeholder in `config/portfolio.yaml`:

```yaml
alerts:
  enabled: true
  ntfy_topic: "quant-arsh-<long-random-string>"   # ← replace the placeholder
```

> Privacy note: a long random string is obscurity, not security. Alert bodies carry signal/regime/drawdown info. For a personal repo this is an acceptable tradeoff; if the repo is ever shared or made public, rotate the topic or self-host ntfy. Do not reuse the committed placeholder `quant-arsh-7k2m9x` — treat it as burned.

**2b. Subscribe a device.** Install the ntfy app (iOS App Store / Google Play) or open `https://ntfy.sh/<your-topic>` in a browser, and subscribe to the exact topic from 2a.

**2c. Send the test ping:**

```powershell
quant alert-test
```

**Verify:** the terminal prints `Test alert sent → https://ntfy.sh/<topic>` **and** a notification titled *"Quant Engine — Alert test — system is live"* lands on your phone within a few seconds. If the terminal succeeds but no push arrives, the topic/subscription is wrong — fix 2a/2b, not the code.

---

## Step 3 — Validate triggers end-to-end (optional but recommended)

Transport is proven by Step 2; trigger *logic* is unit-tested. To confirm the wiring on the live DB, run a notify-enabled recommend and watch for a real push if a card passes all gates:

```powershell
quant fetch
quant recommend --cash 0 --notify
```

**Verify:** if ≥1 card is actionable, a *New Recommendation* push arrives and a row appears in `alerts_log`:

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/quant.db'); print([dict(zip(['type','n','last'],r)) for r in c.execute('SELECT alert_type, COUNT(*), MAX(fired_at) FROM alerts_log GROUP BY alert_type')])"
```

(No actionable card is a valid outcome — it means nothing cleared the cost gate today, not a failure.)

---

## Step 4 — First real trade (exercise the execute path)

This is the milestone that turns "coded" into "operating." It runs `record_trade`, the **F1 CRA-cap gate**, the MIN_HOLD gate, and the holdings update — for the first time, with real money.

**4a. Generate fresh, saved recommendations** (the existing 36 predate the F17 `target_weight` fix; start clean):

```powershell
quant fetch
quant recommend --cash <your-contribution-amount> --optimize --save
quant pending
```

Note the `id` of the BUY card you intend to execute.

**4b. Execute the BUY manually in the Wealthsimple app.** Record the **actual fill price and units** Wealthsimple gives you.

**4c. Record the fill** (use the real numbers, not the estimate):

```powershell
quant execute <rec_id> --price <actual_fill_price> --units <actual_units>
```

> If this is ever trade #25+ in a calendar year, the F1 CRA gate will **block** it; override only with `--force --justification "reason"` (logged). At one trade, you are nowhere near the cap.

**Verify:**

```powershell
quant status      # holding + NAV now reflect the trade
quant pending     # the executed rec is gone from pending
python -c "import sqlite3; c=sqlite3.connect('data/quant.db'); print('trades:', c.execute('SELECT COUNT(*) FROM trades').fetchone()[0]); print('holdings:', c.execute('SELECT COUNT(*) FROM holdings').fetchone()[0])"
```

Expected: `trades: 1`, `holdings: 1`, and `quant status` shows the position.

---

## Step 5 — Confirm the scheduled daily run

With a real topic and a synced DB, confirm the unattended pipeline works against live state:

```powershell
quant daily-run        # one manual run: fetch -> recommend (--optimize --save --notify)
```

**Verify:** completes with `0 STEP(S) FAILED`, writes signal_scores + recommendations under one run_id, and (if a card is actionable) delivers a push. Then confirm Windows Task Scheduler is actually registered (`scripts/setup_scheduler.ps1`) so it runs each morning without you.

---

## Rollback / safety

- **Step 1 (`quant init`)** is non-destructive (idempotent, additive). No rollback needed.
- **Step 2 (config topic)** is a one-line config edit; revert via git if needed. No DB impact.
- **Step 4 (first trade)** is the only step that writes real financial state. It is **manual and deliberate** — you place the Wealthsimple order yourself, then record it. If you record wrong numbers, the trade row and holding can be corrected directly in SQLite, but prefer recording carefully the first time. Do **not** `--force` past the CRA cap without a genuine logged reason.

---

## Out of scope — deliberately not here

- **Tier 2 features** (capital-tier transition machinery, individual dividend stocks, covariance re-tuning, H001 re-eval). Tier 2 is gated on **NAV ≥ $10,000** (`universe.yaml: tier_2_unlock_nav`). At ~$0 deployed, building Tier 2 now would be speculation without operating data. Forward-looking Tier 2 candidate work belongs in `docs/research/watchlist/`, not a milestone doc — a Tier 2 milestone doc is deferred until real Tier 1 operating data exists to inform it.
- **A version bump.** This runbook is operations, not code. The next bump (v1.2.1 / v1.3.0) is scoped by whatever the first real trade (Step 4) surfaces.

---

*Created 2026-05-31, post v1.2.0-guardrails merge. State snapshot in "Why this runbook exists" is the verified starting point — update it as steps are completed.*
