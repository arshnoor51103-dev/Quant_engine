"""
SQLite storage layer for the quant engine.

All persistent state lives here:
- prices: daily OHLCV for every ticker in universe
- holdings: current portfolio positions
- trades: executed trade log
- recommendations: signal/recommendation log (not all become trades)
- metrics_snapshots: periodic risk/return snapshots

Schema is deliberately simple — sqlite, no ORM, raw SQL via sqlite3 stdlib.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:
    from ..signals.base import SignalResult


def _default_db_path() -> Path:
    """Resolve the SQLite path: ``$QUANT_DB`` if set, else ``<repo>/data/quant.db``.

    The env override lets the real-execution smoke gate (and isolated tests)
    point write-commands at a throwaway DB instead of the live data/quant.db,
    which is otherwise hardcoded and untouchable without risking real state.
    """
    env = os.environ.get("QUANT_DB")
    return Path(env) if env else (Path(__file__).resolve().parents[2] / "data" / "quant.db")


DB_PATH = _default_db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT NOT NULL,
    trade_date  DATE NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    adj_close   REAL,
    volume      INTEGER,
    PRIMARY KEY (ticker, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(trade_date);

CREATE TABLE IF NOT EXISTS holdings (
    ticker        TEXT PRIMARY KEY,
    units         REAL NOT NULL,
    avg_cost      REAL NOT NULL,
    last_updated  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT NOT NULL,
    side          TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    units         REAL NOT NULL,
    price         REAL NOT NULL,
    trade_date    DATE NOT NULL,
    fees          REAL DEFAULT 0,
    rationale     TEXT,
    signal_id     INTEGER,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ticker        TEXT NOT NULL,
    action        TEXT NOT NULL,
    target_weight REAL,
    signal_score  REAL,
    expected_ret  REAL,
    cost_estimate REAL,
    rationale     TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    fill_price    REAL,
    fill_units    REAL,
    executed_at   TIMESTAMP,
    bucket        TEXT,
    gate_status   TEXT,
    combined_signal REAL,
    run_id        TEXT,
    sell_reason   TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_side ON trades(ticker, side, trade_date);
CREATE INDEX IF NOT EXISTS idx_recs_status ON recommendations(status, generated_at);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    snapshot_date    DATE NOT NULL,
    scope            TEXT NOT NULL,   -- 'portfolio' or ticker symbol
    metric_name      TEXT NOT NULL,   -- 'sharpe', 'sortino', 'max_dd', etc.
    metric_value     REAL,
    window_days      INTEGER,
    PRIMARY KEY (snapshot_date, scope, metric_name, window_days)
);

CREATE TABLE IF NOT EXISTS run_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    component     TEXT NOT NULL,
    level         TEXT NOT NULL,
    message       TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS alerts_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type  TEXT    NOT NULL,
    fired_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_log_type
    ON alerts_log(alert_type, fired_at DESC);

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection with row factory + foreign keys on."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize(db_path: Path = DB_PATH) -> None:
    """Create the schema if not present. Safe to call repeatedly."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    run_migrations(db_path)


def upsert_prices(rows: Iterable[dict], db_path: Path = DB_PATH) -> int:
    """
    Insert/replace OHLCV rows.

    rows: iterable of dicts with keys
        ticker, trade_date, open, high, low, close, adj_close, volume
    Returns number of rows inserted.
    """
    sql = """
    INSERT OR REPLACE INTO prices
        (ticker, trade_date, open, high, low, close, adj_close, volume)
    VALUES
        (:ticker, :trade_date, :open, :high, :low, :close, :adj_close, :volume);
    """
    rows = list(rows)
    if not rows:
        return 0
    with get_connection(db_path) as conn:
        conn.executemany(sql, rows)
        conn.commit()
    return len(rows)


