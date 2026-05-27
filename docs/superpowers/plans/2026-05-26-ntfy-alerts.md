# Phase 3 P3.5 — ntfy.sh Phone Alert Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire ntfy.sh push notifications into the recommendation pipeline — new trade cards, regime shifts, and drawdown threshold crossings all trigger phone alerts.

**Architecture:** Three layers. `src/alerts/ntfy.py` is pure HTTP transport with no DB or logic. `src/data/storage.py` owns the `alerts_log` table and two CRUD helpers (`get_last_alert`, `log_alert`) for state tracking. `src/cli/phase3_commands.py` hosts `_run_alert_triggers()` (private helper, called from `recommend_command --notify`) and `_portfolio_nav_series()` (NAV series builder for the drawdown calculation).

**Tech Stack:** `requests>=2.31.0`, ntfy.sh public instance, SQLite `alerts_log` table, pytest + `unittest.mock`

---

## File Map

| Path | New/Edit | Responsibility |
|---|---|---|
| `requirements.txt` | Edit | Add `requests>=2.31.0` |
| `src/alerts/__init__.py` | New | Package marker (empty) |
| `src/alerts/ntfy.py` | New | `send_alert()` HTTP transport only |
| `src/data/storage.py` | Edit | `alerts_log` DDL appended to `SCHEMA`; `get_last_alert()`; `log_alert()` |
| `config/portfolio.yaml` | Edit | `alerts:` block (enabled, ntfy_topic, triggers list) |
| `src/cli/phase3_commands.py` | Edit | `_portfolio_nav_series()`; `_run_alert_triggers()`; `--notify` flag on `recommend_command` |
| `src/cli/main.py` | Edit | Add `load_portfolio_config` + `send_alert` imports; `alert_test` command |
| `tests/test_alerts.py` | New | 12 tests: 4 transport + 8 trigger logic |
| `tests/test_storage.py` | Edit | 4 new tests for `get_last_alert` / `log_alert` |

**Baseline:** 159 tests passing. **Target:** 175 tests passing (+16).

---

## Task 1 — Add `requests` to requirements.txt

**Files:**
- Edit: `requirements.txt`

- [ ] **Step 1: Add the dependency**

In `requirements.txt`, append after the `scikit-learn` line:

```
# HTTP (for ntfy.sh alerts — Phase 3 P3.5)
requests>=2.31.0
```

- [ ] **Step 2: Install**

```
pip install "requests>=2.31.0"
```

Expected: `Successfully installed requests-2.x.x` or `Requirement already satisfied`.

- [ ] **Step 3: Confirm baseline still passes**

```
python -m pytest tests/ -q
```

Expected: `159 passed`

- [ ] **Step 4: Commit**

```
git add requirements.txt
git commit -m "chore: add requests>=2.31.0 for ntfy.sh alert transport"
```

---

## Task 2 — HTTP transport layer (`src/alerts/ntfy.py`)

**Files:**
- Create: `src/alerts/__init__.py`
- Create: `src/alerts/ntfy.py`
- Create: `tests/test_alerts.py`

- [ ] **Step 1: Create the package marker**

Create `src/alerts/__init__.py` as an empty file.

- [ ] **Step 2: Write 4 failing transport tests**

Create `tests/test_alerts.py`:

```python
"""
Tests for src/alerts/ntfy.py (HTTP transport) and the trigger logic
in src/cli/phase3_commands.py.

All network calls are mocked — no real HTTP is made.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.alerts.ntfy import send_alert


# ─── Transport: send_alert ────────────────────────────────────────────────────

def test_send_alert_posts_correct_payload() -> None:
    """URL, title header, and body must match the ntfy.sh POST contract."""
    with patch("src.alerts.ntfy.requests.post") as mock_post:
        send_alert("my-topic", "Alert Title", "Alert body")
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        kwargs = mock_post.call_args[1]
        assert url == "https://ntfy.sh/my-topic"
        assert kwargs["data"] == b"Alert body"
        assert kwargs["headers"]["X-Title"] == "Alert Title"


def test_send_alert_priority_maps_to_header() -> None:
    """priority=4 must appear as X-Priority: '4' in request headers."""
    with patch("src.alerts.ntfy.requests.post") as mock_post:
        send_alert("t", "T", "M", priority=4)
        assert mock_post.call_args[1]["headers"]["X-Priority"] == "4"


def test_send_alert_no_tags_omits_header() -> None:
    """tags=None must not produce an X-Tags header."""
    with patch("src.alerts.ntfy.requests.post") as mock_post:
        send_alert("t", "T", "M", tags=None)
        assert "X-Tags" not in mock_post.call_args[1]["headers"]


def test_send_alert_silences_network_error() -> None:
    """Any requests exception must be swallowed — never propagates."""
    with patch("src.alerts.ntfy.requests.post", side_effect=ConnectionError("down")):
        send_alert("t", "T", "M")  # must not raise
```

