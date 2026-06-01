"""
Tests for the read-only DB health auditor (src/data/audit.py) and the
`quant db-audit` CLI command.

Every test builds a throwaway in-memory SQLite DB from the canonical SCHEMA,
mutates it into a clean or broken state, and asserts the findings. The live
data/quant.db is never touched (audit is read-only by contract, and conftest.py
isolates DB_PATH regardless).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date

import pytest
import typer

from src.data.storage import SCHEMA, _MIGRATIONS, record_trade
from src.data.audit import (
    AuditFinding,
    AuditReport,
    AuditThresholds,
    check_schema,
    check_migrations,
    check_holdings_reconciliation,
    check_pending_supersession,
    check_universe_integrity,
    check_price_coverage,
    check_price_freshness,
    check_price_quality,
    run_audit,
)

UNIVERSE = {
    "VFV.TO", "XIC.TO", "HXQ.TO", "XEF.TO", "CHPS.TO",
    "VAB.TO", "HSAV.TO", "CDZ.TO", "VDY.TO",
}


def _add_rec(conn, ticker, action, status="pending", run_id="run-A"):
    conn.execute(
        "INSERT INTO recommendations (ticker, action, status, run_id) "
        "VALUES (?, ?, ?, ?);",
        (ticker, action, status, run_id),
    )


def _add_price(conn, ticker, d, close, adj_close=None, volume=1000):
    adj = close if adj_close is None else adj_close
    conn.execute(
        "INSERT INTO prices "
        "(ticker, trade_date, open, high, low, close, adj_close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        (ticker, d.isoformat(), close, close, close, close, adj, volume),
    )


def make_conn() -> sqlite3.Connection:
    """In-memory DB built from the live SCHEMA, fully migrated (mirrors a
    correctly `quant init`-ed database)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for version, _ in _MIGRATIONS:
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?);", (version,)
        )
    conn.commit()
    return conn


# --------------------------------------------------------------------------
# check_schema
# --------------------------------------------------------------------------
def test_check_schema_clean_db_has_no_findings():
    conn = make_conn()
    assert check_schema(conn) == []


def test_check_schema_flags_missing_table():
    conn = make_conn()
    conn.execute("DROP TABLE alerts_log;")
    findings = check_schema(conn)
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert findings[0].check == "schema"
    assert "alerts_log" in findings[0].message


def test_check_schema_flags_missing_column():
    """A live DB predating a migration is missing a recommendations column."""
    conn = make_conn()
    # Rebuild recommendations without the migration-added sell_reason column.
    conn.execute("DROP TABLE recommendations;")
    conn.execute(
        """
        CREATE TABLE recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        );
        """
    )
    findings = check_schema(conn)
    assert any(f.severity == "ERROR" and "sell_reason" in f.message for f in findings)


# --------------------------------------------------------------------------
# check_migrations
# --------------------------------------------------------------------------
def test_check_migrations_clean_db_has_no_findings():
    conn = make_conn()
    assert check_migrations(conn) == []


def test_check_migrations_flags_unrecorded_version():
    conn = make_conn()
    # Simulate a DB where migration 2 ran in code-schema but was never recorded.
    conn.execute("DELETE FROM schema_version WHERE version = 2;")
    findings = check_migrations(conn)
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert findings[0].check == "migrations"
    assert "2" in findings[0].message


def test_check_migrations_flags_missing_schema_version_table():
    conn = make_conn()
    conn.execute("DROP TABLE schema_version;")
    findings = check_migrations(conn)
    assert any(f.severity == "ERROR" for f in findings)


# --------------------------------------------------------------------------
# check_holdings_reconciliation
# --------------------------------------------------------------------------
def test_check_holdings_reconciliation_clean():
    conn = make_conn()
    record_trade("VFV.TO", "BUY", 10, 100.0, date(2026, 1, 5), conn=conn)
    record_trade("VFV.TO", "BUY", 5, 110.0, date(2026, 2, 5), conn=conn)
    conn.commit()
    assert check_holdings_reconciliation(conn) == []