def latest_price_date(ticker: str, db_path: Path = DB_PATH) -> date | None:
    """Return latest trade_date stored for a ticker, or None if no rows."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT MAX(trade_date) AS d FROM prices WHERE ticker = ?;",
            (ticker,),
        ).fetchone()
    return date.fromisoformat(row["d"]) if row and row["d"] else None


def record_trade(
    ticker: str,
    side: str,
    units: float,
    price: float,
    trade_date: date,
    fees: float = 0.0,
    rationale: str | None = None,
    db_path: Path = DB_PATH,
    conn: sqlite3.Connection | None = None,
) -> int:
    """
    Insert a trade row and update holdings atomically.

    For BUY: upserts holdings with VWAP-averaged cost basis.
    For SELL: reduces units; removes holding row when units reach zero.

    Args:
        ticker: Yahoo Finance ticker (e.g. 'VFV.TO')
        side: 'BUY' or 'SELL'
        units: number of units transacted (positive)
        price: execution price per unit in CAD
        trade_date: date of execution
        fees: commission/spread cost in CAD (default 0 for Wealthsimple)
        rationale: free-text note logged with the trade
        conn: optional open connection. When provided, the trade + holdings
            write run on it WITHOUT committing — the caller owns the
            transaction (used by ``execute`` to keep record_trade and
            mark_recommendation_executed atomic). When None, a private
            connection is opened and committed.

    Returns:
        trade id (AUTOINCREMENT primary key)

    Raises:
        ValueError: insufficient units on a SELL
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    if units <= 0:
        raise ValueError(f"units must be positive, got {units}")

    if conn is not None:
        return _record_trade_on_conn(
            conn, ticker, side, units, price, trade_date, fees, rationale
        )
    with get_connection(db_path) as conn:
        trade_id = _record_trade_on_conn(
            conn, ticker, side, units, price, trade_date, fees, rationale
        )
        conn.commit()
    return trade_id