- [ ] **Step 3: Run — expect 4 import errors**

```
python -m pytest tests/test_alerts.py -v
```

Expected: `ERROR` on all 4 — `ModuleNotFoundError: No module named 'src.alerts'`

- [ ] **Step 4: Implement `src/alerts/ntfy.py`**

```python
"""
HTTP transport for ntfy.sh push notifications.

ntfy.sh POST API: https://docs.ntfy.sh/publish/
"""
from __future__ import annotations

import logging

import requests

_BASE_URL = "https://ntfy.sh"
_TIMEOUT = 5  # seconds


def send_alert(
    topic: str,
    title: str,
    message: str,
    priority: int = 3,
    tags: list[str] | None = None,
) -> None:
    """
    POST a push notification to ntfy.sh.

    Args:
        topic:    ntfy.sh topic name (public unless self-hosted).
        title:    Short notification header.
        message:  Body text shown in the notification.
        priority: 1 (min) – 5 (urgent). Default 3 = normal.
        tags:     Optional emoji tags. See https://docs.ntfy.sh/emojis/

    Never raises — network failures are logged at WARNING and dropped.
    The recommendation pipeline must not fail because an alert failed.
    """
    headers: dict[str, str] = {
        "X-Title": title,
        "X-Priority": str(priority),
    }
    if tags:
        headers["X-Tags"] = ",".join(tags)

    try:
        requests.post(
            f"{_BASE_URL}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        logging.warning("ntfy.sh alert failed — %s", exc)
```

- [ ] **Step 5: Run transport tests — expect 4 passes**

```
python -m pytest tests/test_alerts.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Run full suite — no regressions**

```
python -m pytest tests/ -q
```

Expected: `163 passed`

- [ ] **Step 7: Commit**

```
git add src/alerts/__init__.py src/alerts/ntfy.py tests/test_alerts.py
git commit -m "feat: add src/alerts/ntfy.py HTTP transport + 4 tests"
```

---

## Task 3 — `alerts_log` table + storage functions

**Files:**
- Edit: `src/data/storage.py`
- Edit: `tests/test_storage.py`

- [ ] **Step 1: Write 4 failing storage tests**

Open `tests/test_storage.py`. Add `import json` after the existing stdlib imports (line 6–7 area). Then add `get_last_alert` and `log_alert` to the import block at the top:

```python
# Extend the existing import block to include:
from src.data.storage import (
    get_annual_trade_count,
    get_last_alert,         # NEW
    get_last_buy_date,
    initialize,
    log_alert,              # NEW
    mark_recommendation_executed,
    mark_recommendation_skipped,
    migrate_recommendations_v2,
    record_trade,
    save_recommendation,
)
```

Append these four tests at the end of `tests/test_storage.py`:

```python
# ─── alerts_log: get_last_alert / log_alert ───────────────────────────────────

def test_get_last_alert_returns_none_when_empty(tmp_db: Path) -> None:
    """No rows for a given alert_type → None, not an error."""
    assert get_last_alert("NEW_RECOMMENDATION", db_path=tmp_db) is None


def test_log_and_get_last_alert_roundtrip(tmp_db: Path) -> None:
    """log_alert inserts a row; get_last_alert returns it with correct payload."""
    import json
    payload = json.dumps({"regime": "HIGH_VOL", "previous": "NORMAL"})
    row_id = log_alert("REGIME_CHANGE", payload, db_path=tmp_db)
    assert isinstance(row_id, int) and row_id > 0
    result = get_last_alert("REGIME_CHANGE", db_path=tmp_db)
    assert result is not None
    assert result["alert_type"] == "REGIME_CHANGE"
    assert json.loads(result["payload"])["regime"] == "HIGH_VOL"


