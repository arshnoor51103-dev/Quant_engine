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


# Rename map for per-ticker dict keys in SignalResult.ticker_metadata().
# Add entries here when new signals introduce per-ticker dicts with plural keys.
_PER_TICKER_KEY_MAP: dict[str, str] = {
    "raw_returns": "raw_return",
    "z_scores": "z_score",
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
