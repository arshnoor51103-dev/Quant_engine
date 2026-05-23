# Design: Within-Bucket Markowitz Optimizer (Phase 3 P2)

**Date**: 2026-05-22  
**Status**: Approved — proceeding to implementation  
**Author**: Claude Code (brainstorming session)

---

## Problem

The recommendation engine equal-weights tickers within each bucket by signal score.
With 5 growth tickers, equal-weight ignores covariance structure entirely.
Markowitz within-bucket optimization replaces this with a mean-variance efficient
allocation that respects concentration limits.

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Covariance estimator | Ledoit-Wolf via scikit-learn | Battle-tested, 3-line implementation |
| Stable bucket treatment | Equal-weight always | HSAV near-zero vol → optimizer collapses to ~95% HSAV / 5% VAB. P0 decision was explicit. |
| Expected returns proxy | `signal_i × annualized_vol_i` | Gives return-like units; higher-vol tickers need higher expected return to justify risk |
| Solver | scipy SLSQP | Handles equality + inequality constraints natively |
| Fallback | Equal-weight + warning | Never crash the pipeline |
| Integration | Optional `optimized_weights` param to `generate_trade_cards` | No breaking changes to P0 path |
| CLI | `--optimize` flag on `quant recommend` | Opt-in comparison vs equal-weight baseline |

---

## Architecture

```
quant recommend --cash 800 --optimize
       │
       ├─ MomentumSignal.generate()
       ├─ VolRegimeSignal.generate()
       ├─ BucketOptimizer.optimize()  ← NEW
       │      ├─ Growth bucket: LW covariance + SLSQP
       │      ├─ Stable bucket: equal-weight (skip optimizer)
       │      └─ Dividend bucket: LW covariance + SLSQP
       └─ generate_trade_cards(optimized_weights=...)
```

---

## `BucketOptimizer` class (src/portfolio/optimizer.py)

```python
class BucketOptimizer:
    def __init__(self, risk_aversion: float = 2.0, config: dict = {})
    def optimize(
        self,
        signal_scores: dict[str, float],
        price_history: dict[str, pd.Series],
        universe_map: dict[str, dict],
        bucket_config: dict,
    ) -> dict[str, float]  # portfolio-level weights
```

### Per-bucket flow (Growth and Dividend only)

1. Filter to tickers with `signal_score > 0` in bucket
2. Build daily return matrix, 252-day trailing
3. If any ticker has < 60 days history → equal-weight fallback for that bucket
4. `LedoitWolf().fit(returns)` — positive definite covariance guaranteed
5. `mu_i = signal_score_i × sqrt(252) × std(daily_returns_i)` — annualized
6. SLSQP: maximize `w'μ - (λ/2)w'Σw`
7. Constraints: `sum(w) = 1`, `w_i >= min_position_pct (0.05)`, `w_i <= max_position_pct (0.40)`
8. Fallback on solver failure
9. Multiply by bucket allocation target → portfolio-level weights

### Stable bucket
Fixed equal-weight: `1 / len(stable_tickers)` per stable ticker × stable bucket target.

---

## Config additions (portfolio.yaml)

```yaml
optimizer:
  risk_aversion: 2.0
  max_position_pct: 0.40
  min_position_pct: 0.05
  rebalance_threshold_pct: 0.02
```

---

## Integration points

- `recommendations.py`: `generate_trade_cards(..., optimized_weights: dict | None = None)`
- `phase3_commands.py`: `quant recommend --optimize`
- `requirements.txt`: add `scikit-learn>=1.4.0`

---

## Tests (tests/test_optimizer.py)

14 targeted tests covering: weight constraints, LW positive-definiteness, 2-ticker buckets,
single-ticker, degenerate signals, short-history, correlated duplicate series,
near-singular covariance, solver fallback, determinism, integration with trade cards.