def test_get_last_alert_returns_most_recent(tmp_db: Path) -> None:
    """When multiple rows exist for the same type, returns the newest."""
    import json
    log_alert("DRAWDOWN", json.dumps({"status": "WARNING",   "drawdown": 0.17}), db_path=tmp_db)
    log_alert("DRAWDOWN", json.dumps({"status": "RECOVERED", "drawdown": 0.12}), db_path=tmp_db)
    result = get_last_alert("DRAWDOWN", db_path=tmp_db)
    assert json.loads(result["payload"])["status"] == "RECOVERED"


def test_get_last_alert_does_not_cross_alert_types(tmp_db: Path) -> None:
    """Rows for REGIME_CHANGE must not appear in DRAWDOWN queries."""
    import json
    log_alert("REGIME_CHANGE", json.dumps({"regime": "NORMAL"}), db_path=tmp_db)
    assert get_last_alert("DRAWDOWN", db_path=tmp_db) is None
```

- [ ] **Step 2: Run — expect 4 import errors**

```
python -m pytest tests/test_storage.py::test_get_last_alert_returns_none_when_empty tests/test_storage.py::test_log_and_get_last_alert_roundtrip tests/test_storage.py::test_get_last_alert_returns_most_recent tests/test_storage.py::test_get_last_alert_does_not_cross_alert_types -v
```

Expected: `ImportError: cannot import name 'get_last_alert'`

- [ ] **Step 3: Append `alerts_log` DDL to `SCHEMA` in `storage.py`**

In `src/data/storage.py`, find the `SCHEMA` string. The last line before the closing `"""` is:

```
    ON signal_scores(ticker, run_date DESC);
```

Insert these two SQL statements immediately before that closing `"""`:

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

- [ ] **Step 4: Append `get_last_alert` and `log_alert` to `storage.py`**

Add these two functions at the end of `src/data/storage.py`:

```python
def get_last_alert(alert_type: str, db_path: Path = DB_PATH) -> dict | None:
    """
    Return the most recent alerts_log row for alert_type, or None.

    Used by trigger checks to detect state transitions — e.g. whether the
    last DRAWDOWN row has status WARNING or RECOVERED.
    """
    sql = """
    SELECT id, alert_type, fired_at, payload
    FROM alerts_log
    WHERE alert_type = ?
    ORDER BY fired_at DESC
    LIMIT 1;
    """
    with get_connection(db_path) as conn:
        row = conn.execute(sql, (alert_type,)).fetchone()
    return dict(row) if row is not None else None


def log_alert(alert_type: str, payload: str, db_path: Path = DB_PATH) -> int:
    """
    Insert a row into alerts_log and return the new row id.

    Called both when an ntfy POST fires (alert sent) and when a recovery
    state is recorded with no POST (DRAWDOWN transition bookkeeping only).
    """
    sql = "INSERT INTO alerts_log (alert_type, payload) VALUES (?, ?);"
    with get_connection(db_path) as conn:
        cur = conn.execute(sql, (alert_type, payload))
        return cur.lastrowid
```

- [ ] **Step 5: Run 4 storage tests — expect pass**

```
python -m pytest tests/test_storage.py::test_get_last_alert_returns_none_when_empty tests/test_storage.py::test_log_and_get_last_alert_roundtrip tests/test_storage.py::test_get_last_alert_returns_most_recent tests/test_storage.py::test_get_last_alert_does_not_cross_alert_types -v
```

Expected: `4 passed`

- [ ] **Step 6: Run full suite**

```
python -m pytest tests/ -q
```

Expected: `167 passed`

- [ ] **Step 7: Commit**

```
git add src/data/storage.py tests/test_storage.py
git commit -m "feat: add alerts_log table + get_last_alert / log_alert to storage"
```

---

## Task 4 — `alerts:` config block in `portfolio.yaml`

**Files:**
- Edit: `config/portfolio.yaml`

- [ ] **Step 1: Append the alerts block**

Add at the end of `config/portfolio.yaml`:

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

- [ ] **Step 2: Verify YAML parses cleanly**

```
python -c "import yaml; d = yaml.safe_load(open('config/portfolio.yaml')); assert 'alerts' in d; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add config/portfolio.yaml
git commit -m "config: add alerts block to portfolio.yaml (ntfy_topic + triggers)"
```

---

## Task 5 — Trigger logic in `phase3_commands.py`

**Files:**
- Edit: `src/cli/phase3_commands.py`
- Edit: `tests/test_alerts.py`

- [ ] **Step 1: Write 8 failing trigger tests**

Append to `tests/test_alerts.py` (after the 4 transport tests already there):

```python
# ─── Trigger logic: _run_alert_triggers ──────────────────────────────────────

