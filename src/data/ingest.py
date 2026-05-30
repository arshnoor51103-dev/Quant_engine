"""
Market data ingestion via yfinance.

Pulls daily OHLCV for each ticker in the universe and writes to SQLite.
Incremental: only pulls dates after the latest stored date per ticker.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

from .storage import latest_price_date, upsert_prices, log

UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "config" / "universe.yaml"


def load_universe(path: Path = UNIVERSE_PATH) -> list[dict]:
    """Read universe.yaml and return the list of asset dicts."""
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["universe"]


def fetch_ticker(ticker: str, start: date, end: date) -> pd.DataFrame:
    """
    Fetch daily OHLCV for one ticker from yfinance.

    Returns a DataFrame with columns: Open, High, Low, Close, Adj Close, Volume
    indexed by datetime. Empty DF if no data.
    """
    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),  # yfinance end is exclusive
        progress=False,
        auto_adjust=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    # Flatten multi-index columns if present (newer yfinance versions)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def df_to_rows(ticker: str, df: pd.DataFrame) -> list[dict]:
    """Convert yfinance DataFrame to list of dicts for SQLite upsert."""
    rows = []
    for idx, row in df.iterrows():
        rows.append({
            "ticker": ticker,
            "trade_date": idx.date().isoformat(),
            "open": float(row.get("Open", 0) or 0),
            "high": float(row.get("High", 0) or 0),
            "low": float(row.get("Low", 0) or 0),
            "close": float(row.get("Close", 0) or 0),
            "adj_close": float(row.get("Adj Close", row.get("Close", 0)) or 0),
            "volume": int(row.get("Volume", 0) or 0),
        })
    return rows


def ingest_universe(
    years: int = 20,
    incremental: bool = True,
    retries: int = 3,
    backoff_seconds: float = 2.0,
) -> dict[str, int]:
    """
    Pull OHLCV for every ticker in the universe.

    Args:
        years: history depth on a full pull.
        incremental: if True, fetch only since latest stored date per ticker.
        retries: attempts per ticker before marking it failed (transient errors).
        backoff_seconds: base backoff between retries; doubles each attempt.

    Returns:
        dict mapping ticker -> rows inserted (-1 marks a ticker that failed all retries).
    """
    universe = load_universe()
    today = date.today()
    full_start = today.replace(year=today.year - years)

    results = {}
    for asset in universe:
        ticker = asset["ticker"]
        if incremental:
            latest = latest_price_date(ticker)
            start = (latest + timedelta(days=1)) if latest else full_start
        else:
            start = full_start

        if start > today:
            results[ticker] = 0
            continue

        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                df = fetch_ticker(ticker, start, today)
                rows = df_to_rows(ticker, df)
                n = upsert_prices(rows)
                results[ticker] = n
                log("ingest", "INFO", f"{ticker}: {n} rows from {start} to {today}")
                last_err = None
                break
            except Exception as e:  # noqa: BLE001 — per-ticker isolation, retried with backoff
                last_err = e
                log("ingest", "WARNING",
                    f"{ticker}: attempt {attempt}/{retries} failed: {type(e).__name__}: {e}")
                if attempt < retries:
                    time.sleep(backoff_seconds * (2 ** (attempt - 1)))
        if last_err is not None:
            log("ingest", "ERROR", f"{ticker}: all {retries} attempts failed: {last_err}")
            results[ticker] = -1
            # Don't raise — one bad ticker shouldn't kill the run; fetch() reports failures.

    return results
