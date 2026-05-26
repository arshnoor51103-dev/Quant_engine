"""
Phase 2 CLI additions.

Merge these commands into src/cli/main.py.
These add: `quant signals`, `quant backtest`, `quant dashboard`.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, timedelta

import typer
from rich.console import Console
from rich.table import Table

from ..data.ingest import load_universe
from ..data.storage import persist_signals, query_signal_history
from ..portfolio.model import price_series
from ..signals.momentum import MomentumSignal, ShortTermMomentum
from ..signals.vol_regime import VolRegimeSignal
from ..signals.mean_reversion import MeanReversionSignal
from ..backtest.engine import run_backtest, BacktestConfig

console = Console()


def _make_signal_map() -> dict:
    return {
        "momentum": MomentumSignal(),
        "momentum_short": ShortTermMomentum(),
        "vol_regime": VolRegimeSignal(),
        "mean_reversion": MeanReversionSignal(),
    }


# ─── ADD THESE TO THE EXISTING app IN main.py ─────────────────────


def signals_command(
    signal_type: str = typer.Option("momentum", help="Signal type: momentum, momentum_short, vol_regime, mean_reversion"),
    save: bool = typer.Option(False, "--save", help="Persist signal scores to DB"),
) -> None:
    """Generate signal scores for the universe."""
    universe = load_universe()
    tickers = [a["ticker"] for a in universe]

    # Select signal first so we know the required lookback
    signal_map = _make_signal_map()
    if signal_type not in signal_map:
        console.print(f"[red]Unknown signal: {signal_type}. Options: {list(signal_map.keys())}[/red]")
        return

    sig = signal_map[signal_type]

    # Load enough history to satisfy the signal's lookback requirement
    lookback = sig.lookback_days
    prices = {}
    for t in tickers:
        ps = price_series(t, lookback_days=lookback)
        if not ps.empty:
            prices[t] = ps

    result = sig.generate(prices)

    if save:
        run_id = str(uuid.uuid4())[:8]
        n = persist_signals([result], run_id=run_id)
        console.print(f"[dim]Saved {n} signal rows (run_id: {run_id})[/dim]")

    # Display
    table = Table(title=f"Signal: {sig.name} — {result.run_date}")
    table.add_column("Rank", justify="right")
    table.add_column("Ticker")
    table.add_column("Score", justify="right")
    table.add_column("Signal")

    ranked = result.ranked()
    for i, (ticker, score) in enumerate(reversed(ranked), 1):
        bar_len = int(abs(score) * 20)
        bar = ("█" * bar_len).ljust(20)
        color = "green" if score > 0.3 else "yellow" if score > 0 else "red"
        table.add_row(
            str(i),
            ticker,
            f"{score:+.3f}",
            f"[{color}]{bar}[/{color}]",
        )

    console.print(table)

    # Show metadata if vol regime
    if result.metadata and "regime" in result.metadata:
        console.print(f"\n[bold]Regime:[/bold] {result.metadata['regime']}")
        vp = result.metadata.get('vol_percentile')
        cv = result.metadata.get('current_annualized_vol')
        console.print(f"[bold]Vol percentile:[/bold] {vp:.1%}" if vp is not None else "[bold]Vol percentile:[/bold] n/a")
        console.print(f"[bold]Current annualized vol:[/bold] {cv:.2%}" if cv is not None else "[bold]Current annualized vol:[/bold] n/a")

    # Show raw returns for momentum
    if result.metadata and "raw_returns" in result.metadata:
        console.print("\n[dim]Raw momentum returns:[/dim]")
        for t, r in sorted(result.metadata["raw_returns"].items(), key=lambda x: -x[1]):
            console.print(f"  {t}: {r:+.2%}")


def backtest_command(
    signal_type: str = typer.Option("momentum", help="Signal to backtest"),
    years: int = typer.Option(5, help="Years of history to backtest"),
    top_n: int = typer.Option(4, help="Number of top-ranked tickers to hold"),
) -> None:
    """Run a walk-forward backtest on a signal strategy."""
    universe = load_universe()
    tickers = [a["ticker"] for a in universe]

    console.print(f"[cyan]Running backtest: {signal_type}, {years}yr, top-{top_n}...[/cyan]\n")

    # Load price data
    prices = {}
    for t in tickers:
        ps = price_series(t, lookback_days=252 * (years + 2))
        if not ps.empty:
            prices[t] = ps

    # Select signal
    signal_map = _make_signal_map()
    sig = signal_map.get(signal_type)
    if not sig:
        console.print(f"[red]Unknown signal: {signal_type}[/red]")
        return

    config = BacktestConfig(
        start_date=date.today() - timedelta(days=365 * years),
        end_date=date.today(),
        top_n=top_n,
    )

    try:
        result = run_backtest(sig, prices, config)
    except ValueError as e:
        console.print(f"[red]Backtest failed: {e}[/red]")
        return

    # Display results
    table = Table(title=f"Backtest Results: {result.signal_name}")
    table.add_column("Metric")
    table.add_column("Strategy", justify="right")
    table.add_column("Benchmark (VFV)", justify="right")

    rows = [
        ("Ann. Return", "annualized_return", "bench_annualized_return"),
        ("Ann. Vol", "annualized_vol", None),
        ("Sharpe", "sharpe", "bench_sharpe"),
        ("Sortino", "sortino", None),
        ("Max Drawdown", "max_drawdown", "bench_max_drawdown"),
        ("Calmar", "calmar", None),
        ("Alpha vs Bench", "alpha_vs_benchmark", None),
        ("Beta vs Bench", "beta_vs_benchmark", None),
    ]

    for label, key, bench_key in rows:
        strat_val = result.metrics.get(key)
        bench_val = result.metrics.get(bench_key) if bench_key else None
        s = f"{strat_val:+.4f}" if isinstance(strat_val, float) else "—"
        b = f"{bench_val:+.4f}" if isinstance(bench_val, float) else "—"
        # Color: green if strategy beats benchmark
        if isinstance(strat_val, float) and isinstance(bench_val, float):
            color = "green" if strat_val > bench_val else "red"
            table.add_row(label, f"[{color}]{s}[/{color}]", b)
        else:
            table.add_row(label, s, b)

    console.print(table)
    console.print(f"\nRebalances: {result.metrics.get('n_rebalances', '?')}")
    console.print(f"Avg holdings/period: {result.metrics.get('avg_holdings_per_period', '?'):.1f}")

    # Show last 3 rebalance holdings
    console.print("\n[dim]Last 3 rebalance picks:[/dim]")
    for entry in result.rebalance_log[-3:]:
        tickers_held = ", ".join(entry["holdings"]) if entry["holdings"] else "[cash]"
        console.print(f"  {entry['date']}: {tickers_held}")


def dashboard_command(
    port: int = typer.Option(8501, help="Port for local dashboard server"),
) -> None:
    """Launch the local web dashboard."""
    try:
        import uvicorn
        console.print(f"[green]Starting dashboard at http://localhost:{port}[/green]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]")
        uvicorn.run("src.api.server:app", host="0.0.0.0", port=port, reload=False)
    except ImportError:
        console.print("[red]Missing: pip install uvicorn fastapi[/red]")