import pandas as pd
from src.cli.phase3_commands import _run_alert_triggers
from src.portfolio.recommendations import GateStatus


def _nav_series_with_dd(dd: float) -> pd.Series:
    """Price series whose peak-to-trough drawdown equals dd (positive fraction).
    Series is [1.0, 1.0, 1.0 - dd], so max_drawdown returns -(dd)."""
    return pd.Series(
        [1.0, 1.0, 1.0 - dd],
        index=pd.date_range("2026-01-01", periods=3),
    )


def _cfg(enabled: bool = True, triggers: list[str] | None = None) -> dict:
    return {
        "alerts": {
            "enabled": enabled,
            "ntfy_topic": "test-topic",
            "triggers": triggers if triggers is not None
                        else ["NEW_RECOMMENDATION", "REGIME_CHANGE", "DRAWDOWN_WARNING"],
        },
        "risk": {"drawdown_alert": 0.15},
    }


def _buy_card() -> MagicMock:
    c = MagicMock()
    c.action = "BUY"
    c.gate_status = GateStatus.PASS
    c.ticker = "VFV.TO"
    c.combined_signal = 0.75
    c.expected_return_pct = 0.08
    return c


def _skip_card() -> MagicMock:
    c = MagicMock()
    c.action = "SKIP"
    c.gate_status = GateStatus.SKIP_SIGNAL
    return c


# Test 5
def test_alerts_disabled_suppresses_send() -> None:
    """enabled: false → send_alert never called regardless of cards or regime."""
    with patch("src.cli.phase3_commands.send_alert") as mock_send:
        _run_alert_triggers([_buy_card()], "NORMAL", _cfg(enabled=False), [], {})
        mock_send.assert_not_called()


# Test 6
def test_new_recommendation_fires_on_passing_card() -> None:
    """A PASS-gate BUY card triggers a NEW_RECOMMENDATION alert and log entry."""
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.log_alert") as mock_log:
        _run_alert_triggers([_buy_card()], "NORMAL",
                            _cfg(triggers=["NEW_RECOMMENDATION"]), [], {})
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == "New Recommendation"
        mock_log.assert_called_once()
        logged = json.loads(mock_log.call_args[0][1])
        assert logged[0]["ticker"] == "VFV.TO"
        assert logged[0]["action"] == "BUY"


# Test 7
def test_new_recommendation_silent_on_all_skip() -> None:
    """Only SKIP-action cards → send_alert not called."""
    with patch("src.cli.phase3_commands.send_alert") as mock_send:
        _run_alert_triggers([_skip_card()], "NORMAL",
                            _cfg(triggers=["NEW_RECOMMENDATION"]), [], {})
        mock_send.assert_not_called()


# Test 8
def test_regime_change_fires_on_transition() -> None:
    """Persisted regime NORMAL, current HIGH_VOL → REGIME_CHANGE alert fires."""
    last_row = {"payload": json.dumps({"regime": "NORMAL", "previous": None})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands.log_alert") as mock_log:
        _run_alert_triggers([], "HIGH_VOL", _cfg(triggers=["REGIME_CHANGE"]), [], {})
        mock_send.assert_called_once()
        assert "HIGH_VOL" in mock_send.call_args[0][2].upper()
        logged = json.loads(mock_log.call_args[0][1])
        assert logged["regime"] == "HIGH_VOL"
        assert logged["previous"] == "NORMAL"


# Test 9
def test_regime_change_silent_if_same() -> None:
    """Persisted regime equals current regime → send_alert not called."""
    last_row = {"payload": json.dumps({"regime": "NORMAL", "previous": None})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["REGIME_CHANGE"]), [], {})
        mock_send.assert_not_called()