def test_check_holdings_reconciliation_fully_sold_is_clean():
    conn = make_conn()
    record_trade("XEF.TO", "BUY", 10, 20.0, date(2026, 1, 5), conn=conn)
    record_trade("XEF.TO", "SELL", 10, 25.0, date(2026, 2, 5), conn=conn)
    conn.commit()
    # record_trade removed the holdings row at zero; net trades = 0 → reconciled
    assert check_holdings_reconciliation(conn) == []


def test_check_holdings_reconciliation_units_mismatch():
    conn = make_conn()
    record_trade("VFV.TO", "BUY", 10, 100.0, date(2026, 1, 5), conn=conn)
    conn.commit()
    conn.execute("UPDATE holdings SET units = 99 WHERE ticker = 'VFV.TO';")
    findings = check_holdings_reconciliation(conn)
    assert any(
        f.severity == "ERROR" and "VFV.TO" in f.message for f in findings
    )


def test_check_holdings_reconciliation_avg_cost_mismatch():
    conn = make_conn()
    record_trade("HXQ.TO", "BUY", 10, 50.0, date(2026, 1, 5), conn=conn)
    conn.commit()
    conn.execute("UPDATE holdings SET avg_cost = 999.0 WHERE ticker = 'HXQ.TO';")
    findings = check_holdings_reconciliation(conn)
    assert any(
        f.severity == "ERROR" and "HXQ.TO" in f.message for f in findings
    )


def test_check_holdings_reconciliation_holding_without_backing_trades():
    conn = make_conn()
    conn.execute(
        "INSERT INTO holdings (ticker, units, avg_cost, last_updated) "
        "VALUES ('XIC.TO', 5, 30.0, CURRENT_TIMESTAMP);"
    )
    findings = check_holdings_reconciliation(conn)
    assert any(
        f.severity == "ERROR" and "XIC.TO" in f.message for f in findings
    )


def test_check_holdings_reconciliation_missing_holding_for_net_position():
    conn = make_conn()
    record_trade("VDY.TO", "BUY", 8, 40.0, date(2026, 1, 5), conn=conn)
    conn.commit()
    conn.execute("DELETE FROM holdings WHERE ticker = 'VDY.TO';")
    findings = check_holdings_reconciliation(conn)
    assert any(
        f.severity == "ERROR" and "VDY.TO" in f.message for f in findings
    )


# --------------------------------------------------------------------------
# check_pending_supersession
# --------------------------------------------------------------------------
def test_check_pending_supersession_clean_single_run():
    conn = make_conn()
    for t, a in [("VFV.TO", "BUY"), ("VAB.TO", "HOLD"), ("XIC.TO", "SELL")]:
        _add_rec(conn, t, a, run_id="run-A")
    conn.commit()
    assert check_pending_supersession(conn) == []


def test_check_pending_supersession_flags_multiple_runs():
    conn = make_conn()
    _add_rec(conn, "VFV.TO", "BUY", run_id="run-A")
    _add_rec(conn, "VFV.TO", "BUY", run_id="run-B")
    conn.commit()
    findings = check_pending_supersession(conn)
    assert any(f.severity == "ERROR" for f in findings)


def test_check_pending_supersession_flags_duplicate_ticker_same_run():
    conn = make_conn()
    _add_rec(conn, "VFV.TO", "BUY", run_id="run-A")
    _add_rec(conn, "VFV.TO", "BUY", run_id="run-A")
    conn.commit()
    findings = check_pending_supersession(conn)
    assert any(f.severity == "ERROR" and "VFV.TO" in f.message for f in findings)


def test_check_pending_supersession_flags_null_run_id():
    conn = make_conn()
    _add_rec(conn, "VFV.TO", "BUY", run_id=None)
    conn.commit()
    findings = check_pending_supersession(conn)
    assert any(f.severity == "ERROR" for f in findings)


def test_check_pending_supersession_ignores_non_pending():
    conn = make_conn()
    _add_rec(conn, "VFV.TO", "BUY", status="superseded", run_id="run-A")
    _add_rec(conn, "VFV.TO", "BUY", status="executed", run_id="run-B")
    _add_rec(conn, "XIC.TO", "BUY", status="pending", run_id="run-C")
    conn.commit()
    assert check_pending_supersession(conn) == []


