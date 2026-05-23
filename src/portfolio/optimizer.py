"""
Within-Bucket Markowitz Portfolio Optimizer (Phase 3 P2).

Replaces equal-weight proportional allocation with mean-variance optimized
weights within each bucket (Growth, Dividend). Stable bucket always uses
equal-weight because HSAV is a near-zero-vol cash equivalent — the optimizer
would collapse to ~95% HSAV / 5% VAB, which defeats diversification.

Math:
    Maximize  w'μ - (λ/2) * w'Σw
    Subject to:
        sum(w) = 1
        w_i >= min_position_pct  (for each included ticker)
        w_i <= max_position_pct

    μ_i = signal_score_i × annualized_vol_i
        Scales dimensionless signal ranks by realized volatility so the
        risk–return tradeoff is calibrated in return-like units.

    Σ = Ledoit-Wolf shrinkage estimator (sklearn.covariance.LedoitWolf).
        Sample covariance on 2–5 assets is near-singular and noise-dominated.
        Shrinkage toward the constant-correlation target is analytically
        optimal; no hyperparameter tuning required.

References:
    Markowitz, H. (1952). Portfolio Selection. Journal of Finance, 7(1), 77–91.
    Ledoit, O., & Wolf, M. (2004). A well-conditioned estimator for
        large-dimensional covariance matrices. Journal of Multivariate
        Analysis, 88(2), 365–411.
    Jegadeesh, N., & Titman, S. (1993). Returns to Buying Winners and
        Selling Losers. Journal of Finance, 48(1), 65–91. (signal source)

Design decisions (2026-05-22, LEARNING.md):
    - Stable bucket excluded: HSAV has near-zero vol → LW + SLSQP would
      over-concentrate. P0 equal-weight decision stands for stable.
    - Signal scores as expected return proxy: avoids using noisy historical
      means; signal IS the return forecast at monthly frequency.
    - Fallback to equal-weight on any failure: pipeline never crashes.
    - 252-day trailing window with 60-day floor: CHPS.TO ~1234 rows, safe.
"""
from __future__ import annotations

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from ..signals.vol_regime import STABLE_TICKERS

logger = logging.getLogger(__name__)

# Tickers that always use equal-weight (never run through the optimizer)
_EQUAL_WEIGHT_BUCKETS = frozenset({"stable"})

_MIN_HISTORY_DAYS = 60      # floor: below this → equal-weight fallback
_LOOKBACK_DAYS = 252        # trailing window for covariance estimation
_TRADING_DAYS_PER_YEAR = 252


def _annualized_vol(daily_returns: np.ndarray) -> float:
    """Annualized realized volatility from daily returns array."""
    if len(daily_returns) < 2:
        return 0.0
    return float(np.std(daily_returns, ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR))


def _equal_weights(n: int) -> np.ndarray:
    """Uniform weight vector summing to 1.0."""
    return np.full(n, 1.0 / n)


def _build_return_matrix(
    tickers: list[str],
    price_history: dict[str, pd.Series],
    lookback: int,
) -> tuple[np.ndarray, list[str]]:
    """
    Build a T × N matrix of daily log returns, aligned to a common date range.

    Returns (returns_matrix, valid_tickers). Tickers with < _MIN_HISTORY_DAYS
    rows are excluded so the caller can detect the short-history case.
    """
    series_map: dict[str, pd.Series] = {}
    for t in tickers:
        ps = price_history.get(t)
        if ps is None or ps.empty:
            continue
        ret = np.log(ps).diff().dropna()
        if len(ret) < _MIN_HISTORY_DAYS:
            logger.warning(
                "optimizer: %s has only %d days of return history (< %d min) — "
                "excluding from this bucket",
                t, len(ret), _MIN_HISTORY_DAYS,
            )
            continue
        # Trailing window
        series_map[t] = ret.iloc[-lookback:]

    if not series_map:
        return np.empty((0, 0)), []

    # Align on common dates (inner join)
    df = pd.DataFrame(series_map).dropna()
    if df.empty:
        return np.empty((0, 0)), []

    valid_tickers = list(df.columns)
    return df.values, valid_tickers