# Test 10
def test_drawdown_warning_fires_on_crossing() -> None:
    """Last status RECOVERED + current drawdown 17% > 15% threshold → WARNING fires."""
    last_row = {"payload": json.dumps({"status": "RECOVERED", "drawdown": 0.10})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands.log_alert") as mock_log, \
         patch("src.cli.phase3_commands._portfolio_nav_series",
               return_value=_nav_series_with_dd(0.17)):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["DRAWDOWN_WARNING"]), [], {})
        mock_send.assert_called_once()
        assert mock_send.call_args[1]["priority"] == 5
        logged = json.loads(mock_log.call_args[0][1])
        assert logged["status"] == "WARNING"
        assert abs(logged["drawdown"] - 0.17) < 0.01


# Test 11
def test_drawdown_warning_silent_if_already_in_warning() -> None:
    """Portfolio already in WARNING state (18% dd) → do not re-fire."""
    last_row = {"payload": json.dumps({"status": "WARNING", "drawdown": 0.16})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands._portfolio_nav_series",
               return_value=_nav_series_with_dd(0.18)):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["DRAWDOWN_WARNING"]), [], {})
        mock_send.assert_not_called()


# Test 12
def test_drawdown_warning_logs_recovery_no_post() -> None:
    """Drawdown recovers below threshold → log RECOVERED row, no ntfy POST."""
    last_row = {"payload": json.dumps({"status": "WARNING", "drawdown": 0.16})}
    with patch("src.cli.phase3_commands.send_alert") as mock_send, \
         patch("src.cli.phase3_commands.get_last_alert", return_value=last_row), \
         patch("src.cli.phase3_commands.log_alert") as mock_log, \
         patch("src.cli.phase3_commands._portfolio_nav_series",
               return_value=_nav_series_with_dd(0.10)):
        _run_alert_triggers([], "NORMAL", _cfg(triggers=["DRAWDOWN_WARNING"]), [], {})
        mock_send.assert_not_called()
        mock_log.assert_called_once()
        logged = json.loads(mock_log.call_args[0][1])
        assert logged["status"] == "RECOVERED"
        assert abs(logged["drawdown"] - 0.10) < 0.01
```

- [ ] **Step 2: Run 8 trigger tests — expect import errors**

```
python -m pytest tests/test_alerts.py -k "not test_send_alert" -v
```

Expected: `ImportError: cannot import name '_run_alert_triggers'`

- [ ] **Step 3: Add new imports to `phase3_commands.py`**

In `src/cli/phase3_commands.py`, extend the existing import blocks:

```python
# Add to stdlib imports (after `from collections import Counter`):
import json

# Add as a new third-party import (after the `from rich...` block):
import pandas as pd

# Add to local imports (after `from ..signals.vol_regime import VolRegimeSignal`):
from ..alerts.ntfy import send_alert
from ..data.storage import get_last_alert, log_alert
from ..portfolio.metrics import max_drawdown
```

- [ ] **Step 4: Add `_portfolio_nav_series` to `phase3_commands.py`**

Add this private helper function before `recommend_command` (after the `_print_weight_comparison` function):

```python
def _portfolio_nav_series(
    holdings: list,
    price_data: dict[str, pd.Series],
) -> pd.Series:
    """
    Weighted NAV series summed across all currently held tickers.

    Uses full price history (no lookback truncation). Aligns on the
    intersection of dates where all held tickers have price data.
    Returns an empty Series if no holdings match any price data.
    """
    frames = []
    for h in holdings:
        if h.ticker in price_data and not price_data[h.ticker].empty:
            frames.append(price_data[h.ticker] * h.units)
    if not frames:
        return pd.Series(dtype=float)
    combined = pd.concat(frames, axis=1)
    return combined.dropna().sum(axis=1)
