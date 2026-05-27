# Phase 3 P3.5 — ntfy.sh Phone Alert Pipeline
**Date**: 2026-05-26
**Status**: Approved — ready for implementation planning

---

## Goal

Push one-way phone notifications to Arsh when the quant engine produces an actionable event:
a new trade recommendation, a volatility regime shift, or portfolio drawdown crossing 15%.

No bot framework, no webhooks, no polling. ntfy.sh is a single HTTP POST.

---

## Files Changed

| File | Type | Summary |
|---|---|---|
| `requirements.txt` | Edit | Add `requests>=2.31.0` |
| `src/alerts/__init__.py` | New | Empty package marker |
| `src/alerts/ntfy.py` | New | `send_alert()` — HTTP transport only |
| `src/data/storage.py` | Edit | `alerts_log` table DDL + `get_last_alert()` + `log_alert()` |
| `config/portfolio.yaml` | Edit | Add `alerts:` config block |
| `src/cli/phase3_commands.py` | Edit | `--notify` flag + three inline trigger checks in `recommend_command` |
| `src/cli/main.py` | Edit | Register `quant alert-test` command |
| `tests/test_alerts.py` | New | 12 unit tests |

---

## Section 1 — `requirements.txt`

Add before writing any code:

```
# HTTP (for ntfy.sh alerts — Phase 3 P3.5)
requests>=2.31.0
```

---

## Section 2 — `src/alerts/ntfy.py`

Single public function. HTTP transport only — no DB, no config, no trigger logic.

```python
def send_alert(
    topic: str,
    title: str,
    message: str,
    priority: int = 3,
    tags: list[str] | None = None,
) -> None:
```

- POSTs to `https://ntfy.sh/{topic}`
- Headers: `X-Title: {title}`, `X-Priority: {priority}`, `X-Tags: {comma-joined tags}` (omit X-Tags if tags is None or empty)
- Body: `message` (UTF-8 text)
- On any exception (`requests.RequestException`, timeout, etc.): `logging.warning(...)`, return silently. Never raises. The recommendation pipeline must not fail because a phone alert failed.
- Timeout: 5 seconds.

---

## Section 3 — `storage.py` additions

### New table (append to `SCHEMA_SQL`)

```sql
CREATE TABLE IF NOT EXISTS alerts_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type  TEXT    NOT NULL,
    fired_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_log_type
    ON alerts_log(alert_type, fired_at DESC);
```

### `get_last_alert(alert_type: str, db_path: Path = DB_PATH) -> dict | None`

Returns the single most recent row for `alert_type` as `{"id", "alert_type", "fired_at", "payload"}`, or `None` if no rows exist. Used to read previous state for transition detection.

### `log_alert(alert_type: str, payload: str, db_path: Path = DB_PATH) -> int`

Inserts a new row into `alerts_log`, returns the new `id`. Called both when an alert fires (POST sent) and when a recovery state is recorded (no POST sent). The payload distinguishes the two cases.

### Alert type naming convention

| `alert_type` | When written | Payload shape |
|---|---|---|
| `"NEW_RECOMMENDATION"` | ntfy POST sent | `[{"ticker": str, "action": str, "signal": float}, ...]` |
| `"REGIME_CHANGE"` | ntfy POST sent | `{"regime": str, "previous": str \| null}` |
| `"DRAWDOWN"` | ntfy POST sent OR recovery recorded | `{"status": "WARNING"\|"RECOVERED", "drawdown": float}` |

`get_last_alert("DRAWDOWN")` returns the most recent row regardless of `status`. The crossing logic reads `payload["status"]` to determine direction.

---

## Section 4 — `config/portfolio.yaml` additions

Append to `portfolio.yaml`:

```yaml
# Phone alerts via ntfy.sh (Phase 3 P3.5)
# Public topic — anyone who knows the topic name can subscribe.
# Use an obscure name. Self-host ntfy if privacy matters later.
alerts:
  enabled: true
  ntfy_topic: "quant-arsh-7k2m9x"   # change before first use
  triggers:
    - NEW_RECOMMENDATION
    - REGIME_CHANGE
    - DRAWDOWN_WARNING
```

