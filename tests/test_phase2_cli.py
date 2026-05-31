"""
CLI-level tests for phase2 commands (F4).

`quant signals` must fail loud — exit non-zero on an unknown signal type and
when no price data is available — so the daily run cannot record a no-op signals
step as success.
"""
from __future__ import annotations

import pandas as pd
import pytest
import typer

import src.cli.phase2_commands as p2


def test_signals_unknown_type_exits_nonzero(monkeypatch):
    monkeypatch.setattr(p2, "load_universe", lambda: [{"ticker": "VFV.TO"}])
    with pytest.raises(typer.Exit) as e:
        p2.signals_command(signal_type="does_not_exist", save=False)
    assert e.value.exit_code != 0


def test_signals_empty_data_exits_nonzero(monkeypatch):
    monkeypatch.setattr(p2, "load_universe", lambda: [{"ticker": "VFV.TO"}])
    monkeypatch.setattr(p2, "price_series",
                        lambda t, lookback_days=0: pd.Series(dtype=float))
    with pytest.raises(typer.Exit) as e:
        p2.signals_command(signal_type="momentum", save=False)
    assert e.value.exit_code != 0
