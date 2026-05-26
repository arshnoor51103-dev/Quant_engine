# Signal Persistence (P3.3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist signal scores to SQLite on `--save`, enabling historical audit trails and a `quant signal-history` command for tracking score evolution over time.

**Architecture:** Add `signal_scores` table to the existing `SCHEMA` string in `storage.py`; add `ticker_metadata()` method to `SignalResult` for ticker-specific metadata extraction; add `persist_signals()` and `query_signal_history()` to `storage.py`; wire into `signals_command --save`, a new `signal_history_command`, and `recommend_command --save`. No new files except the test file.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), json (stdlib), uuid (stdlib), Rich (tables), typer, pytest

---

## File Map

| File | Change |
|------|--------|
| `src/signals/base.py` | Add `_PER_TICKER_KEY_MAP` constant + `ticker_metadata()` method to `SignalResult` |
| `src/data/storage.py` | Add `import json`, `TYPE_CHECKING` guard; append `signal_scores` DDL to `SCHEMA`; add `persist_signals()`, `query_signal_history()` |
| `src/cli/phase2_commands.py` | Add `import json`, `import uuid`, `from collections import defaultdict`; import `persist_signals`, `query_signal_history`; add `--save` to `signals_command`; add `signal_history_command` |
| `src/cli/phase3_commands.py` | Add `persist_signals` to storage imports; wire into `recommend_command`; update `_print_cards` signature |
| `src/cli/main.py` | Import `signal_history_command`; register `signal-history` command |
| `tests/test_signal_persistence.py` | New file — 9 tests (4 unit + 5 storage) |
| `LEARNING.md` | Append P3.3 decision entry |
| `docs/PROJECT_STATUS.md` | Update schema table, CLI commands table, phase status |

---

### Task 1: `SignalResult.ticker_metadata()` — TDD

**Files:**
- Create: `tests/test_signal_persistence.py`
- Modify: `src/signals/base.py`

- [ ] **Step 1: Create `tests/test_signal_persistence.py` with unit tests for `ticker_metadata()`**

```python
"""Tests for P3.3 signal persistence: ticker_metadata, persist_signals, query_signal_history."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.signals.base import SignalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _db(tmp_path: Path) -> Path:
    """Initialize an isolated test DB and return its path."""
    from src.data.storage import initialize
    db = tmp_path / "test.db"
    initialize(db)
    return db


# ── ticker_metadata unit tests ────────────────────────────────────────────────

class TestTickerMetadata:
    def test_per_ticker_dict_key_rename(self) -> None:
        """raw_returns dict → raw_return scalar; key renamed via explicit map."""
        result = SignalResult(
            signal_name="momentum",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.75, "XIC.TO": 0.50},
            metadata={"raw_returns": {"VFV.TO": 0.34, "XIC.TO": 0.46}},
        )
        assert result.ticker_metadata("VFV.TO") == {"raw_return": 0.34}

    def test_broadcast_scalar_passthrough(self) -> None:
        """Scalar values pass through verbatim to every ticker."""
        result = SignalResult(
            signal_name="vol_regime",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.30},
            metadata={"regime": "NORMAL", "vol_percentile": 0.625},
        )
        assert result.ticker_metadata("VFV.TO") == {
            "regime": "NORMAL",
            "vol_percentile": 0.625,
        }

    def test_none_metadata_returns_empty_dict(self) -> None:
        """metadata=None returns {} without error."""
        result = SignalResult(
            signal_name="mean_reversion",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.10},
            metadata=None,
        )
        assert result.ticker_metadata("VFV.TO") == {}

    def test_ticker_absent_from_per_ticker_dict_excluded(self) -> None:
        """Ticker missing from a per-ticker dict is silently excluded."""
        result = SignalResult(
            signal_name="momentum",
            run_date=date(2026, 5, 1),
            scores={"VFV.TO": 0.75},
            metadata={"raw_returns": {"XIC.TO": 0.46}},  # VFV.TO absent
        )
        assert result.ticker_metadata("VFV.TO") == {}
```

- [ ] **Step 2: Run to verify FAIL**

```
python -m pytest tests/test_signal_persistence.py -v
```

Expected: `AttributeError: 'SignalResult' object has no attribute 'ticker_metadata'`

