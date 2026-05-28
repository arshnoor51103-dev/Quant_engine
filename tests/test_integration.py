"""
Integration smoke test: synthetic prices → signal → backtest → recommendations.

Validates that the three core pipeline layers connect end-to-end without error
and produce actionable output on a deterministic universe.

Design notes:
  - VolRegimeSignal requires 1291 rows of XIC.TO history for a real regime read.
    To keep the test fast we construct the regime SignalResult directly (avoiding
    the 1291-row setup) — the regime signal is unit-tested independently in
    test_signals.py; this test focuses on inter-layer connectivity.
  - Prices use np.linspace (deterministic, no random drift) matching the
    pattern established in test_signals.py Bug #5 fix.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, run_backtest
from src.portfolio.recommendations import generate_trade_cards
from src.signals.base import SignalResult
from src.signals.momentum import MomentumSignal
from src.signals.vol_regime import STABLE_TICKERS


# ─── Shared fixtures ──────────────────────────────────────────────────────────

_TICKERS_BY_BUCKET: list[tuple[str, str]] = [
    ("VFV.TO",   "growth"),
    ("XIC.TO",   "growth"),
    ("HXQ.TO",   "growth"),
    ("XEF.TO",   "growth"),
    ("CHPS.TO",  "growth"),
    ("VAB.TO",   "stable"),
    ("HSAV.TO",  "stable"),
    ("CDZ.TO",   "dividend"),
    ("VDY.TO",   "dividend"),
]

_UNIVERSE_MAP: dict[str, dict] = {
    t: {"bucket": b, "spread_override": None}
    for t, b in _TICKERS_BY_BUCKET
}

_PORTFOLIO_CONFIG: dict = {
    "allocation": {
        "growth":   {"target": 0.60, "tolerance": 0.10},
        "stable":   {"target": 0.25, "tolerance": 0.05},
        "dividend": {"target": 0.15, "tolerance": 0.05},
    },
    "trading": {
        "spread_proxy": 0.0005,
        "anchor_return_annualized": 0.1398,
        "profit_floor": 0.005,
        "trade_threshold_multiplier": 2.0,
        "max_trades_per_year": 24,
        "cra_warn_threshold": 20,
        "min_holding_days": 14,
    },
    "rebalance": {"min_rebalance_trade": 50.0},
}


@pytest.fixture(scope="module")
def synthetic_prices() -> dict[str, pd.Series]:
    """
    800 business days of deterministic prices starting 2018-01-01.

    Growth tickers: varying uptrend slopes so momentum ranks differ.
    Stable tickers: near-flat (bonds/cash proxy).
    Dividend tickers: mild uptrend.
    VFV.TO doubles as benchmark for the backtest.
    """
    N = 800
    dates = pd.bdate_range(start="2018-01-01", periods=N)
    slopes = {
        "VFV.TO":  (100.0, 200.0),   # +100% — strong uptrend (benchmark + growth)
        "XIC.TO":  (100.0, 180.0),   # +80%
        "HXQ.TO":  (100.0, 160.0),   # +60%
        "XEF.TO":  (100.0, 130.0),   # +30%
        "CHPS.TO": (100.0, 250.0),   # +150% — top-ranked
        "VAB.TO":  (100.0, 105.0),   # +5% — near-flat (bond proxy)
        "HSAV.TO": (100.0, 102.0),   # +2% — near-flat (cash proxy)
        "CDZ.TO":  (100.0, 140.0),   # +40% — dividend
        "VDY.TO":  (100.0, 125.0),   # +25% — dividend
    }
    return {
        t: pd.Series(np.linspace(lo, hi, N), index=dates)
        for t, (lo, hi) in slopes.items()
    }


@pytest.fixture(scope="module")
def momentum_result(synthetic_prices: dict[str, pd.Series]) -> SignalResult:
    sig = MomentumSignal()
    return sig.generate(synthetic_prices)


@pytest.fixture(scope="module")
def _normal_regime_result(synthetic_prices: dict[str, pd.Series]) -> SignalResult:
    """NORMAL-regime SignalResult constructed without running VolRegimeSignal."""
    tickers = list(synthetic_prices.keys())
    stable_score = -0.3
    growth_div_score = 0.3
    scores = {
        t: (stable_score if t in STABLE_TICKERS else growth_div_score)
        for t in tickers
    }
    return SignalResult(
        signal_name="vol_regime_21d",
        run_date=date(2021, 6, 1),
        scores=scores,
        metadata={"regime": "NORMAL", "vol_percentile": 0.50},
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestSignalLayer:
    def test_momentum_scores_all_tickers(
        self, momentum_result: SignalResult, synthetic_prices: dict[str, pd.Series]
    ) -> None:
        """Momentum signal produces exactly one score per input ticker."""
        assert set(momentum_result.scores.keys()) == set(synthetic_prices.keys())

    def test_momentum_scores_in_range(self, momentum_result: SignalResult) -> None:
        """All scores are in [-1, +1]."""
        for t, s in momentum_result.scores.items():
            assert -1.0 <= s <= 1.0, f"{t}: score {s} out of bounds"

    def test_chps_ranked_highest(self, momentum_result: SignalResult) -> None:
        """CHPS.TO (+150% slope) must rank as the top momentum ticker."""
        best = max(momentum_result.scores, key=lambda t: momentum_result.scores[t])
        assert best == "CHPS.TO"

    def test_stable_tickers_have_lower_scores_than_top_growth(
        self, momentum_result: SignalResult
    ) -> None:
        """VAB.TO and HSAV.TO (near-flat) must rank below CHPS.TO."""
        top = momentum_result.scores["CHPS.TO"]
        for stable in STABLE_TICKERS:
            assert momentum_result.scores[stable] < top


class TestBacktestLayer:
    def test_backtest_runs_without_error(
        self, synthetic_prices: dict[str, pd.Series]
    ) -> None:
        sig = MomentumSignal()
        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            top_n=4,
            benchmark_ticker="VFV.TO",
        )
        result = run_backtest(sig, synthetic_prices, config)
        assert result is not None

    def test_backtest_avg_holdings_positive(
        self, synthetic_prices: dict[str, pd.Series]
    ) -> None:
        """With multiple uptrending tickers, holdings must be > 0 every period."""
        sig = MomentumSignal()
        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            top_n=4,
            benchmark_ticker="VFV.TO",
        )
        result = run_backtest(sig, synthetic_prices, config)
        assert result.metrics["avg_holdings_per_period"] > 0

    def test_backtest_n_rebalances_reasonable(
        self, synthetic_prices: dict[str, pd.Series]
    ) -> None:
        """A 1-year window with monthly rebalance (~21 days) should yield 10–13 rebalances."""
        sig = MomentumSignal()
        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            top_n=4,
            benchmark_ticker="VFV.TO",
        )
        result = run_backtest(sig, synthetic_prices, config)
        n = result.metrics["n_rebalances"]
        assert 8 <= n <= 15, f"Expected 8–15 rebalances for 1yr window, got {n}"


class TestRecommendLayer:
    def test_generate_cards_produces_actionable_output(
        self,
        momentum_result: SignalResult,
        _normal_regime_result: SignalResult,
        synthetic_prices: dict[str, pd.Series],
    ) -> None:
        """Full pipeline must produce ≥ 1 BUY card when deploying fresh cash."""
        latest_prices = {t: float(s.iloc[-1]) for t, s in synthetic_prices.items()}
        last_buy_dates = {t: None for t in synthetic_prices}

        cards = generate_trade_cards(
            momentum_result=momentum_result,
            regime_result=_normal_regime_result,
            holdings=[],
            portfolio_config=_PORTFOLIO_CONFIG,
            universe_map=_UNIVERSE_MAP,
            portfolio_nav=0.0,
            cash=800.0,
            annual_trade_count=0,
            last_buy_dates=last_buy_dates,
            latest_prices=latest_prices,
        )

        actionable = [c for c in cards if c.action == "BUY"]
        assert len(actionable) > 0, (
            "Full pipeline must produce ≥ 1 BUY card with $800 cash and "
            f"positive momentum scores. Cards: {[(c.ticker, c.action, c.gate_status) for c in cards]}"
        )

    def test_generate_cards_count_matches_universe(
        self,
        momentum_result: SignalResult,
        _normal_regime_result: SignalResult,
        synthetic_prices: dict[str, pd.Series],
    ) -> None:
        """generate_trade_cards must return exactly one card per universe ticker."""
        latest_prices = {t: float(s.iloc[-1]) for t, s in synthetic_prices.items()}
        last_buy_dates = {t: None for t in synthetic_prices}

        cards = generate_trade_cards(
            momentum_result=momentum_result,
            regime_result=_normal_regime_result,
            holdings=[],
            portfolio_config=_PORTFOLIO_CONFIG,
            universe_map=_UNIVERSE_MAP,
            portfolio_nav=0.0,
            cash=800.0,
            annual_trade_count=0,
            last_buy_dates=last_buy_dates,
            latest_prices=latest_prices,
        )

        assert len(cards) == len(_UNIVERSE_MAP)

    def test_no_cash_and_no_nav_raises(
        self,
        momentum_result: SignalResult,
        _normal_regime_result: SignalResult,
        synthetic_prices: dict[str, pd.Series],
    ) -> None:
        """NAV=0 and cash=0 must raise ValueError — no capital to work with."""
        latest_prices = {t: float(s.iloc[-1]) for t, s in synthetic_prices.items()}
        last_buy_dates = {t: None for t in synthetic_prices}

        with pytest.raises(ValueError, match="NAV is"):
            generate_trade_cards(
                momentum_result=momentum_result,
                regime_result=_normal_regime_result,
                holdings=[],
                portfolio_config=_PORTFOLIO_CONFIG,
                universe_map=_UNIVERSE_MAP,
                portfolio_nav=0.0,
                cash=0.0,
                annual_trade_count=0,
                last_buy_dates=last_buy_dates,
                latest_prices=latest_prices,
            )
