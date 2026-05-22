"""
Volatility Regime Detection.

Classifies the current market environment into regimes based on
realized volatility relative to its own history.

Regimes:
    LOW_VOL  : realized vol < 25th percentile of trailing window → risk-on
    NORMAL   : 25th–75th percentile → neutral
    HIGH_VOL : > 75th percentile → risk-off
    CRISIS   : > 95th percentile → defensive

Signal output:
    +1.0 for LOW_VOL (risk-on, favor growth)
    +0.3 for NORMAL (slight tilt to growth)
    -0.5 for HIGH_VOL (reduce exposure)
    -1.0 for CRISIS (defensive / max stable bucket)

Reference:
    Standard rolling realized volatility with percentile-based regime thresholds.
    Similar to the approach in Kritzman et al. (2012) "Regime Shifts."
"""
from __future__ import annotations

from datetime import date
from enum import Enum

import numpy as np
import pandas as pd

from .base import Signal, SignalResult


class Regime(str, Enum):
    LOW_VOL = "low_vol"
    NORMAL = "normal"
    HIGH_VOL = "high_vol"
    CRISIS = "crisis"


REGIME_SCORES = {
    Regime.LOW_VOL: 1.0,
    Regime.NORMAL: 0.3,
    Regime.HIGH_VOL: -0.5,
    Regime.CRISIS: -1.0,
}

STABLE_TICKERS: frozenset[str] = frozenset({"VAB.TO", "ZAG.TO", "HSAV.TO"})


class VolRegimeSignal(Signal):
    """
    Realized volatility regime detector.

    Uses a benchmark ticker (default: XIC.TO for Canadian broad market)
    and broadcasts the regime signal to all tickers.
    Growth tickers get the raw regime score; stable tickers get the inverse.

    Parameters:
        vol_window: rolling window for realized vol (default 21 = 1 month)
        history_window: lookback for percentile calculation (default 252*5 = 5yr)
        benchmark_ticker: which ticker's vol determines the regime
    """

    def __init__(
        self,
        vol_window: int = 21,
        history_window: int = 1260,
        benchmark_ticker: str = "XIC.TO",
    ):
        self._vol_window = vol_window
        self._history_window = history_window
        self._benchmark = benchmark_ticker

    @property
    def name(self) -> str:
        return f"vol_regime_{self._vol_window}d"

    @property
    def lookback_days(self) -> int:
        return self._history_window + self._vol_window + 10

    @property
    def description(self) -> str:
        return (
            f"Volatility regime: {self._vol_window}d realized vol of {self._benchmark}, "
            f"percentile-ranked against {self._history_window}d history."
        )

    def _classify(self, current_vol: float, vol_history: pd.Series) -> Regime:
        """Classify current vol into regime based on historical percentiles."""
        p = (vol_history < current_vol).mean()  # percentile rank
        if p >= 0.95:
            return Regime.CRISIS
        elif p >= 0.75:
            return Regime.HIGH_VOL
        elif p >= 0.25:
            return Regime.NORMAL
        else:
            return Regime.LOW_VOL

    def generate(
        self, prices: dict[str, pd.Series], run_date: date | None = None
    ) -> SignalResult:
        if self._benchmark not in prices or len(prices[self._benchmark]) < self.lookback_days:
            # Not enough data — return neutral
            return SignalResult(
                signal_name=self.name,
                run_date=run_date or date.today(),
                scores={t: 0.0 for t in prices},
                metadata={"regime": "unknown", "error": "insufficient benchmark data"},
            )

        bench = prices[self._benchmark]
        if run_date:
            bench = bench[bench.index <= pd.Timestamp(run_date)]

        returns = bench.pct_change().dropna()
        rolling_vol = returns.rolling(window=self._vol_window).std() * np.sqrt(252)
        rolling_vol = rolling_vol.dropna()

        if len(rolling_vol) < 2:
            return SignalResult(
                signal_name=self.name,
                run_date=run_date or date.today(),
                scores={t: 0.0 for t in prices},
                metadata={"regime": "unknown", "error": "insufficient vol data"},
            )

        current_vol = rolling_vol.iloc[-1]
        vol_history = rolling_vol.iloc[-self._history_window:]
        regime = self._classify(current_vol, vol_history)
        base_score = REGIME_SCORES[regime]

        # Broadcast to universe:
        # growth/dividend tickers get the raw score (risk-on = positive)
        # stable tickers get inverted (risk-off = positive for bonds)
        # This is a simplification — Phase 3 optimizer will handle this more precisely.
        scores = {}
        for ticker in prices:
            if ticker in STABLE_TICKERS:
                scores[ticker] = -base_score  # inverse: crisis = buy bonds
            else:
                scores[ticker] = base_score

        return SignalResult(
            signal_name=self.name,
            run_date=run_date or date.today(),
            scores=scores,
            metadata={
                "regime": regime.value,
                "current_annualized_vol": float(current_vol),
                "vol_percentile": float((vol_history < current_vol).mean()),
                "benchmark": self._benchmark,
            },
        )
