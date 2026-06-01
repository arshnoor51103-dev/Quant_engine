"""
Entry point for a scheduled / standalone database health check.

Runs the same logic as `quant db-audit` (schema, reconciliation, supersession,
price coverage/freshness/quality). Exits non-zero if any ERROR-severity finding
exists, so a task scheduler can alert on DB corruption. Read-only apart from a
single run_log summary row.

    python scripts/db_audit.py     # exit 0 clean/WARN-only, 1 on any ERROR
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import typer

from src.cli.db_audit_command import db_audit_command


def main() -> int:
    """Run the audit, translating the command's ``typer.Exit`` to an int code."""
    try:
        db_audit_command(json_output=False)
    except typer.Exit as exc:
        return int(exc.exit_code or 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
