# Signal Persistence — Design Spec
**Phase 3 P3.3 | Date: 2026-05-26**

## Overview

Add a `signal_scores` table to SQLite and wire signal persistence into `quant signals --save` and `quant recommend --save`. Enables historical signal tracking, regime-change audit trails, and a `quant signal-history` command for reviewing score evolution over time.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Metadata per row | Ticker-specific slices (Option B) | Avoids duplicating run-level blobs 9× per run |
| Metadata extraction | `SignalResult.ticker_metadata()` method | `storage.py` imports nothing from `signals/` |
| Per-ticker key rename | Explicit map `{"raw_returns": "raw_return", "z_scores": "z_score"}` | Safer and self-documenting vs `rstrip("s")` |
| Persistence gating | `--save` gates all writes — signals + cards together | No silent side effects from read-only commands |
| `run_id` on `signal_scores` | Yes | JOIN path `signal_scores.run_id = recommendations.run_id` |
| `signal-history` display | Pivoted (one row per date, signal types as columns) | More readable for multi-signal comparison |
| `signal-history` limit | Last-N-records, flag `--records`, default 12 | More useful than calendar-days for a monthly system |
| Architecture | Pure extension of existing layers | Follows existing patterns, no new files |

## Schema

Added to the `SCHEMA` string in `storage.py`. Safe inline addition — `CREATE TABLE IF NOT EXISTS` is idempotent on live DBs. No migration function required.

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

## `SignalResult.ticker_metadata(ticker: str) -> dict`

Method on `SignalResult` in `signals/base.py`. **Two-tier extraction contract** — binding on all future signals:

- **Per-ticker dict**: any key whose value is a `dict` is a ticker-keyed mapping. Extract `value[ticker]` and rename the key via explicit map.
- **Broadcast scalar**: any key whose value is not a `dict` is passed through verbatim to all tickers.
- `metadata is None` → returns `{}`

**Key rename map** (explicit, not `rstrip('s')`):
```python
_PER_TICKER_KEY_MAP: dict[str, str] = {
    "raw_returns": "raw_return",
    "z_scores": "z_score",
}
```

**Examples:**
- Momentum: `metadata = {"raw_returns": {"VFV.TO": 0.34, ...}}` → `ticker_metadata("VFV.TO") == {"raw_return": 0.34}`
- Vol regime: `metadata = {"regime": "NORMAL", "vol_percentile": 0.625, "current_annualized_vol": 0.127}` → `ticker_metadata("VFV.TO") == {"regime": "NORMAL", "vol_percentile": 0.625, "current_annualized_vol": 0.127}`
- Mean reversion (no per-ticker metadata yet): `ticker_metadata("VFV.TO") == {}`

## `persist_signals()` in `storage.py`

```python
def persist_signals(
    results: list[SignalResult],
    run_id: str,
    db_path: Path = DB_PATH,
) -> int:
    """
    Persist a batch of SignalResult objects to signal_scores.

    Uses INSERT OR REPLACE — revisit to ON CONFLICT DO UPDATE if nullable
    columns are added to this table in future.

    Args:
        results: one SignalResult per signal type in the run
        run_id:  short UUID linking these rows to a recommendation batch
        db_path: path to SQLite DB

    Returns:
        total rows written
    """
```

- Iterates all results, all tickers per result
- Calls `result.ticker_metadata(ticker)` → `json.dumps()`
- Uses `result.run_date.isoformat()` for the date column
- `INSERT OR REPLACE` for upsert semantics
- Returns total row count

## `query_signal_history()` in `storage.py`

```python
def query_signal_history(
    ticker: str,
    limit: int,
    signal_types: list[str] | None = None,
    db_path: Path = DB_PATH,
) -> list[dict]:
```

Returns flat rows — pivot happens in CLI. Fields: `run_date`, `signal_type`, `score`, `metadata` (JSON string), `run_id`. Ordered `run_date DESC`, limited to `limit`. Optional `signal_types` adds `AND signal_type IN (...)`.

## CLI Changes

### `signals_command` — `phase2_commands.py`

New flag: `save: bool = typer.Option(False, "--save", help="Persist signal scores to DB")`

After `result = sig.generate(prices)`:
```python
if save:
    run_id = str(uuid.uuid4())[:8]
    n = persist_signals([result], run_id=run_id)
    console.print(f"[dim]Saved {n} signal rows (run_id: {run_id})[/dim]")
```

### `signal_history_command` — `phase2_commands.py`

```
quant signal-history TICKER [--records N] [--signal-type TYPE]
```

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `ticker` | positional str | — | Warn if not in current universe; don't abort |
| `--records` | int | 12 | Last N persisted records |
| `--signal-type` | str \| None | None | Single type filter; None = all types |

Flow:
1. Call `query_signal_history(ticker, limit=records, signal_types=[signal_type] if signal_type else None)`
2. Empty result → print `No signal history for {ticker}.` and return
3. Pivot by `run_date` in Python — determine signal type columns from distinct types in result
4. For each date row, extract:
   - `regime` from vol_regime metadata `["regime"]`, `—` on absence
   - `raw_return` from momentum metadata `["raw_return"]`, `—` on absence
   - `run_id` from the most recent signal row for that date
5. Print Rich table

**Example output:**
```
Date        Momentum   Vol Regime   Regime   Raw Return    Run ID
2026-05-01  +0.750     +0.300       NORMAL   +50.2%        abc12345
2026-04-01  +0.500     +0.300       NORMAL   +45.9%        def67890
```

### `recommend_command` — `phase3_commands.py`

Inside existing `if save:` block, before the card loop:

```python
if save:
    run_id = str(uuid.uuid4())[:8]
    # Persist signal scores first — audit trail precedes trade cards
    signal_results = [momentum_result, regime_result]
    # Extension point: add new signal results to this list as signals are added
    n_signal_rows = persist_signals(signal_results, run_id=run_id)
    for card in cards:
        rec_id = save_recommendation(..., run_id=run_id)
        card.rec_id = rec_id
```

`_print_cards` gains one line when `saved=True`:
```
Signals persisted (18 rows, run_id: abc12345)
```

## Tests

New file: `tests/test_signal_persistence.py`. All tests use `tmp_path` for isolated SQLite DB. Deterministic synthetic data only — no yfinance calls.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_persist_and_read_roundtrip` | Score + metadata match exactly after persist + query |
| 2 | `test_upsert_overwrites` | Same PK re-persisted → 1 row, new score wins |
| 3 | `test_signal_history_limit` | 15 rows inserted, `limit=12` returns exactly 12 newest |
| 4 | `test_signal_history_empty` | Fresh DB → `[]` without error |
| 5 | `test_signal_type_filter` | Two types persisted, filter returns only queried type |
| 6 | `test_ticker_metadata_extraction` | Per-ticker key rename, broadcast scalar passthrough, `None → {}` |

## Scheduler Note (Phase 3.6)

`daily_run.py` **must** always pass `--save` to `quant recommend`. Without `--save`, no signal scores or trade cards are persisted — the daily audit trail is lost.

```
quant fetch --incremental && quant recommend --cash 0 --save
```