def _record_trade_on_conn(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    units: float,
    price: float,
    trade_date: date,
    fees: float,
    rationale: str | None,
) -> int:
    """
    Trade insert + holdings update on an open connection. Does NOT commit —
    the caller (record_trade, or an enclosing transaction) owns the commit so
    the write can be made atomic with sibling writes.
    """
    # Validate sell quantity against current holding
    if side == "SELL":
        row = conn.execute(
            "SELECT units FROM holdings WHERE ticker = ?;", (ticker,)
        ).fetchone()
        held = row["units"] if row else 0.0
        if units > held + 1e-9:
            raise ValueError(
                f"Cannot sell {units} units of {ticker} — only {held:.4f} held"
            )

    # Log the trade
    cur = conn.execute(
        """
        INSERT INTO trades (ticker, side, units, price, trade_date, fees, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (ticker, side, units, price, trade_date.isoformat(), fees, rationale),
    )
    trade_id = cur.lastrowid

    # Update holdings
    existing = conn.execute(
        "SELECT units, avg_cost FROM holdings WHERE ticker = ?;", (ticker,)
    ).fetchone()

    if side == "BUY":
        if existing:
            old_units = existing["units"]
            old_cost = existing["avg_cost"]
            new_units = old_units + units
            new_avg_cost = (old_units * old_cost + units * price) / new_units
        else:
            new_units = units
            new_avg_cost = price
        conn.execute(
            """
            INSERT INTO holdings (ticker, units, avg_cost, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                units = excluded.units,
                avg_cost = excluded.avg_cost,
                last_updated = excluded.last_updated;
            """,
            (ticker, new_units, new_avg_cost),
        )
    else:  # SELL
        new_units = existing["units"] - units
        if new_units < 1e-9:
            conn.execute("DELETE FROM holdings WHERE ticker = ?;", (ticker,))
        else:
            conn.execute(
                "UPDATE holdings SET units = ?, last_updated = CURRENT_TIMESTAMP WHERE ticker = ?;",
                (new_units, ticker),
            )
    return trade_id


def log(component: str, level: str, message: str, db_path: Path = DB_PATH) -> None:
    """Append a row to run_log."""
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO run_log (component, level, message) VALUES (?, ?, ?);",
            (component, level, message),
        )
        conn.commit()


def _migration_1_p0_columns(conn: sqlite3.Connection) -> None:
    """P0 recommendation columns (fill_price...run_id). Column-existence guarded.

    Historic schemas predating these columns get them added; fresh DBs created
    from SCHEMA already have them, so this is a no-op there.
    """
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(recommendations);").fetchall()
    }
    for col_name, col_type in [
        ("fill_price",      "REAL"),
        ("fill_units",      "REAL"),
        ("executed_at",     "TIMESTAMP"),
        ("bucket",          "TEXT"),
        ("gate_status",     "TEXT"),
        ("combined_signal", "REAL"),
        ("run_id",          "TEXT"),
    ]:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE recommendations ADD COLUMN {col_name} {col_type};"
            )


def _migration_2_sell_reason(conn: sqlite3.Connection) -> None:
    """sell_reason column (NULL non-SELL; 'SIGNAL'/'DRIFT' for SELLs). Guarded."""
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(recommendations);").fetchall()
    }
    if "sell_reason" not in existing:
        conn.execute("ALTER TABLE recommendations ADD COLUMN sell_reason TEXT;")


# Registered migrations: (version, fn). Versions are sequential and never reused.
# To add schema change N: append (N, _migration_N_...) — run_migrations applies
# each exactly once, tracked in the schema_version table.
_MIGRATIONS: list[tuple[int, Callable[[sqlite3.Connection], None]]] = [
    (1, _migration_1_p0_columns),
    (2, _migration_2_sell_reason),
]


def run_migrations(db_path: Path = DB_PATH) -> None:
    """
    Apply every registered migration once, tracked in the schema_version table.

    Replaces the ad-hoc migrate_recommendations_v2/v3 + module-global guard
    pattern (F15). Idempotent: a version already present in schema_version is
    skipped, so repeated calls and repeated process starts are safe.
    """
    with get_connection(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, "
            "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);"
        )
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_version;").fetchall()
        }
        for version, fn in _MIGRATIONS:
            if version not in applied:
                fn(conn)
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?);", (version,)
                )
        conn.commit()


def migrate_recommendations_v2(db_path: Path = DB_PATH) -> None:
    """Back-compat shim — superseded by run_migrations (F15). Delegates fully."""
    run_migrations(db_path)


def migrate_recommendations_v3(db_path: Path = DB_PATH) -> None:
    """Back-compat shim — superseded by run_migrations (F15). Delegates fully."""
    run_migrations(db_path)


def save_recommendation(
    ticker: str,
    action: str,
    bucket: str,
    target_weight: float,
    combined_signal: float,
    expected_ret: float | None,
    cost_estimate: float | None,
    gate_status: str,
    rationale: str | None,
    run_id: str,
    sell_reason: str | None = None,
    db_path: Path = DB_PATH,
) -> int:
    """
    Persist a single trade card to the recommendations table.

    Returns the new recommendation id.
    """
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO recommendations
                (ticker, action, bucket, target_weight, combined_signal,
                 expected_ret, cost_estimate, gate_status, rationale, run_id,
                 status, sell_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?);
            """,
            (
                ticker, action, bucket, target_weight, combined_signal,
                expected_ret, cost_estimate, gate_status, rationale, run_id,
                sell_reason,
            ),
        )
        conn.commit()
        return cur.lastrowid


def mark_recommendation_executed(
    rec_id: int,
    fill_price: float,
    fill_units: float,
    db_path: Path = DB_PATH,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Update recommendation status to executed with actual fill details.

    When ``conn`` is provided the UPDATE runs on it WITHOUT committing — the
    caller owns the transaction so this can be made atomic with the matching
    record_trade write. When None, a private connection is opened and committed.
    """
    sql = """
        UPDATE recommendations
        SET status = 'executed',
            fill_price = ?,
            fill_units = ?,
            executed_at = CURRENT_TIMESTAMP
        WHERE id = ?;
    """
    params = (fill_price, fill_units, rec_id)
    if conn is not None:
        conn.execute(sql, params)
        return
    with get_connection(db_path) as conn:
        conn.execute(sql, params)
        conn.commit()


def mark_recommendation_skipped(rec_id: int, db_path: Path = DB_PATH) -> None:
    """Update recommendation status to skipped."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE recommendations SET status = 'skipped' WHERE id = ?;",
            (rec_id,),
        )
        conn.commit()


def supersede_pending_recommendations(
    keep_run_id: str, db_path: Path = DB_PATH, conn: sqlite3.Connection | None = None
) -> int:
    """Mark every *pending* recommendation NOT from ``keep_run_id`` as 'superseded'.

    A ``recommend --save`` run is a full-universe snapshot, so the previous
    snapshot's still-pending cards are obsolete the moment a newer run lands.
    Leaving them pending lets stale / duplicate BUY cards (and zombie recs for
    tickers later dropped from the universe) appear as actionable, inviting a
    double-execution. Superseded recs drop out of ``list_pending_recommendations``
    while staying in the append-only log for audit. Rows with a NULL run_id are
    also superseded (they predate run_id tracking and cannot be the current run).

    Args:
        keep_run_id: the run_id whose pending recs remain pending.
        conn: optional open connection (caller owns the commit); else private.

    Returns:
        number of recommendations transitioned to 'superseded'.
    """
    sql = (
        "UPDATE recommendations SET status = 'superseded' "
        "WHERE status = 'pending' AND (run_id IS NULL OR run_id != ?);"
    )
    if conn is not None:
        return conn.execute(sql, (keep_run_id,)).rowcount
    with get_connection(db_path) as conn:
        n = conn.execute(sql, (keep_run_id,)).rowcount
        conn.commit()
    return n


def get_recommendation_by_id(rec_id: int, db_path: Path = DB_PATH) -> dict | None:
    """Return a single recommendation row as a dict, or None if not found."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM recommendations WHERE id = ?;", (rec_id,)
        ).fetchone()
    return dict(row) if row else None


def list_pending_recommendations(db_path: Path = DB_PATH) -> list[dict]:
    """Return all pending recommendation rows ordered by generated_at desc."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE status = 'pending' ORDER BY generated_at DESC;"
        ).fetchall()
    return [dict(r) for r in rows]


