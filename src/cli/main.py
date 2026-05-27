"""
Quant Engine CLI.

Run:
    python -m src.cli.main init
    python -m src.cli.main fetch --years 20
    python -m src.cli.main status
    python -m src.cli.main metrics --ticker VFV.TO
    python -m src.cli.main universe
    python -m src.cli.main trade VFV.TO BUY 10 95.42
"""
from __future__ import annotations

import typer
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..data.ingest import ingest_universe, load_universe
from ..data.storage import initialize, record_trade
from ..portfolio.model import (
    bucket_allocation,
    get_holdings,
    load_portfolio_config,
    nav,
    price_series,
)
from ..portfolio import metrics as m
from .phase2_commands import signals_command, backtest_command, dashboard_command, signal_history_command
from .phase3_commands import (
    recommend_command,
    execute_command,
    pending_command,
    skip_command,
)
from ..alerts.ntfy import send_alert

app = typer.Typer(add_completion=False, help="Quant Engine CLI")
console = Console()


@app.command()
def init() -> None:
    """Create SQLite schema."""
    initialize()
    console.print("[green]✓ Database initialized at data/quant.db[/green]")


@app.command()
def fetch(
    years: int = typer.Option(20, help="History depth on full pull"),
    full: bool = typer.Option(False, help="Force full re-pull (ignore incremental)"),
) -> None:
    """Pull OHLCV for every ticker in the universe."""
    console.print(f"[cyan]Fetching universe — years={years}, full={full}[/cyan]")
    results = ingest_universe(years=years, incremental=not full)
    table = Table(title="Ingest Results")
    table.add_column("Ticker")
    table.add_column("Rows inserted", justify="right")
    table.add_column("Status")
    for ticker, n in results.items():
        if n == -1:
            table.add_row(ticker, "—", "[red]ERROR[/red]")
        elif n == 0:
            table.add_row(ticker, "0", "[yellow]up-to-date[/yellow]")
        else:
            table.add_row(ticker, str(n), "[green]ok[/green]")
    console.print(table)


@app.command()
def universe() -> None:
    """List current asset universe."""
    u = load_universe()
    table = Table(title="Asset Universe")
    table.add_column("Ticker")
    table.add_column("Bucket")
    table.add_column("Asset class")
    table.add_column("Region")
    table.add_column("MER")
    table.add_column("Name")
    for a in u:
        table.add_row(
            a["ticker"], a["bucket"], a["asset_class"], a["region"],
            f"{a['mer']*100:.2f}%", a["name"],
        )
    console.print(table)


@app.command()
def status() -> None:
    """Portfolio state, NAV, bucket drift."""
    holdings = get_holdings()
    total = nav(holdings)
    console.print(f"\n[bold]Portfolio NAV:[/bold] ${total:,.2f} CAD\n")

    if not holdings:
        console.print("[yellow]No holdings yet. Add via the trade log when you make your first buy.[/yellow]\n")
        return

    h_table = Table(title="Holdings")
    for c in ("Ticker", "Bucket", "Units", "Avg cost", "Last", "Mkt value", "PnL"):
        h_table.add_column(c)
    for h in holdings:
        h_table.add_row(
            h.ticker, h.bucket, f"{h.units:.4f}",
            f"${h.avg_cost:.2f}",
            f"${h.last_price:.2f}" if h.last_price else "—",
            f"${h.market_value:,.2f}",
            f"${h.unrealized_pnl:+,.2f}",
        )
    console.print(h_table)

    b_table = Table(title="Bucket Allocation vs Target")
    for c in ("Bucket", "Target", "Actual", "Drift", "Needs rebalance"):
        b_table.add_column(c)
    for b, info in bucket_allocation(holdings).items():
        b_table.add_row(
            b,
            f"{info['target']*100:.1f}%",
            f"{info['actual']*100:.1f}%",
            f"{info['drift']*100:+.1f}%",
            "[red]YES[/red]" if info["needs_rebalance"] else "no",
        )
    console.print(b_table)


