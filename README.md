# Quant Engine

> Personal systematic investing engine. Daily signals, monthly execution, real money.

**Status**: Phase 1 — Foundation

---

## Setup

### 1. Drop the folder on E:\ drive

Recommended location:
```
E:\quant_engine\
```

If E:\ is small/external, fall back to:
```
C:\Users\Arshnoor singh sidhu\quant_engine\
```

Claude Code runs identically from either path — no main-drive constraint.

### 2. Open in Claude Code

```bash
cd E:\quant_engine
claude
```

Claude Code will pick up `CLAUDE.md` on launch.

### 3. Python environment

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Initialize database

```bash
python -m src.cli.main init
```

Creates `data/quant.db` with the schema.

### 5. First data pull

```bash
python -m src.cli.main fetch --years 20
```

Pulls 20 years of daily OHLCV for the 9 ETFs in `config/universe.yaml`.

### 6. View status

```bash
python -m src.cli.main status
python -m src.cli.main metrics
```

---

## CLI Commands

| Command | Purpose |
|---|---|
| `quant init` | Create SQLite schema |
| `quant fetch [--years N]` | Pull OHLCV for universe |
| `quant status` | Portfolio state + last-update timestamps |
| `quant metrics [--ticker X]` | Risk/return metrics |
| `quant universe` | List current asset universe |

(More commands added in Phase 2: `signals`, `recommend`, `backtest`.)

---

## Read These Before Changing Anything

1. **`CLAUDE.md`** — operating brief, hard constraints
2. **`LEARNING.md`** — decisions log, mistakes, open questions
3. **`docs/PHASE_1_ROADMAP.md`** — current phase milestones
4. **`docs/ARCHITECTURE.md`** — module boundaries

---

## Project Structure

```
quant_engine/
├── CLAUDE.md         ← Claude Code operating brief
├── LEARNING.md       ← rolling decisions + concepts log
├── README.md         ← this file
├── config/           ← portfolio + universe YAML
├── src/              ← all source
├── tests/            ← unit tests
├── docs/             ← phase plans, architecture
├── data/             ← SQLite db, parquet cache (gitignored)
└── logs/             ← daily run logs (gitignored)
```

---

## Hard Rules

- No live trading recommendation without a backtest behind the signal.
- No LLM in the signal generation path.
- Canadian-listed ETFs only at current capital tier.
- All decisions get logged in `LEARNING.md`.

---

*Real money. Real consequences. Build slow, test everything.*
