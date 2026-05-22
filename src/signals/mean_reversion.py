"""
Mean Reversion Signal.

Combines a time-series z-score (idiosyncratic oversold/overbought) with
cross-sectional rank (relative to the universe) in regime-conditional weights.

References:
    Jegadeesh, N. (1990). Evidence of Predictable Behavior of Security Returns.
        Journal of Finance, 45(3), 881–898.  (1-month reversal)
    Lehmann, B. N. (1990). Fads, Martingales, and Market Efficiency.
        Quarterly Journal of Economics, 105(1), 1–28.
    Asness, C., Moskowitz, T., & Pedersen, L. (2013). Value and Momentum Everywhere.
        Journal of Finance, 68(3), 929–985.  (TS vs CS combination framework)
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .base import Signal, SignalResult
from .vol_regime import VolRegimeSignal

# Regime weights: (w_ts, w_cs)
# CRISIS: lean on idiosyncratic TS signal (tickers decorrelate in crisis).
# LOW_VOL: lean on cross-sectional ranking (high correlation = relative rank is informative).
_REGIME_WEIGHTS: dict[str, tuple[float, float]] = {
    "crisis":   (0.70, 0.30),
    "high_vol": (0.60, 0.40),
    "normal":   (0.50, 0.50),
    "low_vol":  (0.35, 0.65),
    "unknown":  (0.50, 0.50),  # fallback when benchmark data is insufficient
}


class MeanReversionSignal(Signal):
    """
    Regime-conditional mean reversion signal.

    For each ticker, at run_date:
      1. Compute log returns.
      2. Compute rolling z-scores at `short_window` and `long_window` days.
      3. Average: z_ts = 0.5 * z_short + 0.5 * z_long.
      4. TS component: tanh(z_ts) — per-ticker normalization to (-1, 1).
      5. CS component: rank-normalize z_ts across tickers to [-1, +1].
      6. Combine: combined = w_ts * tanh(z_ts) + w_cs * z_cs,
         where (w_ts, w_cs) depend on current vol regime.
      7. Flip sign: oversold (negative z) becomes positive (buy signal).
      8. Final: rank-normalize flipped combined across tickers.

    Tickers with fewer than `long_window` price rows get score 0.0 (neutral).

    Parameters:
        short_window: rolling window for short-term z-score (default 20 ≈ 1 month)
        long_window: rolling window for intermediate z-score (default 60 ≈ 3 months)
    """

    def __init__(self, short_window: int = 20, long_window: int = 60):
        self._short = short_window
        self._long = long_window
        self._regime_sig = VolRegimeSignal()

    @property
    def name(self) -> str:
        return f"mean_reversion_{self._short}_{self._long}"

    @property
    def lookback_days(self) -> int:
        return self._long + 10  # buffer for weekends and data gaps

    @property
    def description(self) -> str:
        return (
            f"Regime-conditional mean reversion: {self._short}/{self._long}d "
            f"rolling z-score of log returns, tanh(TS) + cross-sectional rank, "
            f"sign-flipped so positive = oversold = buy."
        )

    def _rolling_zscore(self, log_ret: pd.Series, window: int) -> pd.Series:
        """
        Rolling z-score: (log_ret - rolling_mean) / rolling_std.

        Returns NaN for the first `window - 1` rows. std=0 rows yield NaN.
        """
        roll = log_ret.rolling(window)
        mean = roll.mean()
        std = roll.std()
        # Avoid division by zero when all returns in the window are identical
        return (log_ret - mean) / std.where(std > 0)

    def _rank_normalize(self, raw_scores: dict[str, float]) -> dict[str, float]:
        """
        Cross-sectional rank normalization to [-1, +1].

        score = 2 * (rank / (n - 1)) - 1.0
        With n=1, returns 0.0.
        """
        items = sorted(raw_scores.items(), key=lambda x: x[1])
        n = len(items)
        if n <= 1:
            return {t: 0.0 for t, _ in items}
        return {
            ticker: 2.0 * rank / (n - 1) - 1.0
            for rank, (ticker, _) in enumerate(items)
        }

    def generate(
        self, prices: dict[str, pd.Series], run_date: date | None = None
    ) -> SignalResult:
        """
        Generate mean reversion scores for all tickers.

        Args:
            prices: dict mapping ticker -> pd.Series of adjusted close prices,
                    indexed by datetime (ascending). Same format as MomentumSignal.
            run_date: effective date (defaults to minimum of latest dates across
                      all series, matching momentum.py convention).

        Returns:
            SignalResult with scores in [-1, +1] per ticker.
            Positive score = oversold = buy pressure.
        """
        # Determine run_date
        if run_date is None:
            latest_dates = [p.index.max() for p in prices.values() if len(p) > 0]
            run_date = min(latest_dates).date() if latest_dates else date.today()

        # Detect vol regime from the same prices dict (self-contained)
        regime_result = self._regime_sig.generate(prices, run_date)
        regime = regime_result.metadata.get("regime", "unknown")
        w_ts, w_cs = _REGIME_WEIGHTS.get(regime, (0.50, 0.50))

        # Compute z_ts per ticker at run_date
        z_ts_raw: dict[str, float] = {}
        skipped: list[str] = []

        for ticker, price_series in prices.items():
            if (
                price_series.empty
                or not hasattr(price_series.index, "dtype")
                or price_series.index.dtype == "int64"
            ):
                skipped.append(ticker)
                continue

            trimmed = price_series[price_series.index <= pd.Timestamp(run_date)]

            if len(trimmed) < self._long:
                skipped.append(ticker)
                continue

            log_ret = np.log(trimmed).diff()
            z_short = self._rolling_zscore(log_ret, self._short)
            z_long = self._rolling_zscore(log_ret, self._long)
            z_ts = 0.5 * z_short + 0.5 * z_long

            val = z_ts.iloc[-1]
            if np.isnan(val):
                skipped.append(ticker)
            else:
                z_ts_raw[ticker] = float(val)

        if z_ts_raw:
            # CS component: rank-normalize z_ts across tickers
            z_cs = self._rank_normalize(z_ts_raw)

            # TS component: tanh(z_ts) — compresses raw z-score to (-1, 1) per ticker
            z_ts_norm = {t: float(np.tanh(v)) for t, v in z_ts_raw.items()}

            # Combine then flip sign: oversold (negative z) → positive (buy)
            combined_flipped: dict[str, float] = {
                t: -(w_ts * z_ts_norm[t] + w_cs * z_cs[t])
                for t in z_ts_raw
            }

            # Final rank-normalization
            scores = self._rank_normalize(combined_flipped)
        else:
            scores = {}

        # Tickers with insufficient data get neutral score
        for ticker in skipped:
            scores[ticker] = 0.0

        return SignalResult(
            signal_name=self.name,
            run_date=run_date,
            scores=scores,
            metadata={
                "regime": regime,
                "regime_weights": {"w_ts": w_ts, "w_cs": w_cs},
                "z_ts_raw": z_ts_raw,
                "skipped_tickers": skipped,
            },
        )
