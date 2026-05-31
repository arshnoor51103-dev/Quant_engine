"""
Base signal interface.

Every signal model implements this ABC. Enforces:
- Deterministic: same inputs → same outputs (no LLM, no randomness)
- Scored: returns a normalized score in [-1, +1] per ticker
- Documented: must declare its lookback requirement and math reference

Signal scores:
    +1.0 = maximum bullish conviction
     0.0 = neutral / no signal
    -1.0 = maximum bearish conviction

Scores are relative within the universe, not absolute.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd


# Metadata keys whose VALUE is a per-ticker dict ({ticker: x}). Register new
# per-ticker keys here so ticker_metadata() extracts them rather than broadcasting.
_PER_TICKER_KEYS: frozenset[str] = frozenset({
    "raw_returns", "z_scores", "z_ts_raw", "rsi_values",
})

# Rename per-ticker keys to their singular form on extraction.
_PER_TICKER_KEY_MAP: dict[str, str] = {
    "raw_returns": "raw_return",
    "z_scores": "z_score",
    "z_ts_raw": "z_ts",
    "rsi_values": "rsi_value",
}


@dataclass
class SignalResult:
    """Output of a single signal run."""
    signal_name: str
    run_date: date
    scores: dict[str, float]         # ticker -> score [-1, +1]
    metadata: dict | None = None     # extra info (lookback used, regime, etc.)

    def ranked(self, ascending: bool = False) -> list[tuple[str, float]]:
        """Return (ticker, score) sorted by score."""
        return sorted(self.scores.items(), key=lambda x: x[1], reverse=not ascending)

    def ticker_metadata(self, ticker: str) -> dict:
        """
        Extract a ticker-specific metadata slice from this result's metadata blob.

        Two-tier extraction contract — binding on all Signal implementations:
        - Per-ticker keys (registered in _PER_TICKER_KEYS): value is a
          {ticker: x} dict; extract value[ticker], renamed via
          _PER_TICKER_KEY_MAP. Omitted if ticker is absent.
        - List values (e.g. skipped_tickers): dropped from per-ticker rows —
          run-level data does not belong on every row (F20).
        - Everything else (scalars AND structural dicts like regime_weights):
          broadcast verbatim — preserved, not dropped (F6).

        Args:
            ticker: Yahoo Finance ticker symbol (e.g. 'VFV.TO')

        Returns:
            dict suitable for JSON serialisation. Empty dict if metadata is None.
        """
        if not self.metadata:
            return {}
        out: dict = {}
        for key, value in self.metadata.items():
            if key in _PER_TICKER_KEYS:
                # Per-ticker dict: extract this ticker's value, renamed (omit if absent).
                if isinstance(value, dict) and ticker in value:
                    out[_PER_TICKER_KEY_MAP.get(key, key)] = value[ticker]
            elif isinstance(value, list):
                # F20: run-level lists (e.g. skipped_tickers) don't belong on every row.
                continue
            else:
                # Scalar OR structural dict (e.g. regime_weights): broadcast verbatim.
                out[key] = value
        return out


class Signal(ABC):
    """Abstract base class for all signal models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable signal name."""
        ...

    @property
    @abstractmethod
    def lookback_days(self) -> int:
        """Minimum trading days of history required."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line math description for LEARNING.md."""
        ...

    @abstractmethod
    def generate(self, prices: dict[str, pd.Series], run_date: date | None = None) -> SignalResult:
        """
        Generate signal scores for all tickers.

        Args:
            prices: dict mapping ticker -> pd.Series of adjusted close prices
                    (indexed by datetime, sorted ascending).
            run_date: effective date (defaults to latest date in prices).

        Returns:
            SignalResult with scores in [-1, +1] per ticker.
        """
        ...
