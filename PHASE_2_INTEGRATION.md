# PHASE 2 INTEGRATION GUIDE

> Instructions for Claude Code to integrate Phase 2 files into the existing quant_engine project.

## New Files to Add

Copy these into the existing project:

```
src/signals/base.py        ← signal ABC + SignalResult dataclass
src/signals/momentum.py    ← 12-1 month momentum (Jegadeesh-Titman)
src/signals/vol_regime.py  ← volatility regime detection
src/signals/__init__.py    ← replace existing empty file

src/backtest/__init__.py   ← new package
src/backtest/engine.py     ← walk-forward backtesting framework

src/api/__init__.py        ← new package
src/api/server.py          ← FastAPI dashboard server

src/cli/phase2_commands.py ← new CLI commands (signals, backtest, dashboard)

tests/test_signals.py      ← momentum signal unit tests
```

## Merge Into Existing main.py

Add these imports and commands to `src/cli/main.py`:

```python
# Add to imports section:
from .phase2_commands import signals_command, backtest_command, dashboard_command

# Add after existing commands:
app.command(name="signals")(signals_command)
app.command(name="backtest")(backtest_command)
app.command(name="dashboard")(dashboard_command)
```

## New Dependencies

Add to requirements.txt:
```
fastapi>=0.111.0
uvicorn>=0.30.0
```

Then run: `pip install -r requirements.txt`

## New Directories

Create if not present:
```
mkdir src\backtest
mkdir src\api
```

## Verify Integration

After merging, run:

```bash
# Tests should pass (existing + new)
pytest tests/ -v

# Signal generation should work
python -m src.cli.main signals --signal-type momentum
python -m src.cli.main signals --signal-type vol_regime

# Backtest should run
python -m src.cli.main backtest --signal-type momentum --years 5 --top-n 4

# Dashboard should launch
python -m src.cli.main dashboard
# Then open http://localhost:8501 in browser
```

## LEARNING.md Entry

Add this decision:

### 2026-05-19 — Phase 2: Signal engine + backtesting + API dashboard
**Context**: Phase 1 complete (data pipeline, metrics, CLI). Moving to signal generation.
**Decision**: Built three components simultaneously: (1) momentum + vol regime signals, (2) walk-forward backtesting framework, (3) FastAPI server for web dashboard.
**Rationale**: Signals without backtests are dangerous. Dashboard without signals has nothing to show. All three needed to land together for Phase 2 to be useful.

## What's Now Available

After integration:

1. **`quant signals`** — generate live signal scores for the universe
2. **`quant backtest`** — walk-forward test any signal against VFV benchmark
3. **`quant dashboard`** — launch local web UI at localhost:8501
4. **Momentum signal** — 12-1 month cross-sectional momentum (Jegadeesh-Titman 1993)
5. **Vol regime signal** — realized vol percentile → risk-on/off classification
6. **Backtest engine** — monthly rebalance, equal-weight top-N, full metrics vs benchmark