```

- [ ] **Step 5: Add `_run_alert_triggers` to `phase3_commands.py`**

Add immediately after `_portfolio_nav_series`:

```python
def _run_alert_triggers(
    cards: list[TradeCard],
    regime_name: str,
    portfolio_cfg: dict,
    holdings: list,
    price_data: dict[str, pd.Series],
) -> None:
    """
    Evaluate the three alert triggers and POST to ntfy.sh where warranted.

    Called from recommend_command when --notify is set. All HTTP failures
    are swallowed inside send_alert — this function never raises.
    """
    alerts_cfg = portfolio_cfg.get("alerts", {})
    if not alerts_cfg.get("enabled"):
        return

    topic: str = alerts_cfg["ntfy_topic"]
    triggers: set[str] = set(alerts_cfg.get("triggers") or [])

    # NEW_RECOMMENDATION — fire when ≥1 card passes all gates
    if "NEW_RECOMMENDATION" in triggers:
        passing = [
            c for c in cards
            if c.action in ("BUY", "SELL") and c.gate_status == GateStatus.PASS
        ]
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
            send_alert(
                topic, "Regime Change",
                f"{(last_regime or 'unknown').upper()} → {regime_name.upper()}",
                priority=4, tags=["warning"],
            )
            log_alert("REGIME_CHANGE",
                      json.dumps({"regime": regime_name, "previous": last_regime}))

    # DRAWDOWN — transition detector.
    # Fires once on first crossing above drawdown_alert threshold.
    # Logs a RECOVERED row (no POST) when portfolio returns below threshold,
    # enabling the next crossing to fire again.
    if "DRAWDOWN_WARNING" in triggers:
        threshold: float = portfolio_cfg["risk"]["drawdown_alert"]
        nav_series = _portfolio_nav_series(holdings, price_data)
        current_dd = abs(max_drawdown(nav_series)) if not nav_series.empty else 0.0

        last = get_last_alert("DRAWDOWN")
        last_payload = json.loads(last["payload"]) if (last and last["payload"]) else {}
        last_status = last_payload.get("status", "RECOVERED")  # absent = never fired

        if current_dd > threshold and last_status == "RECOVERED":
            send_alert(
                topic, "Drawdown Warning",
                f"Portfolio drawdown {current_dd:.1%} — alert threshold {threshold:.0%}",
                priority=5, tags=["rotating_light"],
            )
            log_alert("DRAWDOWN",
                      json.dumps({"status": "WARNING", "drawdown": round(current_dd, 4)}))
        elif current_dd <= threshold and last_status == "WARNING":
            log_alert("DRAWDOWN",
                      json.dumps({"status": "RECOVERED", "drawdown": round(current_dd, 4)}))
```

- [ ] **Step 6: Add `--notify` flag and call site to `recommend_command`**

In `recommend_command`, add the new parameter after the `optimize` parameter:

```python
notify: bool = typer.Option(
    False, "--notify", help="Send ntfy.sh push alerts for actionable events"
),
```

At the very end of `recommend_command`, after the `_print_cards(...)` call, add:

```python
    if notify:
        _run_alert_triggers(cards, regime_name, portfolio_cfg, holdings, price_data)
```

- [ ] **Step 7: Run 8 trigger tests — expect all pass**

```
python -m pytest tests/test_alerts.py -k "not test_send_alert" -v
```

Expected: `8 passed`

- [ ] **Step 8: Run full suite**

```
python -m pytest tests/ -q
```

Expected: `175 passed`

- [ ] **Step 9: Commit**

```
git add src/cli/phase3_commands.py tests/test_alerts.py
git commit -m "feat: add --notify flag + _run_alert_triggers to recommend_command"
```

---

## Task 6 — `quant alert-test` command

**Files:**
- Edit: `src/cli/main.py`

- [ ] **Step 1: Add imports to `main.py`**

In `src/cli/main.py`, extend the `from ..portfolio.model import (...)` block to include `load_portfolio_config`:

```python
from ..portfolio.model import (
    bucket_allocation,
    get_holdings,
    load_portfolio_config,   # ADD
    nav,
    price_series,
)
```

Add a new local import line after the `.phase3_commands` block:

```python
from ..alerts.ntfy import send_alert
```

- [ ] **Step 2: Add the `alert_test` function**

Add this function before the `if __name__ == "__main__":` line at the bottom of `src/cli/main.py`:

```python
@app.command(name="alert-test")
def alert_test() -> None:
    """Send a test ping to the configured ntfy.sh topic."""
    cfg = load_portfolio_config().get("alerts", {})
    if not cfg.get("enabled"):
        console.print("[yellow]alerts.enabled is false in portfolio.yaml — nothing sent.[/yellow]")
        return
    topic = cfg["ntfy_topic"]
    send_alert(topic, "Quant Engine", "Alert test — system is live")
    console.print(f"[green]Test alert sent → https://ntfy.sh/{topic}[/green]")
