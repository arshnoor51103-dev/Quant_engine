"""
Phase 3 P0 CLI additions.

Commands: `quant recommend`, `quant execute`, `quant pending`
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections import Counter
from datetime import date

import pandas as pd
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..data.ingest import load_universe
from ..data.storage import (
    get_all_last_buy_dates,
    get_annual_trade_count,
    get_connection,
    get_last_alert,
    get_recommendation_by_id,
    list_pending_recommendations,
    log,
    log_alert,
    mark_recommendation_executed,
    mark_recommendation_skipped,
    persist_signals,
    record_trade,
    save_recommendation,
)
from ..portfolio.metrics import max_drawdown
from ..portfolio.model import (
    get_holdings,
    load_portfolio_config,
    load_universe_map,
    nav,
    price_series,
    price_series_batch,
)
from ..portfolio.optimizer import BucketOptimizer
from ..portfolio.recommendations import (
    GateStatus,
    TradeCard,
    apply_drawdown_halt,
    compute_target_weights,
    compute_combined_scores,
    generate_trade_cards,
)
from ..alerts.ntfy import send_alert
from ..signals.momentum import MomentumSignal
from ..signals.vol_regime import VolRegimeSignal

console = Console()

_GATE_COLOUR = {
    GateStatus.PASS:            "green",
    GateStatus.CRA_WARN:        "yellow",
    GateStatus.CRA_LIMIT:       "yellow",
    GateStatus.SKIP_SIGNAL:     "dim",
    GateStatus.SKIP_COST:       "dim",
    GateStatus.MIN_HOLD:        "dim",
    GateStatus.OVERWEIGHT:      "red",
    GateStatus.BELOW_THRESHOLD: "dim",
}

_ACTION_COLOUR = {
    "BUY":  "green",
    "SELL": "red",
    "WARN": "yellow",
    "HOLD": "dim",
    "SKIP": "dim",
}


def _fmt_pct(v: float | None) -> str:
    return f"{v*100:+.2f}%" if v is not None else "—"


def _fmt_dollar(v: float | None) -> str:
    return f"${v:+,.2f}" if v is not None else "—"


def _fmt_units(v: float | None) -> str:
    return f"{v:.4f}" if v is not None else "—"


def _fmt_price(v: float | None) -> str:
    return f"${v:.2f}" if v is not None else "—"


def _make_card_panel(card: TradeCard) -> Panel:
    """Build a Rich Panel for a single non-SKIP card."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", min_width=9)
    grid.add_column(min_width=16)
    grid.add_column(style="dim", min_width=9)
    grid.add_column(min_width=16)

    gate_style = _GATE_COLOUR.get(card.gate_status, "")
    grid.add_row(
        "Bucket",  card.bucket,
        "Gate",    Text(card.gate_status.value, style=gate_style),
    )
    grid.add_row(
        "Units",   _fmt_units(card.units),
        "Signal",  f"{card.combined_signal:+.3f}",
    )
    grid.add_row(
        "Price",   _fmt_price(card.est_price),
        "Exp Ret", _fmt_pct(card.expected_return_pct),
    )
    if card.sell_reason:
        label = "Full exit" if card.sell_reason == "SIGNAL" else "Drift correction"
        grid.add_row("Sell", Text(f"{card.sell_reason} — {label}", style="bold red"), "", "")
    if card.delta_dollars is not None:
        grid.add_row("Delta $", _fmt_dollar(card.delta_dollars), "", "")
    if card.gate_reason:
        grid.add_row("Reason", Text(card.gate_reason, style="dim"), "", "")
    if card.action in ("BUY", "SELL"):
        if card.rec_id is not None:
            hint = f"quant execute {card.rec_id} --price <fill> --units <units>"
        else:
            hint = "Run with --save to get a rec ID"
        grid.add_row("", Text(hint, style="dim italic"), "", "")

    border = {"BUY": "green", "SELL": "red", "WARN": "yellow", "HOLD": "dim"}.get(card.action, "dim")
    action_colour = _ACTION_COLOUR.get(card.action, "")
    title = Text()
    title.append(card.action, style=f"bold {action_colour}")
    title.append(f"  {card.ticker}", style="bold")
    if card.rec_id:
        title.append(f"  #{card.rec_id}", style="dim")

    return Panel(grid, title=title, border_style=border)


