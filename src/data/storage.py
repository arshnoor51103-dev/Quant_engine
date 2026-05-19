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

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "quant.db"

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
    status        TEXT NOT NULL DEFAULT 'pending'
);

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
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection with row factory + foreign keys on."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize(db_path: Path = DB_PATH) -> None:
    """Create the schema if not present. Safe to call repeatedly."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


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

    Returns:
        trade id (AUTOINCREMENT primary key)

    Raises:
        ValueError: insufficient units on a SELL
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    if units <= 0:
        raise ValueError(f"units must be positive, got {units}")

    with get_connection(db_path) as conn:
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

        conn.commit()
    return trade_id


def log(component: str, level: str, message: str, db_path: Path = DB_PATH) -> None:
    """Append a row to run_log."""
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO run_log (component, level, message) VALUES (?, ?, ?);",
            (component, level, message),
        )
        conn.commit()