```

- [ ] **Step 3: Verify the command appears in help**

```
python -m src.cli.main --help
```

Expected: `alert-test` appears in the list of commands.

```
python -m src.cli.main recommend --help
```

Expected: `--notify` flag appears in the output.

- [ ] **Step 4: Run full suite — no regressions**

```
python -m pytest tests/ -q
```

Expected: `175 passed`

- [ ] **Step 5: Commit**

```
git add src/cli/main.py
git commit -m "feat: add quant alert-test command for live ntfy.sh smoke test"
```

---

## Task 7 — Final verification + docs

**Files:**
- Edit: `LEARNING.md`
- Edit: `docs/PROJECT_STATUS.md`

- [ ] **Step 1: Full suite with verbose output**

```
python -m pytest tests/ -v --tb=short
```

Expected: `175 passed, 0 failed` — breakdown:
- `test_metrics.py`: 11
- `test_signals.py`: 11
- `test_recommendations.py`: 22
- `test_mean_reversion.py`: 16
- `test_optimizer.py`: 31
- `test_storage.py`: 21 (17 baseline + 4 new)
- `test_sell_logic.py`: 16
- `test_alerts.py`: 12 (4 transport + 8 trigger) — **new file**

Subtotal: 175

- [ ] **Step 2: Smoke-test imports**

```
python -c "
from src.alerts.ntfy import send_alert
from src.data.storage import get_last_alert, log_alert
from src.cli.phase3_commands import _run_alert_triggers, _portfolio_nav_series
print('imports OK')
"
```

Expected: `imports OK`

- [ ] **Step 3: Append LEARNING.md entry**

Append to `LEARNING.md`:

```markdown
### 2026-05-27 — Phase 3 P3.5: ntfy.sh phone alert pipeline
**Context**: `quant recommend` was purely a terminal tool. No notification fires when signals trigger while the operator is away from the computer.
**Decision**: ntfy.sh one-way push alerts (confirmed from 2026-05-20 decision). Three triggers wired into `recommend_command --notify`:
- `NEW_RECOMMENDATION`: fires when ≥1 gate-passing BUY or SELL card is produced.
- `REGIME_CHANGE`: fires when the vol regime value shifts from the last persisted row in `alerts_log`.
- `DRAWDOWN` (config key `DRAWDOWN_WARNING`): transition detector — fires once on first crossing above 15% alert threshold; logs a RECOVERED row (no POST) when portfolio returns below threshold, enabling re-fire on the next crossing.
**Implementation**: `src/alerts/ntfy.py` (HTTP transport only, fire-and-forget); `alerts_log` SQLite table + `get_last_alert` / `log_alert` in `storage.py`; `_run_alert_triggers()` private helper in `phase3_commands.py`; `--notify` flag on `quant recommend`; `quant alert-test` command. `requests>=2.31.0` added. 16 new tests (4 transport + 4 storage + 8 trigger).
**Key invariant**: `send_alert` never raises — network failure logs a WARNING and returns. Recommendation pipeline integrity is not conditional on ntfy.sh availability.
```

- [ ] **Step 4: Update `docs/PROJECT_STATUS.md`**

In the status table, update Phase 3 P3.5 row from `🔲 Not started` to:

```
| Phase 3 P3.5 — ntfy.sh Alerts | ✅ Complete (2026-05-27) | --notify flag on recommend, 3 triggers, alerts_log table, quant alert-test, 16 tests |
```

Update the "Last updated" line at the bottom of `PROJECT_STATUS.md`.

- [ ] **Step 5: Final commit**

```
git add LEARNING.md docs/PROJECT_STATUS.md
git commit -m "docs: log P3.5 ntfy alert pipeline — LEARNING.md + PROJECT_STATUS.md"
```

---

## Test Count Summary

| File | Baseline | Added | Final |
|---|---|---|---|
| `test_metrics.py` | 11 | 0 | 11 |
| `test_signals.py` | 11 | 0 | 11 |
| `test_recommendations.py` | 22 | 0 | 22 |
| `test_mean_reversion.py` | 16 | 0 | 16 |
| `test_optimizer.py` | 31 | 0 | 31 |
| `test_storage.py` | 17 | +4 | 21 |
| `test_sell_logic.py` | 16 | 0 | 16 |
| `test_alerts.py` | 0 | +12 | 12 |
| **Total** | **159** | **+16** | **175** |