`enabled: false` suppresses all alerts. Remove individual items from `triggers` to suppress specific ones without disabling the module.

`portfolio_cfg` is already loaded inside `recommend_command` — access via `portfolio_cfg.get("alerts", {})`.

---

## Section 5 — `phase3_commands.py` changes

### New flag on `recommend_command`

```python
notify: bool = typer.Option(False, "--notify", help="Send ntfy.sh push alerts for actionable events")
```

Independent of `--save`. Can notify without saving.

### New private helper

```python
def _portfolio_nav_series(
    holdings: list[Holding],
    price_data: dict[str, pd.Series],
) -> pd.Series:
```

Uses full price history (no lookback truncation). Sums `holding.units * price_data[ticker]` for each held ticker that has price data. Aligns on the intersection of available dates. Returns an empty Series if no holdings or no matching price data.

Called only from the DRAWDOWN trigger. `max_drawdown(nav_series)` from `portfolio.metrics` operates on this output.

### Trigger block (appended after the `if save:` block)

```python
if notify:
    alerts_cfg = portfolio_cfg.get("alerts", {})
    if alerts_cfg.get("enabled"):
        topic = alerts_cfg["ntfy_topic"]
        triggers = set(alerts_cfg.get("triggers") or [])

        # NEW_RECOMMENDATION — fire when ≥1 card passes all gates
        if "NEW_RECOMMENDATION" in triggers:
            passing = [c for c in cards
                       if c.action in ("BUY", "SELL") and c.gate_status == GateStatus.PASS]
            if passing:
                body = "\n".join(
                    f"{c.action} {c.ticker}  signal={c.combined_signal:+.3f}"
                    f"  exp={c.expected_return_pct:.1%}"
                    for c in passing
                )
                send_alert(topic, "New Recommendation", body,
                           tags=["chart_with_upwards_trend"])
                log_alert("NEW_RECOMMENDATION", json.dumps(
                    [{"ticker": c.ticker, "action": c.action,
                      "signal": round(c.combined_signal, 4)} for c in passing]
                ))

        # REGIME_CHANGE — fire when vol regime shifts from last persisted value
        if "REGIME_CHANGE" in triggers:
            last = get_last_alert("REGIME_CHANGE")
            last_regime = json.loads(last["payload"]).get("regime") if last else None
            if last_regime != regime_name:
                send_alert(topic, "Regime Change",
                           f"{(last_regime or 'unknown').upper()} → {regime_name.upper()}",
                           priority=4, tags=["warning"])
                log_alert("REGIME_CHANGE",
                          json.dumps({"regime": regime_name, "previous": last_regime}))

        # DRAWDOWN — transition detector
        # Fires when portfolio crosses above drawdown_alert threshold.
        # Logs a RECOVERED entry (no POST) when it returns below threshold,
        # enabling the next crossing to fire again.
        if "DRAWDOWN_WARNING" in triggers:
            threshold = portfolio_cfg["risk"]["drawdown_alert"]   # 0.15
            nav_series = _portfolio_nav_series(holdings, price_data)
            current_dd = abs(max_drawdown(nav_series)) if not nav_series.empty else 0.0

            last = get_last_alert("DRAWDOWN")
            last_payload = json.loads(last["payload"]) if (last and last["payload"]) else {}
            last_status = last_payload.get("status", "RECOVERED")   # default: not in warning

            if current_dd > threshold and last_status == "RECOVERED":
                send_alert(topic, "Drawdown Warning",
                           f"Portfolio drawdown {current_dd:.1%} — "
                           f"alert threshold {threshold:.0%}",
                           priority=5, tags=["rotating_light"])
                log_alert("DRAWDOWN",
                          json.dumps({"status": "WARNING", "drawdown": round(current_dd, 4)}))
            elif current_dd <= threshold and last_status == "WARNING":
                log_alert("DRAWDOWN",
                          json.dumps({"status": "RECOVERED", "drawdown": round(current_dd, 4)}))
```

