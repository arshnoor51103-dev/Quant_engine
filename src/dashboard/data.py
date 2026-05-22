"""
Data layer for the Quant Engine dashboard.

All @st.cache_data wrappers live here. Components receive data as arguments —
no direct DB or signal calls in components.py.
"""
from __future__ import annotations

import uuid
from datetime import date

import streamlit as st

from ..data.storage import (
    get_all_last_buy_dates,
    get_annual_trade_count,
    latest_price_date,
    list_pending_recommendations,
    save_recommendation,
)
from ..portfolio.model import (
    get_holdings,
    load_portfolio_config,
    load_universe_map,
    nav,
    price_series,
)
from ..portfolio.recommendations import (
    TradeCard,
    compute_combined_scores,
    generate_trade_cards,
)
from ..signals.momentum import MomentumSignal
from ..signals.vol_regime import VolRegimeSignal


@st.cache_data(ttl=300)
def load_signal_data() -> dict:
    """
    Fetch all price series and run both signals. Cached 5 min.

    Returns dict with: momentum_result, regime_result, combined_scores,
    latest_prices, universe_map, portfolio_cfg.
    """
    universe_map = load_universe_map()
    portfolio_cfg = load_portfolio_config()

    mom_sig = MomentumSignal()
    vol_sig = VolRegimeSignal()
    lookback = max(mom_sig.lookback_days, vol_sig.lookback_days)

    price_data: dict = {}
    latest_prices: dict[str, float] = {}
    for ticker in universe_map:
        ps = price_series(ticker, lookback_days=lookback)
        if not ps.empty:
            price_data[ticker] = ps
            latest_prices[ticker] = float(ps.iloc[-1])

    momentum_result = mom_sig.generate(price_data)
    regime_result = vol_sig.generate(price_data)
    combined_scores = compute_combined_scores(momentum_result, regime_result)

    return {
        "momentum_result": momentum_result,
        "regime_result": regime_result,
        "combined_scores": combined_scores,
        "latest_prices": latest_prices,
        "universe_map": universe_map,
        "portfolio_cfg": portfolio_cfg,
    }


@st.cache_data(ttl=300)
def load_portfolio_state() -> dict:
    """
    Load holdings, NAV, annual trade count, last buy dates. Cached 5 min.
    """
    universe_map = load_universe_map()
    holdings = get_holdings()
    portfolio_nav = nav(holdings)
    annual_trades = get_annual_trade_count()
    all_last_buys = get_all_last_buy_dates()
    last_buy_dates: dict[str, date | None] = {t: all_last_buys.get(t) for t in universe_map}
    return {
        "holdings": holdings,
        "nav": portfolio_nav,
        "annual_trades": annual_trades,
        "last_buy_dates": last_buy_dates,
    }


@st.cache_data(ttl=60)
def load_pending_from_db() -> list[dict]:
    """Pending recommendations from DB. Short TTL so Save transitions are immediate."""
    return list_pending_recommendations()


def check_has_price_data() -> bool:
    """Return True if XIC.TO (benchmark) has any price data in DB."""
    return latest_price_date("XIC.TO") is not None


def generate_recommendations(
    signal_data: dict,
    portfolio_state: dict,
    cash: float,
) -> list[TradeCard]:
    """Run the full recommendation pipeline. Not cached — called on button press only."""
    return generate_trade_cards(
        momentum_result=signal_data["momentum_result"],
        regime_result=signal_data["regime_result"],
        holdings=portfolio_state["holdings"],
        portfolio_config=signal_data["portfolio_cfg"],
        universe_map=signal_data["universe_map"],
        portfolio_nav=portfolio_state["nav"],
        cash=cash,
        annual_trade_count=portfolio_state["annual_trades"],
        last_buy_dates=portfolio_state["last_buy_dates"],
        latest_prices=signal_data["latest_prices"],
    )


def save_cards_to_db(
    cards: list[TradeCard],
    portfolio_cfg: dict,
    universe_map: dict,
) -> list[TradeCard]:
    """
    Persist all TradeCards to DB with a shared run_id. Returns cards with rec_id set.
    Invalidates the pending-from-DB cache after write.
    """
    run_id = str(uuid.uuid4())[:8]

    for card in cards:
        rec_id = save_recommendation(
            ticker=card.ticker,
            action=card.action,
            bucket=card.bucket,
            target_weight=0.0,
            combined_signal=card.combined_signal,
            expected_ret=card.expected_return_pct,
            cost_estimate=card.cost_estimate,
            gate_status=card.gate_status.value,
            rationale=card.gate_reason,
            run_id=run_id,
        )
        card.rec_id = rec_id

    load_pending_from_db.clear()
    return cards
