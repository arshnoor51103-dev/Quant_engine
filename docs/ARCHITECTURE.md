# Architecture

## Module Boundaries

```
┌──────────────────────────────────────────────────────────┐
│                         CLI (typer)                       │
│  init │ fetch │ status │ metrics │ universe │ (more...)   │
└─────────────────┬────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│  portfolio/      │  │   data/          │
│  - model         │  │  - ingest        │
│  - metrics       │  │  - storage       │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
            ┌────────────────┐
            │  SQLite        │
            │  data/quant.db │
            └────────────────┘

                  ▲
                  │ reads
                  │
            ┌────────────────┐
            │  config/       │
            │  *.yaml        │
            └────────────────┘
```

## Data Flow (current — Phase 1)

1. **Ingest**: `cli fetch` → `data/ingest.py` → yfinance API → `data/storage.upsert_prices` → SQLite `prices` table.
2. **Status**: `cli status` → `portfolio/model.py` reads `holdings` + latest `prices` → enriched holdings printed.
3. **Metrics**: `cli metrics` → `portfolio/model.price_series` → `portfolio/metrics.*` → printed.

## Data Flow (Phase 2 — preview, not built yet)

1. **Signal generation** (`src/signals/`): pulls price history, computes signal scores per ticker per strategy (momentum, MR, regime). Writes to `signals` table.
2. **Optimizer** (`src/portfolio/optimizer.py`): consumes signals + current holdings + bucket constraints → target weights.
3. **Recommendation engine**: target weights vs current + cost gate → `recommendations` table → CLI surfaces.
4. **Operator executes manually** in Wealthsimple → trade entered via `quant trade ...` → `holdings` updated.

## Dependency Rules

- `data/` knows nothing about `portfolio/` or `signals/`.
- `portfolio/` reads from `data/` but doesn't write prices.
- `signals/` (Phase 2) reads from `data/` and `portfolio/`, writes to `signals` table only.
- `cli/` is the only place side effects (printing, taking user input) live.
- All config in `config/*.yaml`. No hardcoded thresholds in code.

## Schema

See `src/data/storage.py` — single source of truth.

Tables:
- `prices` — daily OHLCV per ticker
- `holdings` — current positions
- `trades` — executed trade log
- `recommendations` — signal/recommendation log
- `metrics_snapshots` — periodic risk/return snapshots
- `run_log` — system event log
