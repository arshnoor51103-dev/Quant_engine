"""
Tests for ingest retry/backoff and fetch exit-code behaviour (F3).

CLAUDE.md: data fetch must never silently return stale data — transient
failures retry with backoff, and `quant fetch` exits non-zero when tickers
fail past the configured threshold so the daily run reports the failure.
"""
from __future__ import annotations

import pandas as pd
import pytest
import typer

import src.data.ingest as ing
import src.cli.main as cli


def test_ingest_retries_then_succeeds(monkeypatch):
    """A transient failure on the first attempt is retried and then succeeds."""
    calls = {"n": 0}

    def flaky(ticker, start, end):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient network error")
        return pd.DataFrame()  # empty -> 0 rows, but no exception

    monkeypatch.setattr(ing, "load_universe", lambda: [{"ticker": "VFV.TO"}])
    monkeypatch.setattr(ing, "latest_price_date", lambda t: None)
    monkeypatch.setattr(ing, "fetch_ticker", flaky)
    monkeypatch.setattr(ing, "upsert_prices", lambda rows: len(rows))
    monkeypatch.setattr(ing, "log", lambda *a, **k: None)
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)

    res = ing.ingest_universe(retries=3, backoff_seconds=0.0)
    assert res["VFV.TO"] == 0   # eventual success (0 rows inserted)
    assert calls["n"] == 2      # one retry


def test_ingest_marks_failure_after_exhausting_retries(monkeypatch):
    """All attempts failing leaves the ticker marked -1 (not silently 0)."""
    def always_fail(ticker, start, end):
        raise RuntimeError("down")

    monkeypatch.setattr(ing, "load_universe", lambda: [{"ticker": "VFV.TO"}])
    monkeypatch.setattr(ing, "latest_price_date", lambda t: None)
    monkeypatch.setattr(ing, "fetch_ticker", always_fail)
    monkeypatch.setattr(ing, "upsert_prices", lambda rows: len(rows))
    monkeypatch.setattr(ing, "log", lambda *a, **k: None)
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)

    res = ing.ingest_universe(retries=2, backoff_seconds=0.0)
    assert res["VFV.TO"] == -1


def test_fetch_exits_nonzero_when_all_fail(monkeypatch):
    """`quant fetch` must exit non-zero when ticker failures exceed the threshold."""
    monkeypatch.setattr(cli, "ingest_universe", lambda **k: {"VFV.TO": -1, "XIC.TO": -1})
    with pytest.raises(typer.Exit) as e:
        cli.fetch(years=20, full=False)
    assert e.value.exit_code != 0


def test_fetch_exits_zero_when_all_ok(monkeypatch):
    """`quant fetch` exits cleanly (no raise) when all tickers succeed."""
    monkeypatch.setattr(cli, "ingest_universe", lambda **k: {"VFV.TO": 5, "XIC.TO": 0})
    cli.fetch(years=20, full=False)  # must not raise