# --------------------------------------------------------------------------
# check_universe_integrity
# --------------------------------------------------------------------------
def test_check_universe_integrity_clean():
    conn = make_conn()
    _add_rec(conn, "VFV.TO", "BUY", run_id="run-A")
    record_trade("XIC.TO", "BUY", 5, 30.0, date(2026, 1, 5), conn=conn)
    conn.commit()
    assert check_universe_integrity(conn, UNIVERSE) == []


def test_check_universe_integrity_warns_off_universe_pending_rec():
    conn = make_conn()
    _add_rec(conn, "ZAG.TO", "BUY", run_id="run-A")  # dropped from universe
    conn.commit()
    findings = check_universe_integrity(conn, UNIVERSE)
    assert any(f.severity == "WARN" and "ZAG.TO" in f.message for f in findings)


def test_check_universe_integrity_errors_off_universe_holding():
    conn = make_conn()
    conn.execute(
        "INSERT INTO holdings (ticker, units, avg_cost, last_updated) "
        "VALUES ('ZAG.TO', 5, 30.0, CURRENT_TIMESTAMP);"
    )
    conn.commit()
    findings = check_universe_integrity(conn, UNIVERSE)
    assert any(f.severity == "ERROR" and "ZAG.TO" in f.message for f in findings)


def test_check_universe_integrity_ignores_off_universe_superseded_rec():
    conn = make_conn()
    _add_rec(conn, "ZAG.TO", "BUY", status="superseded", run_id="run-A")
    conn.commit()
    assert check_universe_integrity(conn, UNIVERSE) == []


# --------------------------------------------------------------------------
# check_price_coverage
# --------------------------------------------------------------------------
def test_check_price_coverage_clean():
    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    conn.commit()
    assert check_price_coverage(conn, UNIVERSE) == []


def test_check_price_coverage_flags_ticker_with_no_rows():
    conn = make_conn()
    for t in UNIVERSE - {"CHPS.TO"}:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    conn.commit()
    findings = check_price_coverage(conn, UNIVERSE)
    assert any(f.severity == "ERROR" and "CHPS.TO" in f.message for f in findings)


# --------------------------------------------------------------------------
# check_price_freshness
# --------------------------------------------------------------------------
_TODAY = date(2026, 6, 1)  # a Monday


def test_check_price_freshness_clean_when_recent():
    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 29), 100.0)  # prior Friday
    conn.commit()
    assert check_price_freshness(conn, UNIVERSE, _TODAY, AuditThresholds()) == []


def test_check_price_freshness_warns_when_aging():
    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 15), 100.0)  # ~11 business days back
    conn.commit()
    findings = check_price_freshness(conn, UNIVERSE, _TODAY, AuditThresholds())
    assert findings, "expected a staleness finding"
    assert all(f.severity == "WARN" for f in findings)


def test_check_price_freshness_errors_when_very_stale():
    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 4, 1), 100.0)  # ~40 business days back
    conn.commit()
    findings = check_price_freshness(conn, UNIVERSE, _TODAY, AuditThresholds())
    assert any(f.severity == "ERROR" for f in findings)


def test_check_price_freshness_warns_single_ticker_lag():
    conn = make_conn()
    for t in UNIVERSE - {"HSAV.TO"}:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    _add_price(conn, "HSAV.TO", date(2026, 5, 20), 100.0)  # ~7 business days behind
    conn.commit()
    findings = check_price_freshness(conn, UNIVERSE, _TODAY, AuditThresholds())
    assert any(f.severity == "WARN" and "HSAV.TO" in f.message for f in findings)


# --------------------------------------------------------------------------
# check_price_quality
# --------------------------------------------------------------------------
def test_check_price_quality_clean():
    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    conn.commit()
    assert check_price_quality(conn) == []


def test_check_price_quality_flags_null_close():
    conn = make_conn()
    conn.execute(
        "INSERT INTO prices "
        "(ticker, trade_date, open, high, low, close, adj_close, volume) "
        "VALUES ('VFV.TO', '2026-05-29', 100, 100, 100, NULL, 100, 1000);"
    )
    conn.commit()
    findings = check_price_quality(conn)
    assert any(f.severity == "ERROR" and "VFV.TO" in f.message for f in findings)