def _print_cards(
    cards: list[TradeCard],
    portfolio_nav: float,
    cash: float,
    annual_trade_count: int,
    regime_name: str,
    saved: bool,
    max_trades: int = 24,
    n_signal_rows: int = 0,
    halted: bool = False,
    current_dd: float = 0.0,
    ceiling: float = 0.20,
) -> None:
    total_capital = portfolio_nav + cash

    if halted:
        console.print(Panel(
            f"[bold red]DRAWDOWN CEILING BREACHED[/bold red] — current {current_dd:.1%} "
            f">= {ceiling:.0%}. New BUY recommendations are HALTED (soft). "
            f"SELL / rebalance still active.",
            border_style="red", title="[bold red]RISK HALT[/bold red]",
        ))

    header_lines = [
        f"NAV: ${portfolio_nav:,.2f}  |  Deploying: ${cash:,.2f}  |  "
        f"Total capital: ${total_capital:,.2f}",
        f"Regime: {regime_name.upper()}  |  "
        f"CRA trades used: {annual_trade_count}/{max_trades}  |  "
        f"Date: {date.today()}",
    ]
    if saved:
        header_lines.append(
            f"[dim]Signals persisted ({n_signal_rows} rows) | "
            "Cards saved — use rec ID with `quant execute`[/dim]"
        )
    console.print(Panel("\n".join(header_lines), title="[bold]Quant Recommend[/bold]"))

    actionable = [c for c in cards if c.action in ("BUY", "SELL", "WARN", "HOLD")]
    skipped    = [c for c in cards if c.action == "SKIP"]

    if not actionable and not skipped:
        console.print("[yellow]No recommendations generated.[/yellow]")
        return

    for card in actionable:
        console.print(_make_card_panel(card))

    if skipped:
        counts = Counter(c.gate_status.value for c in skipped)
        breakdown = "  |  ".join(f"{v}× {k}" for k, v in sorted(counts.items()))
        tickers = " ".join(c.ticker for c in skipped)
        console.print(
            f"[dim]  Skipped ({len(skipped)}):  {breakdown}  [{tickers}][/dim]"
        )

    buy_cards  = [c for c in cards if c.action == "BUY"]
    sell_cards = [c for c in cards if c.action == "SELL"]

    summary_parts = []
    if sell_cards:
        total_proceeds = sum(abs(c.delta_dollars or 0.0) for c in sell_cards)
        summary_parts.append(
            f"[red]Recommended sells: {len(sell_cards)} "
            f"| Total proceeds: ${total_proceeds:,.2f} CAD[/red]"
        )
    if buy_cards:
        total_deploy = sum(c.delta_dollars or 0.0 for c in buy_cards)
        summary_parts.append(
            f"[green]Recommended buys: {len(buy_cards)} "
            f"| Total deployment: ${total_deploy:,.2f} CAD[/green]"
        )

    if summary_parts:
        console.print("\n" + "  |  ".join(summary_parts))
        if not saved:
            console.print("[dim]Run with --save to persist these cards and get rec IDs.[/dim]")
    else:
        console.print("\n[yellow]No BUY or SELL recommendations generated.[/yellow]")


def _print_weight_comparison(
    equal_weights: dict[str, float],
    opt_weights: dict[str, float],
    universe_map: dict[str, dict],
    total_capital: float,
) -> None:
    """Print a side-by-side table of equal-weight vs optimized portfolio weights."""
    table = Table(title="Weight Comparison: Equal-Weight vs Optimized")
    table.add_column("Ticker")
    table.add_column("Bucket")
    table.add_column("Equal-Weight", justify="right")
    table.add_column("Optimized",   justify="right")
    table.add_column("Delta",        justify="right")
    table.add_column("$ Delta",      justify="right")

    for ticker in sorted(universe_map.keys()):
        ew = equal_weights.get(ticker, 0.0)
        ow = opt_weights.get(ticker, 0.0)
        diff = ow - ew
        dollar_diff = diff * total_capital
        bucket = universe_map[ticker].get("bucket", "—")
        diff_style = "green" if diff > 0.001 else ("red" if diff < -0.001 else "dim")
        table.add_row(
            ticker,
            bucket,
            f"{ew*100:.1f}%",
            f"{ow*100:.1f}%",
            Text(f"{diff*100:+.1f}%", style=diff_style),
            Text(f"${dollar_diff:+,.0f}", style=diff_style),
        )

    console.print(table)


