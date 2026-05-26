"""
RSI Gate Signal — Wilder's RSI as a binary trend confirmation filter (H005).

Computes Wilder's Relative Strength Index using SMMA (alpha=1/n).
Returns +1.0 if RSI(period) > threshold (trend confirmed), else 0.0 (gate closed).

Designed for use as a multiplicative gate on an existing momentum signal:
    combined = momentum_score * rsi_gate

The bar frequency depends on the input price series:
    RSI(14) on daily prices  → canonical Wilder (1978) specification
    RSI(21) on monthly prices → H005 proposed spec (21-month lookback)

Math note: RSI > 50 iff SMMA(gains) > SMMA(losses) iff smoothed net signed
price change > 0. This is a bounded transform of the same positive-drift
construct as price momentum — correlated with but not identical to price
above an N-period moving average.

Reference:
    Wilder, J.W. (1978). New Concepts in Technical Trading Systems. Trend Research.
    Mathematical relationship documented in DL-012.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .base import Signal, SignalResult


def _rsi_at_date(
    prices: pd.Series,
    period: int,
    as_of: pd.Timestamp,
) -> float | None:
    """
    Compute Wilder's RSI(period) at a specific date.

    Uses Wilder's SMMA: ewm(alpha=1/period, adjust=False).
    This differs from standard EMA (alpha=2/(period+1)).

    Args:
        prices: price series indexed by datetime, ascending
        period: RSI lookback period
        as_of: compute RSI using data up to and including this timestamp

    Returns:
        RSI value in [0, 100], or None if insufficient data.
    """
    trimmed = prices[prices.index <= as_of].dropna()
    if len(trimmed) < period + 1:
        return None

    delta = trimmed.diff().dropna()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)

    avg_gain = gains.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, adjust=False).mean()

    last_gain = float(avg_gain.iloc[-1])
    last_loss = float(avg_loss.iloc[-1])

    if last_loss == 0.0:
        return 100.0
    if last_gain == 0.0:
        return 0.0

    rs = last_gain / last_loss
    return 100.0 - (100.0 / (1.0 + rs))


class RSISignal(Signal):
    """
    Wilder's RSI(period) > threshold as a binary trend confirmation gate.

    Returns +1.0 when RSI exceeds threshold (gate open).
    Returns 0.0 when RSI is at or below threshold (gate closed).

    Parameters:
        period: RSI lookback in bars (default 14 — Wilder's daily spec).
                For H005's monthly-bar variant pass period=21 with monthly prices.
        threshold: gate level (default 50.0 — positive-drift boundary).
    """

    def __init__(self, period: int = 14, threshold: float = 50.0):
        if period < 2:
            raise ValueError(f"RSI period must be >= 2, got {period}")
        if not (0.0 < threshold < 100.0):
            raise ValueError(
                f"RSI threshold must be in (0, 100), got {threshold}"
            )
        self._period = period
        self._threshold = threshold

    @property
    def name(self) -> str:
        return f"rsi_{self._period}_gate_{int(self._threshold)}"

    @property
    def lookback_days(self) -> int:
        return self._period + 10

    @property
    def description(self) -> str:
        return (
            f"Wilder RSI({self._period}) > {self._threshold} binary gate. "
            f"SMMA alpha=1/{self._period}. +1.0 gate open, 0.0 gate closed."
        )

    def generate(
        self,
        prices: dict[str, pd.Series],
        run_date: date | None = None,
    ) -> SignalResult:
        """
        Compute RSI gate for all tickers at run_date.

        Insufficient-data tickers return 0.0 (conservative — gate closed).

        Args:
            prices: daily (or monthly) price series per ticker
            run_date: evaluation date (defaults to min of latest dates)

        Returns:
            SignalResult with per-ticker gate scores: 1.0 or 0.0.
        """
        if run_date is None:
            latest_dates = [p.index.max() for p in prices.values() if len(p) > 0]
            run_date = min(latest_dates).date() if latest_dates else date.today()

        as_of = pd.Timestamp(run_date)
        scores: dict[str, float] = {}
        rsi_values: dict[str, float] = {}
        skipped: list[str] = []

        for ticker, price_series in prices.items():
            if price_series.empty:
                scores[ticker] = 0.0
                skipped.append(ticker)
                continue

            rsi = _rsi_at_date(price_series, self._period, as_of)
            if rsi is None:
                scores[ticker] = 0.0
                skipped.append(ticker)
            else:
                rsi_values[ticker] = rsi
                scores[ticker] = 1.0 if rsi > self._threshold else 0.0

        return SignalResult(
            signal_name=self.name,
            run_date=run_date,
            scores=scores,
            metadata={
                "period": self._period,
                "threshold": self._threshold,
                "rsi_values": rsi_values,
                "skipped_tickers": skipped,
            },
        )
