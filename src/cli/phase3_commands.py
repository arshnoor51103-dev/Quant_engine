"""
Phase 3 P0 CLI additions.

Commands: `quant recommend`, `quant execute`, `quant pending`
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..data.ingest import load_universe
from ..data.storage import (
    get_all_last_buy_dates,
    get_annual_trade_count,
    get_recommendation_by_id,
    list_pending_recommendations,
    mark_recommendation_executed,
    mark_recommendation_skipped,
    record_trade,
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
    GateStatus,
    TradeCard,
    generate_trade_cards,
)
from ..signals.momentum import MomentumSignal
from ..signals.vol_regime import VolRegimeSignal

console = Console()

_GATE_COLOUR = {
    GateStatus.PASS:         "green",
    GateStatus.CRA_WARN:     "yellow",
    GateStatus.CRA_LIMIT:    "yellow",
    GateStatus.SKIP_SIGNAL:  "dim",
    GateStatus.SKIP_COST:    "dim",
    GateStatus.MIN_HOLD:     "dim",
    GateStatus.OVERWEIGHT:   "red",
}

_ACTION_COLOUR = {
    "BUY":  "green",
    "WARN": "red",
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
    if card.delta_dollars is not None:
        grid.add_row("Delta $", _fmt_dollar(card.delta_dollars), "", "")
    if card.gate_reason:
        grid.add_row("Reason", Text(card.gate_reason, style="dim"), "", "")
    if card.action == "BUY":
        if card.rec_id is not None:
            hint = f"quant execute {card.rec_id} --price <fill> --units <units>"
        else:
            hint = "Run with --save to get a rec ID"
        grid.add_row("", Text(hint, style="dim italic"), "", "")

    border = {"BUY": "green", "WARN": "yellow", "HOLD": "dim"}.get(card.action, "dim")
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
) -> None:
    total_capital = portfolio_nav + cash

    header_lines = [
        f"NAV: ${portfolio_nav:,.2f}  |  Deploying: ${cash:,.2f}  |  "
        f"Total capital: ${total_capital:,.2f}",
        f"Regime: {regime_name.upper()}  |  "
        f"CRA trades used: {annual_trade_count}/{max_trades}  |  "
        f"Date: {date.today()}",
    ]
    if saved:
        header_lines.append("[dim]Saved to DB — use rec ID with `quant execute`[/dim]")
    console.print(Panel("\n".join(header_lines), title="[bold]Quant Recommend[/bold]"))

    actionable = [c for c in cards if c.action in ("BUY", "WARN", "HOLD")]
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

    buy_cards = [c for c in cards if c.action == "BUY"]
    if buy_cards:
        total_deploy = sum(c.delta_dollars or 0.0 for c in buy_cards)
        console.print(
            f"\n[green]Recommended buys: {len(buy_cards)} "
            f"| Total deployment: ${total_deploy:,.2f} CAD[/green]"
        )
        if not saved:
            console.print("[dim]Run with --save to persist these cards and get rec IDs.[/dim]")
    else:
        console.print("\n[yellow]No BUY recommendations generated.[/yellow]")


def recommend_command(
    cash: float = typer.Option(0.0, "--cash", help="New cash to deploy in CAD"),
    save: bool = typer.Option(False, "--save", help="Persist recommendations to DB"),
) -> None:
    """
    Generate trade recommendations for the current portfolio.

    With no holdings (NAV=0), --cash is required to specify deployable capital.
    With existing holdings, --cash is optional and represents new deployment
    on top of the existing portfolio.
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
    )

    if save:
        run_id = str(uuid.uuid4())[:8]
        for card in cards:
            rec_id = save_recommendation(
                ticker=card.ticker,
                action=card.action,
                bucket=card.bucket,
                target_weight=0.0,  # resolved from delta/total_capital by caller if needed
                combined_signal=card.combined_signal,
                expected_ret=card.expected_return_pct,
                cost_estimate=card.cost_estimate,
                gate_status=card.gate_status.value,
                rationale=card.gate_reason,
                run_id=run_id,
            )
            card.rec_id = rec_id

    max_trades = int(portfolio_cfg["trading"].get("max_trades_per_year", 24))
    _print_cards(cards, portfolio_nav, cash, annual_trades, regime_name, saved=save, max_trades=max_trades)


def execute_command(
    rec_id: int = typer.Argument(..., help="Recommendation ID (from quant recommend --save)"),
    price: float = typer.Option(..., "--price", help="Actual fill price per unit in CAD"),
    units: float = typer.Option(..., "--units", help="Actual units filled"),
    trade_date_str: str = typer.Option(None, "--date", help="Execution date YYYY-MM-DD (default today)"),
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

    if rec["action"] not in ("BUY",):
        console.print(
            f"[red]Recommendation #{rec_id} has action '{rec['action']}' — "
            "only BUY recommendations can be executed via this command.[/red]"
        )
        raise typer.Exit(1)

    exec_date = (
        date.fromisoformat(trade_date_str) if trade_date_str else date.today()
    )

    universe_map = load_universe_map()
    if rec["ticker"] not in universe_map:
        console.print(f"[red]{rec['ticker']} not in universe.[/red]")
        raise typer.Exit(1)

    trade_id = record_trade(
        ticker=rec["ticker"],
        side="BUY",
        units=units,
        price=price,
        trade_date=exec_date,
        fees=0.0,
        rationale=f"Recommendation #{rec_id}",
    )
    mark_recommendation_executed(rec_id, fill_price=price, fill_units=units)

    gross = units * price
    console.print(Panel(
        f"[green]BUY[/green]  {rec['ticker']}  {units:.4f} units @ ${price:.2f}  "
        f"=  ${gross:,.2f} CAD\n"
        f"Date: {exec_date}   Trade ID: #{trade_id}   Rec ID: #{rec_id}",
        title="Trade Executed",
        border_style="green",
    ))


def pending_command() -> None:
    """List all pending (unsaved or unexecuted) recommendations."""
    rows = list_pending_recommendations()
    if not rows:
        console.print("[yellow]No pending recommendations.[/yellow]")
        return

    table = Table(title=f"Pending Recommendations ({len(rows)})")
    table.add_column("ID",       justify="right")
    table.add_column("Ticker")
    table.add_column("Bucket")
    table.add_column("Action")
    table.add_column("Signal",   justify="right")
    table.add_column("Exp Ret",  justify="right")
    table.add_column("Gate")
    table.add_column("Run ID",   style="dim")
    table.add_column("Generated At", style="dim")

    for r in rows:
        exp = f"{r['expected_ret']*100:+.2f}%" if r.get("expected_ret") else "—"
        table.add_row(
            str(r["id"]),
            r["ticker"],
            r.get("bucket") or "—",
            r["action"],
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
