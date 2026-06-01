"""
Read-only database health auditor.

Codifies the manual DB sweep that found the 2026-05-31 pending pile-up into a
re-runnable check. Every function here is **read-only** — it inspects the
database and returns findings, but never mutates a domain table. The single
permitted write (a run_log summary row) lives in the CLI command, not here.

Design (see LEARNING.md 2026-05-31 Decision):
    - `AuditFinding`  — one problem, with severity + structured detail.
    - `AuditReport`   — the aggregate; `exit_code` is 1 iff any ERROR exists.
    - `check_*(conn, ...)` — independent check functions returning findings;
      an empty list means the check passed. Everything they need (universe
      ticker set, `today`, thresholds) is injected so they are pure and
      deterministic in tests.
    - `run_audit(...)` — runs every check and composes the report.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .storage import SCHEMA, _MIGRATIONS

SEVERITY_ERROR = "ERROR"
SEVERITY_WARN = "WARN"


@dataclass(frozen=True)
class AuditFinding:
    """A single audit problem.

    Attributes:
        check:    id of the check that produced it (e.g. "schema").
        severity: SEVERITY_ERROR or SEVERITY_WARN.
        message:  human one-liner; should name the fix where possible.
        detail:   structured context for ``--json`` consumers.
    """

    check: str
    severity: str
    message: str
    detail: dict = field(default_factory=dict)


@dataclass
class AuditThresholds:
    """Tunable thresholds for the price-freshness check (business days)."""

    price_staleness_warn_days: int = 5
    price_staleness_error_days: int = 15
    per_ticker_lag_warn_days: int = 3

    @classmethod
    def from_config(cls, cfg: dict | None) -> "AuditThresholds":
        """Build from a portfolio.yaml dict; the ``db_audit`` block is optional."""
        block = (cfg or {}).get("db_audit", {}) or {}
        return cls(
            price_staleness_warn_days=int(
                block.get("price_staleness_warn_days", 5)
            ),
            price_staleness_error_days=int(
                block.get("price_staleness_error_days", 15)
            ),
            per_ticker_lag_warn_days=int(block.get("per_ticker_lag_warn_days", 3)),
        )


@dataclass
class AuditReport:
    """Aggregate result of an audit run."""

    findings: list[AuditFinding]
    checks_run: list[str]

    @property
    def errors(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARN]

    @property
    def ok(self) -> bool:
        """True when no findings at all were produced."""
        return not self.findings

    @property
    def exit_code(self) -> int:
        """1 if any ERROR finding exists, else 0. WARN-only stays 0."""
        return 1 if self.errors else 0

    def to_dict(self) -> dict:
        """JSON-serializable view of the report (for ``--json``)."""
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "checks_run": list(self.checks_run),
            "findings": [
                {
                    "check": f.check,
                    "severity": f.severity,
                    "message": f.message,
                    "detail": f.detail,
                }
                for f in self.findings
            ],
        }

    def render(self) -> str:
        """Human-readable, severity-grouped report.

        Uses ASCII-only markers ([ok]/[FAIL]) so the report can never trigger
        the cp1252 console crash this project has already been bitten by.
        """
        by_check: dict[str, list[AuditFinding]] = {}
        for finding in self.findings:
            by_check.setdefault(finding.check, []).append(finding)

        lines = [
            f"DB Audit — {len(self.errors)} error(s), {len(self.warnings)} warning(s)",
            "",
        ]
        for check in self.checks_run:
            check_findings = by_check.get(check, [])
            if not check_findings:
                lines.append(f"  [ok]   {check}")
            else:
                lines.append(f"  [FAIL] {check}")
                for finding in check_findings:
                    lines.append(f"           [{finding.severity}] {finding.message}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Schema introspection helpers
# --------------------------------------------------------------------------
def _expected_schema() -> dict[str, set[str]]:
    """Tables -> column-name sets, materialized from the canonical SCHEMA.

    Building an in-memory DB from SCHEMA makes SCHEMA the single source of
    truth: when a column is added to SCHEMA, the audit expects it automatically.
    """
    mem = sqlite3.connect(":memory:")
    try:
        mem.executescript(SCHEMA)
        tables: dict[str, set[str]] = {}
        for row in mem.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall():
            tname = row[0]
            cols = {c[1] for c in mem.execute(f"PRAGMA table_info({tname});").fetchall()}
            tables[tname] = cols
        return tables
    finally:
        mem.close()


def _live_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }


def _live_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {c[1] for c in conn.execute(f"PRAGMA table_info({table});").fetchall()}


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def check_schema(conn: sqlite3.Connection) -> list[AuditFinding]:
    """Every table in SCHEMA exists and carries all its columns.

    Catches a live DB that predates a DDL change (e.g. the 2026-05-31 stale DB
    missing ``alerts_log``/``schema_version``, or a missing migration column).
    """
    findings: list[AuditFinding] = []
    expected = _expected_schema()
    live = _live_tables(conn)
    for table in sorted(expected):
        if table not in live:
            findings.append(
                AuditFinding(
                    check="schema",
                    severity=SEVERITY_ERROR,
                    message=f"Table '{table}' missing from database — run `quant init`.",
                    detail={"table": table},
                )
            )
            continue
        missing_cols = expected[table] - _live_columns(conn, table)
        for col in sorted(missing_cols):
            findings.append(
                AuditFinding(
                    check="schema",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"Column '{table}.{col}' missing — run `quant init` "
                        f"to apply migrations."
                    ),
                    detail={"table": table, "column": col},
                )
            )
    return findings


def check_migrations(conn: sqlite3.Connection) -> list[AuditFinding]:
    """Every registered migration version is recorded in ``schema_version``.

    A version present in ``_MIGRATIONS`` but absent from ``schema_version``
    means the live DB never had that migration applied — schema drift that
    ``quant init`` (which calls ``run_migrations``) resolves.
    """
    expected = {version for version, _ in _MIGRATIONS}
    try:
        applied = {
            row[0]
            for row in conn.execute(
                "SELECT version FROM schema_version;"
            ).fetchall()
        }
    except sqlite3.OperationalError:
        return [
            AuditFinding(
                check="migrations",
                severity=SEVERITY_ERROR,
                message=(
                    "schema_version table missing — cannot verify migrations; "
                    "run `quant init`."
                ),
                detail={"reason": "schema_version table missing"},
            )
        ]
    return [
        AuditFinding(
            check="migrations",
            severity=SEVERITY_ERROR,
            message=(
                f"Migration {version} registered in code but not recorded in "
                f"schema_version — run `quant init`."
            ),
            detail={"version": version},
        )
        for version in sorted(expected - applied)
    ]


_UNIT_TOL = 1e-6
_COST_TOL = 1e-4


def check_holdings_reconciliation(conn: sqlite3.Connection) -> list[AuditFinding]:
    """The holdings table equals a replay of the trades log.

    Replays every trade in execution order using the same VWAP-on-BUY /
    units-down-on-SELL logic as ``storage._record_trade_on_conn``, then compares
    the derived position to the live ``holdings`` row for each ticker. Catches a
    holdings table that has silently diverged from its trade history (units or
    avg_cost drift, a holding with no backing trades, or a net position with no
    holdings row).
    """
    findings: list[AuditFinding] = []
    trade_rows = conn.execute(
        "SELECT ticker, side, units, price FROM trades ORDER BY trade_date, id;"
    ).fetchall()

    expected: dict[str, dict] = {}  # ticker -> {"units", "avg_cost"}
    for row in trade_rows:
        ticker, side, units, price = (
            row["ticker"], row["side"], row["units"], row["price"],
        )
        state = expected.get(ticker)
        if side == "BUY":
            if state:
                new_units = state["units"] + units
                state["avg_cost"] = (
                    state["units"] * state["avg_cost"] + units * price
                ) / new_units
                state["units"] = new_units
            else:
                expected[ticker] = {"units": units, "avg_cost": price}
        else:  # SELL
            if not state or units > state["units"] + _UNIT_TOL:
                findings.append(
                    AuditFinding(
                        check="holdings_reconciliation",
                        severity=SEVERITY_ERROR,
                        message=(
                            f"{ticker}: SELL of {units} units exceeds units held "
                            f"in trade replay — trades log is internally inconsistent."
                        ),
                        detail={"ticker": ticker},
                    )
                )
                expected.pop(ticker, None)
                continue
            state["units"] -= units
            if state["units"] < _UNIT_TOL:
                del expected[ticker]

    actual = {
        row["ticker"]: {"units": row["units"], "avg_cost": row["avg_cost"]}
        for row in conn.execute(
            "SELECT ticker, units, avg_cost FROM holdings;"
        ).fetchall()
    }

    for ticker in sorted(expected):
        exp = expected[ticker]
        act = actual.get(ticker)
        if act is None:
            findings.append(
                AuditFinding(
                    check="holdings_reconciliation",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{ticker}: trade replay yields {exp['units']:.4f} units "
                        f"but there is no holdings row."
                    ),
                    detail={"ticker": ticker, "expected_units": exp["units"]},
                )
            )
            continue
        if abs(act["units"] - exp["units"]) > _UNIT_TOL:
            findings.append(
                AuditFinding(
                    check="holdings_reconciliation",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{ticker}: holdings units {act['units']:.4f} != "
                        f"net trades {exp['units']:.4f}."
                    ),
                    detail={
                        "ticker": ticker,
                        "holdings_units": act["units"],
                        "expected_units": exp["units"],
                    },
                )
            )
        if abs(act["avg_cost"] - exp["avg_cost"]) > _COST_TOL:
            findings.append(
                AuditFinding(
                    check="holdings_reconciliation",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{ticker}: holdings avg_cost {act['avg_cost']:.4f} != "
                        f"replayed VWAP {exp['avg_cost']:.4f}."
                    ),
                    detail={
                        "ticker": ticker,
                        "holdings_avg_cost": act["avg_cost"],
                        "expected_avg_cost": exp["avg_cost"],
                    },
                )
            )

    for ticker in sorted(actual):
        if ticker not in expected:
            findings.append(
                AuditFinding(
                    check="holdings_reconciliation",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{ticker}: holdings row exists but trade replay yields no "
                        f"position (no backing trades, or net-zero/over-sold)."
                    ),
                    detail={"ticker": ticker, "holdings_units": actual[ticker]["units"]},
                )
            )

    return findings


def check_pending_supersession(conn: sqlite3.Connection) -> list[AuditFinding]:
    """Pending recommendations form a single, deduplicated snapshot.

    ``recommend --save`` supersedes prior pending cards, so the invariant is:
    every ``pending`` row shares one (non-NULL) ``run_id`` and no ticker appears
    twice. A violation is the 2026-05-31 pile-up signature — stale duplicate
    cards (and zombie recs for dropped tickers) inviting a double execution.
    """
    findings: list[AuditFinding] = []
    rows = conn.execute(
        "SELECT id, ticker, action, run_id FROM recommendations "
        "WHERE status = 'pending';"
    ).fetchall()
    if not rows:
        return []

    run_ids = [r["run_id"] for r in rows]
    has_null = any(rid is None for rid in run_ids)
    distinct_non_null = {rid for rid in run_ids if rid is not None}

    if len(distinct_non_null) > 1 or (has_null and distinct_non_null):
        n_runs = len(distinct_non_null) + (1 if has_null else 0)
        findings.append(
            AuditFinding(
                check="pending_supersession",
                severity=SEVERITY_ERROR,
                message=(
                    f"{len(rows)} pending recommendations span {n_runs} runs; only "
                    f"the newest snapshot should be pending — supersession did not "
                    f"run. Re-run `quant recommend --save`."
                ),
                detail={"pending_count": len(rows), "distinct_runs": n_runs},
            )
        )
    elif has_null and not distinct_non_null:
        findings.append(
            AuditFinding(
                check="pending_supersession",
                severity=SEVERITY_ERROR,
                message=(
                    f"{len(rows)} pending recommendation(s) have no run_id (predate "
                    f"run_id tracking) and should be superseded. Re-run "
                    f"`quant recommend --save`."
                ),
                detail={"pending_count": len(rows)},
            )
        )

    counts = Counter(r["ticker"] for r in rows)
    for ticker in sorted(t for t, c in counts.items() if c > 1):
        findings.append(
            AuditFinding(
                check="pending_supersession",
                severity=SEVERITY_ERROR,
                message=(
                    f"{ticker}: {counts[ticker]} pending recommendations — duplicate "
                    f"actionable cards risk a double execution. Re-run "
                    f"`quant recommend --save` to supersede."
                ),
                detail={"ticker": ticker, "count": counts[ticker]},
            )
        )

    return findings


def check_universe_integrity(
    conn: sqlite3.Connection, universe_tickers: set[str]
) -> list[AuditFinding]:
    """No state references a ticker outside the configured universe.

    A **holding** outside the universe is a universe-lock breach (Hard
    Constraint 2) → ERROR. A **pending recommendation** outside the universe is
    a zombie actionable card (e.g. the ZAG.TO rec left over after the ticker was
    dropped) → WARN, cleared by the next ``recommend --save``.
    """
    findings: list[AuditFinding] = []

    for row in conn.execute(
        "SELECT ticker FROM holdings ORDER BY ticker;"
    ).fetchall():
        ticker = row["ticker"]
        if ticker not in universe_tickers:
            findings.append(
                AuditFinding(
                    check="universe_integrity",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{ticker}: held position is outside the configured universe "
                        f"(universe-lock breach). Add it to universe.yaml or exit the "
                        f"position."
                    ),
                    detail={"ticker": ticker, "kind": "holding"},
                )
            )

    for row in conn.execute(
        "SELECT DISTINCT ticker FROM recommendations "
        "WHERE status = 'pending' ORDER BY ticker;"
    ).fetchall():
        ticker = row["ticker"]
        if ticker not in universe_tickers:
            findings.append(
                AuditFinding(
                    check="universe_integrity",
                    severity=SEVERITY_WARN,
                    message=(
                        f"{ticker}: pending recommendation for a ticker outside the "
                        f"configured universe (zombie card). Re-run "
                        f"`quant recommend --save` to supersede."
                    ),
                    detail={"ticker": ticker, "kind": "pending_rec"},
                )
            )

    return findings


def check_price_coverage(
    conn: sqlite3.Connection, universe_tickers: set[str]
) -> list[AuditFinding]:
    """Every universe ticker has at least one price row.

    A ticker with no price history cannot produce a signal; an ERROR here means
    ``quant fetch`` has never successfully loaded it.
    """
    have = {
        row["ticker"]
        for row in conn.execute("SELECT DISTINCT ticker FROM prices;").fetchall()
    }
    return [
        AuditFinding(
            check="price_coverage",
            severity=SEVERITY_ERROR,
            message=(
                f"{ticker}: no price rows — `quant fetch` has never loaded it; "
                f"signals cannot compute."
            ),
            detail={"ticker": ticker},
        )
        for ticker in sorted(universe_tickers - have)
    ]


def _busday_age(begin: date, end: date) -> int:
    """Business days from ``begin`` to ``end`` (0 if begin >= end)."""
    return max(0, int(np.busday_count(begin, end)))


def check_price_freshness(
    conn: sqlite3.Connection,
    universe_tickers: set[str],
    today: date,
    thresholds: AuditThresholds,
) -> list[AuditFinding]:
    """Price history is current and no single ticker's feed has fallen behind.

    Staleness and lag are measured in **business days** (``numpy.busday_count``)
    so a normal weekend/holiday gap is not flagged. Tickers with no price rows
    are skipped here — ``check_price_coverage`` owns that case.
    """
    findings: list[AuditFinding] = []
    latest: dict[str, date] = {}
    for row in conn.execute(
        "SELECT ticker, MAX(trade_date) AS d FROM prices GROUP BY ticker;"
    ).fetchall():
        if row["ticker"] in universe_tickers and row["d"]:
            latest[row["ticker"]] = date.fromisoformat(row["d"])
    if not latest:
        return []

    freshest = max(latest.values())
    age = _busday_age(freshest, today)
    if age > thresholds.price_staleness_error_days:
        findings.append(
            AuditFinding(
                check="price_freshness",
                severity=SEVERITY_ERROR,
                message=(
                    f"Prices are stale: the freshest price is {age} business days "
                    f"old (> {thresholds.price_staleness_error_days}). Run "
                    f"`quant fetch`."
                ),
                detail={"age_business_days": age, "freshest": freshest.isoformat()},
            )
        )
    elif age > thresholds.price_staleness_warn_days:
        findings.append(
            AuditFinding(
                check="price_freshness",
                severity=SEVERITY_WARN,
                message=(
                    f"Prices are aging: the freshest price is {age} business days "
                    f"old (> {thresholds.price_staleness_warn_days}). Run "
                    f"`quant fetch`."
                ),
                detail={"age_business_days": age, "freshest": freshest.isoformat()},
            )
        )

    for ticker in sorted(latest):
        lag = _busday_age(latest[ticker], freshest)
        if lag > thresholds.per_ticker_lag_warn_days:
            findings.append(
                AuditFinding(
                    check="price_freshness",
                    severity=SEVERITY_WARN,
                    message=(
                        f"{ticker}: latest price lags the freshest universe price by "
                        f"{lag} business days — possible broken feed for this ticker."
                    ),
                    detail={
                        "ticker": ticker,
                        "lag_business_days": lag,
                        "ticker_latest": latest[ticker].isoformat(),
                    },
                )
            )

    return findings


def check_price_quality(conn: sqlite3.Connection) -> list[AuditFinding]:
    """No price row carries a NULL or non-positive close / adj_close.

    A zero/negative/NULL close silently corrupts every return and signal
    computed from it, so these are ERROR-level.
    """
    rows = conn.execute(
        "SELECT ticker, COUNT(*) AS n FROM prices "
        "WHERE close IS NULL OR close <= 0 "
        "OR adj_close IS NULL OR adj_close <= 0 "
        "GROUP BY ticker ORDER BY ticker;"
    ).fetchall()
    return [
        AuditFinding(
            check="price_quality",
            severity=SEVERITY_ERROR,
            message=(
                f"{row['ticker']}: {row['n']} price row(s) with NULL or non-positive "
                f"close/adj_close — corrupts every return computed from them."
            ),
            detail={"ticker": row["ticker"], "bad_rows": row["n"]},
        )
        for row in rows
    ]


# Ordered registry of checks. Each entry runs against the live connection; the
# id is recorded in ``checks_run`` so the report can show passed checks too.
_CHECK_ORDER = [
    "schema",
    "migrations",
    "holdings_reconciliation",
    "pending_supersession",
    "universe_integrity",
    "price_coverage",
    "price_freshness",
    "price_quality",
]


def run_audit(
    conn: sqlite3.Connection,
    universe_tickers: set[str],
    today: date,
    thresholds: AuditThresholds,
) -> AuditReport:
    """Run every check against ``conn`` and compose the report.

    Read-only: no check mutates the database. ``today`` and ``thresholds`` are
    injected so freshness is deterministic in tests.
    """
    findings: list[AuditFinding] = []
    findings += check_schema(conn)
    findings += check_migrations(conn)
    findings += check_holdings_reconciliation(conn)
    findings += check_pending_supersession(conn)
    findings += check_universe_integrity(conn, universe_tickers)
    findings += check_price_coverage(conn, universe_tickers)
    findings += check_price_freshness(conn, universe_tickers, today, thresholds)
    findings += check_price_quality(conn)
    return AuditReport(findings=findings, checks_run=list(_CHECK_ORDER))
