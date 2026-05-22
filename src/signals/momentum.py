"""
12-1 Month Momentum Signal.

The workhorse quant factor. Jegadeesh & Titman (1993).

Logic:
    For each ticker, compute total return over the window [t-252, t-21]
    (i.e., 12 months lookback, skip the most recent month).
    The skip-month avoids short-term reversal — well-documented in
    equity returns at the 1-month horizon.

    Cross-sectionally rank all tickers. Normalize to [-1, +1].

Reference:
    Jegadeesh, N., & Titman, S. (1993). Returns to Buying Winners and
    Selling Losers: Implications for Stock Market Efficiency.
    Journal of Finance, 48(1), 65–91.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .base import Signal, SignalResult


class MomentumSignal(Signal):
    """
    12-1 month cross-sectional momentum.

    Parameters:
        formation_days: total lookback window in trading days (default 252 ≈ 12mo)
        skip_days: recent days to skip (default 21 ≈ 1mo, avoids reversal)
    """

    def __init__(self, formation_days: int = 252, skip_days: int = 21):
        self._formation = formation_days
        self._skip = skip_days

    @property
    def name(self) -> str:
        return f"momentum_{self._formation}_{self._skip}"

    @property
    def lookback_days(self) -> int:
        return self._formation + self._skip + 10  # buffer for data gaps

    @property
    def description(self) -> str:
        return (
            f"Cross-sectional momentum: total return over "
            f"[t-{self._formation}, t-{self._skip}], rank-normalized to [-1,+1]."
        )

    def _raw_momentum(self, prices: pd.Series) -> float | None:
        """
        Compute raw momentum return for a single ticker.

        Return: (P_{t-skip} / P_{t-formation}) - 1
        or None if insufficient data.
        """
        if len(prices) < (self._formation + self._skip):
            return None

        # Prices should be sorted ascending by date
        recent = prices.iloc[-self._skip] if self._skip > 0 else prices.iloc[-1]
        distant = prices.iloc[-(self._formation + self._skip)]

        if distant == 0 or np.isnan(distant) or np.isnan(recent):
            return None

        return float((recent / distant) - 1)

    def _rank_normalize(self, raw_scores: dict[str, float]) -> dict[str, float]:
        """
        Cross-sectional rank normalization to [-1, +1].

        Rank all tickers, then map:
            score = 2 * (rank - 1) / (n - 1) - 1

        With n=1, returns 0.0 for the single ticker.
        """
        items = sorted(raw_scores.items(), key=lambda x: x[1])
        n = len(items)
        if n <= 1:
            return {t: 0.0 for t, _ in items}

        normalized = {}
        for rank, (ticker, _) in enumerate(items):
            normalized[ticker] = 2.0 * rank / (n - 1) - 1.0
        return normalized

    def generate(
        self, prices: dict[str, pd.Series], run_date: date | None = None
    ) -> SignalResult:
        """
        Generate momentum scores for all tickers.

        Tickers with insufficient data get score 0.0 (neutral).
        """
        if run_date is None:
            # Use latest common date across all series
            latest_dates = [p.index.max() for p in prices.values() if len(p) > 0]
            run_date = min(latest_dates).date() if latest_dates else date.today()

        # Compute raw momentum returns
        raw = {}
        skipped = []
        for ticker, price_series in prices.items():
            if price_series.empty or not hasattr(price_series.index, 'dtype') or price_series.index.dtype == 'int64':
                skipped.append(ticker)
                continue
            # Trim to data up to run_date
            trimmed = price_series[price_series.index <= pd.Timestamp(run_date)]
            mom = self._raw_momentum(trimmed)
            if mom is not None:
                raw[ticker] = mom
            else:
                skipped.append(ticker)

        # Rank-normalize across the universe
        if raw:
            scores = self._rank_normalize(raw)
        else:
            scores = {}

        # Skipped tickers get neutral score
        for ticker in skipped:
            scores[ticker] = 0.0

        return SignalResult(
            signal_name=self.name,
            run_date=run_date,
            scores=scores,
            metadata={
                "formation_days": self._formation,
                "skip_days": self._skip,
                "raw_returns": raw,
                "skipped_tickers": skipped,
            },
        )


class ShortTermMomentum(MomentumSignal):
    """3-1 month momentum — faster signal, noisier."""
    def __init__(self):
        super().__init__(formation_days=63, skip_days=21)


