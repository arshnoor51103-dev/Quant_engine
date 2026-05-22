"""
Dashboard render functions. Pure display layer — all data passed as arguments.
Each function wraps its rendering in try/except and shows st.error() on failure.
"""
from __future__ import annotations

import html as _html
from collections import Counter

import streamlit as st

from ..portfolio.model import Holding
from ..portfolio.recommendations import STABLE_TICKERS, TradeCard
from ..signals.base import SignalResult
from .styles import GLOBAL_CSS as GLOBAL_CSS  # re-export

_REGIME_STYLE: dict[str, dict[str, str]] = {
    "low_vol":  {"border": "#00c896", "bg": "rgba(0,200,150,0.06)",  "text": "#00c896", "label": "LOW VOL"},
    "normal":   {"border": "#4d9ef7", "bg": "rgba(77,158,247,0.06)", "text": "#4d9ef7", "label": "NORMAL"},
    "high_vol": {"border": "#e8a020", "bg": "rgba(232,160,32,0.06)", "text": "#e8a020", "label": "HIGH VOL"},
    "crisis":   {"border": "#e8314a", "bg": "rgba(232,49,74,0.06)",  "text": "#e8314a", "label": "CRISIS"},
    "unknown":  {"border": "#4a5568", "bg": "rgba(74,85,104,0.06)",  "text": "#68788f", "label": "UNKNOWN"},
}

_GATE_CHIP: dict[str, str] = {
    "PASS":       "qt-chip-pass",
    "CRA_WARN":   "qt-chip-warn",
    "CRA_LIMIT":  "qt-chip-limit",
    "SKIP":       "qt-chip-skip",
    "SKIP_COST":  "qt-chip-skip",
    "MIN_HOLD":   "qt-chip-skip",
    "OVERWEIGHT": "qt-chip-warn",
}

_BUCKET_CHIP: dict[str, str] = {
    "growth":   "qt-bucket-gr",
    "stable":   "qt-bucket-st",
    "dividend": "qt-bucket-dv",
}