def _portfolio_nav_series(
    holdings: list,
    price_data: dict[str, pd.Series],
) -> pd.Series:
    """
    Weighted NAV series summed across all currently held tickers.

    Uses full price history (no lookback truncation). Aligns on the
    intersection of dates where all held tickers have price data.
    Returns an empty Series if no holdings match any price data.
    """
    frames = []
    for h in holdings:
        if h.ticker in price_data and not price_data[h.ticker].empty:
            frames.append(price_data[h.ticker] * h.units)
    if not frames:
        return pd.Series(dtype=float)
    combined = pd.concat(frames, axis=1)
    return combined.dropna().sum(axis=1)


def _run_alert_triggers(
    cards: list[TradeCard],
    regime_name: str,
    portfolio_cfg: dict,
    holdings: list,
    price_data: dict[str, pd.Series],
) -> None:
    """
    Run the alert triggers as a fire-and-forget side effect.

    Alerting must never abort the recommendation pipeline (ntfy.py contract:
    "The recommendation pipeline must not fail because an alert failed.").
    Any failure — HTTP, header encoding, or a missing/locked DB table such as
    alerts_log — is logged at WARNING and surfaced to the console, then
    dropped. This function never raises.
    """
    try:
        _evaluate_alert_triggers(
            cards, regime_name, portfolio_cfg, holdings, price_data
        )
    except Exception as exc:  # noqa: BLE001 — alerts are non-critical by contract
        logging.warning("alert triggers failed — %s", exc, exc_info=True)
        console.print(f"[yellow]Alerts skipped (non-fatal): {exc}[/yellow]")


def _evaluate_alert_triggers(
    cards: list[TradeCard],
    regime_name: str,
    portfolio_cfg: dict,
    holdings: list,
    price_data: dict[str, pd.Series],
) -> None:
    """
    Evaluate the three alert triggers and POST to ntfy.sh where warranted.

    Called via _run_alert_triggers, which owns the never-raise guarantee.
    May raise on DB errors (e.g. a missing alerts_log table); the wrapper
    logs and drops them so the recommendation pipeline is unaffected.
    """
    alerts_cfg = portfolio_cfg.get("alerts", {})
    if not alerts_cfg.get("enabled"):
        return

    topic: str = alerts_cfg["ntfy_topic"]
    triggers: set[str] = set(alerts_cfg.get("triggers") or [])

    # NEW_RECOMMENDATION — fire when ≥1 card passes all gates
    if "NEW_RECOMMENDATION" in triggers:
        passing = [
            c for c in cards
            if c.action in ("BUY", "SELL") and c.gate_status == GateStatus.PASS
        ]
        if passing:
            body = "\n".join(
                f"{c.action} {c.ticker}  signal={c.combined_signal:+.3f}"
                f"  exp={c.expected_return_pct:.1%}"
                for c in passing
            )
            send_alert(topic, "New Recommendation", body,
                       tags=["chart_with_upwards_trend"])
            log_alert("NEW_RECOMMENDATION", json.dumps(
                [{"ticker": c.ticker, "action": c.action,
                  "signal": round(c.combined_signal, 4)} for c in passing]
            ))

    # REGIME_CHANGE — fire when vol regime shifts from last persisted value
    if "REGIME_CHANGE" in triggers:
        last = get_last_alert("REGIME_CHANGE")
        try:
            last_regime = (
                json.loads(last["payload"]).get("regime")
                if (last and last["payload"]) else None
            )
        except (json.JSONDecodeError, TypeError):
            last_regime = None
        if last_regime != regime_name:
            send_alert(
                topic, "Regime Change",
                f"{(last_regime or 'unknown').upper()} → {regime_name.upper()}",
                priority=4, tags=["warning"],
            )
            log_alert("REGIME_CHANGE",
                      json.dumps({"regime": regime_name, "previous": last_regime}))

    # DRAWDOWN — transition detector.
    # Fires once on first crossing above drawdown_alert threshold.
    # Logs a RECOVERED row (no POST) when portfolio returns below threshold,
    # enabling the next crossing to fire again.
    if "DRAWDOWN_WARNING" in triggers:
        threshold: float = portfolio_cfg["risk"]["drawdown_alert"]
        nav_series = _portfolio_nav_series(holdings, price_data)
        current_dd = abs(max_drawdown(nav_series)) if not nav_series.empty else 0.0

        ceiling: float = portfolio_cfg["risk"].get("max_drawdown", 0.20)
        last = get_last_alert("DRAWDOWN")
        try:
            last_payload = json.loads(last["payload"]) if (last and last["payload"]) else {}
        except (json.JSONDecodeError, TypeError):
            last_payload = {}
        last_status = last_payload.get("status", "RECOVERED")  # absent = never fired

        if current_dd > threshold and last_status == "RECOVERED":
            ceiling_note = (
                f"  CEILING {ceiling:.0%} BREACHED — new BUYs halted."
                if current_dd >= ceiling else ""
            )
            send_alert(
                topic, "Drawdown Warning",
                f"Portfolio drawdown {current_dd:.1%} — alert threshold {threshold:.0%}.{ceiling_note}",
                priority=5, tags=["rotating_light"],
            )
            log_alert("DRAWDOWN",
                      json.dumps({"status": "WARNING", "drawdown": round(current_dd, 4)}))
        elif current_dd <= threshold and last_status == "WARNING":
            log_alert("DRAWDOWN",
                      json.dumps({"status": "RECOVERED", "drawdown": round(current_dd, 4)}))


