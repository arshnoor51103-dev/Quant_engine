# Phase 1 Roadmap — Foundation

> Goal: stand up a working data pipeline + portfolio model + core metrics + CLI.
> No signals yet. No trade recommendations yet. Just the bedrock everything else stands on.

---

## Milestone 1 — Data Pipeline ✅ scaffolded
- [x] SQLite schema (`src/data/storage.py`)
- [x] yfinance ingester (`src/data/ingest.py`)
- [x] CLI: `quant init`, `quant fetch`
- [ ] **Verify on Claude Code**: run `quant fetch --years 20`, confirm 9 ETFs × ~5000 rows each in `data/quant.db`
- [ ] Handle yfinance rate limits + retries (Phase 1.5 polish)

## Milestone 2 — Portfolio Model ✅ scaffolded
- [x] Holdings dataclass (`src/portfolio/model.py`)
- [x] NAV calculation
- [x] Bucket allocation drift detection
- [ ] Trade entry helper (insert trade → update holdings) — Phase 1.5
- [ ] Tax-lot accounting (FIFO for ACB tracking) — Phase 1.5

## Milestone 3 — Core Risk Metrics ✅ scaffolded
- [x] daily/log returns
- [x] annualized return, vol, downside vol
- [x] Sharpe, Sortino, Calmar
- [x] Max drawdown
- [x] Beta, alpha
- [x] Rolling metric helper
- [x] Unit tests for all of the above
- [ ] **Verify**: `pytest tests/ -v` should pass before any new feature

## Milestone 4 — CLI Dashboard ✅ scaffolded
- [x] `quant init` — schema bootstrap
- [x] `quant fetch` — incremental data pull
- [x] `quant universe` — list current asset universe
- [x] `quant status` — NAV + holdings + bucket drift
- [x] `quant metrics` — risk/return per ticker
- [ ] `quant log` — recent ingest/system events
- [ ] `quant trade BUY VFV.TO --units 3 --price 142.50` — record a trade

## Milestone 5 — End-to-End Verification
- [ ] Fresh clone → init → fetch → metrics produces a clean run
- [ ] First real trade entered, NAV reflects correctly
- [ ] First monthly performance snapshot saved to `metrics_snapshots`
- [ ] `LEARNING.md` updated with any surprises from real data

---

## Out of Scope for Phase 1 (Don't Build These Yet)
- Signal generation (momentum, MR, regime) — Phase 2
- Portfolio optimization (Markowitz, Black-Litterman) — Phase 3
- Trade recommendations — Phase 4
- Phone alerts (Telegram bot) — Phase 4
- Web dashboard / phone UI — Phase 5

Building these prematurely without solid data + metrics underneath = compounded bugs.

---

## Definition of Done (Phase 1)
Phase 1 ships when:
1. All scaffolded modules pass `pytest`.
2. `quant fetch --years 20` completes for all 9 tickers.
3. `quant status` and `quant metrics` produce sensible output.
4. A real trade has been logged and reflects in `quant status`.
5. The first `metrics_snapshots` row has been written.

Then we move to Phase 2.