_BUCKET_SHORT: dict[str, str] = {
    "growth": "GR", "stable": "ST", "dividend": "DV",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _e(s: str) -> str:
    """HTML-escape a string."""
    return _html.escape(str(s))


def _chip(label: str, css_class: str) -> str:
    return f'<span class="qt-chip {css_class}">{_e(label)}</span>'


def _field(label: str, value: str, val_class: str = "qt-val") -> str:
    return (
        f'<div class="qt-field">'
        f'<span class="qt-lbl">{_e(label)}</span>'
        f'<span class="{val_class}">{value}</span>'
        f'</div>'
    )


def _fmt_pct(v: float | None) -> str:
    return f"{v*100:+.2f}%" if v is not None else "—"


def _fmt_dollar(v: float | None) -> str:
    return f"${v:+,.2f}" if v is not None else "—"


def _fmt_units(v: float | None) -> str:
    return f"{v:.4f}" if v is not None else "—"


def _fmt_price(v: float | None) -> str:
    return f"${v:.2f}" if v is not None else "—"


# ── Render functions ──────────────────────────────────────────────────────────

def render_regime_badge(regime_result: SignalResult) -> None:
    try:
        meta = regime_result.metadata or {}
        regime = meta.get("regime", "unknown")
        style = _REGIME_STYLE.get(regime, _REGIME_STYLE["unknown"])
        vol = meta.get("current_annualized_vol")
        pct = meta.get("vol_percentile")
        meta_line = ""
        if vol is not None and pct is not None:
            meta_line = f"Vol {vol*100:.1f}%  ·  P{pct*100:.0f}"
        elif meta.get("error"):
            meta_line = meta["error"]

        st.markdown(
            f'<div class="qt-regime" style="background:{style["bg"]};border-left-color:{style["border"]}">'
            f'<div class="qt-section-label">REGIME</div>'
            f'<div class="qt-regime-name" style="color:{style["text"]}">{style["label"]}</div>'
            f'<div class="qt-regime-meta">{_e(meta_line)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"Regime badge: {e}")


def render_cra_counter(annual_trades: int, max_trades: int = 24, warn_at: int = 20) -> None:
    try:
        segs = []
        for i in range(max_trades):
            if i < annual_trades:
                if i >= warn_at:
                    color = "#e8314a"
                elif i >= warn_at - 4:
                    color = "#e8a020"
                else:
                    color = "#00c896"
            else:
                color = "#1c2333"
            segs.append(f'<div class="qt-cra-seg" style="background:{color}"></div>')

        count_color = "#e8314a" if annual_trades >= max_trades else "#e8a020" if annual_trades >= warn_at else "#dce6f0"
        st.markdown(
            f'<div class="qt-card">'
            f'<div class="qt-section-label">CRA TRADES</div>'
            f'<div class="qt-cra-count" style="color:{count_color}">{annual_trades} / {max_trades}</div>'
            f'<div class="qt-cra-bar">{"".join(segs)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"CRA counter: {e}")


def render_signal_scorecard(
    momentum_result: SignalResult,
    combined_scores: dict[str, float],
    universe_map: dict[str, dict],
    gate_statuses: dict[str, str] | None = None,
) -> None:
    try:
        st.markdown('<div class="qt-section-label">SIGNAL SCORECARD</div>', unsafe_allow_html=True)
        tickers = sorted(universe_map.keys(), key=lambda t: -combined_scores.get(t, 0.0))

        rows = []
        for ticker in tickers:
            meta = universe_map[ticker]
            bucket = meta.get("bucket", "")
            bchip = _chip(_BUCKET_SHORT.get(bucket, bucket[:2].upper()), _BUCKET_CHIP.get(bucket, ""))
            mom = momentum_result.scores.get(ticker, 0.0)

            if ticker in STABLE_TICKERS:
                mom_cell = f'<td class="qt-dim">EW</td>'
            else:
                mom_class = "qt-pos" if mom > 0 else "qt-neg" if mom < 0 else "qt-mono"
                mom_cell = f'<td class="{mom_class}">{mom:+.3f}</td>'

            comb = combined_scores.get(ticker, 0.0)
            comb_class = "qt-pos qt-bold" if comb > 0 else "qt-neg qt-bold" if comb < 0 else "qt-mono qt-bold"
            comb_cell = f'<td class="{comb_class}">{comb:+.3f}</td>'

            gate_str = (gate_statuses or {}).get(ticker)
            if gate_str:
                gate_cell = f'<td>{_chip(gate_str, _GATE_CHIP.get(gate_str, "qt-chip-skip"))}</td>'
            else:
                gate_cell = '<td class="qt-dim">—</td>'

            rows.append(
                f"<tr>"
                f'<td class="qt-mono">{_e(ticker)}</td>'
                f"<td>{bchip}</td>"
                f"{mom_cell}"
                f"{comb_cell}"
                f"{gate_cell}"
                f"</tr>"
            )

        table = (
            '<table class="qt-table">'
            "<thead><tr>"
            "<th>TICKER</th><th>BKT</th><th>MOMENTUM</th><th>COMBINED</th><th>GATE</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
        st.markdown(table, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Signal scorecard: {e}")


def _rec_card_html(card: TradeCard) -> str:
    action_map = {"BUY": "qt-rec-buy", "WARN": "qt-rec-warn", "HOLD": "qt-rec-hold"}
    card_class = action_map.get(card.action, "qt-rec-hold")
    chip_class = {"BUY": "qt-chip-buy", "WARN": "qt-chip-warn", "HOLD": "qt-chip-hold"}.get(card.action, "qt-chip-skip")
    id_text = f'<span class="qt-rec-id">#{card.rec_id}</span>' if card.rec_id else ""

    delta_class = "qt-val-buy" if (card.delta_dollars or 0) > 0 else "qt-val-warn"
    footer = ""
    if card.action == "BUY":
        if card.rec_id:
            footer = (
                f'<div class="qt-rec-footer">'
                f'quant execute {card.rec_id} --price &lt;fill&gt; --units &lt;units&gt;'
                f'</div>'
            )
        else:
            footer = '<div class="qt-rec-footer">Save to DB to get a rec ID</div>'

    return (
        f'<div class="qt-rec {card_class}">'
        f'<div class="qt-rec-header">'
        f'{_chip(card.action, chip_class)}'
        f'<span class="qt-ticker">{_e(card.ticker)}</span>'
        f'{id_text}'
        f'</div>'
        f'<div class="qt-rec-grid">'
        f'{_field("Bucket", _chip(_BUCKET_SHORT.get(card.bucket, card.bucket), _BUCKET_CHIP.get(card.bucket, "")))}'
        f'{_field("Gate", _chip(card.gate_status.value, _GATE_CHIP.get(card.gate_status.value, "qt-chip-skip")))}'
        f'{_field("Units", _e(_fmt_units(card.units)))}'
        f'{_field("Signal", _e(f"{card.combined_signal:+.3f}"))}'
        f'{_field("Price", _e(_fmt_price(card.est_price)))}'
        f'{_field("Exp Ret", _e(_fmt_pct(card.expected_return_pct)))}'
        f'{_field("Delta $", _e(_fmt_dollar(card.delta_dollars)), delta_class + " qt-val")}'
        f'{_field("Reason", _e(card.gate_reason or ""), "qt-val-dim qt-val") if card.gate_reason else ""}'
        f'</div>'
        f'{footer}'
        f'</div>'
    )


def render_recommendations_panel(
    pending_cards: list[TradeCard] | None,
    db_records: list[dict],
) -> None:
    try:
        st.markdown('<div class="qt-section-label">RECOMMENDATIONS</div>', unsafe_allow_html=True)

        if pending_cards is not None:
            source_label = "Freshly generated — not saved to DB"
            cards = pending_cards
        elif db_records:
            first = db_records[0]
            run_id = first.get("run_id", "?")
            ts = str(first.get("generated_at", ""))[:16]
            source_label = f"Previous run — {run_id} — {ts}"
            cards = None
        else:
            st.markdown('<div class="qt-empty">No recommendations. Click Generate or run quant recommend --save.</div>', unsafe_allow_html=True)
            return

        st.caption(source_label)

        if cards is not None:
            actionable = [c for c in cards if c.action in ("BUY", "WARN", "HOLD")]
            skipped = [c for c in cards if c.action == "SKIP"]

            html_parts = [_rec_card_html(c) for c in actionable]
            if html_parts:
                st.markdown("".join(html_parts), unsafe_allow_html=True)

            if skipped:
                counts = Counter(c.gate_status.value for c in skipped)
                breakdown = "  ·  ".join(f"{v}× {k}" for k, v in sorted(counts.items()))
                tickers = ", ".join(c.ticker for c in skipped)
                with st.expander(f"{len(skipped)} skipped  —  {breakdown}"):
                    rows = "".join(
                        f"<tr>"
                        f'<td class="qt-mono">{_e(c.ticker)}</td>'
                        f'<td>{_chip(c.gate_status.value, _GATE_CHIP.get(c.gate_status.value, "qt-chip-skip"))}</td>'
                        f'<td class="qt-dim">{_e(c.gate_reason or "")}</td>'
                        f"</tr>"
                        for c in skipped
                    )
                    st.markdown(
                        f'<table class="qt-table"><thead><tr><th>TICKER</th><th>GATE</th><th>REASON</th></tr></thead>'
                        f'<tbody>{rows}</tbody></table>',
                        unsafe_allow_html=True,
                    )

            if not actionable and not skipped:
                st.markdown('<div class="qt-empty">No cards generated.</div>', unsafe_allow_html=True)

        else:
            # Render from DB records
            buy_recs = [r for r in db_records if r.get("action") == "BUY"]
            other_recs = [r for r in db_records if r.get("action") != "BUY"]

            html_parts = []
            for r in buy_recs:
                gate = r.get("gate_status", "PASS")
                exp_ret = r.get("expected_ret")
                comb = r.get("combined_signal", 0.0)
                html_parts.append(
                    f'<div class="qt-rec qt-rec-buy">'
                    f'<div class="qt-rec-header">'
                    f'{_chip("BUY", "qt-chip-buy")}'
                    f'<span class="qt-ticker">{_e(r["ticker"])}</span>'
                    f'<span class="qt-rec-id">#{r["id"]}</span>'
                    f'</div>'
                    f'<div class="qt-rec-grid">'
                    f'{_field("Bucket", _chip(_BUCKET_SHORT.get(r.get("bucket",""),"?"), _BUCKET_CHIP.get(r.get("bucket",""),""))  )}'
                    f'{_field("Gate", _chip(gate, _GATE_CHIP.get(gate,"qt-chip-skip")))}'
                    f'{_field("Signal", _e(f"{comb:+.3f}"))}'
                    f'{_field("Exp Ret", _e(_fmt_pct(exp_ret)))}'
                    f'</div>'
                    f'<div class="qt-rec-footer">quant execute {r["id"]} --price &lt;fill&gt; --units &lt;units&gt;</div>'
                    f'</div>'
                )
            if html_parts:
                st.markdown("".join(html_parts), unsafe_allow_html=True)

            if other_recs:
                counts = Counter(r.get("action", "?") for r in other_recs)
                breakdown = "  ·  ".join(f"{v}× {k}" for k, v in sorted(counts.items()))
                with st.expander(f"{len(other_recs)} non-BUY  —  {breakdown}"):
                    rows = "".join(
                        f"<tr>"
                        f'<td class="qt-mono">{_e(r["ticker"])}</td>'
                        f'<td>{_chip(r.get("action","?"), "qt-chip-skip")}</td>'
                        f'<td>{_chip(r.get("gate_status",""), _GATE_CHIP.get(r.get("gate_status",""),"qt-chip-skip"))}</td>'
                        f'<td class="qt-dim">{_e(r.get("rationale") or "")}</td>'
                        f"</tr>"
                        for r in other_recs
                    )
                    st.markdown(
                        f'<table class="qt-table"><thead><tr><th>TICKER</th><th>ACTION</th><th>GATE</th><th>REASON</th></tr></thead>'
                        f'<tbody>{rows}</tbody></table>',
                        unsafe_allow_html=True,
                    )

    except Exception as e:
        st.error(f"Recommendations panel: {e}")


def render_holdings_table(holdings: list[Holding], portfolio_nav: float) -> None:
    try:
        st.markdown('<div class="qt-section-label">HOLDINGS</div>', unsafe_allow_html=True)
        if not holdings:
            st.markdown('<div class="qt-empty">No holdings yet.</div>', unsafe_allow_html=True)
            return

        rows = []
        for h in sorted(holdings, key=lambda x: -x.market_value):
            pnl = h.unrealized_pnl
            pnl_class = "qt-pos" if pnl > 0 else "qt-neg" if pnl < 0 else "qt-mono"
            weight = (h.market_value / portfolio_nav * 100) if portfolio_nav > 0 else 0.0
            rows.append(
                f"<tr>"
                f'<td class="qt-mono">{_e(h.ticker)}</td>'
                f'<td class="qt-mono">{h.units:.4f}</td>'
                f'<td class="qt-mono">${h.avg_cost:.2f}</td>'
                f'<td class="qt-mono">{_e(_fmt_price(h.last_price))}</td>'
                f'<td class="{pnl_class}">{pnl:+.2f}</td>'
                f'<td class="qt-mono">{weight:.1f}%</td>'
                f"</tr>"
            )

        st.markdown(
            f'<table class="qt-table">'
            f"<thead><tr><th>TICKER</th><th>UNITS</th><th>AVG COST</th><th>PRICE</th><th>PnL $</th><th>WT%</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"Holdings table: {e}")