def recommend_command(
    cash: float = typer.Option(0.0, "--cash", help="New cash to deploy in CAD"),
    save: bool = typer.Option(False, "--save", help="Persist recommendations to DB"),
    optimize: bool = typer.Option(
        False, "--optimize", help="Use Markowitz within-bucket optimizer instead of equal-weight"
    ),
    notify: bool = typer.Option(
        False, "--notify", help="Send ntfy.sh push alerts for actionable events"
    ),
) -> None:
    """
    Generate trade recommendations for the current portfolio.

    With no holdings (NAV=0), --cash is required to specify deployable capital.
    With existing holdings, --cash is optional and represents new deployment
    on top of the existing portfolio.

    Add --optimize to use the Ledoit-Wolf Markowitz optimizer within each bucket
    instead of the default signal-proportional equal-weight allocation.
    """
    holdings = get_holdings()
    portfolio_nav = nav(holdings)

    if portfolio_nav == 0.0 and cash == 0.0:
        console.print(
            "[red]Error: NAV is $0.00 and --cash was not provided.[/red]\n"
            "[yellow]Specify how much capital to deploy, e.g.:[/yellow]\n"
            "  quant recommend --cash 800\n"
            "The --cash flag tells the engine how much to size positions against."
        )
        raise typer.Exit(1)

    portfolio_cfg = load_portfolio_config()
    universe_map = load_universe_map()
    alloc_cfg = portfolio_cfg["allocation"]

    # Load signal history — enough for the slowest signal
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
    regime_name = (regime_result.metadata or {}).get("regime", "unknown")

    annual_trades = get_annual_trade_count()
    all_last_buys = get_all_last_buy_dates()
    last_buy_dates = {t: all_last_buys.get(t) for t in universe_map}

    # Compute equal-weight signal-proportional weights (always, for comparison)
    combined_scores = compute_combined_scores(momentum_result, regime_result)
    equal_weights = compute_target_weights(combined_scores, alloc_cfg, universe_map)

    optimized_weights = None
    if optimize:
        opt = BucketOptimizer(config=portfolio_cfg)
        # Load full price history for covariance estimation (252 trading days)
        all_tickers = list(universe_map.keys())
        price_history = price_series_batch(all_tickers, lookback_days=252 + 30)
        optimized_weights = opt.optimize(
            signal_scores=momentum_result.scores,
            price_history=price_history,
            universe_map=universe_map,
            bucket_config=alloc_cfg,
        )
        total_capital = portfolio_nav + cash
        if total_capital > 0:
            _print_weight_comparison(equal_weights, optimized_weights, universe_map, total_capital)
        console.print()

    cards = generate_trade_cards(
        momentum_result=momentum_result,
        regime_result=regime_result,
        holdings=holdings,
        portfolio_config=portfolio_cfg,
        universe_map=universe_map,
        portfolio_nav=portfolio_nav,
        cash=cash,
        annual_trade_count=annual_trades,
        last_buy_dates=last_buy_dates,
        latest_prices=latest_prices,
        optimized_weights=optimized_weights,
    )

    # F2: drawdown soft-halt — suppress new BUYs at/above the ceiling
    risk_cfg = portfolio_cfg.get("risk", {})
    ceiling = float(risk_cfg.get("max_drawdown", 0.20))
    halt_enabled = bool(risk_cfg.get("drawdown_halt_enabled", True))
    nav_series = _portfolio_nav_series(holdings, price_data)
    current_dd = abs(max_drawdown(nav_series)) if not nav_series.empty else 0.0
    cards, halted = apply_drawdown_halt(cards, current_dd, ceiling, halt_enabled)

    n_signal_rows = 0
    if save:
        run_id = str(uuid.uuid4())[:8]
        # Persist signal scores first — audit trail precedes trade cards
        signal_results = [momentum_result, regime_result]
        n_signal_rows = persist_signals(signal_results, run_id=run_id)
        for card in cards:
            rec_id = save_recommendation(
                ticker=card.ticker,
                action=card.action,
                bucket=card.bucket,
                target_weight=(optimized_weights or equal_weights).get(card.ticker, 0.0),
                combined_signal=card.combined_signal,
                expected_ret=card.expected_return_pct,
                cost_estimate=card.cost_estimate,
                gate_status=card.gate_status.value,
                rationale=card.gate_reason,
                run_id=run_id,
                sell_reason=card.sell_reason,
            )
            card.rec_id = rec_id

    max_trades = int(portfolio_cfg["trading"].get("max_trades_per_year", 24))
    _print_cards(
        cards=cards,
        portfolio_nav=portfolio_nav,
        cash=cash,
        annual_trade_count=annual_trades,
        regime_name=regime_name,
        saved=save,
        max_trades=max_trades,
        n_signal_rows=n_signal_rows,
        halted=halted,
        current_dd=current_dd,
        ceiling=ceiling,
    )

    if notify:
        _run_alert_triggers(cards, regime_name, portfolio_cfg, holdings, price_data)