- [ ] **Step 3: Add `_PER_TICKER_KEY_MAP` module constant to `src/signals/base.py`**

Insert after `import pandas as pd` and before `@dataclass`:

```python
# Rename map for per-ticker dict keys in SignalResult.ticker_metadata().
# Add entries here when new signals introduce per-ticker dicts with plural keys.
_PER_TICKER_KEY_MAP: dict[str, str] = {
    "raw_returns": "raw_return",
    "z_scores": "z_score",
}
```

- [ ] **Step 4: Add `ticker_metadata()` to `SignalResult` in `src/signals/base.py`**

Inside the `SignalResult` dataclass, after the `ranked()` method:

```python
    def ticker_metadata(self, ticker: str) -> dict:
        """
        Extract a ticker-specific metadata slice from this result's metadata blob.

        Two-tier extraction contract — binding on all Signal implementations:
        - Per-ticker dict: any key whose value is a dict is treated as a
          ticker-keyed mapping. Extracts value[ticker] and renames the key
          via _PER_TICKER_KEY_MAP (e.g. "raw_returns" -> "raw_return").
          If ticker is absent from the dict, the key is omitted entirely.
        - Broadcast scalar: any key whose value is not a dict is passed
          through verbatim to every ticker.

        Args:
            ticker: Yahoo Finance ticker symbol (e.g. 'VFV.TO')

        Returns:
            dict suitable for JSON serialisation. Empty dict if metadata is None.
        """
        if not self.metadata:
            return {}
        out: dict = {}
        for key, value in self.metadata.items():
            if isinstance(value, dict):
                if ticker in value:
                    out_key = _PER_TICKER_KEY_MAP.get(key, key)
                    out[out_key] = value[ticker]
            else:
                out[key] = value
        return out
```

- [ ] **Step 5: Run tests to verify PASS**

```
python -m pytest tests/test_signal_persistence.py::TestTickerMetadata -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```
git add src/signals/base.py tests/test_signal_persistence.py
git commit -m "feat: add SignalResult.ticker_metadata() with two-tier extraction contract"
```

---

### Task 2: Schema + `persist_signals()` + `query_signal_history()` — TDD

**Files:**
- Modify: `tests/test_signal_persistence.py` (add 5 storage tests)
- Modify: `src/data/storage.py`

- [ ] **Step 1: Append 5 storage tests to `tests/test_signal_persistence.py`**

Append after `TestTickerMetadata`:

```python
# ── storage tests ─────────────────────────────────────────────────────────────

def test_persist_and_read_roundtrip(tmp_path: Path) -> None:
    """Persisted score and ticker-specific metadata are recoverable exactly."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    result = SignalResult(
        signal_name="momentum",
        run_date=date(2026, 5, 1),
        scores={"VFV.TO": 0.75, "XIC.TO": 0.50},
        metadata={"raw_returns": {"VFV.TO": 0.34, "XIC.TO": 0.46}},
    )
    n = persist_signals([result], run_id="abc12345", db_path=db)
    assert n == 2  # one row per ticker

    rows = query_signal_history("VFV.TO", limit=10, db_path=db)
    assert len(rows) == 1
    row = rows[0]
    assert row["signal_type"] == "momentum"
    assert abs(row["score"] - 0.75) < 1e-9
    assert row["run_id"] == "abc12345"
    meta = json.loads(row["metadata"])
    assert abs(meta["raw_return"] - 0.34) < 1e-9


def test_upsert_overwrites_on_same_pk(tmp_path: Path) -> None:
    """Re-persisting the same (run_date, ticker, signal_type) PK overwrites the row."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    persist_signals(
        [SignalResult(signal_name="momentum", run_date=date(2026, 5, 1),
                      scores={"VFV.TO": 0.75}, metadata=None)],
        run_id="run001", db_path=db,
    )
    persist_signals(
        [SignalResult(signal_name="momentum", run_date=date(2026, 5, 1),
                      scores={"VFV.TO": 0.90}, metadata=None)],  # same PK, new score
        run_id="run002", db_path=db,
    )

    rows = query_signal_history("VFV.TO", limit=10, db_path=db)
    assert len(rows) == 1, "upsert must not create duplicate rows"
    assert abs(rows[0]["score"] - 0.90) < 1e-9
    assert rows[0]["run_id"] == "run002"


