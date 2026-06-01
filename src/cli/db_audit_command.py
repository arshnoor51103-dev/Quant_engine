"""
`quant db-audit` — re-runnable, read-only database health check.

Codifies the manual sweep that found the 2026-05-31 pending pile-up. Inspects
the live database against eight checks (schema, migrations, holdings/trades
reconciliation, pending-rec supersession, universe integrity, price coverage /
freshness / quality) and reports findings grouped by severity.

Contract (LEARNING.md 2026-05-31 Decision):
    - Exit 0 when clean or WARN-only; exit 1 if any ERROR finding exists, so a
      scheduler can gate on real corruption.
    - Read-only: never mutates a domain table. The single write is one summary
      row to ``run_log`` — guarded so a DB broken enough to be missing run_log
      still prints its findings instead of crashing on the write.
    - ``--json`` emits the structured report for machine / scheduler use.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date

import typer

from ..data.storage import get_connection, log
from ..data.audit import AuditThresholds, run_audit
from ..portfolio.model import load_portfolio_config, load_universe_map


def db_audit_command(
    json_output: bool = typer.Option(
        False, "--json", help="Emit the report as JSON instead of a table."
    ),
) -> None:
    """Read-only DB health check. Exits non-zero on any ERROR finding."""
    universe_tickers = set(load_universe_map().keys())
    thresholds = AuditThresholds.from_config(load_portfolio_config())

    conn = get_connection()
    try:
        report = run_audit(conn, universe_tickers, date.today(), thresholds)
    finally:
        conn.close()

    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.render())

    # Single permitted write: a run_log summary row. Guarded — a DB so broken
    # that run_log is missing must not crash the audit before reporting (the
    # schema check already flags the missing table).
    level = "ERROR" if report.errors else ("WARN" if report.warnings else "INFO")
    summary = (
        f"db-audit: {len(report.errors)} error(s), {len(report.warnings)} "
        f"warning(s) across {len(report.checks_run)} checks"
    )
    try:
        log("db_audit", level, summary)
    except sqlite3.Error:
        pass

    raise typer.Exit(report.exit_code)