def test_check_price_quality_flags_nonpositive_close():
    conn = make_conn()
    _add_price(conn, "XIC.TO", date(2026, 5, 29), 0.0)
    conn.commit()
    findings = check_price_quality(conn)
    assert any(f.severity == "ERROR" and "XIC.TO" in f.message for f in findings)


def test_check_price_quality_flags_negative_adj_close():
    conn = make_conn()
    _add_price(conn, "HXQ.TO", date(2026, 5, 29), 50.0, adj_close=-1.0)
    conn.commit()
    findings = check_price_quality(conn)
    assert any(f.severity == "ERROR" and "HXQ.TO" in f.message for f in findings)


# --------------------------------------------------------------------------
# run_audit (orchestrator)
# --------------------------------------------------------------------------
def test_run_audit_clean_db_is_ok_exit_zero():
    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    conn.commit()
    report = run_audit(conn, UNIVERSE, _TODAY, AuditThresholds())
    assert report.ok
    assert report.exit_code == 0
    assert report.findings == []
    assert "schema" in report.checks_run
    assert "price_quality" in report.checks_run


def test_run_audit_aggregates_error_and_warning():
    conn = make_conn()
    conn.execute("DROP TABLE alerts_log;")            # ERROR (schema)
    _add_rec(conn, "ZAG.TO", "BUY", run_id="run-A")   # WARN (universe_integrity)
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    conn.commit()
    report = run_audit(conn, UNIVERSE, _TODAY, AuditThresholds())
    assert report.exit_code == 1
    assert any(f.check == "schema" for f in report.errors)
    assert any(f.check == "universe_integrity" for f in report.warnings)


def test_run_audit_warn_only_exits_zero():
    conn = make_conn()
    _add_rec(conn, "ZAG.TO", "BUY", run_id="run-A")   # zombie WARN only
    for t in UNIVERSE:
        _add_price(conn, t, date(2026, 5, 29), 100.0)
    conn.commit()
    report = run_audit(conn, UNIVERSE, _TODAY, AuditThresholds())
    assert report.warnings
    assert report.errors == []
    assert report.exit_code == 0


# --------------------------------------------------------------------------
# AuditReport.render / to_dict
# --------------------------------------------------------------------------
def test_audit_report_to_dict_structure():
    finding = AuditFinding("schema", "ERROR", "table X missing", {"table": "x"})
    report = AuditReport(findings=[finding], checks_run=["schema", "migrations"])
    d = report.to_dict()
    assert d["exit_code"] == 1
    assert d["ok"] is False
    assert d["summary"]["errors"] == 1
    assert d["summary"]["warnings"] == 0
    assert d["checks_run"] == ["schema", "migrations"]
    assert d["findings"][0]["check"] == "schema"
    assert d["findings"][0]["detail"]["table"] == "x"


def test_audit_report_to_dict_is_json_serializable():
    import json

    finding = AuditFinding(
        "price_freshness", "WARN", "aging", {"age_business_days": 7}
    )
    report = AuditReport(findings=[finding], checks_run=["price_freshness"])
    json.dumps(report.to_dict())  # must not raise


def test_audit_report_render_marks_passed_and_failed_checks():
    finding = AuditFinding("schema", "ERROR", "table X missing", {})
    report = AuditReport(findings=[finding], checks_run=["schema", "migrations"])
    text = report.render()
    assert "schema" in text
    assert "migrations" in text
    assert "ERROR" in text
    assert "table X missing" in text


def test_audit_report_render_clean_has_no_severity_labels():
    report = AuditReport(findings=[], checks_run=["schema"])
    text = report.render()
    assert "schema" in text
    assert "ERROR" not in text and "WARN" not in text