def execute_command(
    rec_id: int = typer.Argument(..., help="Recommendation ID (from quant recommend --save)"),
    price: float = typer.Option(..., "--price", help="Actual fill price per unit in CAD"),
    units: float = typer.Option(..., "--units", help="Actual units filled"),
    trade_date_str: str = typer.Option(None, "--date", help="Execution date YYYY-MM-DD (default today)"),
    force: bool = typer.Option(False, "--force", help="Override the CRA annual trade cap (requires --justification)"),
    justification: str = typer.Option(None, "--justification", help="Logged reason for a --force CRA override"),
) -> None:
    """
    Mark a pending recommendation as executed and record the trade.

    Updates the recommendation status with actual fill details and creates
    a linked trade record atomically. Recommendation and trade are separate
    records — the recommendation captures what the engine suggested,
    the trade captures what actually happened at the brokerage.
    """
    rec = get_recommendation_by_id(rec_id)
    if rec is None:
        console.print(f"[red]No recommendation with ID {rec_id}.[/red]")
        raise typer.Exit(1)

    if rec["status"] != "pending":
        console.print(
            f"[yellow]Recommendation #{rec_id} is already '{rec['status']}' — "
            "cannot re-execute.[/yellow]"
        )
        raise typer.Exit(1)

    if rec["action"] not in ("BUY", "SELL"):
        console.print(
            f"[red]Recommendation #{rec_id} has action '{rec['action']}' — "
            "only BUY and SELL recommendations can be executed via this command.[/red]"
        )
        raise typer.Exit(1)

    exec_date = (
        date.fromisoformat(trade_date_str) if trade_date_str else date.today()
    )

    universe_map = load_universe_map()
    if rec["ticker"] not in universe_map:
        console.print(f"[red]{rec['ticker']} not in universe.[/red]")
        raise typer.Exit(1)

    # F1: CRA annual trade cap — hard block at the limit (logged --force override)
    trading_cfg = load_portfolio_config()["trading"]
    max_trades = int(trading_cfg.get("max_trades_per_year", 24))
    annual = get_annual_trade_count()
    if annual >= max_trades:
        if not force:
            console.print(
                f"[red]CRA cap reached: {annual}/{max_trades} trades this calendar year. "
                "Execution blocked to stay clear of day-trade reclassification.[/red]\n"
                "[yellow]To override: re-run with --force --justification \"reason\" (logged).[/yellow]"
            )
            raise typer.Exit(1)
        if not justification:
            console.print("[red]--force requires --justification \"reason\".[/red]")
            raise typer.Exit(1)
        log("execute", "WARNING",
            f"CRA cap override: executing trade #{annual + 1} (cap {max_trades}). "
            f"Rec #{rec_id} {rec['ticker']}. Justification: {justification}")
        console.print(
            f"[yellow]CRA override logged — proceeding with trade #{annual + 1}.[/yellow]"
        )

    # F1/F2: record the trade and mark the recommendation executed in ONE
    # transaction so they cannot diverge (a recorded trade with a still-pending
    # rec would invite a double-execution). DB/validation errors surface as a
    # clean message + Exit(1), never a raw traceback on a real-money command.
    try:
        with get_connection() as conn:
            trade_id = record_trade(
                ticker=rec["ticker"],
                side=rec["action"],
                units=units,
                price=price,
                trade_date=exec_date,
                fees=0.0,
                rationale=(
                    f"Recommendation #{rec_id}"
                    + (f" [CRA override: {justification}]" if (force and justification) else "")
                ),
                conn=conn,
            )
            mark_recommendation_executed(
                rec_id, fill_price=price, fill_units=units, conn=conn
            )
    except (ValueError, sqlite3.Error) as exc:
        console.print(f"[red]Trade rejected: {exc}[/red]")
        raise typer.Exit(1)

    gross = units * price
    is_sell = rec["action"] == "SELL"
    action_colour = "red" if is_sell else "green"
    action_label = rec["action"]
    console.print(Panel(
        f"[{action_colour}]{action_label}[/{action_colour}]  "
        f"{rec['ticker']}  {units:.4f} units @ ${price:.2f}  "
        f"=  ${gross:,.2f} CAD\n"
        f"Date: {exec_date}   Trade ID: #{trade_id}   Rec ID: #{rec_id}",
        title="Trade Executed",
        border_style=action_colour,
    ))


