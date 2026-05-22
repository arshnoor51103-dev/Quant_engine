"""
Quant Engine Dashboard — streamlit run dashboard.py
Read-only display layer. All data fetched from src/ modules; no duplicate queries.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.components import (
    GLOBAL_CSS,
    render_cra_counter,
    render_holdings_table,
    render_recommendations_panel,
    render_regime_badge,
    render_signal_scorecard,
)
from src.dashboard.data import (
    check_has_price_data,
    generate_recommendations,
    load_pending_from_db,
    load_portfolio_state,
    load_signal_data,
    save_cards_to_db,
)

st.set_page_config(
    page_title="Quant Engine",
    page_icon="▸",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Cold-start banner (outside fragment — cheap, needs to be fresh) ──────────
if not check_has_price_data():
    st.markdown(
        '<div class="qt-warn-banner">'
        "No price data in DB — run <code>quant ingest</code> to populate."
        "</div>",
        unsafe_allow_html=True,
    )

# ── Session state init ───────────────────────────────────────────────────────
if "pending_cards" not in st.session_state:
    st.session_state.pending_cards = None


# ── Main display fragment — reruns every 5 min, and on any interaction ───────
@st.fragment(run_every="5m")
def main_display() -> None:
    # ── Data load ────────────────────────────────────────────────────────────
    signal_data = None
    portfolio_state = None
    try:
        signal_data = load_signal_data()
    except Exception as e:
        st.error(f"Signal data failed to load: {e}")
    try:
        portfolio_state = load_portfolio_state()
    except Exception as e:
        st.error(f"Portfolio state failed to load: {e}")

    # ── Layout ───────────────────────────────────────────────────────────────
    left, right = st.columns([3, 7], gap="medium")

    # ────────────────────── LEFT RAIL ────────────────────────────────────────
    with left:
        if st.button("↻  Refresh", use_container_width=True, key="refresh_btn"):
            load_signal_data.clear()
            load_portfolio_state.clear()
            load_pending_from_db.clear()

        st.markdown('<div class="qt-section-label" style="margin-top:12px">DEPLOY CAPITAL</div>', unsafe_allow_html=True)
        cash = st.number_input(
            "Cash (CAD $)", min_value=0.0, step=50.0, format="%.2f", key="cash_input", label_visibility="collapsed"
        )
        st.caption("New cash to deploy (CAD)")

        gen_col, save_col = st.columns(2)
        with gen_col:
            if st.button("Generate", type="primary", use_container_width=True, key="gen_btn"):
                if signal_data is None or portfolio_state is None:
                    st.error("Data not loaded — check DB.")
                elif portfolio_state["nav"] + cash == 0.0:
                    st.error("NAV $0 and cash $0 — enter cash to deploy.")
                else:
                    try:
                        st.session_state.pending_cards = generate_recommendations(
                            signal_data, portfolio_state, cash
                        )
                    except Exception as e:
                        st.error(f"Generate failed: {e}")

        with save_col:
            save_disabled = st.session_state.pending_cards is None
            if st.button(
                "Save to DB",
                disabled=save_disabled,
                use_container_width=True,
                key="save_btn",
            ):
                if signal_data and st.session_state.pending_cards:
                    try:
                        save_cards_to_db(
                            st.session_state.pending_cards,
                            signal_data["portfolio_cfg"],
                            signal_data["universe_map"],
                        )
                        st.session_state.pending_cards = None
                    except Exception as e:
                        st.error(f"Save failed: {e}")

        st.divider()

        if signal_data:
            render_regime_badge(signal_data["regime_result"])

        if portfolio_state:
            render_cra_counter(portfolio_state["annual_trades"])

    # ────────────────────── MAIN PANEL ───────────────────────────────────────
    with right:
        db_records: list[dict] = []
        try:
            db_records = load_pending_from_db()
        except Exception as e:
            st.error(f"Pending recs DB read failed: {e}")

        render_recommendations_panel(st.session_state.pending_cards, db_records)

        st.divider()

        score_col, holdings_col = st.columns([6, 4], gap="medium")

        with score_col:
            if signal_data:
                gate_statuses: dict[str, str] | None = None
                if st.session_state.pending_cards:
                    gate_statuses = {
                        c.ticker: c.gate_status.value
                        for c in st.session_state.pending_cards
                    }
                render_signal_scorecard(
                    signal_data["momentum_result"],
                    signal_data["combined_scores"],
                    signal_data["universe_map"],
                    gate_statuses,
                )

        with holdings_col:
            if portfolio_state:
                render_holdings_table(
                    portfolio_state["holdings"],
                    portfolio_state["nav"],
                )


main_display()