def test_signal_history_limit(tmp_path: Path) -> None:
    """15 records inserted; limit=12 returns exactly 12 rows, newest first."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    for day in range(1, 16):  # 15 distinct dates: 2025-01-01 through 2025-01-15
        persist_signals(
            [SignalResult(signal_name="momentum", run_date=date(2025, 1, day),
                          scores={"VFV.TO": day / 15.0}, metadata=None)],
            run_id=f"run{day:03d}", db_path=db,
        )

    rows = query_signal_history("VFV.TO", limit=12, db_path=db)
    assert len(rows) == 12
    assert rows[0]["run_date"] > rows[-1]["run_date"]  # newest first (ISO strings sort correctly)


def test_signal_history_empty_table(tmp_path: Path) -> None:
    """Fresh DB returns empty list without error."""
    from src.data.storage import query_signal_history

    db = _db(tmp_path)
    rows = query_signal_history("VFV.TO", limit=12, db_path=db)
    assert rows == []


def test_signal_type_filter(tmp_path: Path) -> None:
    """signal_types filter returns only rows matching the specified type."""
    from src.data.storage import persist_signals, query_signal_history

    db = _db(tmp_path)
    persist_signals(
        [
            SignalResult(signal_name="momentum",   run_date=date(2026, 5, 1),
                         scores={"VFV.TO": 0.75},  metadata=None),
            SignalResult(signal_name="vol_regime", run_date=date(2026, 5, 1),
                         scores={"VFV.TO": 0.30},  metadata=None),
        ],
        run_id="run001", db_path=db,
    )

    rows = query_signal_history("VFV.TO", limit=10, signal_types=["momentum"], db_path=db)
    assert len(rows) == 1
    assert rows[0]["signal_type"] == "momentum"
```

- [ ] **Step 2: Run to verify FAIL**

```
python -m pytest tests/test_signal_persistence.py -k "not TestTickerMetadata" -v
```

Expected: `ImportError: cannot import name 'persist_signals' from 'src.data.storage'`

- [ ] **Step 3: Add `import json` and `TYPE_CHECKING` guard to `src/data/storage.py`**

Replace the existing typing import line:
```python
from typing import Iterable
```
with:
```python
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from ..signals.base import SignalResult
```

Add `import json` after `import sqlite3` in the stdlib imports block.

- [ ] **Step 4: Append `signal_scores` DDL to the `SCHEMA` string in `src/data/storage.py`**

Inside the `SCHEMA` string, append immediately before the closing `"""`:

```sql

CREATE TABLE IF NOT EXISTS signal_scores (
    run_date    DATE NOT NULL,
    ticker      TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    score       REAL NOT NULL,
    metadata    JSON,
    run_id      TEXT,
    PRIMARY KEY (run_date, ticker, signal_type)
);
CREATE INDEX IF NOT EXISTS idx_signal_scores_ticker
    ON signal_scores(ticker, run_date DESC);