def pending_command() -> None:
    """List all pending (unsaved or unexecuted) recommendations."""
    rows = list_pending_recommendations()
    if not rows:
        console.print("[yellow]No pending recommendations.[/yellow]")
        return

    table = Table(title=f"Pending Recommendations ({len(rows)})")
    table.add_column("ID",         justify="right")
    table.add_column("Ticker")
    table.add_column("Bucket")
    table.add_column("Action")
    table.add_column("Sell",       style="dim")
    table.add_column("Signal",     justify="right")
    table.add_column("Exp Ret",    justify="right")
    table.add_column("Gate")
    table.add_column("Run ID",     style="dim")
    table.add_column("Generated At", style="dim")

    for r in rows:
        exp = f"{r['expected_ret']*100:+.2f}%" if r.get("expected_ret") is not None else "—"
        sell_reason = r.get("sell_reason") or "—"
        action = r["action"]
        action_style = "red" if action == "SELL" else ("green" if action == "BUY" else "")
        table.add_row(
            str(r["id"]),
            r["ticker"],
            r.get("bucket") or "—",
            Text(action, style=action_style),
            sell_reason,
            f"{r['combined_signal']:+.3f}" if r.get("combined_signal") is not None else "—",
            exp,
            r.get("gate_status") or "—",
            r.get("run_id") or "—",
            str(r["generated_at"])[:16],
        )

    console.print(table)
    console.print(
        "\n[dim]To execute: quant execute <ID> --price <fill> --units <units>[/dim]"
    )
    console.print(
        "[dim]To skip:    quant skip <ID>[/dim]"
    )


def skip_command(
    rec_id: int = typer.Argument(..., help="Recommendation ID to mark as skipped"),
) -> None:
    """Mark a pending recommendation as skipped (not executed)."""
    rec = get_recommendation_by_id(rec_id)
    if rec is None:
        console.print(f"[red]No recommendation with ID {rec_id}.[/red]")
        raise typer.Exit(1)

    if rec["status"] != "pending":
        console.print(
            f"[yellow]Recommendation #{rec_id} is already '{rec['status']}'.[/yellow]"
        )
        raise typer.Exit(1)

    mark_recommendation_skipped(rec_id)
    console.print(f"[dim]Recommendation #{rec_id} ({rec['ticker']}) marked as skipped.[/dim]")
