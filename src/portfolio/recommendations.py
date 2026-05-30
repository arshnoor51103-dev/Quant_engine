"""
Trade Recommendation Engine (Phase 3 P0).

Pipeline:
  1. Compute combined signal per ticker: momentum × max(regime_score, 0)
     Stable tickers use equal weight (regime does not gate stable allocation in P0).
  2. Compute signal-proportional target weights within each bucket.
  3. Diff target weights vs current holdings to get per-ticker delta in dollars.
  4. Apply gates to each positive-delta ticker:
       - Signal gate:   combined <= 0 → SKIP
       - Cost gate:     expected_return < 2×spread + profit_floor → SKIP_COST
       - Min-hold gate: last buy < min_holding_days ago → MIN_HOLD
       - CRA gate:      warn at 20 trades, CRA_LIMIT at 24 (still shown, never suppressed)
  5. Return sorted list of TradeCard objects.

Design decisions (2026-05-20, LEARNING.md):
  - BUY-only in P0; sells deferred until NAV justifies trade-slot cost.
  - Signal-proportional weights (no Markowitz optimizer) — added in P3.2.
  - Stable bucket always allocated at equal weight; regime gates growth/dividend only.
  - Flat 0.05% spread proxy; spread_override hook in universe.yaml for Tier 3+.
  - Expected return = combined_score × anchor_return_annualized (backtest anchor).
  - --cash required when NAV=0; optional addition to existing NAV when NAV>0.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from ..signals.base import SignalResult
from ..signals.vol_regime import Regime, REGIME_SCORES, STABLE_TICKERS
from .model import Holding


class GateStatus(str, Enum):
    PASS = "PASS"
    CRA_WARN = "CRA_WARN"             # 20-23 trades used — BUY still recommended
    CRA_LIMIT = "CRA_LIMIT"           # 24 trades used — shown but flagged, Arsh decides
    SKIP_SIGNAL = "SKIP"              # combined signal <= 0
    SKIP_COST = "SKIP_COST"           # expected return below cost threshold
    MIN_HOLD = "MIN_HOLD"             # bought too recently (< min_holding_days)
    OVERWEIGHT = "OVERWEIGHT"         # bucket above tolerance — no additional buy
    BELOW_THRESHOLD = "BELOW_THRESH"  # optimizer weight change < rebalance_threshold


@dataclass
class TradeCard:
    """A single trade recommendation card."""
    ticker: str
    bucket: str
    action: str                       # "BUY" | "SELL" | "HOLD" | "WARN" | "SKIP"
    units: float | None               # units to trade (fractional, Wealthsimple-compatible)
    est_price: float | None           # latest close price in CAD
    delta_dollars: float | None       # target_value - current_value (negative for sells)
    combined_signal: float            # momentum × clamped_regime (or 1/n for stable)
    expected_return_pct: float | None # annualized, decimal (0.035 = 3.5%)
    gate_status: GateStatus
    gate_reason: str | None = None
    cost_estimate: float | None = None
    rec_id: int | None = None         # set after DB persist
    sell_reason: str | None = None    # "SIGNAL" | "DRIFT" | None (BUY/HOLD/SKIP)


def _clamped_regime_score(regime_result: SignalResult) -> float:
    """
    Extract base regime score, clamped to [0, +inf].

    Clamping to 0 in HIGH_VOL/CRISIS suppresses all growth/dividend buys
    without creating spurious signals from negative × negative momentum.
    """
    meta = regime_result.metadata or {}
    regime_str = meta.get("regime", "unknown")
    try:
        base = REGIME_SCORES[Regime(regime_str)]
    except (ValueError, KeyError):
        base = REGIME_SCORES[Regime.NORMAL]
    return max(base, 0.0)


def compute_combined_scores(
    momentum_result: SignalResult,
    regime_result: SignalResult,
) -> dict[str, float]:
    """
    Combined signal score per ticker.

    Growth/dividend: momentum × max(base_regime_score, 0)
      Clamping to 0 in HIGH_VOL/CRISIS suppresses buys without sign-flip artifacts.
    Stable: 1/n_stable (equal weight, always positive — regime does not gate bonds in P0).

    Reference: Phase 3 P0 design decision, LEARNING.md 2026-05-20.
    """
    clamped = _clamped_regime_score(regime_result)
    n_stable = len(STABLE_TICKERS)
    combined: dict[str, float] = {}
    for ticker, mom in momentum_result.scores.items():
        if ticker in STABLE_TICKERS:
            combined[ticker] = 1.0 / n_stable
        else:
            combined[ticker] = mom * clamped
    return combined


def compute_target_weights(
    combined_scores: dict[str, float],
    bucket_config: dict,
    universe_map: dict[str, dict],
) -> dict[str, float]:
    """
    Signal-proportional target weights within each bucket.

    Within each bucket, only tickers with combined_score > 0 receive weight,
    normalized to sum to the bucket's target allocation. If no ticker in a
    bucket is positive, that bucket's capital stays as cash (undeployed).

    Returns portfolio-level target weight per ticker (sum <= 1.0).
    """
    buckets: dict[str, list[str]] = {b: [] for b in bucket_config}
    for ticker, meta in universe_map.items():
        b = meta.get("bucket", "unknown")
        if b in buckets:
            buckets[b].append(ticker)

    target_weights: dict[str, float] = {}
    for bucket_name, tickers in buckets.items():
        bucket_target = bucket_config[bucket_name]["target"]
        positive = {
            t: combined_scores.get(t, 0.0)
            for t in tickers
            if combined_scores.get(t, 0.0) > 0.0
        }
        score_sum = sum(positive.values())
        for t in tickers:
            if t in positive and score_sum > 0.0:
                target_weights[t] = (positive[t] / score_sum) * bucket_target
            else:
                target_weights[t] = 0.0

    return target_weights


def generate_trade_cards(
    momentum_result: SignalResult,
    regime_result: SignalResult,
    holdings: list[Holding],
    portfolio_config: dict,
    universe_map: dict[str, dict],
    portfolio_nav: float,
    cash: float,
    annual_trade_count: int,
    last_buy_dates: dict[str, date | None],
    latest_prices: dict[str, float],
    optimized_weights: dict[str, float] | None = None,
) -> list[TradeCard]:
    """
    Full recommendation pipeline. Returns one TradeCard per universe ticker.

    Args:
        momentum_result:    output of MomentumSignal.generate()
        regime_result:      output of VolRegimeSignal.generate()
        holdings:           current holdings from get_holdings()
        portfolio_config:   loaded portfolio.yaml
        universe_map:       {ticker: metadata} from universe.yaml
        portfolio_nav:      current portfolio market value in CAD
        cash:               new cash to deploy in CAD (0.0 for rebalance-only run)
        annual_trade_count: executed trades in current calendar year (from trades table)
        last_buy_dates:     {ticker: date_of_last_buy_or_None}
        latest_prices:      {ticker: latest_close_price} for all universe tickers
        optimized_weights:  optional pre-computed portfolio-level weights from
                            BucketOptimizer.optimize(). When supplied, replaces the
                            default signal-proportional compute_target_weights output.

    Raises:
        ValueError: if portfolio_nav == 0 and cash == 0 (no capital to work with).
    """
    if portfolio_nav == 0.0 and cash == 0.0:
        raise ValueError(
            "NAV is $0.00 and no --cash amount provided. "
            "Use --cash to specify deployable capital (e.g. --cash 800)."
        )

    trading = portfolio_config["trading"]
    alloc_cfg = portfolio_config["allocation"]
    rebalance_cfg = portfolio_config.get("rebalance", {})

    spread_proxy: float = trading.get("spread_proxy", 0.0005)
    anchor_return: float = trading.get("anchor_return_annualized", 0.1398)
    profit_floor: float = trading.get("profit_floor", 0.005)
    multiplier: float = trading.get("trade_threshold_multiplier", 2.0)
    max_trades: int = int(trading.get("max_trades_per_year", 24))
    cra_warn: int = int(trading.get("cra_warn_threshold", 20))
    min_hold: int = int(trading.get("min_holding_days", 14))
    min_rebalance_trade: float = float(rebalance_cfg.get("min_rebalance_trade", 50.0))

    opt_cfg = portfolio_config.get("optimizer", {})
    rebalance_threshold: float = opt_cfg.get("rebalance_threshold_pct", 0.02)
    total_capital = portfolio_nav + cash

    combined_scores = compute_combined_scores(momentum_result, regime_result)
    if optimized_weights is not None:
        target_weights = optimized_weights
    else:
        target_weights = compute_target_weights(combined_scores, alloc_cfg, universe_map)

    holdings_map: dict[str, Holding] = {h.ticker: h for h in holdings}

    # Bucket-level actual allocation for overweight/drift detection
    bucket_actual: dict[str, float] = {b: 0.0 for b in alloc_cfg}
    if total_capital > 0:
        for ticker, h in holdings_map.items():
            b = universe_map.get(ticker, {}).get("bucket", "unknown")
            if b in bucket_actual:
                bucket_actual[b] += h.market_value / total_capital

    # Bucket overweight flags: True when actual > target + tolerance (exit tolerance band)
    bucket_overweight: dict[str, bool] = {
        b: bucket_actual.get(b, 0.0) > cfg.get("target", 0.0) + cfg.get("tolerance", 0.0)
        for b, cfg in alloc_cfg.items()
    }

    run_date = momentum_result.run_date
    cards: list[TradeCard] = []

    def _cra_gate(count: int) -> tuple[GateStatus, str | None]:
        if count >= max_trades:
            return (
                GateStatus.CRA_LIMIT,
                f"{count}/{max_trades} trades used this year — "
                "recommendation shown; Arsh decides whether to proceed",
            )
        if count >= cra_warn:
            return (
                GateStatus.CRA_WARN,
                f"{count}/{max_trades} trades used — "
                f"{max_trades - count} remaining this year",
            )
        return GateStatus.PASS, None

    for ticker, target_weight in target_weights.items():
        meta = universe_map[ticker]
        bucket = meta.get("bucket", "unknown")
        combined = combined_scores.get(ticker, 0.0)
        override = meta.get("spread_override")
        spread = override if override is not None else spread_proxy
        gate_threshold = multiplier * spread + profit_floor

        h = holdings_map.get(ticker)
        current_value = h.market_value if h else 0.0
        price = (h.last_price if h and h.last_price else None) or latest_prices.get(ticker)

        target_value = target_weight * total_capital
        delta = target_value - current_value

        # ── SELL path: signal turned negative on a held position ──────────
        if combined <= 0.0:
            if h and current_value > 0.0:
                # Full exit — sell all held units
                units_sell = h.units
                sell_delta = -current_value
                sell_exp_ret = abs(combined) * anchor_return

                # Gate: cost gate (symmetric with BUY)
                if sell_exp_ret < gate_threshold:
                    cards.append(TradeCard(
                        ticker=ticker, bucket=bucket, action="SKIP",
                        units=units_sell, est_price=price, delta_dollars=sell_delta,
                        combined_signal=combined, expected_return_pct=sell_exp_ret,
                        gate_status=GateStatus.SKIP_COST,
                        gate_reason=(
                            f"sell expected {sell_exp_ret*100:.2f}% < "
                            f"{gate_threshold*100:.2f}% threshold"
                        ),
                        sell_reason="SIGNAL",
                    ))
                    continue

                # Gate: min-hold (CRA — avoid rapid round-trips)
                last_buy = last_buy_dates.get(ticker)
                if last_buy is not None:
                    days_held = (run_date - last_buy).days
                    if days_held < min_hold:
                        cards.append(TradeCard(
                            ticker=ticker, bucket=bucket, action="SKIP",
                            units=units_sell, est_price=price, delta_dollars=sell_delta,
                            combined_signal=combined, expected_return_pct=sell_exp_ret,
                            gate_status=GateStatus.MIN_HOLD,
                            gate_reason=f"bought {days_held}d ago — min hold {min_hold}d (CRA)",
                            sell_reason="SIGNAL",
                        ))
                        continue

                # Gate: CRA annual trade count
                gate, reason = _cra_gate(annual_trade_count)
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="SELL",
                    units=units_sell, est_price=price, delta_dollars=sell_delta,
                    combined_signal=combined, expected_return_pct=sell_exp_ret,
                    gate_status=gate, gate_reason=reason,
                    cost_estimate=gate_threshold,
                    sell_reason="SIGNAL",
                ))
            else:
                # No holding — nothing to sell
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="SKIP",
                    units=None, est_price=price, delta_dollars=None,
                    combined_signal=combined, expected_return_pct=None,
                    gate_status=GateStatus.SKIP_SIGNAL,
                    gate_reason="negative or zero combined signal",
                ))
            continue

        # ── Positive signal: delta <= 0 means at/above target ─────────────
        if delta <= 0.0:
            b_actual = bucket_actual.get(bucket, 0.0)
            b_cfg = alloc_cfg.get(bucket, {})
            b_max = b_cfg.get("target", 0.0) + b_cfg.get("tolerance", 0.0)
            is_overweight = bucket_overweight.get(bucket, False)

            # Drift-driven SELL: bucket exited tolerance band and this ticker
            # has more value than its target allocation → partial trim
            if h and current_value > 0.0 and delta < 0.0 and is_overweight:
                abs_delta = abs(delta)
                units_trim = round(abs_delta / price, 2) if price else None

                # Gate: dollar floor (spread cost must be worth the correction)
                if abs_delta < min_rebalance_trade:
                    cards.append(TradeCard(
                        ticker=ticker, bucket=bucket, action="HOLD",
                        units=None, est_price=price, delta_dollars=delta,
                        combined_signal=combined,
                        expected_return_pct=combined * anchor_return,
                        gate_status=GateStatus.PASS,
                        gate_reason=(
                            f"drift correction ${abs_delta:.0f} < "
                            f"${min_rebalance_trade:.0f} floor"
                        ),
                    ))
                    continue

                # Gate: min-hold (CRA — avoid rapid round-trips)
                last_buy = last_buy_dates.get(ticker)
                if last_buy is not None:
                    days_held = (run_date - last_buy).days
                    if days_held < min_hold:
                        cards.append(TradeCard(
                            ticker=ticker, bucket=bucket, action="SKIP",
                            units=units_trim, est_price=price, delta_dollars=delta,
                            combined_signal=combined,
                            expected_return_pct=combined * anchor_return,
                            gate_status=GateStatus.MIN_HOLD,
                            gate_reason=f"bought {days_held}d ago — min hold {min_hold}d (CRA)",
                            sell_reason="DRIFT",
                        ))
                        continue

                # Gate: CRA annual trade count
                gate, reason = _cra_gate(annual_trade_count)
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="SELL",
                    units=units_trim, est_price=price, delta_dollars=delta,
                    combined_signal=combined,
                    expected_return_pct=combined * anchor_return,
                    gate_status=gate, gate_reason=reason,
                    cost_estimate=2 * spread,
                    sell_reason="DRIFT",
                ))
                continue

            # No sell needed — HOLD or OVERWEIGHT warning
            if is_overweight:
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="WARN",
                    units=None, est_price=price, delta_dollars=delta,
                    combined_signal=combined,
                    expected_return_pct=combined * anchor_return,
                    gate_status=GateStatus.OVERWEIGHT,
                    gate_reason=f"bucket {bucket} at {b_actual*100:.1f}% > {b_max*100:.1f}% max",
                ))
            else:
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="HOLD",
                    units=None, est_price=price, delta_dollars=delta,
                    combined_signal=combined,
                    expected_return_pct=combined * anchor_return,
                    gate_status=GateStatus.PASS,
                    gate_reason="at or above target weight",
                ))
            continue

        # ── BUY path: positive signal, capital needed ─────────────────────
        exp_ret = combined * anchor_return
        units = delta / price if price else None

        # Gate: rebalance threshold (optimizer mode only)
        if (
            optimized_weights is not None
            and rebalance_threshold > 0.0
            and total_capital > 0.0
        ):
            current_weight = current_value / total_capital if total_capital > 0.0 else 0.0
            weight_change = abs(target_weight - current_weight)
            if weight_change < rebalance_threshold:
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="HOLD",
                    units=None, est_price=price, delta_dollars=delta,
                    combined_signal=combined, expected_return_pct=exp_ret,
                    gate_status=GateStatus.BELOW_THRESHOLD,
                    gate_reason=(
                        f"weight change {weight_change*100:.2f}% < "
                        f"{rebalance_threshold*100:.0f}% threshold"
                    ),
                ))
                continue

        # Gate: cost gate
        if exp_ret < gate_threshold:
            cards.append(TradeCard(
                ticker=ticker, bucket=bucket, action="SKIP",
                units=units, est_price=price, delta_dollars=delta,
                combined_signal=combined, expected_return_pct=exp_ret,
                gate_status=GateStatus.SKIP_COST,
                gate_reason=(
                    f"expected {exp_ret*100:.2f}% < {gate_threshold*100:.2f}% threshold"
                ),
            ))
            continue

        # Gate: min-hold
        last_buy = last_buy_dates.get(ticker)
        if last_buy is not None:
            days_held = (run_date - last_buy).days
            if days_held < min_hold:
                cards.append(TradeCard(
                    ticker=ticker, bucket=bucket, action="SKIP",
                    units=units, est_price=price, delta_dollars=delta,
                    combined_signal=combined, expected_return_pct=exp_ret,
                    gate_status=GateStatus.MIN_HOLD,
                    gate_reason=f"bought {days_held}d ago — min hold {min_hold}d (CRA)",
                ))
                continue

        # Gate: CRA annual trade count
        gate, reason = _cra_gate(annual_trade_count)
        cards.append(TradeCard(
            ticker=ticker, bucket=bucket, action="BUY",
            units=units, est_price=price, delta_dollars=delta,
            combined_signal=combined, expected_return_pct=exp_ret,
            gate_status=gate, gate_reason=reason,
            cost_estimate=gate_threshold,
        ))

    # SELL first (risk-reduction), then BUY, then WARN, then HOLD, then SKIP
    _order = {"SELL": 0, "BUY": 1, "WARN": 2, "HOLD": 3, "SKIP": 4}
    cards.sort(key=lambda c: (_order.get(c.action, 9), -(abs(c.delta_dollars or 0.0))))
    return cards