# --------------------------------------------------------------------------
# db_audit_command (CLI)
# --------------------------------------------------------------------------
def _patch_cli(monkeypatch, dbac, conn):
    """Point the command's injected deps at an in-memory conn + a stub run_log."""
    logged = {}
    monkeypatch.setattr(dbac, "get_connection", lambda *a, **k: conn)
    monkeypatch.setattr(dbac, "load_universe_map", lambda: {t: {} for t in UNIVERSE})
    monkeypatch.setattr(dbac, "load_portfolio_config", lambda: {})
    monkeypatch.setattr(dbac, "log", lambda *a, **k: logged.setdefault("args", a))
    return logged


def test_db_audit_command_clean_exits_zero_and_logs(monkeypatch, capsys):
    import src.cli.db_audit_command as dbac

    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date.today(), 100.0)
    conn.commit()
    logged = _patch_cli(monkeypatch, dbac, conn)

    with pytest.raises(typer.Exit) as ei:
        dbac.db_audit_command(json_output=False)

    assert ei.value.exit_code == 0
    out = capsys.readouterr().out
    assert "DB Audit" in out
    assert logged.get("args") is not None, "a run_log summary row must be written"
    assert logged["args"][0] == "db_audit"
    assert logged["args"][1] == "INFO"


def test_db_audit_command_errors_exit_one(monkeypatch, capsys):
    import src.cli.db_audit_command as dbac

    conn = make_conn()
    conn.execute("DROP TABLE alerts_log;")  # schema ERROR
    for t in UNIVERSE:
        _add_price(conn, t, date.today(), 100.0)
    conn.commit()
    logged = _patch_cli(monkeypatch, dbac, conn)

    with pytest.raises(typer.Exit) as ei:
        dbac.db_audit_command(json_output=False)

    assert ei.value.exit_code == 1
    assert logged["args"][1] == "ERROR"


def test_db_audit_command_json_output_is_valid(monkeypatch, capsys):
    import src.cli.db_audit_command as dbac

    conn = make_conn()
    for t in UNIVERSE:
        _add_price(conn, t, date.today(), 100.0)
    conn.commit()
    _patch_cli(monkeypatch, dbac, conn)

    with pytest.raises(typer.Exit):
        dbac.db_audit_command(json_output=True)

    data = json.loads(capsys.readouterr().out)
    assert data["exit_code"] == 0
    assert "findings" in data and "checks_run" in data


def test_db_audit_command_survives_missing_run_log_table(monkeypatch, capsys):
    """A DB so broken that run_log is gone must still print findings and exit by
    code, not crash on the summary write."""
    import src.cli.db_audit_command as dbac

    conn = make_conn()
    conn.execute("DROP TABLE run_log;")  # schema ERROR + summary write would fail
    for t in UNIVERSE:
        _add_price(conn, t, date.today(), 100.0)
    conn.commit()
    monkeypatch.setattr(dbac, "get_connection", lambda *a, **k: conn)
    monkeypatch.setattr(dbac, "load_universe_map", lambda: {t: {} for t in UNIVERSE})
    monkeypatch.setattr(dbac, "load_portfolio_config", lambda: {})
    # real log() against this conn would raise OperationalError; the command must
    # swallow it. Route log() at the real storage.log bound to this conn.
    monkeypatch.setattr(
        dbac, "log",
        lambda c, lvl, msg, **k: conn.execute(
            "INSERT INTO run_log (component, level, message) VALUES (?,?,?);",
            (c, lvl, msg),
        ),
    )

    with pytest.raises(typer.Exit) as ei:
        dbac.db_audit_command(json_output=False)

    assert ei.value.exit_code == 1
    assert "DB Audit" in capsys.readouterr().out


# --------------------------------------------------------------------------
# scripts/db_audit.py thin entry
# --------------------------------------------------------------------------
def _load_db_audit_script():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "db_audit.py"
    spec = importlib.util.spec_from_file_location("db_audit_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_db_audit_script_main_returns_exit_code_one(monkeypatch):
    mod = _load_db_audit_script()

    def _raise(**_):
        raise typer.Exit(1)

    monkeypatch.setattr(mod, "db_audit_command", _raise)
    assert mod.main() == 1


def test_db_audit_script_main_returns_zero_when_clean(monkeypatch):
    mod = _load_db_audit_script()
    monkeypatch.setattr(mod, "db_audit_command", lambda **_: None)
    assert mod.main() == 0