```

**Note for existing DBs:** Any user with a pre-existing `data/quant.db` must run `quant init` once to create this table. The `CREATE TABLE IF NOT EXISTS` is idempotent — running it on a fresh DB or one that already has the table is safe.

- [ ] **Step 5: Add `persist_signals()` to `src/data/storage.py`**

Append after `get_all_last_buy_dates()`:

```python
def persist_signals(
    results: list[SignalResult],
    run_id: str,
    db_path: Path = DB_PATH,
) -> int:
    """
    Persist a batch of SignalResult objects to the signal_scores table.

    Uses INSERT OR REPLACE — revisit to ON CONFLICT DO UPDATE if nullable
    columns are added to this table in future.

    Args:
        results:  one SignalResult per signal type in this run
        run_id:   short UUID linking these rows to a recommendation batch;
                  stamp the same value on recommendations rows to enable the
                  JOIN audit path (signal_scores.run_id = recommendations.run_id)
        db_path:  path to SQLite DB

    Returns:
        total rows written across all results
    """
    sql = """
    INSERT OR REPLACE INTO signal_scores
        (run_date, ticker, signal_type, score, metadata, run_id)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    rows: list[tuple] = []
    for result in results:
        run_date_str = result.run_date.isoformat()
        for ticker, score in result.scores.items():
            meta = result.ticker_metadata(ticker)
            rows.append((
                run_date_str,
                ticker,
                result.signal_name,
                score,
                json.dumps(meta),
                run_id,
            ))
    if not rows:
        return 0
    with get_connection(db_path) as conn:
        conn.executemany(sql, rows)
        conn.commit()
    return len(rows)
```

- [ ] **Step 6: Add `query_signal_history()` to `src/data/storage.py`**

Append after `persist_signals()`:

```python
def query_signal_history(
    ticker: str,
    limit: int,
    signal_types: list[str] | None = None,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """
    Return persisted signal scores for a ticker, newest first.

    Args:
        ticker:       Yahoo Finance ticker symbol (e.g. 'VFV.TO')
        limit:        maximum number of rows to return
        signal_types: if provided, restrict results to these signal type names
        db_path:      path to SQLite DB

    Returns:
        list of dicts with keys run_date (str ISO), signal_type (str),
        score (float), metadata (JSON string — caller must json.loads()),
        run_id (str | None). Ordered by run_date DESC.
    """
    sql = """
    SELECT run_date, signal_type, score, metadata, run_id
    FROM signal_scores
    WHERE ticker = ?
    """
    params: list = [ticker]
    if signal_types:
        placeholders = ", ".join("?" * len(signal_types))
        sql += f" AND signal_type IN ({placeholders})"
        params.extend(signal_types)
    sql += " ORDER BY run_date DESC LIMIT ?;"
    params.append(limit)
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 7: Run all 9 tests to verify PASS**

```
python -m pytest tests/test_signal_persistence.py -v
```

Expected: 9 tests PASS

- [ ] **Step 8: Run full suite to verify no regressions**

```
python -m pytest tests/ -v
```

Expected: all previously passing tests still PASS (109 + 9 = 118 total)

- [ ] **Step 9: Commit**

```
git add src/data/storage.py tests/test_signal_persistence.py
git commit -m "feat: add signal_scores table, persist_signals(), query_signal_history()"
```

---

### Task 3: Wire `--save` into `signals_command`

**Files:**
- Modify: `src/cli/phase2_commands.py`

- [ ] **Step 1: Add new imports at the top of `src/cli/phase2_commands.py`**

After the existing `from __future__ import annotations`:

```python
import json
import uuid
from collections import defaultdict
```

After the existing `from ..data.ingest import load_universe` line, add:

```python
from ..data.storage import persist_signals, query_signal_history
```

- [ ] **Step 2: Add `--save` parameter to `signals_command`**

Replace the existing function signature:

```python
def signals_command(
    signal_type: str = typer.Option("momentum", help="Signal type: momentum, momentum_short, vol_regime, mean_reversion"),
) -> None:
```

with:

```python
def signals_command(
    signal_type: str = typer.Option("momentum", help="Signal type: momentum, momentum_short, vol_regime, mean_reversion"),
    save: bool = typer.Option(False, "--save", help="Persist signal scores to DB"),
) -> None:
```

- [ ] **Step 3: Add persist block after signal generation in `signals_command`**

Locate the line `result = sig.generate(prices)`. Immediately after it, before the display table code, add:

```python
    if save:
        run_id = str(uuid.uuid4())[:8]
        n = persist_signals([result], run_id=run_id)
        console.print(f"[dim]Saved {n} signal rows (run_id: {run_id})[/dim]")
```

- [ ] **Step 4: Verify commands still work**

```
$env:PYTHONUTF8 = "1"; python -m src.cli.main signals --signal-type momentum
```

Expected: table prints, no crash, no DB write (no `--save` flag).

```
$env:PYTHONUTF8 = "1"; python -m src.cli.main signals --signal-type momentum --save
```

Expected: table prints, then `[dim]Saved 9 signal rows (run_id: xxxxxxxx)[/dim]`

- [ ] **Step 5: Run full test suite**

```
python -m pytest tests/ -v
```

Expected: 118 PASS

- [ ] **Step 6: Commit**

```
git add src/cli/phase2_commands.py
git commit -m "feat: add --save flag to quant signals command"
```

---

### Task 4: `signal_history_command` + `main.py` registration

**Files:**
- Modify: `src/cli/phase2_commands.py`
- Modify: `src/cli/main.py`

- [ ] **Step 1: Add `signal_history_command` to `src/cli/phase2_commands.py`**

Append at the end of the file:

```python
def signal_history_command(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. VFV.TO"),
    records: int = typer.Option(12, "--records", help="Last N persisted records to show"),
    signal_type: str | None = typer.Option(
        None, "--signal-type",
        help="Filter by signal type (momentum, vol_regime, mean_reversion, etc.)",
    ),
) -> None:
    """Show persisted signal score history for a ticker."""
    universe = load_universe()
    known_tickers = {a["ticker"] for a in universe}
    if ticker not in known_tickers:
        console.print(
            f"[yellow]Warning: {ticker} not in current universe — querying history anyway.[/yellow]"
        )

    signal_types_filter: list[str] | None = [signal_type] if signal_type else None
    rows = query_signal_history(ticker, limit=records, signal_types=signal_types_filter)

    if not rows:
        console.print(f"[yellow]No signal history for {ticker}.[/yellow]")
        return

    # Pivot: group by run_date, signal_type
    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        meta = json.loads(row["metadata"] or "{}")
        by_date[row["run_date"]][row["signal_type"]] = {
            "score": row["score"],
            "metadata": meta,
            "run_id": row["run_id"],
        }

    # Determine signal type columns from data (not hardcoded)
    signal_types_present = sorted({row["signal_type"] for row in rows})

    table = Table(title=f"Signal History: {ticker} (last {records} records)")
    table.add_column("Date")
    for st in signal_types_present:
        table.add_column(st.replace("_", " ").title(), justify="right")
    table.add_column("Regime")
    table.add_column("Raw Return", justify="right")
    table.add_column("Run ID", style="dim")

    for run_date in sorted(by_date.keys(), reverse=True):
        date_data = by_date[run_date]

        score_cells: list[str] = []
        for st in signal_types_present:
            if st in date_data:
                score = date_data[st]["score"]
                color = "green" if score > 0.3 else "yellow" if score > 0 else "red"
                score_cells.append(f"[{color}]{score:+.3f}[/{color}]")
            else:
                score_cells.append("—")

        regime = "—"
        raw_return = "—"
        run_id = "—"
        if "vol_regime" in date_data:
            regime = date_data["vol_regime"]["metadata"].get("regime", "—")
            run_id = date_data["vol_regime"]["run_id"] or "—"
        if "momentum" in date_data:
            rr = date_data["momentum"]["metadata"].get("raw_return")
            if rr is not None:
                raw_return = f"{rr:+.1%}"
            if run_id == "—":
                run_id = date_data["momentum"]["run_id"] or "—"

        table.add_row(run_date, *score_cells, regime, raw_return, run_id)

    console.print(table)
```

- [ ] **Step 2: Register `signal-history` in `src/cli/main.py`**

Replace the existing import line:

```python
from .phase2_commands import signals_command, backtest_command, dashboard_command
```

with:

```python
from .phase2_commands import signals_command, backtest_command, dashboard_command, signal_history_command
```

Append after the last `app.command(...)` call (after `app.command(name="skip")(skip_command)`):

```python
app.command(name="signal-history")(signal_history_command)
```

- [ ] **Step 3: Verify `signal-history` command is discoverable**

```
python -m src.cli.main --help
```

Expected: `signal-history` appears in the command list.

- [ ] **Step 4: Run the command against a DB with persisted data**

If you ran `signals --save` in Task 3 Step 4, data is already in the DB:

```
$env:PYTHONUTF8 = "1"; python -m src.cli.main signal-history VFV.TO
```

Expected: a Rich table with one date row (from the Task 3 save), momentum score, `—` for vol_regime (not persisted yet), `—` for Regime, raw_return populated.

- [ ] **Step 5: Run full test suite**

```
python -m pytest tests/ -v
```

Expected: 118 PASS

- [ ] **Step 6: Commit**

```
git add src/cli/phase2_commands.py src/cli/main.py
git commit -m "feat: add quant signal-history command with pivoted Rich table"
```

---

### Task 5: Wire `persist_signals` into `recommend_command`

**Files:**
- Modify: `src/cli/phase3_commands.py`

- [ ] **Step 1: Add `persist_signals` to the storage import block in `src/cli/phase3_commands.py`**

Replace:

```python
from ..data.storage import (
    get_all_last_buy_dates,
    get_annual_trade_count,
    get_recommendation_by_id,
    list_pending_recommendations,
    mark_recommendation_executed,
    mark_recommendation_skipped,
    record_trade,
    save_recommendation,
)
```

with:

```python
from ..data.storage import (
    get_all_last_buy_dates,
    get_annual_trade_count,
    get_recommendation_by_id,
    list_pending_recommendations,
    mark_recommendation_executed,
    mark_recommendation_skipped,
    persist_signals,
    record_trade,
    save_recommendation,
)
```

- [ ] **Step 2: Add `n_signal_rows` parameter to `_print_cards`**

Replace the `_print_cards` signature:

```python
def _print_cards(
    cards: list[TradeCard],
    portfolio_nav: float,
    cash: float,
    annual_trade_count: int,
    regime_name: str,
    saved: bool,
    max_trades: int = 24,
) -> None:
```

with:

```python
def _print_cards(
    cards: list[TradeCard],
    portfolio_nav: float,
    cash: float,
    annual_trade_count: int,
    regime_name: str,
    saved: bool,
    max_trades: int = 24,
    n_signal_rows: int = 0,
) -> None:
```

- [ ] **Step 3: Update the saved header line in `_print_cards`**

Replace:

```python
    if saved:
        header_lines.append("[dim]Saved to DB — use rec ID with `quant execute`[/dim]")
```

with:

```python
    if saved:
        header_lines.append(
            f"[dim]Signals persisted ({n_signal_rows} rows) | "
            "Cards saved — use rec ID with `quant execute`[/dim]"
        )
```

- [ ] **Step 4: Wire `persist_signals` into the `if save:` block in `recommend_command`**

Locate the `if save:` block. Replace it entirely with:

```python
    n_signal_rows = 0
    if save:
        run_id = str(uuid.uuid4())[:8]
        # Persist signal scores first — audit trail precedes trade cards
        signal_results = [momentum_result, regime_result]
        # Extension point: add new signal results to this list as signals are added
        n_signal_rows = persist_signals(signal_results, run_id=run_id)
        for card in cards:
            rec_id = save_recommendation(
                ticker=card.ticker,
                action=card.action,
                bucket=card.bucket,
                target_weight=0.0,
                combined_signal=card.combined_signal,
                expected_ret=card.expected_return_pct,
                cost_estimate=card.cost_estimate,
                gate_status=card.gate_status.value,
                rationale=card.gate_reason,
                run_id=run_id,
            )
            card.rec_id = rec_id
```

- [ ] **Step 5: Update the `_print_cards` call site in `recommend_command`**

Replace:

```python
    _print_cards(cards, portfolio_nav, cash, annual_trades, regime_name, saved=save, max_trades=max_trades)
```

with:

```python
    _print_cards(
        cards, portfolio_nav, cash, annual_trades, regime_name,
        saved=save, max_trades=max_trades, n_signal_rows=n_signal_rows,
    )
```

- [ ] **Step 6: Verify `quant recommend --save` works end-to-end**

```
$env:PYTHONUTF8 = "1"; python -m src.cli.main recommend --cash 800 --save
```

Expected output includes: `Signals persisted (18 rows) | Cards saved — use rec ID with quant execute` in the header panel. (18 = 9 tickers × 2 signals)

Then verify signal history captured both signals:

```
$env:PYTHONUTF8 = "1"; python -m src.cli.main signal-history VFV.TO
```

Expected: a row showing both Momentum and Vol Regime scores, with Regime populated (e.g. NORMAL) and Raw Return populated.

- [ ] **Step 7: Run full test suite**

```
python -m pytest tests/ -v
```

Expected: 118 PASS

- [ ] **Step 8: Commit**

```
git add src/cli/phase3_commands.py
git commit -m "feat: wire persist_signals into quant recommend --save with run_id audit link"
```

---

### Task 6: LEARNING.md + PROJECT_STATUS.md + final validation

**Files:**
- Modify: `LEARNING.md`
- Modify: `docs/PROJECT_STATUS.md`

- [ ] **Step 1: Append P3.3 decision entry to `LEARNING.md`**

Append at the end of the file (never modify existing entries):

```markdown
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
```

- [ ] **Step 2: Update the SQLite Schema table in `docs/PROJECT_STATUS.md`**

In the `## SQLite Schema` section, add a row to the table:

```markdown
| `signal_scores` | Persisted signal scores per ticker per run. PK: (run_date, ticker, signal_type). JOIN to recommendations via run_id. |
```

Also update the note below the table from:

```
**Signal scores are not yet persisted** — they're computed on the fly. Phase 3 should write `signal_scores` to the DB or to the `recommendations` table.
```

to:

```
**Signal scores** are persisted to `signal_scores` via `quant signals --save` or `quant recommend --save`. JOIN path: `signal_scores.run_id = recommendations.run_id`.
```

- [ ] **Step 3: Add `signal-history` to the CLI Commands table in `docs/PROJECT_STATUS.md`**

In the `### Phase 2 Commands` table, update the signals row and add signal-history:

Update:
```
| `quant signals --signal-type [momentum\|momentum_short\|vol_regime\|mean_reversion]` | Generate signal scores for universe. Prints ranked table + raw returns or regime metadata. |
```
to:
```
| `quant signals --signal-type [momentum\|momentum_short\|vol_regime\|mean_reversion] [--save]` | Generate signal scores. `--save` persists to DB with a run_id. |
```

Add new row:
```
| `quant signal-history TICKER [--records N] [--signal-type TYPE]` | Show persisted signal score history. Pivoted table: date, signal scores, regime, raw return. Default last 12 records. |
```

- [ ] **Step 4: Update the Phase 3 status section in `docs/PROJECT_STATUS.md`**

In the `## Current State` table, update Phase 3 P3.3 row (or add it if not present) to `✅ Complete`.

Add to the `## Current Phase` narrative:

```
**Phase 3 P3.3 — Signal Persistence. Complete (2026-05-26).** `signal_scores` table. `persist_signals()` + `query_signal_history()` in storage.py. `quant signals --save`, `quant recommend --save` now write signal evidence before trade cards. `quant signal-history` command. 9 new tests. 118/118 passing.
```

- [ ] **Step 5: Run `quant init` to create `signal_scores` on existing DB**

```
python -m src.cli.main init
```

Expected: `✓ Database initialized at data/quant.db` (idempotent — existing tables untouched, `signal_scores` created if not present)

- [ ] **Step 6: Final full test suite run**

```
python -m pytest tests/ -v --tb=short
```

Expected: 118 PASS, 0 FAIL

- [ ] **Step 7: Commit**

```
git add LEARNING.md docs/PROJECT_STATUS.md
git commit -m "docs: P3.3 signal persistence — update LEARNING.md and PROJECT_STATUS.md"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `signal_scores` table with specified schema | Task 2 Step 4 |
| `persist_signals()` with upsert semantics | Task 2 Step 5 |
| `quant signals --save` | Task 3 |
| `quant signal-history TICKER [--records N]` | Task 4 |
| `quant recommend` always persists on `--save` | Task 5 |
| Unit tests: roundtrip, upsert, limit, empty, filter | Task 2 Step 1 |
| `ticker_metadata()` unit test | Task 1 Step 1 |
| `LEARNING.md` decision entry | Task 6 Step 1 |
| `PROJECT_STATUS.md` update | Task 6 Steps 2–4 |
| Scheduler note re `--save` | Task 6 Step 1 (LEARNING.md) |

**No placeholders found.** All code blocks are complete. All commands include expected output.

**Type consistency check:** `persist_signals(results: list[SignalResult], run_id: str, ...)` matches call sites in Task 3 (`persist_signals([result], run_id=run_id)`) and Task 5 (`persist_signals(signal_results, run_id=run_id)`). `query_signal_history(ticker, limit, signal_types, db_path)` matches call in Task 4. `ticker_metadata(ticker: str) -> dict` matches usage in `persist_signals` body.