def get_annual_trade_count(year: int | None = None, db_path: Path = DB_PATH) -> int:
    """
    Count executed trades (rows in trades table) for a given calendar year.

    Defaults to the current year. CRA cares about executed trades,
    not pending recommendations.
    """
    target_year = str(year or datetime.now().year)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM trades WHERE strftime('%Y', trade_date) = ?;",
            (target_year,),
        ).fetchone()
    return row["cnt"] if row else 0


def get_last_buy_date(ticker: str, db_path: Path = DB_PATH) -> date | None:
    """
    Return the most recent BUY trade date for a ticker, or None.

    Used to enforce min_holding_days before recommending adding to a position.
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT MAX(trade_date) AS d FROM trades WHERE ticker = ? AND side = 'BUY';",
            (ticker,),
        ).fetchone()
    return date.fromisoformat(row["d"]) if row and row["d"] else None


def get_all_last_buy_dates(db_path: Path = DB_PATH) -> dict[str, date]:
    """Single query for most recent BUY date per ticker. Replaces per-ticker get_last_buy_date loop."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT ticker, MAX(trade_date) AS d FROM trades WHERE side = 'BUY' GROUP BY ticker;"
        ).fetchall()
    return {r["ticker"]: date.fromisoformat(r["d"]) for r in rows if r["d"]}


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
    ORDER BY fired_at DESC, id DESC
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