def _ledoit_wolf_cov(returns_matrix: np.ndarray) -> np.ndarray:
    """
    Ledoit-Wolf shrinkage covariance on T × N daily return matrix.

    LedoitWolf().fit() returns covariance in daily units.
    We annualize by multiplying by 252.

    Raises ValueError if the matrix is degenerate after shrinkage
    (all eigenvalues <= 0) — caller falls back to equal-weight.
    """
    lw = LedoitWolf(assume_centered=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lw.fit(returns_matrix)
    cov_daily = lw.covariance_
    cov_annual = cov_daily * _TRADING_DAYS_PER_YEAR

    eigenvalues = np.linalg.eigvalsh(cov_annual)
    if np.any(eigenvalues <= 0):
        raise ValueError(
            f"Ledoit-Wolf covariance has non-positive eigenvalues: {eigenvalues.min():.2e}"
        )
    return cov_annual


def _solve_qp(
    mu: np.ndarray,
    cov: np.ndarray,
    risk_aversion: float,
    min_w: float,
    max_w: float,
) -> Optional[np.ndarray]:
    """
    SLSQP quadratic program: maximize w'μ - (λ/2) * w'Σw.
    Equivalent to minimize -w'μ + (λ/2) * w'Σw.

    Returns weight vector or None if solver fails to converge.
    """
    n = len(mu)

    def objective(w: np.ndarray) -> float:
        return -w @ mu + 0.5 * risk_aversion * (w @ cov @ w)

    def grad(w: np.ndarray) -> np.ndarray:
        return -mu + risk_aversion * (cov @ w)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(min_w, max_w)] * n

    # Warm start: equal weight
    w0 = _equal_weights(n)
    # Clip to feasible region
    w0 = np.clip(w0, min_w, max_w)
    w0 = w0 / w0.sum()

    result = minimize(
        objective,
        w0,
        jac=grad,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    if not result.success:
        logger.warning(
            "optimizer: SLSQP did not converge — message: %s", result.message
        )
        return None

    w = np.array(result.x, dtype=float)
    # Numerical cleanup: clip and renormalize
    w = np.clip(w, 0.0, max_w)
    total = w.sum()
    if total <= 0.0:
        return None
    return w / total


def _optimize_bucket(
    tickers: list[str],
    signal_scores: dict[str, float],
    price_history: dict[str, pd.Series],
    risk_aversion: float,
    min_position_pct: float,
    max_position_pct: float,
) -> dict[str, float]:
    """
    Optimize within-bucket weights for a single bucket.

    Only tickers with positive signal scores participate.
    Returns within-bucket weights summing to 1.0.

    Falls back to equal-weight on any numerical failure.
    """
    # Only include tickers with positive signal scores
    included = [t for t in tickers if signal_scores.get(t, 0.0) > 0.0]

    if not included:
        # No positive signals — return zero weights (bucket undeployed)
        return {t: 0.0 for t in tickers}

    if len(included) == 1:
        # Single ticker — full allocation, no optimization needed
        return {t: (1.0 if t == included[0] else 0.0) for t in tickers}

    # Build return matrix
    ret_matrix, valid = _build_return_matrix(included, price_history, _LOOKBACK_DAYS)

    if len(valid) < len(included):
        excluded = set(included) - set(valid)
        logger.warning(
            "optimizer: excluded %s from optimization (insufficient history) — "
            "falling back to equal-weight for this bucket",
            excluded,
        )
        # Fallback: equal-weight among all included (even the short-history ones)
        n = len(included)
        w = {t: 1.0 / n for t in included}
        for t in tickers:
            if t not in w:
                w[t] = 0.0
        return w

    if len(valid) < 2:
        # Only one ticker survived history filter
        w = {t: (1.0 if t == valid[0] else 0.0) for t in tickers}
        return w

    n = len(valid)

    # Check feasibility: min_position_pct * n must be <= 1.0
    effective_min = min_position_pct
    if effective_min * n > 1.0:
        effective_min = 1.0 / n
        logger.warning(
            "optimizer: min_position_pct %.2f * %d tickers > 1.0 — "
            "clamping min to %.4f",
            min_position_pct, n, effective_min,
        )

    # Build expected return vector: mu_i = signal_i × annualized_vol_i
    mu = np.array([
        signal_scores.get(t, 0.0) * _annualized_vol(ret_matrix[:, i])
        for i, t in enumerate(valid)
    ])

    # Guard: if all mu are zero or negative, fall back to equal weight
    if np.all(mu <= 0.0):
        logger.warning(
            "optimizer: all expected returns <= 0 for %s — equal-weight fallback",
            valid,
        )
        w_arr = _equal_weights(n)
        w = {t: float(w_arr[i]) for i, t in enumerate(valid)}
        for t in tickers:
            if t not in w:
                w[t] = 0.0
        return w

    # Covariance
    try:
        cov = _ledoit_wolf_cov(ret_matrix)
    except (ValueError, np.linalg.LinAlgError) as exc:
        logger.warning(
            "optimizer: covariance estimation failed (%s) — equal-weight fallback",
            exc,
        )
        w_arr = _equal_weights(n)
        w = {t: float(w_arr[i]) for i, t in enumerate(valid)}
        for t in tickers:
            if t not in w:
                w[t] = 0.0
        return w

    # Solve QP
    w_arr = _solve_qp(mu, cov, risk_aversion, effective_min, max_position_pct)

    if w_arr is None:
        logger.warning(
            "optimizer: QP solver failed for %s — equal-weight fallback", valid
        )
        w_arr = _equal_weights(n)

    w = {t: float(w_arr[i]) for i, t in enumerate(valid)}
    # Tickers excluded from optimization (negative signal) get zero weight
    for t in tickers:
        if t not in w:
            w[t] = 0.0
    return w


class BucketOptimizer:
    """
    Mean-variance optimizer that works within each portfolio bucket independently.

    The optimizer does NOT change which tickers are selected — that is the signal's
    job. It changes how much capital goes to each selected ticker within its bucket.

    Stable bucket always uses equal-weight. Growth and Dividend are optimized.

    Usage:
        opt = BucketOptimizer(risk_aversion=2.0, config=portfolio_config)
        weights = opt.optimize(signal_scores, price_history, universe_map, bucket_config)
        # weights: {ticker: portfolio_level_weight} summing to <= 1.0
    """

    def __init__(
        self,
        risk_aversion: float = 2.0,
        config: dict | None = None,
    ) -> None:
        """
        Args:
            risk_aversion: lambda in w'μ - (λ/2)w'Σw. Higher = more conservative.
            config: full portfolio.yaml dict. Reads optimizer sub-block if present.
        """
        opt_cfg = (config or {}).get("optimizer", {})
        self.risk_aversion: float = opt_cfg.get("risk_aversion", risk_aversion)
        self.max_position_pct: float = opt_cfg.get("max_position_pct", 0.40)
        self.min_position_pct: float = opt_cfg.get("min_position_pct", 0.05)
        self.rebalance_threshold_pct: float = opt_cfg.get("rebalance_threshold_pct", 0.02)

    def optimize(
        self,
        signal_scores: dict[str, float],
        price_history: dict[str, pd.Series],
        universe_map: dict[str, dict],
        bucket_config: dict,
    ) -> dict[str, float]:
        """
        Compute portfolio-level target weights for all tickers.

        Args:
            signal_scores: {ticker: score} from MomentumSignal.generate().scores
            price_history:  {ticker: pd.Series} daily adjusted close prices
            universe_map:   {ticker: metadata} from universe.yaml
            bucket_config:  allocation block from portfolio.yaml (targets + tolerances)

        Returns:
            {ticker: weight} — portfolio-level weights (bucket_allocation × within_bucket_weight).
            Sum is <= 1.0 (may be less if some buckets have no positive signals).
        """
        # Group tickers by bucket
        buckets: dict[str, list[str]] = {b: [] for b in bucket_config}
        for ticker, meta in universe_map.items():
            b = meta.get("bucket", "unknown")
            if b in buckets:
                buckets[b].append(ticker)

        portfolio_weights: dict[str, float] = {}

        for bucket_name, tickers in buckets.items():
            bucket_target: float = bucket_config[bucket_name]["target"]

            if not tickers:
                continue

            if bucket_name in _EQUAL_WEIGHT_BUCKETS:
                # Stable bucket: always equal-weight regardless of signals
                within_weights = self._stable_equal_weights(tickers, signal_scores)
            else:
                within_weights = _optimize_bucket(
                    tickers=tickers,
                    signal_scores=signal_scores,
                    price_history=price_history,
                    risk_aversion=self.risk_aversion,
                    min_position_pct=self.min_position_pct,
                    max_position_pct=self.max_position_pct,
                )

            # Scale by bucket target allocation
            for ticker, w in within_weights.items():
                portfolio_weights[ticker] = w * bucket_target

        return portfolio_weights

    @staticmethod
    def _stable_equal_weights(
        tickers: list[str],
        signal_scores: dict[str, float],
    ) -> dict[str, float]:
        """
        Equal-weight allocation for the stable bucket.

        Matches Phase 3 P0 decision: stable bucket always equal-weight,
        regime does not gate bond allocation.

        All stable tickers receive equal weight regardless of signal scores,
        because the purpose of the stable bucket is to always have defensive
        exposure — it's not selected by signal.
        """
        n = len(tickers)
        if n == 0:
            return {}
        per_ticker = 1.0 / n
        return {t: per_ticker for t in tickers}