@app.command()
def metrics(
    ticker: str = typer.Option(None, help="Single ticker, or omit for full universe"),
    lookback: int = typer.Option(1260, help="Lookback in trading days (default 5yr)"),
) -> None:
    """Risk/return metrics for a ticker or the whole universe."""
    tickers = [ticker] if ticker else [a["ticker"] for a in load_universe()]

    table = Table(title=f"Metrics — lookback {lookback} days")
    for c in ("Ticker", "Ann return", "Ann vol", "Sharpe", "Sortino", "Max DD", "Calmar"):
        table.add_column(c)

    for t in tickers:
        prices = price_series(t, lookback_days=lookback)
        if prices.empty:
            table.add_row(t, "—", "—", "—", "—", "—", "—")
            continue
        rets = m.daily_returns(prices)
        s = m.summary(rets)
        table.add_row(
            t,
            f"{s['annualized_return']*100:+.2f}%",
            f"{s['annualized_vol']*100:.2f}%",
            f"{s['sharpe']:.2f}",
            f"{s['sortino']:.2f}",
            f"{s['max_drawdown']*100:.2f}%",
            f"{s['calmar']:.2f}",
        )

    console.print(table)


@app.command()
def trade(
    ticker: str = typer.Argument(..., help="Ticker, e.g. VFV.TO"),
    side: str = typer.Argument(..., help="BUY or SELL"),
    units: float = typer.Argument(..., help="Number of units"),
    price: float = typer.Argument(..., help="Execution price per unit in CAD"),
    trade_date: str = typer.Option(None, "--date", help="YYYY-MM-DD, defaults to today"),
    fees: float = typer.Option(0.0, help="Commission/fees in CAD (Wealthsimple = 0)"),
    rationale: str = typer.Option(None, help="Optional note logged with the trade"),
) -> None:
    """Record a manually executed trade and update holdings."""
    side = side.upper()
    if side not in ("BUY", "SELL"):
        console.print("[red]side must be BUY or SELL[/red]")
        raise typer.Exit(1)

    universe = {a["ticker"]: a for a in load_universe()}
    if ticker not in universe:
        console.print(f"[red]{ticker} not in universe — check config/universe.yaml[/red]")
        raise typer.Exit(1)

    exec_date = date.fromisoformat(trade_date) if trade_date else date.today()
    gross = units * price
    net = gross + fees if side == "BUY" else gross - fees

    try:
        trade_id = record_trade(
            ticker=ticker,
            side=side,
            units=units,
            price=price,
            trade_date=exec_date,
            fees=fees,
            rationale=rationale,
        )
    except ValueError as exc:
        console.print(f"[red]Trade rejected: {exc}[/red]")
        raise typer.Exit(1)

    colour = "green" if side == "BUY" else "red"
    summary = (
        f"[bold {colour}]{side}[/bold {colour}]  {ticker}  "
        f"{units:.4f} units @ ${price:.4f}  =  ${gross:,.2f} CAD\n"
        f"Fees: ${fees:.2f}   Net: ${net:,.2f} CAD\n"
        f"Date: {exec_date}   Trade ID: #{trade_id}"
    )
    if rationale:
        summary += f"\nNote: {rationale}"
    console.print(Panel(summary, title="Trade Recorded", border_style=colour))


@app.command(name="alert-test")
def alert_test() -> None:
    """Send a test ping to the configured ntfy.sh topic."""
    cfg = load_portfolio_config().get("alerts", {})
    if not cfg.get("enabled"):
        console.print("[yellow]alerts.enabled is false in portfolio.yaml — nothing sent.[/yellow]")
        return
    topic = cfg["ntfy_topic"]
    send_alert(topic, "Quant Engine", "Alert test — system is live")
    console.print(f"[green]Test alert sent → https://ntfy.sh/{topic}[/green]")


app.command(name="signals")(signals_command)
app.command(name="backtest")(backtest_command)
app.command(name="dashboard")(dashboard_command)
app.command(name="recommend")(recommend_command)
app.command(name="execute")(execute_command)
app.command(name="pending")(pending_command)
app.command(name="skip")(skip_command)
app.command(name="signal-history")(signal_history_command)


if __name__ == "__main__":
    app()
