"""
Portfolio state model.

Tracks current holdings, market value, bucket allocation drift, and provides
the data interface for the CLI and (later) signal generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from ..data.storage import get_connection

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@dataclass
class Holding:
    ticker: str
    units: float
    avg_cost: float
    bucket: str
    last_price: float | None = None

    @property
    def market_value(self) -> float:
        if self.last_price is None:
            return 0.0
        return self.units * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        if self.last_price is None:
            return 0.0
        return (self.last_price - self.avg_cost) * self.units


@lru_cache(maxsize=1)
def load_universe_map() -> dict[str, dict]:
    """Map ticker -> universe metadata."""
    with open(CONFIG_DIR / "universe.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {a["ticker"]: a for a in cfg["universe"]}


@lru_cache(maxsize=1)
def load_portfolio_config() -> dict:
    with open(CONFIG_DIR / "portfolio.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_holdings() -> list[Holding]:
    """Read holdings from DB, enrich with last close price and bucket."""
    universe = load_universe_map()
    with get_connection() as conn:
        rows = conn.execute("SELECT ticker, units, avg_cost FROM holdings;").fetchall()
        if not rows:
            return []
        tickers = [r["ticker"] for r in rows]
        placeholders = ",".join("?" * len(tickers))
        price_rows = conn.execute(
            f"""SELECT p.ticker, p.adj_close FROM prices p
            INNER JOIN (SELECT ticker, MAX(trade_date) AS mx FROM prices
                        WHERE ticker IN ({placeholders}) GROUP BY ticker) latest
            ON p.ticker = latest.ticker AND p.trade_date = latest.mx""",
            tickers,
        ).fetchall()
    latest_map = {r["ticker"]: r["adj_close"] for r in price_rows}
    return [
        Holding(
            ticker=r["ticker"],
            units=r["units"],
            avg_cost=r["avg_cost"],
            bucket=universe.get(r["ticker"], {}).get("bucket", "unknown"),
            last_price=latest_map.get(r["ticker"]),
        )
        for r in rows
    ]


def nav(holdings: list[Holding] | None = None) -> float:
    """Total portfolio market value."""
    if holdings is None:
        holdings = get_holdings()
    return sum(h.market_value for h in holdings)


def bucket_allocation(holdings: list[Holding] | None = None) -> dict[str, dict]:
    """
    Current bucket weights vs targets + drift.

    Returns:
        {
            'growth': {'target': 0.60, 'actual': 0.62, 'drift': 0.02},
            ...
        }
    """
    cfg = load_portfolio_config()
    targets = cfg["allocation"]
    if holdings is None:
        holdings = get_holdings()
    total = sum(h.market_value for h in holdings) or 1.0

    actual = {b: 0.0 for b in targets.keys()}
    for h in holdings:
        if h.bucket in actual:
            actual[h.bucket] += h.market_value / total

    return {
        b: {
            "target": targets[b]["target"],
            "actual": actual[b],
            "drift": actual[b] - targets[b]["target"],
            "tolerance": targets[b]["tolerance"],
            "needs_rebalance": abs(actual[b] - targets[b]["target"]) > targets[b]["tolerance"],
        }
        for b in targets
    }


def price_series(ticker: str, lookback_days: int = 252 * 6) -> pd.Series:
    """
    Pull price history as a pandas Series indexed by date.

    Default 6-year window — adjust per use case.
    """
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT trade_date, adj_close
            FROM prices
            WHERE ticker = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            conn,
            params=(ticker, lookback_days),
        )
    if df.empty:
        return pd.Series(dtype=float)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.set_index("trade_date").sort_index()["adj_close"]


def price_series_batch(tickers: list[str], lookback_days: int = 252 * 6) -> dict[str, pd.Series]:
    """Load price history for multiple tickers in one DB query."""
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    with get_connection() as conn:
        df = pd.read_sql_query(
            f"SELECT ticker, trade_date, adj_close FROM prices WHERE ticker IN ({placeholders}) ORDER BY ticker, trade_date",
            conn,
            params=tickers,
        )
    if df.empty:
        return {}
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return {
        str(t): g.set_index("trade_date")["adj_close"].tail(lookback_days)
        for t, g in df.groupby("ticker", sort=False)
    }