### Imports added to `phase3_commands.py`

```python
import json
from ..alerts.ntfy import send_alert
from ..data.storage import get_last_alert, log_alert
from ..portfolio.metrics import max_drawdown
```

---

## Section 6 — `main.py`: `quant alert-test`

```python
@app.command(name="alert-test")
def alert_test() -> None:
    """Send a test ping to the configured ntfy.sh topic."""
    from ..portfolio.model import load_portfolio_config
    from ..alerts.ntfy import send_alert
    cfg = load_portfolio_config().get("alerts", {})
    if not cfg.get("enabled"):
        console.print("[yellow]alerts.enabled is false in portfolio.yaml — nothing sent.[/yellow]")
        return
    topic = cfg["ntfy_topic"]
    send_alert(topic, "Quant Engine", "Alert test — system is live")
    console.print(f"[green]Test alert sent → https://ntfy.sh/{topic}[/green]")
```

---

## Section 7 — Tests (`tests/test_alerts.py`)

All tests mock `requests.post` (or use monkeypatching on `send_alert`) to avoid real network calls.

| # | Test name | What it verifies |
|---|---|---|
| 1 | `test_send_alert_posts_correct_payload` | `requests.post` called with correct URL, title header, body |
| 2 | `test_send_alert_priority_maps_to_header` | `priority=4` → `X-Priority: 4` header |
| 3 | `test_send_alert_no_tags_omits_header` | `tags=None` → no `X-Tags` header in the call |
| 4 | `test_send_alert_silences_network_error` | `requests.post` raises `ConnectionError` → no exception propagates from `send_alert` |
| 5 | `test_alerts_disabled_suppresses_send` | `enabled: false` in `portfolio_cfg` → trigger block exits early, `requests.post` never called — tested through `recommend_command` trigger logic, not by calling `send_alert` directly |
| 6 | `test_new_recommendation_fires_on_passing_card` | Passing BUY card + `PASS` gate → `send_alert` called + `log_alert` called |
| 7 | `test_new_recommendation_silent_on_all_skip` | All cards have action `SKIP` → `send_alert` not called |
| 8 | `test_regime_change_fires_on_transition` | `get_last_alert("REGIME_CHANGE")` returns `{"regime": "NORMAL"}`, current regime = `"HIGH_VOL"` → fires |
| 9 | `test_regime_change_silent_if_same` | Last persisted regime = current regime → `send_alert` not called |
| 10 | `test_drawdown_warning_fires_on_crossing` | `last_status="RECOVERED"`, `current_dd=0.17` → fires, logs `{"status": "WARNING"}` |
| 11 | `test_drawdown_warning_silent_if_already_in_warning` | `last_status="WARNING"`, `current_dd=0.18` → silent |
| 12 | `test_drawdown_warning_logs_recovery_no_post` | `last_status="WARNING"`, `current_dd=0.10` → `log_alert` called with `status=RECOVERED`, `requests.post` not called |

---

## Transition State Machine (DRAWDOWN)

```
          current_dd > 0.15        current_dd ≤ 0.15
last=RECOVERED   → fire WARNING + log WARNING   → no-op
last=WARNING     → no-op                         → log RECOVERED (no POST)
last=None        → fire WARNING + log WARNING   → no-op
```

---

## What This Does NOT Do

- No retry on ntfy.sh failure — fire-and-forget by design.
- No alert deduplication window for NEW_RECOMMENDATION — every passing card run fires. If you run `recommend --notify` twice in a row with the same cards, you get two alerts. Acceptable for a manual-trigger workflow.
- No Telegram fallback — ntfy.sh only. Revisit at Phase 4 if interactive trade approval (inline buttons) is needed.
- No scheduled invocation — that is Phase 3 P3.6.
