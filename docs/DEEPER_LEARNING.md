# DEEPER LEARNING

Validated quantitative knowledge base for the Quant Engine project.

**Rules:**
1. Every entry has survived Council deliberation (Config G — Quantitative Research)
2. Append-only — never modify past entries; add new entries that reference and supersede
3. Convergence level is always stated — the reader knows if this is settled or contested
4. Math is the validated version, not raw research output
5. Status tracks lifecycle: THEORETICAL → CANDIDATE → ACTIVE (or REJECTED)

**Entry ID format:** DL-001, DL-002, ... (sequential, never reused)

---

## DL-001: Cross-Sectional Momentum (12-1 Month)

**Date:** 2026-05-22
**Classification:** NEW_ALGORITHM
**Status:** ACTIVE
**Council Convergence:** N/A — pre-dates Council system, validated via backtest
**Relevant Phase:** Phase 2 — Signal Generation

### Source
Canonical reference: Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling
Losers: Implications for Stock Market Efficiency." Journal of Finance, 48(1), 65-91.

### Mathematical Specification

R_i(t) = (P_i(t) - P_i(t-12)) / P_i(t-12)  — skip most recent month

Signal_i(t) = rank_normalize(R_i(t)) → [-1, +1]

Where:
- P_i(t) = adjusted close price of asset i at month t
- 12-month lookback with 1-month skip (avoids short-term reversal)
- Cross-sectional rank normalization across the ETF universe
- Top-N assets by rank are selected for equal-weight allocation

### Intuition
Assets that have outperformed over the past year (excluding the most recent month) tend to continue
outperforming in the near term. The 1-month skip avoids the well-documented short-term reversal
effect. This is one of the most robust anomalies in finance — documented across decades, geographies,
and asset classes.

### Assumptions
1. Momentum effect persists in Canadian-listed ETFs (less studied than US equities)
2. Monthly rebalance frequency is sufficient to capture the signal
3. The 12-1 lookback is appropriate for the current ETF universe (originally calibrated on stocks)
4. Transaction costs don't eat the alpha at our trade frequency

### Known Failure Modes
- Momentum crashes: sharp, violent reversals (e.g., March 2009) where winners become losers overnight
- Low-volatility regimes: signal strength weakens when cross-sectional dispersion is low
- Small universe: with only 9 ETFs, rank discrimination is coarse — limited cross-sectional spread

### Council Deliberation Summary
This entry pre-dates the Council system. Validation was performed via walk-forward backtest:
5-year period, top-4 selection, monthly rebalance, equal-weight. Results: +1.19% alpha vs VFV,
max drawdown -15.9% (within 20% ceiling), beta 0.685, Sortino 1.03. Strategy confirmed viable.

**Key Agreement:** N/A (backtest-validated)
**Key Tension:** N/A

### Quant Engine Integration
**Module affected:** src/signals/momentum.py
**Dependencies:** None beyond current stack (pandas, numpy)
**Implementation complexity:** Low — already implemented and running
**Interaction with existing signals:** Primary signal. Vol regime detector modulates position sizing.

### Cross-References
- Related DEEPER_LEARNING entries: DL-002, DL-003, DL-004
- Related LEARNING.md entries: Phase 2 integration bugs (5 bugs found and fixed)
- Supersedes: N/A

---

## DL-002: Discretionary Technical Analysis Pattern Strategies — Group Rejection

**Date:** 2026-05-23
**Classification:** LITERATURE_SCAN
**Status:** REJECTED
**Council Convergence:** UNANIMOUS
**Relevant Phase:** Phase 3 — Signal Generation (evaluated and ruled out)

### Source
- Fibonacci: ScienceDirect (2021). "Automatic identification and evaluation of Fibonacci
  retracements: Empirical evidence from three equity markets."
- Elliott Wave: D'Angelo, G. & Grimaldi, D. (2017). "The Effectiveness of the Elliott Waves
  Theory to Forecast Financial Markets." International Business Research, 10(6), 1–18.
- Chart Reversals: Lo, A.W., Mamaysky, H. & Wang, J. (2000). "Foundations of Technical
  Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation."
  Journal of Finance, 55(4), 1705–1765.
- Fair Value Gaps: ICT / Inner Circle Trader methodology (Michael Huddleston). No
  peer-reviewed academic source exists.

### Mathematical Specification

This entry covers four strategies evaluated as a group due to their shared failure mode.

**Fibonacci Retracements:**
Level_k = L + k × (H − L)   for k ∈ {0.236, 0.382, 0.500, 0.618, 0.786}
where H = swing high, L = swing low (subjectively identified)

**Elliott Wave wave-ratio constraints:**
Wave 3 ≥ 1.618 × Wave 1
Wave 2 retraces 38.2–61.8% of Wave 1 (Fibonacci ratios throughout)
5-wave impulse sequence + 3-wave corrective; fractal at all scales
→ wave identification is subjective; multiple valid counts coexist

**Head & Shoulders price target:**
Neckline = line through inter-shoulder troughs
Signal = Close < Neckline
Price target = Neckline − (Head − Neckline)   [rule of thumb, not derived]

**Fair Value Gap (3-candle definition):**
Bullish FVG:  High[i−2] < Low[i]   → imbalance zone = [High[i−2], Low[i]]
Bearish FVG:  Low[i−2]  > High[i]  → imbalance zone = [High[i], Low[i−2]]
Premise: price returns to fill the imbalance zone (mean-reversion hypothesis)

### Intuition

Fibonacci/Elliott Wave assert that Fibonacci ratios (derived from sequence convergence
to φ ≈ 1.618) govern price structure. Chart patterns assert that visual geometric
formations repeat predictably. Fair value gaps assert institutional order flow leaves
detectable imbalances that price later fills. All four are variations on the same claim:
past price geometry predicts future price direction.

### Assumptions
1. Golden ratio governs market price structure (Fibonacci, Elliott Wave)
2. Visual/geometric patterns in historical price data repeat predictably
3. Retail attention on Fibonacci levels creates sufficient focal-point trading flow
4. Markets move fast enough to leave detectable microstructure imbalances (FVG)
5. Monthly ETF rebalancing captures price patterns designed for intraday/daily use

### Known Failure Modes
- Fibonacci: Prices bounce at Fibonacci and non-Fibonacci zones with equal probability
  (ScienceDirect 2021); Fibonacci-based rules underperform buy-and-hold on broad equities
- Elliott Wave: Unfalsifiable — any price path fits a wave count post-hoc; multiple valid
  counts coexist at any point; "great accuracy" in EUR/USD 2009–2015 is a trend-following
  result, not Elliott Wave validation
- Chart Reversals: Lo et al (2000) found marginal significance on US equities 1962–1996;
  result has not been replicated on ETFs; any inefficiency documented 25 years ago has been
  traded away; patterns require continuous daily monitoring
- FVG: Zero peer-reviewed validation; designed for intraday forex/futures; at monthly ETF
  candle frequency the 3-candle rule detects extreme 3-month price gaps, not ICT imbalances
- ALL FOUR: H001 tested the mean-reversion hypothesis (reversal-adjacent) directly on this
  9-ETF universe: Sharpe −0.03, DD −24.2%, alpha −6.6%. KILLED 2026-05-22. Chart reversals
  and FVGs are mean-reversion hypotheses; H001 is the empirical answer for our system.
- Discretionary overlay risk: incorporating unfalsifiable tools creates pathways for human
  override of the systematic signal — literature shows this consistently underperforms the
  systematic signal alone (Kahneman, Thaler)

### Council Deliberation Summary
All five Council members voted REJECT independently, reaching UNANIMOUS convergence — the
rarest outcome. The Mathematician found no derivable predictive mechanism in any of the four.
The Empiricist cited H001's failure as directly dispositive for reversal-adjacent strategies
on this universe. The Skeptic steelmanned the focal-point argument for Fibonacci (retail
coordination on 61.8% levels) and dismissed it on the grounds that Canadian ETF markets are
institutionally dominated — the coordination mechanism does not operate. The Engineer found
nothing implementable for monthly ETF rebalancing. The Risk Manager added the behavioral
override risk as the primary danger: these tools invite discretionary exceptions to the
systematic process.

**Key Agreement:** All four strategies are REJECTED for the Quant Engine, on mathematical,
empirical, implementation, and behavioral grounds simultaneously.
**Key Tension:** None — no minority position survived the full evaluation.

### Quant Engine Integration
**Module affected:** N/A — not implemented, not to be implemented
**Dependencies:** N/A
**Implementation complexity:** N/A (Donchian/FVG trivially automatable; signal quality
                                   insufficient to justify any engineering)
**Interaction with existing signals:** H001 mean-reversion test already disposed of the
reversal hypothesis for this universe. DL-001 momentum captures trend continuation. No
gap remains that these four strategies could fill.

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (momentum, the signal these would compete with);
  DL-003 (systematized breakout, which IS defensible); DL-004 (Giordano MVCT, which IS
  defensible)
- Related LEARNING.md entries: H001 graveyard — mean reversion standalone, KILLED 2026-05-22
- Supersedes: N/A

---

## DL-003: Systematized Price Breakout — 52-Week High Momentum Variant

**Date:** 2026-05-23
**Classification:** NEW_ALGORITHM
**Status:** THEORETICAL
**Council Convergence:** STRONG_CONSENSUS
**Relevant Phase:** Phase 3 — Signal Generation (candidate for H002 hypothesis pipeline)

### Source
Canonical reference: George, T.J. & Hwang, C-Y. (2004). "The 52-Week High and Momentum
Investing." Journal of Finance, 59(5), 2145–2176.
Secondary: Fung, W. & Hsieh, D.A. (2001). "The Risk in Hedge Fund Strategies." Review of
Financial Studies, 14(2). (Donchian/trend-following analysis.)
ETF evidence: ScienceDirect (2020). "Empirical evidence on the profitability of momentum
trading strategies using ETFs."

### Mathematical Specification

**52-Week High Distance Factor (George & Hwang):**
H52_i(t) = max(Close_i(t−252d), ..., Close_i(t))
Dist_i(t) = (H52_i(t) − Close_i(t)) / H52_i(t)   ∈ [0, 1]

Cross-sectional ranking: sort assets by Dist ascending (lower Dist = price near 52-wk high)
Higher-ranked assets (near 52-wk high) are selected for long allocation.

This is scale-free, requires no subjective inputs, and is unambiguously automatable.

**Donchian N-day Channel (deprioritized):**
Upper_i(t) = max(Close_i(t−N), ..., Close_i(t))
Lower_i(t) = min(Close_i(t−N), ..., Close_i(t))
Signal_i(t) = +1 if Close_i(t) > Upper_i(t−1); −1 if Close_i(t) < Lower_i(t−1); 0 otherwise
At monthly frequency: largely collapses to the 12-1 momentum signal (high correlation).

### Intuition

Investors use the 52-week high as a behavioral anchoring point when assessing whether an
asset is "expensive" or "cheap." Positive news causes less adjustment when price is far below
the 52-week high (investors resist paying near-high prices). This produces predictable
cross-sectional return continuation: assets near their 52-week high keep outperforming.
Unlike 12-1 month momentum (DL-001), this mechanism has an explicit behavioral grounding in
Kahneman-Tversky anchoring theory, not just empirical observation.

### Assumptions
1. Anchoring bias persists among investors — reference point dependence is real
2. 252-day rolling max is the appropriate reference point (could be 200, 300 days)
3. Monthly resampling captures enough of the effect (designed for daily, tested for monthly)
4. The factor adds cross-sectional signal orthogonal to 12-1 month momentum in 9-ETF universe

### Known Failure Modes
- Crisis reversals: assets far from 52-week high (large Dist) outperform during recovery;
  the signal inverts exactly when momentum crashes (identical failure regime to DL-001)
- Orthogonality collapse: at 9-asset scale, rank correlation between 52-week high distance
  and 12-1 month momentum is likely > 0.8 (George & Hwang showed the factor subsumes 12-month
  momentum in cross-sectional regressions — they may be measuring the same thing)
- Lookback sensitivity: the 252-day window is conventional, not theoretically optimal

### Council Deliberation Summary
The Council accepted the George & Hwang factor as theoretically sound and empirically
validated (Journal of Finance, replicated internationally). The key debate: does it add
orthogonal signal beyond DL-001 in a 9-asset Canadian ETF universe? The Empiricist and
Risk Manager noted the two signals fail in the same regimes (momentum crashes), suggesting
correlated rather than orthogonal risk exposures. The Skeptic raised the likely > 0.8
cross-sectional rank correlation in a 9-asset universe. The Mathematician and Engineer
argued the theoretical independence of anchoring mechanism from trend measurement justifies
CANDIDATE status. The Chair ruled THEORETICAL pending backtest.

**Key Agreement:** The factor is legitimate and implementable; do not implement before testing
orthogonality in our specific universe.
**Key Tension:** Mathematician argues CANDIDATE; majority voted THEORETICAL. The resolution
is: route to hypothesis pipeline as H002, with orthogonality to DL-001 as the primary test.

### Minority Report
**Member:** The Mathematician
**Position:** The 52-week high factor has a theoretically independent mechanism (behavioral
anchoring) from 12-1 month momentum (trend continuation), cross-market empirical support at
Journal of Finance standard, and trivial implementation. This meets the CANDIDATE bar.
**Falsification:** Spearman rank correlation between 52-week high distance ranking and
12-1 momentum ranking > 0.85 over the full backtest period would justify downgrading to
THEORETICAL (essentially the same signal in this universe).

### Quant Engine Integration
**Module affected:** src/signals/momentum.py (add 252-day rolling max computation)
**Dependencies:** None beyond current stack — daily OHLCV already in SQLite
**Implementation complexity:** Low — 2 lines of pandas alongside existing momentum computation
**Interaction with existing signals:** Likely high correlation with DL-001; must be tested
for orthogonality before adding to signal composition

### Implementation Notes
Only applicable if H002 hypothesis passes backtest. If implemented:

  h52 = prices['Close'].rolling(252).max()
  dist_52w = (h52 - prices['Close']) / h52
  signal_52w = dist_52w.rank(ascending=True)   # lower dist = higher rank

Integration: percentile-rank alongside 12-1 momentum in the existing ranking pipeline.
If Spearman(rank_52w, rank_12_1) > 0.85, discard — DL-001 already captures this.

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (12-1 momentum — likely correlated); DL-004
  (Giordano MVCT — includes momentum component; look for synergy)
- Related LEARNING.md entries: H001 graveyard (mean reversion, inverse of breakout momentum)
- Supersedes: N/A

---

## DL-004: Giordano MVCT Ranked Asset Allocation Model

**Date:** 2026-05-23
**Classification:** NEW_ALGORITHM
**Status:** CANDIDATE
**Council Convergence:** STRONG_CONSENSUS
**Relevant Phase:** Phase 3 — Signal Generation + Portfolio Construction (multi-component)

### Source
Canonical reference: Giordano, G. (2018). "Ranked Asset Allocation Models." CMT Association
Journal. 2018 Charles H. Dow Award — highest prize in technical analysis practitioner research.
Secondary: Giordano, G. (2019). "Antifragile Asset Allocation Model." NAAIM Founders Award
paper (1st place, $5,000 prize). DOC: naaim.org/wp-content/uploads/2019/05/...
Replication: QuantSeeker blog — independent replication from Yahoo Finance data (confirmed
reproducible).

### Mathematical Specification

Four factors per asset i at time t. Each factor is percentile-ranked before summing.

**1. Momentum (M_i):** 4-month absolute return
M_i(t) = (Close_i(t) − Close_i(t−4m)) / Close_i(t−4m)
Note: differs from DL-001 (12-1 month lookback); captures intermediate momentum range.

**2. Volatility (V_i, inverted — lower vol ranks higher):**
V_i(t) = −σ_i(t,N)   where σ = rolling std of daily returns over N trading days

**3. Correlation (C_i, inverted — lower avg correlation ranks higher):**
C_i(t) = −(1/(n−1)) × Σ_{j≠i} ρ_ij(t,N)
where ρ_ij = Pearson correlation of daily returns (rolling N days)
Applied WITHIN each bucket, not at universe level (see Integration Notes).

**4. Trend (T_i):** ATR-normalized deviation from moving average
ATR_i(t) = rolling_mean(max(H−L, |H−C_{t-1}|, |L−C_{t-1}|), N)
T_i(t) = (Close_i(t) − SMA_i(t,N)) / ATR_i(t)

**Composite Rank:**
Rank_i(t) = PercentileRank(M_i) + PercentileRank(V_i) + PercentileRank(C_i) + PercentileRank(T_i)
Select top assets by lowest Total Rank within each bucket.

**Absolute Momentum Filter (Antonacci 2012 dual-momentum principle):**
Include asset i iff M_i(t) > 0; else replace with cash equivalent (HSAV.TO in stable bucket,
or raise bucket cash allocation to maximum permitted by 60±10/25±5/15±5 guardrails).

**Antifragile Extension (NOT applicable to current system):**
Tail risk hedge via long-volatility instruments (options, inverse ETFs) triggered by regime
signals. Unavailable: TFSA at Tier 1 has no options, no inverse ETFs.

### Intuition

The RAM combines four distinct dimensions of asset quality: momentum (trend continuation),
low volatility (the empirically documented low-vol anomaly — Ang et al 2006, Frazzini &
Pedersen 2014), diversification value (correlation to peers), and trend confirmation (ATR
normalization). Percentile-ranking before summation ensures equal-contribution from each
dimension, preventing scale-driven dominance. The absolute momentum filter (cash when M < 0)
acts as a defensive drawdown brake — equivalent to Antonacci's dual-momentum principle applied
at the asset level. The Antifragile extension adds tail-risk positioning, but this requires
instruments unavailable in our current TFSA tier.

### Assumptions
1. Low-volatility assets carry genuine outperformance (low-vol anomaly is real and persistent)
2. Lower average correlation to peers improves portfolio-level diversification
3. 4-month momentum captures a meaningful signal on Canadian ETFs (not validated for this
   specific universe — requires backtest)
4. ATR-normalized trend score adds signal beyond raw momentum (requires validation)
5. Absolute momentum filter reduces drawdown without unacceptable opportunity cost (requires
   backtest specifically on 2020 COVID crash and 2022 correction)
6. MVCT ranking discriminates meaningfully with 3-4 assets per bucket (uncertain for small
   sub-universes — the Skeptic's primary concern)

### Known Failure Modes
- Correlation collapse in crisis: all pairwise correlations approach 1 in severe crashes;
  C score degenerates to noise precisely when diversification matters most
- Small bucket problem: ranking 3-4 assets on 4 factors has limited discrimination; rank
  differences may be noise-dominated
- Lookback sensitivity: N must be chosen for σ, ρ, ATR, SMA — multiple free parameters;
  Giordano optimized on his universe (~30 ETFs); our universe is different
- Antifragile gap: without tail hedging, the model is a sophisticated momentum+quality ranking
  but not "antifragile" in Taleb's sense (asymmetric upside in crises is missing)
- Absolute momentum filter false signals: premature cash in temporary corrections costs
  dollar-cost-averaging efficiency for our $300-400/month contribution schedule

### Council Deliberation Summary
This is the strongest model evaluated in this session. The Mathematician validated the
percentile-ranking composite methodology as sound (Piotroski F-score analog). The Empiricist
emphasized the award provenance (Dow Award + NAAIM) and independent replication as strong
evidence of quality. All five members agreed the V component (inverted volatility = low-vol
anomaly) is a genuinely new, academically grounded signal not currently in the system. The
Skeptic's primary concern — correlation score C degenerates in small bucket sub-universes —
was addressed by the Engineer's Option A recommendation: apply within-bucket, not
universe-level. The Risk Manager flagged the absolute momentum filter's interaction with
contribution-based dollar-cost-averaging as requiring backtest. The Chair overruled the
Skeptic's preference for THEORETICAL status; CANDIDATE is appropriate given the quality
of the source evidence.

**Key Agreement:** The V component (low-vol anomaly) is the highest-confidence new addition;
the correlation score requires within-bucket application; route to hypothesis pipeline for
full backtest before any implementation.
**Key Tension:** Skeptic vs. majority on CANDIDATE vs. THEORETICAL status for overall model.
Within-bucket application addresses the correlation concern; the lookback parameter
sensitivity is the residual unresolved risk.

### Minority Report
**Member:** The Skeptic
**Position:** With 3-4 assets per bucket and 4 factor dimensions, the MVCT ranking has very
limited degrees of freedom. The model is designed for a universe ~3× larger. Factor rankings
within buckets of 3 ETFs may be noise-dominated. THEORETICAL status until a preliminary
correlation analysis shows the factors actually discriminate within our sub-universes.
**Falsification:** If Kendall's tau between any two MVCT factors within the Growth bucket
(4 assets) is consistently > 0.7, those factors are co-linear in our universe — reduce the
model to a 2-3 factor version before proceeding to full backtest.

### Quant Engine Integration
**Module affected:** src/signals/ (new signal module — `mvct_rank.py`); src/portfolio/model.py
(absolute momentum filter integration)
**Dependencies:** No new libraries. High/Low data already in SQLite (OHLCV stored by ingest.py).
ATR requires H/L/C — available.
**Implementation complexity:** Medium — new ATR + trend computation, correlation matrix per
bucket, ranking aggregation, absolute momentum filter. Estimated: ~150 lines of code + 20
unit tests.
**Interaction with existing signals:** V (volatility) overlaps with vol_regime signal —
clarify whether MVCT-V and vol_regime are computing the same thing or different. C (correlation)
is genuinely new. T (ATR trend) may overlap with momentum signal direction — quantify.

### Implementation Notes
Only applicable after H002 (or equivalent designation) passes backtest. Recommended protocol:

1. Test V component alone (low-vol anomaly) — highest academic confidence, cleanest test.
2. Test M_MVCT (4-month) vs M_DL001 (12-1) orthogonality — Spearman rank correlation.
3. Test C within-bucket — verify within-bucket correlation rankings are stable (not noise).
4. Test T (ATR trend) as standalone and in combination.
5. Test absolute momentum filter: measure drawdown reduction vs. missed upside on 2020, 2022.
6. Only implement full MVCT composite after individual components validate.

Specific integration architecture: Option A (within-bucket MVCT ranking). Each bucket's
assets ranked by MVCT; top-N per bucket selected; equal-weight within bucket (or feed as
expected-return input to existing Ledoit-Wolf optimizer — Option C, more elegant, to be
evaluated).

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (momentum signal — MVCT-M may overlap);
  DL-003 (52-week high factor — evaluate alongside MVCT-M before implementing either)
- Related LEARNING.md entries: Phase 3 P2 — Ledoit-Wolf optimizer (MVCT may modify
  weight inputs to this optimizer rather than replacing it)
- Supersedes: N/A

---

## DL-005: Momentum Backtest Methodology — Walk-Forward Protocol

**Date:** 2026-05-24
**Classification:** ALGO_CHECK
**Status:** ACTIVE (validates current implementation in DL-001)
**Council Convergence:** STRONG_CONSENSUS
**Evidence Quality:** Strong — 30+ years of replications across 20+ geographies
**Relevant Phase:** Phase 2/3 — Signal Generation (backtest validation for existing signal)

### Source Coverage
- Academic: 7 databases searched (training data, cutoff Aug 2025). All 7 returned relevant results.
- Practitioner: 10/10 sites checked (training data). Strong coverage: AQR, Alpha Architect, Robeco, Flirting with Models. Weak: Man, NAAIM, Vanguard, Bank of Canada.
- Replication: 6 independent studies confirmed.

### Source
Canonical reference: Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling
Losers." Journal of Finance, 48(1), 65-91.
Methodology refinement: Novy-Marx, R. (2012). "Is Momentum Really Momentum?" Journal of
Financial Economics, 103(3), 429-453.
Post-publication decay: McLean, R.D. & Pontiff, J. (2016). "Does Academic Research Destroy
Stock Return Predictability?" Journal of Finance, 71(1), 5-32.
Practitioner: Asness, Moskowitz & Pedersen (2013). "Value and Momentum Everywhere." Journal
of Finance. (AQR) / Gray & Vogel (2016). "Quantitative Momentum." (Alpha Architect)

### Mathematical Specification

**Formation and Holding Period (JT 1993 canonical):**
R_i(t-12, t-2) = [P_i(t-2) − P_i(t-14)] / P_i(t-14)   — 12-month return, skip most recent month
Cross-sectional rank: Signal_i = rank_normalize(R_i(t-12, t-2)) → [-1, +1]

**Skip-Month Convention (mandatory):**
The 1-month skip (use t-2, not t-1, as end of formation window) avoids contamination by
short-term reversal (Jegadeesh 1990). At ETF monthly frequency, bid-ask bounce is negligible
(ETF spreads <1bp), but the convention remains correct practice.

**Novy-Marx (2012) Intermediate-Horizon Refinement:**
R_i(t-12, t-7) = [P_i(t-7) − P_i(t-14)] / P_i(t-14)   — months 12 to 7 prior to portfolio
R_i(t-6, t-2) = recent component (months 6 to 2 prior) — adds noise, not signal
Finding: intermediate horizon drives nearly all cross-sectional predictability; recent 6
months contain noise. On a 9-ETF universe, this distinction likely collapses (too few assets
to discriminate rank between 12-7 and 12-1 formation windows).

**Look-Ahead Bias Prevention (critical):**
Rank assets using prices as of last trading day of month t-1.
Apply weights on first trading day of month t (or last day of month t-1 at close).
Never use any information from month t in computing the ranking.
Our SQLite query: `WHERE date <= rebalance_date` enforces this correctly.

**Overlapping Portfolio Construction (JT for tracking purposes only):**
JT paper constructs 1/K-weighted overlapping cohorts to smooth return estimation.
For implementation (single monthly rebalance), a single cohort at each month-end is correct.

**Post-Publication Decay (McLean & Pontiff 2016):**
58% lower post-publication return across 97 cross-sectional predictors. Momentum is in
this sample. Raw alpha ~1%/month → post-decay ~0.4%/month. Our backtest: +1.19% alpha
over 2019-2024 walk-forward period — this is a post-decay, post-cost result.

### Assumptions
1. Skip-month prevents short-term reversal contamination — validated; correct for our system
2. Monthly rebalance frequency captures the signal — validated by practitioner evidence
3. Post-publication decay already priced into walk-forward period (2019-2024 is post-decay)
4. Transaction costs for ETFs are low enough that momentum survives — validated (ETF spread negligible)
5. 9-ETF universe has sufficient cross-sectional dispersion for ranking to be meaningful
   (the Skeptic's unresolved concern — universe size limits rank discrimination)

### Source Coverage
| Source | Finding |
|--------|---------|
| AQR | Skip-month canonical; 12-1 formation; transaction cost models documented |
| Alpha Architect | Momentum quality (smooth path) reduces crash exposure; look-ahead bias |
| Robeco | Residual momentum reduces sector/factor contamination |
| Flirting with Models | Rebalancing timing luck; monthly-end convention reduces this |
| Man Institute | Momentum crowding and capacity constraints |
| Research Affiliates | Skeptical on timing ability; factor reliability concerns |
| Vanguard | Skeptical: costs erode premium for non-institutional |
| Bank of Canada | Momentum weaker in Canadian equities (smaller universe, sector concentration) |

### Replication Evidence
| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Jegadeesh & Titman (1993) | US | 1965-1989 | Confirmed: 1%/month alpha |
| Jegadeesh & Titman (2001) | US | 1990-1998 | Confirmed out-of-sample |
| Rouwenhorst (1998) | Europe | 1978-1995 | Confirmed |
| Asness et al (2013) | Multi-asset | 1972-2011 | Confirmed |
| McLean & Pontiff (2016) | US | Post-pub | 58% decay documented |
| Hou et al (2017) | US | Full | Confirmed (in 37 momentum anomaly sub-types) |

### Practitioner Consensus
Strong agreement across AQR, Alpha Architect, Robeco on: (1) skip-month is mandatory,
(2) transaction costs are material for stocks, minimal for ETFs, (3) momentum crashes are a
real tail risk requiring explicit risk management, (4) timing luck is real at monthly rebalance
frequency — fixed month-end convention reduces but doesn't eliminate.

### Known Failure Modes
- Momentum crashes: March 2009, post-COVID — winners reverse violently in recovery rallies
  (Daniel & Moskowitz 2016; AQR documented)
- Post-publication decay: 58% reduction (McLean & Pontiff) — already in our backtest window
- Timing luck: backtest results vary by rebalance date (Hoffstein / Newfound Research) —
  mitigated by fixed end-of-month convention
- Small universe: 9 ETFs has limited cross-sectional rank discrimination (unresolved)
- Bank of Canada: momentum is weaker in Canadian equity markets specifically

### Council Deliberation Summary
STRONG_CONSENSUS. Council validated the current implementation as correct: skip-month
enforced, look-ahead bias prevented via correct SQLite query, walk-forward period (2019-2024)
already incorporates post-publication decay. The Skeptic's concern about statistical power
with 9 assets is valid but irresolvable by methodology — it's a fundamental universe
constraint. Novy-Marx intermediate-horizon refinement (12-7 month) is a valid candidate for
sensitivity testing as a DL-001 addendum or H003.

**Key Agreement:** Current implementation is correct. Post-decay alpha is still positive on
our walk-forward. Skip-month and look-ahead prevention are both properly implemented.
**Key Tension:** Skeptic notes 9-asset universe limits rank discrimination — cannot be resolved
by methodology, only by expanding the universe (Tier 2+ trigger).

### Quant Engine Integration
**Module affected:** src/signals/momentum.py — implementation validated as correct
**Enhancement candidate:** Add Novy-Marx 12-7 month formation as alternative signal;
test correlation with current 12-1 signal in `tests/test_momentum.py`
**Implementation status:** ACTIVE — no changes required; sensitivity test optional

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (the signal itself); DL-003 (52-week high factor);
  DL-004 (MVCT — 4-month momentum component vs 12-1)
- Related LEARNING.md entries: Phase 2 signal implementation; Phase 3 P0 trade engine
- Supersedes: N/A

---

## DL-006: Mean Reversion Backtest Methodology — With Residual Reversal Variant

**Date:** 2026-05-24
**Classification:** ALGO_CHECK
**Status:** THEORETICAL (residual variant); raw reversal REJECTED for current system (see H001)
**Council Convergence:** STRONG_CONSENSUS
**Evidence Quality:** Strong (methodology); Weak (Canadian ETF / monthly applicability)
**Relevant Phase:** Phase 3 — Signal Generation (revisit conditions for Tier 2+ or weekly rebalance)

### Source Coverage
- Academic: 7 databases searched (training data, cutoff Aug 2025). 10 canonical and secondary papers.
- Practitioner: Robeco confirmed (key finding); AQR contextual; 6 of 10 sites had no content.
- Replication: 6 independent studies; mixed results in ETF and low-liquidity contexts.

### Source
Canonical: Jegadeesh, N. (1990). "Evidence of Predictable Behavior of Security Returns."
Journal of Finance, 45(3), 881-898.
Canonical: Lehmann, B.N. (1990). "Fads, Martingales, and Market Efficiency." Quarterly
Journal of Economics, 105(1), 1-28. [Note: commonly misattributed to JoF — published in QJE]
Residual variant: Blitz, D., Huij, J., Lansdorp, S. & Verbeek, M. (2013). "Short-Term
Residual Reversal." Journal of Financial Markets, 16(3), 477-504.
Microstructure: Roll, R. (1984). "A Simple Implicit Measure of the Effective Bid-Ask Spread."
Journal of Finance, 39(4), 1127-1139.
Cross-autocorrelation: Lo, A.W. & MacKinlay, A.C. (1990). "When Are Contrarian Profits Due
to Stock Market Overreaction?" Review of Financial Studies, 3(2), 175-205.

### Mathematical Specification

**Jegadeesh (1990) raw reversal:**
Signal_i(t) = −R_{i,t-1}   (negative of prior month return)
Portfolio: cross-sectional decile sort; long bottom decile (prior losers), short top
Holding period: 1 month. Formation period: 1 month.

**Lehmann (1990) contrarian weighting:**
w_i(t) ∝ −(R_{i,t-1} − R̄_{t-1})
where R̄_{t-1} = equal-weighted universe return at t-1
This is cross-sectional demeaning only — does NOT divide by cross-sectional standard deviation.

**Bid-ask contamination correction (Roll 1984):**
Effective spread: s = 2√(−Cov(ΔP_t, ΔP_{t-1}))
Negative autocovariance from bid-ask bounce mechanically generates apparent reversal signal.
At monthly ETF frequency: bid-ask bounce is negligible (<1bp for liquid ETFs).

**Boudoukh-Richardson-Whitelaw (1994) decomposition of measured reversal profit:**
π = π_{bid-ask} + π_{non-synchronous} + π_{genuine overreaction}
For Canadian ETFs at monthly frequency: π_{bid-ask} ≈ 0, π_{non-synchronous} ≈ 0.
Only π_{genuine overreaction} remains. Evidence that this component exists for ETFs: none.

**Blitz et al (2013) residual reversal (best variant, not tested on ETFs):**
Residual_i(t-1) = R_{i,t-1} − β̂_i × R_{mkt,t-1}   (CAPM residual)
Signal: −Residual_i(t-1)
β̂_i = OLS slope from regression of R_{i} on R_{mkt} over rolling N-day window
Result: 2× Sharpe vs raw return reversal; robust to transaction costs; tested on US stocks.

**H001 empirical result on our system (DISPOSITIVE):**
Raw z-score(20-day window) on 9-ETF universe:
Sharpe: −0.027, Max DD: −24.18%, Alpha: −6.59%, Correlation with momentum: +0.836
Kill criteria triggered: 4 of 5. KILLED 2026-05-22. See graveyard/H001.

### Assumptions
1. ETF monthly returns exhibit genuine mean reversion (NOT supported by H001)
2. Cross-sectional dispersion in 9 ETFs is sufficient for reversal signal (NOT supported — 
   H001 showed 0.836 correlation with momentum; ranking produces nearly identical portfolios)
3. Residual reversal requires >20 assets for stable beta decomposition (9 ETFs insufficient)
4. Monthly frequency is fast enough to capture reversal (Jegadeesh/Lehmann used weekly/monthly 
   on stocks; reversal profits concentrated in first trading day after ranking — Gutierrez & Kelley)

### Source Coverage
| Source | Finding |
|--------|---------|
| Robeco (2023) | Enhanced reversal (+ industry/factor momentum) = 2× Sharpe; premium from liquidity provision |
| Robeco (2011) | Residual reversal (CAPM residuals) = 2× Sharpe; robust post-cost |
| AQR | Short-term reversal as liquidity provision; profitability degrades with transaction costs |
| Alpha Architect | Context only; no specific mean reversion backtest content |
| Man, Verdad, Research Affiliates, Flirting with Models, NAAIM, Vanguard, Bank of Canada | No content found — practitioners have largely moved on from pure mean reversion |

### Replication Evidence
| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Jegadeesh & Titman (1995) | US | 1990-1993 | Confirmed, smaller magnitude |
| Gutierrez & Kelley (2008) | US | 1983-2003 | Confirmed (first trading day only — microstructure) |
| Hameed & Mian (2015) | 22 markets | 1980-2011 | Mixed — liquidity-dependent |
| Stivers & Sun (2010) | US | 1962-2004 | Confirmed; VIX-regime dependent |
| Blitz et al (2013) | US | 1926-2010 | Confirmed (residual variant; stronger) |
| H001 (this system) | CA ETFs | 2021-2026 | FAILED — see graveyard |

### Practitioner Consensus
Robeco (strongest practitioner voice): enhanced reversal (combining with industry/factor
momentum) and residual reversal (CAPM residuals) each deliver ~2× the Sharpe of raw reversal.
Premium is from liquidity provision (temporary supply-demand imbalances), not genuine 
overreaction. Raw mean reversion has been superseded by these enhanced variants.
6 of 10 practitioner sites: no content — the strategy has been largely abandoned or subsumed
into broader factor models at institutional level.

### Known Failure Modes
- Bid-ask bounce contamination: Roll (1984) — up to 50% of measured reversal is mechanical
  (not a concern for monthly ETFs, but academic studies may overstate reversal on stocks)
- Non-synchronous trading: thin markets inflate spurious autocorrelation (not ETF concern)
- Avramov et al (2006): half the reversal disappears when illiquid stocks excluded
- H001 structural failure on our system: universe too small, frequency too slow, high
  correlation with momentum signal, negative Sharpe (see full autopsy in graveyard)
- Residual reversal inapplicable at 9-ETF scale: beta estimation too noisy

### Council Deliberation Summary
STRONG_CONSENSUS. H001's kill verdict is validated. Raw mean reversion is REJECTED for the
current 9-ETF monthly system. The residual reversal variant (Blitz 2013) is theoretically
superior but structurally inapplicable at current tier (universe too small, frequency too
slow). Council directed: create H003 hypothesis file for residual reversal with explicit
Tier 2+ revisit conditions, THEORETICAL status.

**Key Agreement:** H001's kill verdict stands for raw reversal and likely for residual
reversal at the current tier. Mean reversion in any form requires Tier 2+ (25-40 individual
CA stocks) and preferably weekly rebalance capability.
**Key Tension:** Residual reversal has genuine academic support (Blitz 2013) — it should
not be permanently killed but shelved pending tier upgrade.

### Quant Engine Integration
**Module affected:** src/signals/mean_reversion.py — code complete, NOT in signal path
**Status:** Raw reversal: REJECTED (KILLED via H001). Residual variant: THEORETICAL,
SHELVED pending Tier 2+ and weekly rebalance capability.
**Revisit conditions:**
  1. Tier 2+ universe (25-40 individual CA stocks with genuine idiosyncratic returns)
  2. Weekly rebalance capability (CRA trigger: 24 trades hit OR NAV ≥ $5k)
  3. As position-sizing modifier only: tanh(z_ts) applied to momentum-selected tickers as
     caution flag (identified in H001 autopsy as the least problematic use case)

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (momentum — highly correlated, explained 0.836
  of H001 returns); DL-002 (discretionary reversal patterns — Group Rejection, same universe)
- Related LEARNING.md entries: H001 graveyard — mean reversion standalone, KILLED 2026-05-22
- Supersedes: N/A (H001 graveyard is the empirical record; this entry adds methodology context)

---

## DL-007: Volatility Targeting — Moreira-Muir Scaling

**Date:** 2026-05-24
**Classification:** NEW_ALGORITHM
**Status:** CANDIDATE (portfolio-level scaling modifier; requires backtest vs existing vol_regime)
**Council Convergence:** CONTESTED_RESOLVED (3–2 for CANDIDATE over THEORETICAL)
**Evidence Quality:** Mixed — pre-cost result strong; post-cost mixed; monthly frequency untested
**Relevant Phase:** Phase 3 — Portfolio Construction (position-sizing modifier)

### Source Coverage
- Academic: 7 databases searched. Canonical + 4 secondary papers + 2 challenges found.
- Practitioner: AQR, Research Affiliates confirmed; Verdad contextual; 7 of 10 not found.
- Replication: 3 studies — one strong confirmation, one failure after costs, one nuanced.

### Source
Canonical: Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." Journal of
Finance, 72(4), 1611-1644. SSRN: 2659431. NBER: w22208.
Challenge: Barroso, P. & Detzel, A.L. (2021). "Do Limits to Arbitrage Explain the Benefits
of Volatility-Managed Portfolios?" Journal of Financial Economics, 140(3), 744-767.
Extension: DeMiguel, V. et al. (2024). "A Multifactor Perspective on Volatility-Managed
Portfolios." Journal of Finance. DOI: 10.1111/jofi.13395.
Practitioner: AQR (2017). "Risk Everywhere: Modeling and Managing Volatility." Working Paper.
Research Affiliates (2024). "Harnessing Volatility Targeting in Multi-Asset Portfolios."

### Mathematical Specification

**Moreira-Muir core formula:**
f_t^managed = (c / RV_{t-1}) × f_t
where:
  f_t = original portfolio/factor return at time t
  RV_{t-1} = realized variance of past month = Σ_{d ∈ month t-1} r_d²  (sum of squared daily returns)
  c = scaling constant s.t. E[c / RV_{t-1}] = 1  (unconditional variance preserved)
  Equivalently: w_t ∝ 1 / RV_{t-1}  (inverse realized variance weighting)

The managed portfolio takes the same unconditional variance as the original — this is NOT
a fixed-target strategy; it redistributes variance exposure over time, scaling down in
high-vol months and up in low-vol months.

**Alternative fixed-target formulation (risk parity style):**
w_t = σ_target / σ̂_t
where σ̂_t = annualized realized vol = √(252 × RV_{t-1})
σ_target = desired annual portfolio volatility (e.g., 10%)

**Volatility estimator options (by estimation quality vs. lag):**
1. 21-day realized variance (Moreira-Muir default): Σ r_d² over 21 trading days
   Pros: no parameters; clean. Cons: ~31% standard error (chi-sq, ~21 df)
2. EWMA (λ=0.94, RiskMetrics): σ²_t = 0.94 σ²_{t-1} + 0.06 r²_{t-1}
   Pros: responsive; downweights old data. Cons: one free parameter (λ)
3. GARCH(1,1): σ²_t = ω + α r²_{t-1} + β σ²_{t-1}
   Pros: most theoretically sound; Cons: 3 parameters, estimation risk
Best choice for our system: 21-day realized variance (no parameters, consistent with M&M)

**Condition for Sharpe ratio improvement (the key mathematical claim):**
d E[SR_t] > 0 if Corr(E[r_{t+1}], σ²_t) < 0
i.e., strategy improves Sharpe iff expected returns are negatively correlated with variance.
Equities: YES (leverage effect — vol spikes during drawdowns, returns recover after)
Bonds (VAB.TO): AMBIGUOUS — rate-driven vol may correlate positively with returns
HISA (HSAV.TO): NO — return is the daily interest rate, no vol-return relationship

### Assumptions
1. Volatility clustering holds for Canadian-listed ETFs (VFV.TO, XIC.TO) — LIKELY TRUE
2. Negative return-volatility correlation (leverage effect) holds for equity ETFs — LIKELY TRUE
3. At monthly rebalance, the 21-day realized variance estimate is timely enough to be
   informative (the signal may have largely resolved by month-end) — UNCERTAIN
4. Transaction costs of monthly weight adjustment are negligible — TRUE for ETFs (<0.1%)
5. Vol targeting at portfolio level does not double-count the existing vol_regime signal —
   REQUIRES TESTING (critical interaction; see Engineering note)

### Source Coverage
| Source | Finding |
|--------|---------|
| AQR | Panel-based vol estimation improves forecasts; utility framework shows implementation costs matter |
| Research Affiliates | Multi-asset vol targeting works; regime-dependent; costs non-trivial |
| Verdad | Trend following (related) destroys value returns — warning on vol-scaling + value interaction |
| Man Institute, Alpha Architect, Robeco, Newfound Research, NAAIM, Vanguard, Bank of Canada | No content found — practitioner coverage sparse vs academic |

### Replication Evidence
| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Moreira & Muir (2017) | US | 1927-2012 | Confirmed: +50-100% Sharpe for market + factors |
| Barroso & Detzel (2021) | US | 1963-2018 | MIXED: market OK after costs; factor portfolios → 0 |
| DeMiguel et al (2024) | US | 1963-2022 | Mixed: multifactor complexity reduces gains |

### Practitioner Consensus
AQR validates vol modeling framework; emphasizes transaction cost modeling is critical.
Research Affiliates confirms multi-asset applicability but with regime caveats.
Verdad's finding that trend following destroys value returns is a warning: volatility-scaling
strategies interact with style exposures in complex ways; cannot be assumed additive.

### Known Failure Modes
- Transaction cost erosion: Barroso & Detzel (2021) — factor portfolio alpha goes to zero
  after costs at daily rebalancing. Monthly rebalancing substantially reduces this concern.
- Monthly rebalancing delay: by the time monthly RV is computed, the vol regime may have
  shifted. This is the primary reason to expect weaker results than Moreira-Muir's daily paper.
- Vol estimate precision: 21-day window has ~31% standard error (chi-squared distribution,
  ~21 df) — scaling by a noisy estimate introduces measurement error into position sizing.
- Double-counting: vol_regime signal already modulates signal strength. Stacking vol targeting
  on top may over-penalize high-vol periods and reduce returns without proportional risk reduction.
- Leverage effect absent in stable bucket: VAB.TO and HSAV.TO likely do not exhibit the
  negative return-vol correlation that makes the formula work. Apply to EQUITY bucket only.

### Council Deliberation Summary
CONTESTED_RESOLVED (3–2 CANDIDATE). Mathematician, Empiricist, Engineer voted CANDIDATE
on grounds that: monthly rebalance reduces the cost problem, equity ETF leverage effect holds,
and the interaction with vol_regime can be tested directly. Skeptic and Risk Manager voted
THEORETICAL on grounds that: vol estimate precision (31% std error on 21-day window) makes
the scaling noisy, and double-counting with vol_regime is unquantified risk.
Chair resolved: CANDIDATE subject to two mandatory backtest conditions.

**Key Agreement:** Vol targeting at portfolio level (not per-signal) is the correct scope.
Equity bucket ETFs satisfy the negative return-vol correlation condition. Monthly rebalance
substantially reduces the transaction cost objection vs daily-rebalanced academic papers.
**Key Tension:** Skeptic/Risk Manager on vol estimate precision and double-counting risk.
**Minority Report — Skeptic:** Realized variance with 21-day window has ~31% standard error.
We are scaling portfolio weights by a quantity with 31% measurement noise. The improvement
may be within estimation error. Falsification: compare managed vs unmanaged Sharpe at monthly
frequency using EWMA (more precise) vs realized variance — if they diverge by >0.1 Sharpe,
the estimate precision matters and EWMA should be the default.

### Implementation Notes
Route to hypothesis pipeline as H004 (portfolio-level vol scaling modifier).
Pre-backtest requirements:
1. Compute Corr(momentum_signal, RV_t) for each equity ETF — verify leverage effect holds.
2. Compute Corr(vol_regime_score, RV_t) — quantify overlap with existing signal.
   If Corr > 0.85: vol targeting is redundant, do not implement.
3. Test 21-day RV vs EWMA — which produces better out-of-sample Sharpe?
4. Apply vol targeting to EQUITY BUCKET ONLY (not stable). Stable bucket (VAB, HSAV)
   is already near-zero equity beta; vol scaling adds noise, not signal.

Candidate implementation (if H004 passes):
  rv_monthly = daily_returns.resample('ME').apply(lambda r: (r**2).sum())
  scale_t = c / rv_monthly.shift(1)  # use PRIOR month RV, not current (look-ahead)
  c = rv_monthly.mean()              # unconditional mean as scaling constant
  position_t *= scale_t              # apply before cost gate, after signal ranking

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (momentum — primary signal to be modified);
  DL-004 (MVCT — V component is low-vol anomaly, related but distinct from vol targeting);
  DL-005 (momentum backtest methodology — walk-forward framework applies here too)
- Related LEARNING.md entries: Phase 3 P2 — Ledoit-Wolf optimizer (vol targeting modifies
  inputs to optimizer, or is an alternative layer)
- Supersedes: N/A

---

## DL-008: Pair Trading via Cointegration — Backtesting Framework

**Date:** 2026-05-24
**Classification:** NEW_ALGORITHM
**Status:** SHELVED — structurally incompatible with current system; viable at Tier 3+ non-registered
**Council Convergence:** UNANIMOUS
**Evidence Quality:** Strong (methodology); verdict is CLEAR for our constraints
**Relevant Phase:** Future (Tier 3+, non-registered account)

### Source Coverage
- Academic: 7 databases searched (training data, cutoff Aug 2025). 12 papers including canonical.
- Practitioner: 0 of 10 sites had specific pairs trading content — complete practitioner absence.
- Replication: 4 independent studies; declining post-2002; cointegration variant more robust.

### Source
Canonical: Gatev, E., Goetzmann, W.N. & Rouwenhorst, K.G. (2006). "Pairs Trading: Performance
of a Relative-Value Arbitrage Rule." Review of Financial Studies, 19(3), 797-827.
Cointegration basis: Engle, R.F. & Granger, C.W.J. (1987). "Co-integration and Error
Correction." Econometrica, 55(2), 251-276.
Johansen test: Johansen, S. (1991). "Estimation and Hypothesis Testing of Cointegration
Vectors." Econometrica, 59(6), 1551-1580.
Performance update: Do, B.H. & Faff, R. (2010). "Does Simple Pairs Trading Still Work?"
Financial Analysts Journal, 66(4), 83-95.
Cost analysis: Do, B.H. & Faff, R. (2012). "Are Pairs Trading Profits Robust to Trading Costs?"
Journal of Financial Research, 35(2), 261-287.
Survey: Krauss, C. (2017). "Statistical Arbitrage Pairs Trading Strategies: Review and Outlook."
Journal of Economic Surveys, 31(2), 513-545.

### Mathematical Specification

**Pair Selection — Distance Method (Gatev 2006):**
Normalised prices: P̃_i(t) = P_i(t) / P_i(t_0)
Pair distance (SSD): Σ_{t ∈ formation} [P̃_i(t) − P̃_j(t)]²
Select top-N pairs by lowest SSD. No formal stationarity test.
Limitation: Does not verify mean reversion; can select trending divergent pairs.

**Pair Selection — Cointegration Method (superior post-2002):**
Step 1: OLS regression:  log(P_i,t) = α + β·log(P_j,t) + ε_t
Hedge ratio β̂ from OLS (or Kalman filter for time-varying β)
Step 2: Augmented Dickey-Fuller test on residual ε̂_t:
  H₀: unit root (no cointegration); reject if ADF stat < critical value (p < 0.05)
  Note: unadjusted 5% threshold is generous — with N(N-1)/2 pairs tested, Bonferroni
  correction lowers threshold (for 36 pairs: p < 0.05/36 ≈ 0.0014)

**Spread and Signal:**
Spread: S(t) = log(P_i,t) − β̂·log(P_j,t) − α̂
z-score: z(t) = [S(t) − μ_S] / σ_S   (μ_S, σ_S from formation period — fixed, not rolling)
Entry LONG spread (buy i, sell j): z(t) < −2.0
Entry SHORT spread: z(t) > +2.0
Exit: z(t) → 0 (or end of trading period if no convergence)
Stop-loss: |z(t)| > 3.5 (common practitioner convention — no academic consensus)

**Formation and Trading Windows:**
Formation: 12 months (use to select pairs and estimate μ_S, σ_S)
Trading: 6 months (non-overlapping; formation statistics fixed throughout trading period)
Look-ahead: formation stats must be computed ONLY from formation-period data — any use of
trading-period data to update μ_S or σ_S introduces look-ahead bias.

**Declining Profitability (Do & Faff 2010):**
Distance method: 0.86%/month (1962-1988) → 0.37% (1989-2002) → 0.24% (2003-2009)
After transaction costs: distance method near zero; cointegration variant more robust.

### Assumptions
1. Two assets share a stable long-run equilibrium (cointegration is stationary) — requires
   testing over the specific universe and time period
2. Spread mean-reverts within the 6-month trading period — requires stable OU parameters
3. Transaction costs ≤ expected profit from spread — critical; Do & Faff (2012) shows
   this fails for distance method
4. Universe large enough for meaningful pair selection (minimum ~20 assets recommended)
5. Monthly rebalance sufficient — VIOLATED: pairs entry/exit occurs over days-to-weeks,
   not months

### Source Coverage
| Source | Finding |
|--------|---------|
| AQR, Man Institute, Verdad, Alpha Architect, Research Affiliates, Flirting with Models, Robeco, NAAIM, Vanguard, Bank of Canada | No content found (0/10 sites) — complete practitioner absence is a meaningful signal; strategy has been superseded or absorbed into broader factor/ML frameworks at institutional scale |

### Replication Evidence
| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Do & Faff (2010) | US | 2003-2009 | MIXED: declining to 0.24%/month; still works in crises |
| Do & Faff (2012) | US | Full | FAILED (costs): distance method → zero net profit |
| Caldeira & Moura (2013) | Brazil | 2005-2012 | Confirmed (cointegration): ~16% annualised alpha |
| Broussard & Vaihekoski (2012) | Finland | 1987-2008 | Mixed: profitable in liquid pairs only |

### Practitioner Consensus
Complete absence (0/10 verified practitioner sites). Krauss (2017) survey notes that
institutional practitioners have migrated from pure pairs trading to broader stat arb
(PCA/factor-residual models) and machine learning methods. The 0/10 practitioner absence
is a stronger signal than any single "no content found" — it suggests the edge is either
proprietary (unlikely given its long history), arbitraged away at institutional scale, or
subsumed into superior multi-pair frameworks.

### Known Failure Modes
- **Universe too small:** 9 ETFs = 36 possible pairs; after Bonferroni-corrected cointegration
  test (p < 0.0014), likely 0-1 valid pairs — insufficient for any portfolio
- **Frequency mismatch:** Pairs trading profits accrue over hours-to-days; monthly rebalance
  misses the signal entirely. Entry at month-end after divergence may capture no convergence.
- **CRA trade count:** Pair entry/exit = 2 legs × N_pairs × 12 months >> 24-trade annual limit.
  This alone is a structural disqualifier for TFSA.
- **ETF structural binding:** ETF creation/redemption mechanism prevents large persistent
  spread deviations between related ETFs — the arbitrage mechanism is already in the market
  structure, leaving no spread for individual investors to exploit.
- **Post-2002 alpha decline:** Do & Faff documented declining profitability; costs eliminate
  the distance-method edge.

### Council Deliberation Summary
UNANIMOUS. All five members independently found the strategy structurally incompatible with
the current system on at least one hard constraint: (1) CRA 24-trade limit — fatal alone;
(2) 9-ETF universe too small for meaningful pair selection; (3) monthly rebalance mismatches
with pairs convergence timing; (4) ETF creation/redemption prevents persistent spread
deviations (Risk Manager). The Skeptic steelmanned one possible use case — XIC/VFV relative
value spread — but conceded it would be a multi-month relative value bet, not classical
pairs trading, and it would require weekly or daily rebalancing to capture the signal.

**Key Agreement:** SHELVED (not KILLED) because the cointegration methodology is sound and
applicable at Tier 3+ with individual stocks and a non-registered account with higher
trade frequency tolerance.
**Key Tension:** None — unanimous on both the strategy's theoretical validity and its
current inapplicability.

### Quant Engine Integration
**Module affected:** None — no implementation. SHELVED.
**SHELVED unlock conditions:**
  1. Non-registered (non-TFSA) account opened (removes CRA trade-count constraint)
  2. Tier 3+ universe: ≥25 liquid Canadian-listed equities or US-listed instruments
  3. Rebalance frequency: weekly minimum (to capture days-to-weeks convergence window)
  4. Cointegration variant only (not distance method): Do & Faff (2012) shows distance
     method fails after costs; cointegration + transaction cost model required

### Cross-References
- Related DEEPER_LEARNING entries: DL-006 (mean reversion methodology — shares z-score
  framework and shares the structural frequency-mismatch failure on this system)
- Related LEARNING.md entries: H001 graveyard (mean reversion killed for same structural reasons)
- Supersedes: N/A

---

## DL-009: Fibonacci Retracements — Technical Analysis Support/Resistance Tool

**Date:** 2026-05-25
**Classification:** NEW_ALGORITHM
**Status:** REJECTED
**Council Convergence:** STRONG_CONSENSUS
**Evidence Quality:** Weak
**Relevant Phase:** N/A — rejected before any phase implementation

### Source
Canonical reference (skeptical, largest systematic test):
Tsinaslanidis, P., Guijarro, F., & Voukelatos, N. (2021). "Automatic identification and
evaluation of Fibonacci retracements: Empirical evidence from three equity markets."
Expert Systems with Applications, 187, 115893.

Partial positive result (sole positive paper, unreplicated preprint):
Shanaev, S. & Gibson, R. (2022). "Can Returns Breed Like Rabbits? Econometric Tests for
Fibonacci Retracements." SSRN Working Paper 4212430.

Secondary sources consulted: Gurrib, Nourani & Bhaskaran (2022) Financial Innovation;
Aggarwal et al. (City University London, DJIA clustering study); Bhattacharya & Kumar
(2006) Annals of Economics and Finance; Erdogan & Doguc (2012) SSRN 2011743;
Khan & Rehman (2022) Journal of Management Info; Sethi et al. (2020) SSRN 3701439;
Lo, Mamaysky & Wang (2000) Journal of Finance 55(4).

### Mathematical Specification
Retracement level for a price move from swing high H to swing low L:

  R_k = H − f_k × (H − L)     [downswing retracement; flip for upswing]

Where:
- H = identified swing high price
- L = identified swing low price
- f_k ∈ {0.236, 0.382, 0.500, 0.618, 0.786} — the canonical Fibonacci levels
- φ = (1+√5)/2 ≈ 1.6180 — the golden ratio

Derivation of Fibonacci ratios from φ:
  f₁ = 1/φ² ≈ 0.382
  f₂ = 1/φ  ≈ 0.618
  f₃ = 1 − 1/φ² ≈ 0.236

COUNCIL-VALIDATED NOTE: 0.500 is NOT a Fibonacci ratio. It is not derivable from φ
by any Fibonacci operation. Its presence in the canonical set is a practitioner convention.
Its empirical significance in Shanaev & Gibson (2022) likely reflects mean-reversion
tendencies around the midpoint of any price range, not Fibonacci mathematics per se.

Zone construction (Tsinaslanidis 2021):
  Zone_k = [R_k − ε, R_k + ε]
where ε is a free parameter calibrated empirically. No closed-form or theoretically
motivated bandwidth selection has been proposed in any paper.

### Intuition
The premise is that prices tend to pause or reverse at Fibonacci ratio levels of a prior
move, because these ratios appear throughout natural phenomena (φ governs spiral geometry,
leaf arrangements, etc.) and are therefore supposedly "encoded" in market behavior. The
only plausible real-world mechanism is self-fulfilling: if enough traders use Fibonacci
software and enter/exit at the same levels, the levels become true by collective action.
This mechanism is fragile, trader-concentration-dependent, and weakens as markets become
more institutionally dominated — making it an unstable foundation for a systematic signal.

### Assumptions
1. A valid prior swing high and swing low can be objectively identified from price data —
   NO ALGORITHM for this is universally defined; every implementation chooses its own
   swing-detection method, creating a major uncontrolled free parameter.
2. Price retains "memory" of Fibonacci levels from prior swings — empirically weak;
   Tsinaslanidis 2021 finds null results across three markets.
3. The tool is applicable across timeframes — untested statistically; assumed by practitioners.
4. The 50% level behaves like a Fibonacci level — it is not one; its empirical significance
   does not validate the Fibonacci framework.
5. Swing levels maintain predictive relevance across the time window between their formation
   and a monthly rebalance — not established; event-driven signal degrades to a snapshot.

### Known Failure Modes
- Fibonacci zones are statistically indistinguishable from random zones as price bounce
  predictors across US (DJIA, NASDAQ) and German (DAX) equity markets.
  (Source: independent — Tsinaslanidis, Guijarro & Voukelatos, 2021)
- No clustering of price reversals at Fibonacci ratios beyond chance, tested on full DJIA
  history using block bootstrap. (Source: independent — Aggarwal et al., City University London)
- Fails in crypto markets; most price violations cluster during declines, not advances —
  asymmetric failure in the highest-risk regime.
  (Source: independent — Gurrib, Nourani & Bhaskaran, 2022)
- No edge in trending markets; applicability claimed only in ranging/mean-reverting conditions.
  (Source: practitioner literature, multiple sources)
- High-volatility regimes: swing-point identification collapses; price whipsaws through
  levels without producing tradeable bounces. (Source: practitioner literature)
- Cryptomarket failure documented even with the most favorable implementation.
  (Source: independent — Gurrib et al., 2022)
- 63% failure rate in practitioner backtest across 102 securities — below coin-flip on
  turning-point prediction. (Source: Liberatedstocktrader, 2023 — practitioner test)
- Monthly-rebalance structural incompatibility: Fibonacci bounces are event-driven (price
  touches zone → trigger). Monthly polling captures only a static snapshot; the signal
  as studied in the academic literature cannot be faithfully reproduced at monthly frequency.
  (Source: Council deliberation — Engineer)
- Self-fulfilling mechanism is fragile in ETF markets: ETFs are institutional-flow dominated;
  retail size is insufficient to move ETF prices in a sustained way; the mechanism that
  might sustain predictive content in liquid equities or FX does not transfer.
  (Source: Council deliberation — Skeptic)

### Source Coverage
**Academic databases checked:** SSRN, arXiv q-fin, NBER, Google Scholar, Journal of
Portfolio Management, Financial Analysts Journal / CFA Institute, Journal of Finance

**Databases with relevant content:** SSRN (multiple papers), Google Scholar (citation
network, several papers), NBER (Goetzmann 2004 — historical only, not a signal test)

**Databases with no relevant content:** Journal of Portfolio Management, Financial Analysts
Journal / CFA Institute, Journal of Finance (Lo et al. 2000 is methodological ancestor
but does not test Fibonacci), arXiv q-fin (appears only as incidental input feature in
ML papers, not as primary research object)

**Practitioner sites with content:** NONE
**Practitioner sites with no content:** AQR, Man Institute, Verdad, Alpha Architect,
Research Affiliates, Flirting with Models, Robeco, NAAIM, Vanguard, Bank of Canada
(all 10 — complete institutional silence)

**Replication studies found:** 6 total (2 peer-reviewed failures, 1 practitioner failure,
2 mixed, 1 mixed with author self-caveat)

**Factor zoo check:**
- Hou, Xue & Zhang (2017) "Replicating Anomalies": NOT APPLICABLE — Fibonacci
  retracements are a price-pattern tool, not a cross-sectional balance-sheet factor;
  outside scope by construction.
- McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?":
  DOES NOT APPEAR — strategy has never been formalized as a return predictor in the
  asset pricing literature that McLean & Pontiff cover.
- Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns": NOT NAMED
  as a factor, but threshold applies directly — any positive claim must clear t ≥ 3.0
  given the multiple-testing environment in technical analysis research. Shanaev & Gibson
  (2022) have not publicly benchmarked their results against this standard.

### Replication Evidence

| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Tsinaslanidis et al. (2021) | US (DJIA, NASDAQ), Germany (DAX) | Multi-decade | FAILED |
| Aggarwal et al. (City Univ. London) | US (DJIA full history) | Full DJIA history | FAILED |
| Shanaev & Gibson (2022) | International indices + FX | Multi-year | MIXED (preprint) |
| Gurrib, Nourani & Bhaskaran (2022) | US energy stocks + crypto | Nov 2017–Jan 2020 | MIXED |
| Bhattacharya & Kumar (2006) | International (indicative) | Pre-2006 | MIXED (self-caveated) |
| Liberatedstocktrader (2023) | 102 securities, unspecified | Unstated | FAILED (63% failure) |

**Overall replication status:** Weak — tilted toward failure
**Notes:** The two most methodologically rigorous peer-reviewed studies both return null or
failure results. The sole positive result (Shanaev 2022) is an unreplicated SSRN preprint
that has not cleared Harvey et al.'s multiple-testing threshold. Mixed results in Gurrib
cover only a 26-month window that is not regime-neutral. Bhattacharya's authors explicitly
disclaim their own results. No independent replication of the positive claims exists.

### Practitioner Consensus
**Sources with content:** None of the 10 verified practitioner sources.
**Summary:** Complete institutional silence across all 10 verified quantitative research
institutions (AQR, Man Institute, Verdad, Alpha Architect, Research Affiliates, Flirting
with Models, Robeco, NAAIM, Vanguard, Bank of Canada). These organizations collectively
publish on every factor with serious empirical grounding — momentum, value, carry, trend,
mean reversion, quality. Zero publication on Fibonacci retracements constitutes an implicit
institutional rejection, not a gap in coverage.
**Divergence from academic consensus:** None identified — practitioner silence is consistent
with the dominant null/failure findings in the peer-reviewed academic literature.

### Council Deliberation Summary
STRONG_CONSENSUS for REJECTION. All five members (Mathematician, Empiricist, Skeptic,
Engineer, Risk Manager) independently found the signal disqualifying on at least one hard
constraint without relying on the same argument: (1) no mechanism connects integer recursion
to price behavior; the 50% level breaks the mathematical coherence (Mathematician); (2) the
peer-reviewed literature is null; Shanaev 2022 carries near-zero evidential weight against
Tsinaslanidis 2021 (Empiricist); (3) the multiple-testing environment in technical analysis
means Shanaev's t-statistics must clear t ≥ 3.0 before any positive weight is assigned —
this has not been done (Skeptic); (4) monthly-rebalance execution is structurally incompatible
with event-driven bounce signals — the engineering constraint is deterministic (Engineer);
(5) failure modes cluster in down markets, where capital protection is most critical — a
signal with negative skew in the worst case is worse than zero (Risk Manager).

**Key Agreement:** Rejection. Structural incompatibility with monthly execution is
deterministic. Total practitioner silence is an institutional verdict. Evidentiary quality
is insufficient to override either constraint.
**Key Tension:** One secondary debate — whether self-fulfilling retail mechanics could
sustain predictive content in liquid equity markets at daily frequency. Unresolved, but
moot given monthly execution constraint and ETF-universe context.

### Minority Report
**Member:** The Empiricist (minority observation only — not a dissent on the verdict)
**Position:** The self-fulfilling mechanism question remains genuinely open for liquid
individual equities at daily execution frequency. If the system expands to Tier 3+ with
individual stocks and shorter rebalance intervals, Fibonacci levels in high-retail-volume
names may warrant a narrow empirical test — not as a primary signal, but as an entry-timing
overlay evaluated against a random entry baseline.
**Falsification:** A peer-reviewed replication of Shanaev & Gibson (2022) on an independent
dataset, with t-statistics exceeding Harvey et al.'s 3.0 threshold and a defined out-of-
sample period, would open the question for daily-execution equity contexts only. ETF context
remains closed regardless.

### Quant Engine Integration
**Module affected:** None — REJECTED; no implementation.
**Dependencies:** N/A
**Implementation complexity:** Not applicable (REJECTED)
**Interaction with existing signals:** Fibonacci retracements, if they had any edge, would
function as a counter-trend entry-timing tool — orthogonal in character to the existing
momentum × regime signal, but with no documented additive alpha and with failure modes
concentrated in down-market regimes where momentum also struggles. Signal interaction
would have been complex without clear portfolio benefit.

**REJECTION conditions that would need to reverse for reconsideration (any future tier):**
1. Independent peer-reviewed replication of Shanaev & Gibson with t ≥ 3.0 and out-of-sample
   validation on a new dataset
2. Daily-or-higher execution frequency (monthly is structurally incompatible)
3. Individual equities with documented retail concentration at specific levels (not ETFs)
4. Objective swing-point algorithm specified and validated separately before any signal test
All four conditions must hold simultaneously. None currently hold.

### Cross-References
- Related DEEPER_LEARNING entries: DL-002 (discretionary TA group rejection — shares the
  pattern of practitioner silence and weak/null academic evidence for chart-based tools);
  DL-003 (price breakout — a more empirically supported price-pattern approach)
- Related LEARNING.md entries: N/A
- Supersedes: N/A

---

## DL-010: RSI Divergence — Oscillator Reversal Signal

**Date:** 2026-05-25
**Classification:** NEW_ALGORITHM
**Status:** REJECTED
**Council Convergence:** STRONG_CONSENSUS (4/5; Empiricist dissent on non-divergence RSI applications noted below)
**Evidence Quality:** Weak
**Relevant Phase:** Phase 3 — Signal Generation

### Source
Canonical reference: Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*. Trend Research. (Originating practitioner source — no statistical testing)
Secondary sources:
- Chong, T.T-L., Ng, W-K., & Liew, V.K-S. (2014). "Revisiting the Performance of MACD and RSI Oscillators." *Journal of Risk and Financial Management*, 7(1), 1–12. DOI: 10.3390/jrfm7010001
- Zatwarnicki, Zatwarnicki & Stolarski (2023). "Effectiveness of RSI Signals in Timing the Cryptocurrency Market." *Sensors*, 23(3), 1664.
- Bulkowski, T. (2010). *Encyclopedia of Chart Patterns* (2nd ed.). Wiley.
- Sullivan, Timmermann & White (1999). "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap." *Journal of Finance*, 54(5), 1647–1691.
- Harvey, Liu & Zhu (2016). "...and the Cross-Section of Expected Returns." *Review of Financial Studies*, 29(1), 5–68.

### Mathematical Specification

RSI construction (Wilder, 1978):

    RS_t = AvgGain_t / AvgLoss_t

    AvgGain_t = [(AvgGain_{t-1} x (N-1)) + Gain_t] / N
    AvgLoss_t = [(AvgLoss_{t-1} x (N-1)) + Loss_t] / N

    RSI_t = 100 - (100 / (1 + RS_t))

Where: N = lookback period (Wilder default: 14; Chong et al. use 21); Gain_t = max(Close_t - Close_{t-1}, 0); Loss_t = max(Close_{t-1} - Close_t, 0). Wilder smoothing is equivalent to EMA with alpha = 1/N.

Divergence definitions:

    Bearish Divergence: Price_t > Price_{t-k}  AND  RSI_t < RSI_{t-k}  (at successive swing highs)
    Bullish Divergence: Price_t < Price_{t-k}  AND  RSI_t > RSI_{t-k}  (at successive swing lows)

where t and t-k are successive swing pivots. The swing pivot detection algorithm is entirely unspecified in Wilder and in every subsequent academic paper — the lookback for identifying pivots is a free parameter that dominates signal frequency and direction. This is a structural specification gap, not an implementation detail.

### Intuition

When price extends to a new high but the oscillator fails to confirm, momentum is weakening — fewer bars are advancing, average gains are shrinking, and a reversal may be imminent. The logic is economically plausible: markets cannot accelerate indefinitely, and RSI measures rate-of-change of gains vs. losses. The practical problem is that "momentum weakening" is a condition that can persist for months in strong trends without producing the predicted reversal.

### Assumptions

1. Swing highs/lows can be identified algorithmically in real time without look-ahead bias (no paper specifies how)
2. RSI divergence generalizes from Wilder's 1970s commodity futures to ETFs with monthly rebalancing
3. Signal sparsity (~0.8-1.0% of daily candles per Zatwarnicki 2023) does not impair statistical power
4. The pivot lookback parameter has a stable optimal value across markets and regimes
5. Mean reversion is reliably triggered at divergence points, not only in retrospect

### Known Failure Modes

- **Strong-trend failure**: RSI remains overbought/oversold indefinitely in sustained trends, generating continuous spurious divergence signals that never resolve. Universal; original-author-documented (Wilder acknowledged this for divergence in trending markets).
- **Signal sparsity -> statistical powerlessness**: Divergence conditions met in <1% of candles (Zatwarnicki 2023, independent). On 9 ETFs with daily data over 10 years: approx 9 x 252 x 0.01 = 23 events per year -> ~230 events per decade. Insufficient for meaningful statistical inference on a monthly-rebalancing system.
- **Look-ahead bias in backtesting**: Swing pivot identification using ZigZag on historical data is pure look-ahead; only Zatwarnicki et al. (2023) attempted real-time pivot detection, and their result was the most negative (-189pp vs. buy-and-hold). Practitioners routinely violate this; backtests showing positive results should be assumed contaminated unless proven otherwise.
- **Free parameter explosion -> data mining risk**: Pivot lookback, N, confirmation step, hold period, hidden vs. regular divergence — all unspecified. No paper has applied White's Reality Check bootstrap or FDR correction to RSI divergence parameter space. Harvey et al. (2016) t >= 3.0 bar unmet in all source papers. (Independent: Replication Agent, structural)
- **Transaction cost elimination**: Sullivan et al. (1999) showed that even the most robustly supported technical rules (moving averages) fail to generate net profit after costs out-of-sample once data snooping is corrected. RSI divergence is a shorter-signal-window rule with lower expected alpha — costs are more damaging. (Independent: Sullivan et al. 1999)
- **Critical misattribution**: The Chong et al. (2014) positive result for Canadian TSX equity markets applies to RSI(21,50) *centerline crossing*, not divergence. These are analytically distinct signals. This misattribution is pervasive in practitioner literature and was unanimously corrected by the Council.

### Source Coverage

**Academic databases checked:** SSRN, arXiv q-fin, NBER, Google Scholar, Journal of Portfolio Management, Financial Analysts Journal / CFA Institute, Journal of Finance
**Practitioner sites with content:** None (0/10)
**Practitioner sites with no content:** AQR, Man Institute, Verdad, Alpha Architect, Research Affiliates, Flirting with Models, Robeco, NAAIM (partial — member-only archive), Vanguard, Bank of Canada
**Replication studies found:** 5 (Chong & Ng 2008; Chong et al. 2014; Zatwarnicki et al. 2023; Bulkowski 2010; Sullivan et al. 1999)
**Factor zoo check:**
  - Hou, Xue & Zhang (2017) "Replicating Anomalies": does not appear (studies accounting anomalies, not technical rules)
  - McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?": does not appear (covers fundamental cross-sectional predictors); structural decay mechanism is applicable by analogy
  - Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns": does not appear by name; t >= 3.0 bar unmet by all source papers; data mining risk flagged as unaddressed

### Replication Evidence

| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Chong & Ng (2008) | UK (LSE) | 1935-1994 | Mixed — RSI level rules only; not divergence |
| Chong, Ng & Liew (2014) | Canada TSX + 4 OECD | ~1990s-2013 | Mixed — RSI(21,50) threshold; NOT divergence |
| Zatwarnicki et al. (2023) | Crypto (10 coins) | 2018-2022 | Failed — 86% vs 275% buy-and-hold (-189pp) |
| Bulkowski (2010) | US equities (994 stocks) | 2000-2010 | Failed — 45-48% success rate; worse than buy-and-hold |
| Sullivan et al. (1999) | US DJIA | Out-of-sample post-BLL | Failed — technical rules fail after data snooping correction |

**Overall replication status:** Weak
**Notes:** No peer-reviewed study has validated RSI divergence as a standalone signal in equity or ETF markets with out-of-sample testing and transaction cost adjustment. The two studies that test divergence directly (Zatwarnicki 2023; Bulkowski 2010) both show failure. Positive Chong et al. (2014) Canada result applies to a different RSI formulation and was not divergence-tested.

### Practitioner Consensus

**Sources with content:** None
**Summary:** Zero of 10 verified practitioner sites endorse RSI divergence as a validated signal. Eight research-capable institutions (AQR, Man Institute, Verdad, Alpha Architect, Research Affiliates, Flirting with Models, Robeco, Bank of Canada) publish actively on adjacent momentum and reversal topics and have deliberately not engaged with RSI divergence. This selective absence is the strongest available negative practitioner evidence.
**Divergence from academic consensus:** None identified — practitioner silence aligns with weak academic record.

### Council Deliberation Summary

The Council (Config G) reached strong consensus on rejection. The Mathematician identified the pivot detection algorithm as a structural mathematical underspecification that makes the signal non-reproducible. The Empiricist confirmed the direct empirical tests (Zatwarnicki 2023, Bulkowski 2010) both show failure, and explicitly corrected the Chong et al. misattribution. The Skeptic flagged pervasive look-ahead bias in practitioner backtests and the unmet Harvey et al. t-stat bar. The Engineer calculated that signal sparsity on 9 ETFs yields ~23 events/year — insufficient statistical power for any credible hypothesis test. The Risk Manager identified that RSI divergence would fight the existing momentum x regime signal, replicating H001's failure mode.

**Key Agreement:** All five members rejected RSI divergence for this system. The Council unanimously agreed the Chong et al. (2014) Canada positive result does not apply to divergence.
**Key Tension:** The Empiricist holds that RSI(21,50) centerline crossing — a distinct formulation — retains conditional empirical support in Canada and should not be foreclosed without a separate narrow hypothesis evaluation. This dissent does not affect the divergence rejection but creates a residual thread (H005 candidate).

### Minority Report

**Member:** The Empiricist
**Position:** RSI(21,50) centerline crossing — not divergence — showed statistically significant abnormal returns on Canadian TSX in Chong et al. (2014). This is a momentum proxy in oscillator form, not a reversal signal. It should be distinguished from divergence and evaluated in a narrow backtest before being discarded along with divergence.
**Falsification:** A walk-forward backtest of RSI(21) > 50 as a binary filter on Canadian ETF momentum signals over 2010-2025 showing no improvement in Sharpe vs. momentum-only would close this thread.

### Quant Engine Integration

**Module affected:** src/signals/ (would have required a new divergence module)
**Dependencies:** Swing pivot detection algorithm (no canonical implementation); daily data already available via yfinance
**Implementation complexity:** High — undefined pivot detection step; statistical power problem requires resolution; interaction with momentum signal requires careful architecture
**Interaction with existing signals:** RSI divergence is a mean-reversion/anti-momentum signal. The current momentum x regime_score signal is trend-following. In strong trends (where momentum signal is most confident), divergence would fire persistently and incorrectly. The combination amplifies the failure mode documented in H001 (mean reversion standalone, KILLED 2026-05-22).

### Implementation Notes

Not applicable — Status: REJECTED.

**REJECTION conditions that would need to reverse for reconsideration:**
1. A direct replication of RSI divergence on equity ETFs with: (a) real-time pivot detection (no ZigZag look-ahead), (b) out-of-sample period covering at least one full market cycle, (c) transaction costs included, (d) t >= 3.0 after data-snooping correction
2. Sufficient signal events for statistical power (minimum ~500 divergence events in backtest)
3. A theoretically specified pivot detection algorithm adopted by the academic community
All three conditions must hold simultaneously. None currently hold.

### Cross-References
- Related DEEPER_LEARNING entries: DL-002 (discretionary TA group — shares pattern of practitioner silence and weak academic evidence); DL-009 (Fibonacci retracements — same structural rejection basis: undefined swing points, zero practitioner validation, failed replication); DL-006 (mean reversion backtest methodology — H001 KILLED, same failure mode this signal would replicate)
- Related LEARNING.md entries: H001 graveyard (mean reversion standalone, KILLED 2026-05-22)
- Supersedes: N/A

---

## DL-011: Volume-Weighted Support/Resistance (VWSR) — Price-Level Signal via Volume Concentration

**Date:** 2026-05-25
**Classification:** NEW_ALGORITHM
**Status:** REJECTED
**Council Convergence:** UNANIMOUS
**Evidence Quality:** Weak (for ETF/monthly-frequency applications)
**Relevant Phase:** Phase 3 — Signal Generation

### Source
Canonical references:
- Osler, C.L. (2003). "Currency Orders and Exchange-Rate Dynamics: An Explanation for the Success of Technical Analysis." *Journal of Finance*, 58(5), 1791-1819.
- Garzarelli, F., Cristelli, M., Pompa, G., Zaccaria, A., & Pietronero, L. (2014). "Memory effects in stock price dynamics: evidences of technical trading." *Scientific Reports*, 4, 4487. DOI: 10.1038/srep04487
Secondary sources:
- De Angelis, T. & Peskir, G. (2016). "Optimal prediction of resistance and support levels." *Applied Mathematical Finance*, 23(6), 465-483.
- Zapranis, A. & Tsinaslanidis, P. (2012). "Identifying and evaluating horizontal support and resistance levels." *Applied Financial Economics*, 22(19), 1571-1585.
- Spitsin, Martyushev et al. (2025). "Modeling Support and Resistance Zones with Stochastic and Volume-Weighted Methods." *Contemporary Mathematics*, 6(6).
- Steidlmayer, J.P. (1984). *Steidlmayer on Markets*. CME practitioner publication. (Origin of Volume Profile / 70% Value Area heuristic)
- Yadav, K. (2025, preprint). "Support and Resistance Reexamined: A Quantitative Analysis of Pattern Illusions in Random Market Data." SSRN.

### Mathematical Specification

VWAP over window T:

    VWAP_T = SUM(P_i * V_i) / SUM(V_i)  for all trades i in window T

Volume Profile histogram:

    V(p_k) = SUM(V_i)  for all trades where P_i in [p_k - eps/2, p_k + eps/2]

where p_k is the k-th price bucket and eps = bucket width (free parameter — no canonical value).

Point of Control (POC):

    POC = argmax_{p_k} {V(p_k)}  over chosen lookback window (free parameter)

Value Area (VA) — Steidlmayer heuristic, no statistical derivation:

    VA = smallest contiguous price range containing 70% of total session volume

The 70% threshold is a heuristic from Steidlmayer (1984) based on an analogy to normal distribution +/-1 sigma. It is not empirically validated and the volume distribution is not normal.

Garzarelli et al. (2014) bounce probability model (Council-validated scope):

    P(bounce | prior_bounces_at_level = k)  — tested for monotone increase in k
    at stripe width Delta(T) ~ T^alpha around level p*, at timescales T = 45-90 seconds

Osler (2003) order-clustering mechanism (Council-validated scope):

    Order density D(p) = count of stop-loss/take-profit orders at price p
    P(trend_reversal | D(p) = high-cluster) > P(reversal | D(p) = low-cluster)
    Mechanism: FX market only, order-book-specific, round-number clustering

### Intuition

The theory behind VWSR is that price levels where large volumes have traded represent "fair value" anchors — institutions and market makers are aware of where their cost basis lies, and price tends to gravitate back to or reverse from these levels. This is a self-fulfilling prophecy: if enough participants believe VWAP is support, buying pressure near VWAP creates support. Osler (2003) provided a microstructure mechanism for this in FX markets: stop-loss orders cluster at round numbers, creating predictable reversal zones. The theory is coherent. The problem is that the empirical evidence supporting it is restricted to timescales (HFT) and markets (FX, intraday equities) where this specific mechanism operates — not monthly ETF rebalancing.

### Assumptions

1. Volume concentration at price levels persists relevantly long at monthly rebalancing frequency (contradicted by Garzarelli 2014: effect decays at 180 seconds)
2. Self-fulfilling prophecy requires sufficient participant concentration at the level — untested for Canadian ETFs
3. FX order-book clustering mechanism (Osler 2003) transfers to exchange-traded ETF markets (not demonstrated)
4. POC/Volume Profile construction parameters (bucket width, lookback, VA threshold) have stable optimal values
5. Canadian ETF daily volume is sufficient for meaningful Volume Profile formation

### Known Failure Modes

- **Timescale mismatch — structural**: Garzarelli et al. (2014) documented price memory at S/R levels only at 45-90 second resolution; the effect weakens at 150 seconds and is uncharacterized at daily or monthly scales. Monthly ETF rebalancing operates at a timescale ~2.2 million times longer than the documented effect. This is not a margin-of-error issue — the mechanism has no demonstrated channel at this horizon. (Independent: Garzarelli 2014)
- **Asset class specificity**: Osler (2003) mechanism depends on stop-loss/take-profit order clustering at round numbers in dealer FX markets. ETFs on TSX have a different microstructure: exchange-based, market-maker-quoted, no dealer order-book equivalent. The causal mechanism does not transfer even if the surface pattern might. (Independent: Replication Agent)
- **No profit after friction**: Zapranis & Tsinaslanidis (2012) find horizontal S/R levels generate no excess returns vs. buy-and-hold on US equities over 20 years. Garzarelli (2014) explicitly deferred profitability analysis. Sullivan et al. (1999) showed trading-range break rules (the closest proxy) fail after data snooping correction. (Independent: Zapranis 2012, Sullivan 1999)
- **Random walk confound**: Yadav (2025, preprint) demonstrates that price series generated by pure random walks produce patterns visually and statistically indistinguishable from S/R levels in live data. Weight as preprint: lower than peer-reviewed, but methodological approach is sound. (Independent, weight: medium)
- **Volume Profile free parameters -> data mining risk**: Bucket width, lookback window, and Value Area threshold are entirely unspecified. The 70% VA is a heuristic with no empirical validation. No paper applies data snooping correction to the parameter space. (Structural)
- **Canadian ETF thin volume**: Lower average daily volume than US large-cap equities means POC formation is noisier. A level that appears as a strong POC may be artifact of a single large institutional trade rather than sustained market consensus. (Structural)
- **Infrastructure requirement**: Building a Volume Profile requires intraday data (minute-bars or tick). yfinance provides OHLCV daily data and only 60 days of minute-bar history. No accessible free source provides intraday volume data sufficient for a proper Volume Profile over multi-month lookback periods. (Engineer, confirmed)

### Source Coverage

**Academic databases checked:** SSRN, arXiv q-fin, NBER, Google Scholar, Journal of Portfolio Management, Financial Analysts Journal / CFA Institute, Journal of Finance
**Practitioner sites with content:** AQR (VWAP as execution benchmark), Alpha Architect (volume for cost prediction), Man AHL (order book microstructure) — all in an execution/cost context, not signal context
**Practitioner sites with no content:** Verdad, Research Affiliates, Flirting with Models, Robeco, NAAIM (partial), Vanguard, Bank of Canada (adjacent microstructure content; no VWSR signal content)
**Replication studies found:** 5 (Osler 2000/2003; Garzarelli et al. 2014; Sullivan et al. 1999; Zapranis & Tsinaslanidis 2012; Yadav 2025 preprint)
**Factor zoo check:**
  - Hou, Xue & Zhang (2017) "Replicating Anomalies": does not appear (not an accounting anomaly)
  - McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?": does not appear (fundamental cross-sectional predictors); structural decay mechanism applicable by analogy
  - Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns": does not appear; source papers test single datasets over short windows — far below the t >= 3.0 bar; data mining risk flagged

### Replication Evidence

| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Osler (2000, 2003) | FX spot (USD/JPY, USD/GBP, EUR/USD) | Aug 1999-Apr 2000 | Confirmed (FX order-book, intraday, round-number specific) |
| Garzarelli et al. (2014) | UK LSE (9 large-caps) | 2002 (251 days) | Partial — statistically significant at 45-90 sec; no profit test |
| Zapranis & Tsinaslanidis (2012) | US NASDAQ + NYSE | ~20 years | Failed — no excess returns vs. buy-and-hold |
| Sullivan et al. (1999) | US DJIA | Out-of-sample | Failed — trading-range break fails data-snooping correction |
| Yadav (2025, preprint) | Synthetic random walk | Simulation | Challenge — S/R patterns emerge from pure Brownian motion |

**Overall replication status:** Mixed, trending Weak for equity/ETF applications
**Notes:** The strongest evidence (Osler, Garzarelli) is domain-specific (FX, HFT timescales) and does not extend to monthly ETF rebalancing. The equity-market replication studies (Zapranis 2012, Sullivan 1999) show failure. No study has replicated volume-weighted S/R specifically as a profitable standalone signal in equity ETFs with transaction costs.

### Practitioner Consensus

**Sources with content:** AQR (VWAP as execution benchmark), Alpha Architect (volume for cost prediction), Man AHL (order book microstructure) — all in an execution/cost context, not signal context
**Summary:** Zero of 10 verified practitioner sites endorse VWAP or volume-profile-derived levels as a structural S/R signal for investing. VWAP is real institutional infrastructure — but used exclusively as a transaction cost benchmark. The gap between "institutions use VWAP" and "VWAP as S/R generates alpha" is not bridged by any verified practitioner source. The absence from Verdad, Research Affiliates, Flirting with Models, and Robeco — all research-oriented active managers — is informationally significant.
**Divergence from academic consensus:** None identified — practitioner silence aligns with weak equity replication record.

### Council Deliberation Summary

The Council (Config G) reached unanimous rejection. The Mathematician identified the Volume Profile parameter structure as mathematically unjustified — bucket width, lookback, and the 70% Value Area threshold are all heuristics without analytical derivation; De Angelis & Peskir's (2016) rigorous optimal stopping model does not contain volume and does not map to VWAP/POC. The Empiricist identified the timescale mismatch as the decisive empirical problem: the strongest academic evidence (Garzarelli 2014) exists at 45-90 second resolution — inapplicable to monthly rebalancing by 2.2M times. The Skeptic flagged the random walk confound (Yadav 2025) and the failure of trading-range break rules after data-snooping correction (Sullivan 1999). The Engineer confirmed that Volume Profile construction requires intraday data unavailable through yfinance. The Risk Manager identified a conceptually distinct adjacent idea — volume anomaly as a regime-change early warning — that is worth separating from the VWSR rejection.

**Key Agreement:** All five members rejected VWSR for this system. The timescale mismatch was the consensus decisive factor — not merely weak evidence but a structural domain mismatch.
**Key Tension:** The Risk Manager's volume spike hypothesis — anomalous volume relative to rolling average as a regime-change signal — was not disputed but also not voted on. The Chair directed it toward a separate hypothesis evaluation (H006 candidate) rather than letting it contaminate the VWSR rejection.

### Quant Engine Integration

**Module affected:** src/signals/ (would have required a new volume profile module)
**Dependencies:** Intraday volume data (minute-bars or tick) — not available through yfinance for multi-month lookback; would require a paid data source (e.g., Polygon.io, Alpha Vantage premium, or TSX data feed)
**Implementation complexity:** High — data infrastructure upgrade required before any signal code; parameter selection unguided by literature; no comparable implementation in existing codebase
**Interaction with existing signals:** As a price-level signal, VWSR would sometimes agree with and sometimes contradict the existing momentum x regime signal, with no systematic adjudication rule. No additive theoretical mechanism with existing signals.

### Implementation Notes

Not applicable — Status: REJECTED.

**REJECTION conditions that would need to reverse for reconsideration:**
1. A peer-reviewed study replicating volume-profile-derived S/R as a profitable signal in equity ETFs with: (a) daily or lower rebalancing frequency, (b) transaction costs included, (c) out-of-sample period, (d) t >= 3.0 after data snooping correction
2. A theoretical mechanism bridging the HFT-scale price memory effect (Garzarelli 2014) to daily/monthly decision timescales
3. Accessible intraday data source for Canadian ETFs at acceptable cost
4. Falsification of the random-walk confound (Yadav 2025) by a peer-reviewed study
All four conditions must hold simultaneously. None currently hold.

**Adjacent idea preserved — Volume anomaly as regime signal (H006 candidate):**
The Risk Manager identified that abnormal volume relative to rolling baseline is a documented early indicator of regime change — conceptually distinct from VWSR prediction. This would require: (a) daily volume data (already available via yfinance), (b) a rolling baseline (e.g., 20-day average volume), (c) a threshold for anomalous activity (e.g., 2-sigma above baseline). This hypothesis should be evaluated separately if pursued.

### Cross-References
- Related DEEPER_LEARNING entries: DL-002 (discretionary TA group — same pattern of practitioner silence and retail-dominant evidence base); DL-009 (Fibonacci retracements — shares rejection basis: undefined level specification, timescale mismatch, zero practitioner validation); DL-010 (RSI divergence — shares the structural free-parameter problem and practitioner silence pattern)
- Related LEARNING.md entries: N/A
- Supersedes: N/A

---

## DL-012: RSI(21) > 50 as Momentum Confirmation Filter — ALGO_CHECK

**Date:** 2026-05-26
**Classification:** ALGO_CHECK
**Status:** CANDIDATE — mandatory backtest gate before any implementation
**Council Convergence:** STRONG_CONSENSUS (4/5 for CANDIDATE + backtest gate; Skeptic dissents — recommends tighter timeline commitment or immediate SHELVED)
**Evidence Quality:** Weak-to-Mixed
**Relevant Phase:** Phase 3 — Signal layer; H005 in hypothesis pipeline

### Source
Canonical reference (originator): Wilder, J.W. (1978). *New Concepts in Technical Trading Systems.* Trend Research. (book, not peer-reviewed)
Supporting on RSI as trend filter: Hill, A. (2019). "Finding Consistent Trends with Strong Momentum: RSI for Trend-Following and Momentum Strategies." SSRN 3412429.
Supporting on RSI trend-following in crypto: Zatwarnicki, M., Zatwarnicki, K. & Stolarski, P. (2023). "Effectiveness of the RSI Signals in Timing the Cryptocurrency Market." PMC 9920669.
Supporting on signal correlation (indirect): Marshall, B., Nguyen, N. & Visaltanachoti, N. (2017). "Time Series Momentum versus Moving Average Trading Rules." *Quantitative Finance,* 17(3), 405–421.
Null results on TA alpha: Eugster, N. (2023). "Technical Analysis and Stock Returns." *European Financial Management.*
Factor zoo — momentum base signal: Jegadeesh, N. & Titman, S. (1993). JF 48(1), 65–91. Asness, Moskowitz & Pedersen (2013). JF 68(3), 929–985.

### Mathematical Specification

RSI(n) = 100 − 100 / (1 + RS)

Where:
- RS = SMMA(gains, n) / SMMA(losses, n)
- gains_t = max(P_t − P_{t−1}, 0);  losses_t = max(P_{t−1} − P_t, 0)
- SMMA uses Wilder smoothing: α = 1/n  (NB: distinct from EMA's α = 2/(n+1))
- RSI > 50 iff SMMA(gains) > SMMA(losses) iff smoothed net signed price change > 0

Proposed gate (H005):
  Signal_final = momentum_score × max(regime_score, 0) × I(RSI(21) > 50)

Relationship to existing signal:
  RSI(n) > 50 and time-series momentum (sign of N-month return) are both monotonic
  functions of positive price drift over N periods. Marshall et al. (2017) measured
  TSMOM/MA signal correlations at 0.81–0.91. RSI is in the same mathematical family;
  empirical correlation against the Engine's 12-1 month momentum_score on this
  specific 9-ETF dataset has not been measured and must be computed at backtest time.

Parameter note: Wilder specified n=14 for daily commodity bars. RSI(21) on monthly
bars = 21-month lookback. No academic paper establishes RSI(21) for this use case.
The parameter choice is currently unjustified by theory or citation.

### Intuition
RSI > 50 asks whether recent gains have outweighed recent losses on a smoothed
basis — a bounded, oscillator form of the same positive-drift question that raw
price momentum already answers. If the Engine's momentum_score captures the
direction of price drift and RSI(21) captures essentially the same construct with
a different window and smoothing kernel, adding the RSI gate primarily filters out
trades in the ~20% of months where the two disagree. Whether those disagreements
are "noisy momentum" (additive case) or "valid momentum" (redundant case) is
the empirical question H005 must answer via backtest.

### Assumptions
1. RSI(21) computed on monthly bars captures meaningful trend information at monthly
   rebalancing frequency (unstudied in academic literature)
2. RSI(21) > 50 and the Engine's 12-1 month momentum_score disagree often enough to
   create a meaningful filter (requires empirical verification on this dataset)
3. The ~20% disagreement cases represent noise, not valid signal
4. The Wilder SMMA smoothing produces different information from EMA (minor effect)
5. A binary gate (> 50) captures more than a continuous RSI score would

### Known Failure Modes
- Asset class mismatch: canonical supporting papers (Hill 2019: US equities; Zatwarnicki 2023: crypto) do not cover Canadian ETFs. European equity study (Eugster 2023) found no alpha from RSI-type signals. (Independent: Eugster 2023)
- Parameter illegitimacy at monthly frequency: RSI(21) on monthly bars = 21-month lookback; all canonical papers use RSI(14) on daily bars; no academic grounding for monthly-bar RSI period choice. (Source: all canonical papers)
- Mathematical redundancy: RSI(21) > 50 and momentum_score share >0.80 correlation by extrapolation from Marshall et al. 2017; expected marginal R² is near zero. (Source: Marshall et al. 2017 by extrapolation — direct test not published)
- Multiple-testing hazard: RSI parameter space (period × threshold) is large; Harvey et al. (2016) require t > 3.0 for credibility given this search space. (Independent: Harvey, Liu & Zhu 2016)
- Post-publication decay of base signal: McLean & Pontiff (2016) document 58% return decay in momentum post-publication; filtering with RSI on a decayed signal does not restore alpha. (Independent: McLean & Pontiff 2016)
- Dual-criterion collapse: Hill (2019) demonstrated usefulness of RSI range-momentum via DUAL criterion (RSI range + RSI milestone ≥ 70), not the simple RSI > 50 binary gate proposed in H005. H005's simpler specification is weaker than the tested version. (Source: Hill 2019)
- Small-N statistical power: 9-ETF universe at monthly frequency yields ~531 (ticker, month) pairs; RSI/momentum disagreement sub-periods may be too small for significance at t > 3.0. (Council deliberation: Skeptic)

### Source Coverage
**Academic databases checked:** SSRN, arXiv q-fin, NBER, Google Scholar, Journal of Portfolio Management, Financial Analysts Journal, Journal of Finance
**Practitioner sites with content:** NAAIM (partial — categorizes RSI explicitly as "overbought/oversold," not momentum)
**Practitioner sites with no content:** AQR, Man Institute, Verdad, Alpha Architect, Research Affiliates, Flirting with Models/Newfound, Robeco, Vanguard, Bank of Canada
**Replication studies found:** 4 (Hill 2019, Zatwarnicki 2023, Eugster 2023, Marshall et al. 2017 indirect)
**Factor zoo check:**
  - Hou, Xue & Zhang (2017): does not appear — RSI is absent from the 452-anomaly academic zoo
  - McLean & Pontiff (2016): does not appear — RSI absent from 97-predictor dataset; base momentum shows 58% post-publication decay
  - Harvey, Liu & Zhu (2016): does not appear — RSI absent from 316-factor catalogue; t > 3.0 bar applies to all parameter configurations

### Replication Evidence

| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Hill (2019) | US equities (S&P 500) | ~1998–2018 | Mixed — RSI range-momentum CONFIRMED on individual stocks using RSI(14) dual criterion, NOT the RSI(21) > 50 binary gate |
| Zatwarnicki et al. (2023) | Crypto (10 currencies) | 2018–2023 | Mixed — RSI 50-100 CONFIRMED in bull phase; −41% in bear out-of-sample |
| Eugster (2023) | European equities | 2003–2019 | Failed — no significant alpha from technical analysis including RSI |
| Marshall et al. (2017) | Multi-country equity indices | Multi-decade | Indirect — TSMOM/MA correlation 0.81–0.91 implies RSI is near-redundant |

**Overall replication status:** Weak
**Notes:** No replication study tests RSI(21) > 50 as a binary gate on a diversified ETF portfolio at monthly rebalancing frequency. The two most supportive studies (Hill, Zatwarnicki) use different parameters and asset classes. The one equity-market study with RSI scope (Eugster) finds no alpha. The 0.81–0.91 correlation evidence (Marshall et al.) is for a related but not identical signal family.

### Practitioner Consensus
**Sources with content:** NAAIM only (partial — categorization data, not endorsement)
**Summary:** Zero of 10 verified institutional practitioner sources use RSI as a momentum confirmation filter. NAAIM's Indicator Wall explicitly classifies RSI as an "overbought/oversold" indicator, placing it in a separate bucket from momentum signals. All 10 sources use price-return-based momentum (12-month raw return or MA crossover signals) as trend confirmation. The closest practitioner analogue to RSI > 50 logic — price above a moving average — is universally preferred over RSI in verified practitioner literature.
**Divergence from academic consensus:** Academic literature has thin support for RSI > 50 as a trend filter (Hill 2019 in stocks, Zatwarnicki 2023 in crypto). The divergence is that even this thin academic support is absent in practitioner institutional literature — practitioners have converged on simpler price-return metrics.

### Council Deliberation Summary
Configuration G (5 members). The Mathematician established that RSI(21) > 50 is mathematically a near-redundant transform of positive price drift — the same underlying construct as the existing momentum_score, with different window and smoothing. The Empiricist documented zero published evidence for RSI(21) on ETF portfolios at monthly frequency. The Skeptic flagged parameter illegitimacy (no paper uses RSI(21) for this application), Harvey et al.'s t > 3.0 bar, and multiple-testing exposure from RSI's large parameter space. The Engineer noted that if the goal is a trend-consistency filter, price > EMA(N) has cleaner academic grounding and should be tested as a parallel comparison arm. The Risk Manager identified that the additive/redundant question can only be empirically resolved by examining the ~20% of months where RSI and momentum diverge.

**Key Agreement:** RSI(21) > 50 has no direct academic or practitioner grounding for this specific application; the mathematical prior strongly favors redundancy; zero practitioner sources use it; parameter choice is unjustified at monthly frequency.
**Key Tension:** The Risk Manager and Empiricist require an empirical backtest to confirm redundancy. The Skeptic argues the accumulated prior (parameter illegitimacy + factor zoo absence + practitioner silence + Eugster null result) is sufficient to SHELVE without testing. Resolved as CANDIDATE with mandatory backtest gate rather than immediate SHELVED — but the Skeptic dissents on the filing status if no backtest is scheduled promptly.

### Minority Report
**Member:** The Skeptic
**Position:** Filing as CANDIDATE without a committed backtest timeline is soft rejection dressed as openness. Given parameter illegitimacy (RSI(21) unjustified at monthly frequency), factor zoo absence, 10/10 practitioner silence, and Eugster (2023)'s null result on equity TA signals, the prior is strongly against additive value. A CANDIDATE status that persists indefinitely creates false confidence in the hypothesis queue.
**Falsification:** A backtest on the Engine's 9-ETF universe demonstrating t > 3.0 for incremental Sharpe improvement from the RSI(21) > 50 gate, specifically in sub-periods where RSI and momentum_score disagree, and outperforming a simple price > EMA(12) comparison arm, would change the Skeptic's position.

### Quant Engine Integration
**Module affected:** src/signals/ — would add RSI computation; potential modification to signal composition in recommendation engine
**Dependencies:** No new libraries (pandas rolling calculations sufficient). Wilder SMMA is not a standard pandas function — requires manual implementation as `ewm(alpha=1/n, adjust=False)`
**Implementation complexity:** Low — RSI computation is 10 lines; gate integration into existing signal chain is 2 lines
**Interaction with existing signals:** Correlated >0.80 (estimated) with momentum_score. Acts as a multiplicative gate reducing trade frequency. Does not interact with regime_score independently. Stable bucket uses equal-weight — RSI gate would not apply there.

### Implementation Notes
Mandatory backtest protocol before any implementation:
1. Compute empirical correlation: Pearson(RSI(21) > 50, momentum_score > 0) on full 9-ETF monthly history
2. Identify the sub-period where signals diverge (RSI < 50 AND momentum > 0, or RSI > 50 AND momentum < 0)
3. Measure forward 1-month return in the divergence sub-period — this determines whether RSI is filtering noise or valid signal
4. Report incremental Sharpe at Harvey et al. t > 3.0 threshold
5. Run parallel comparison: price > EMA(12) as alternative gate — same intuition, better academic grounding
6. If RSI(21) > 50 does not outperform price > EMA(12) AND does not clear t > 3.0: immediately move to REJECTED

### Cross-References
- Related DEEPER_LEARNING entries: DL-001 (12-1 month momentum — the signal RSI(21) is proposed to filter); DL-003 (52-week high momentum variant — same trend-continuation family); DL-010 (RSI divergence as reversal signal — same indicator, opposite application, also REJECTED); DL-011 (VWSR — shares practitioner silence pattern and TA rejection trajectory)
- Related LEARNING.md entries: H005 hypothesis file in docs/research/hypotheses/
- Supersedes: N/A

---

## DL-013: Volume Spike as Leading Regime Indicator — ETF Markets

**Date:** 2026-05-26
**Classification:** LITERATURE_SCAN
**Status:** THEORETICAL — SHELVED (do not backtest on current data; re-evaluate at Tier 2+)
**Council Convergence:** STRONG_CONSENSUS (5/5 against current implementation; 3/5 SHELVED, 2/5 KILLED — Mathematician and Skeptic prefer KILLED due to direction conflict and 7% factor zoo base rate)
**Evidence Quality:** Mixed (individual equities, developed markets) / Weak (ETF regime application)
**Relevant Phase:** Phase 3 — Regime detection layer; H006 in hypothesis pipeline

### Source
Canonical (visibility/attention mechanism): Gervais, S., Kaniel, R. & Mingelgrin, D.H. (2001). "The High-Volume Return Premium." *Journal of Finance,* 56(3), 877–919.
Canonical (aggregate sentiment mechanism): Baker, M. & Stein, J.C. (2004). "Market Liquidity as a Sentiment Indicator." *Journal of Financial Markets,* 7(3), 271–299.
Canonical (crash risk, leading): Chen, J., Hong, H. & Stein, J.C. (2001). "Forecasting Crashes: Trading Volume, Past Returns, and Conditional Skewness." *Journal of Financial Economics,* 61(3), 345–381. NBER w7687.
Supporting (coincident reversal): Campbell, J.Y., Grossman, S.J. & Wang, J. (1993). "Trading Volume and Serial Correlation in Stock Returns." *QJE,* 108(4), 905–939.
Supporting (information quality): Blume, L., Easley, D. & O'Hara, M. (1994). "Market Statistics and Technical Analysis: The Role of Volume." *JoF,* 49(1), 153–181.
ETF contamination: Ben-David, I., Franzoni, F. & Moussawi, R. (2018). *JoF* 73(6), 2471–2535.
International replication: Kaniel, R., Ozoguz, A. & Starks, L. (2012). *JFE* 103(2), 255–279.
Korean reversal: Chae, J. & Kang, M. (2019). *Pacific-Basin Finance Journal.*
Korean investor decomposition: Kang (2024). arXiv 2512.14134.
Level/turnover: Chordia, T., Subrahmanyam, A. & Anshuman, V.R. (2001). *JFE* 59(1), 3–32.

### Mathematical Specification

**High-Volume Return Premium (Gervais et al. 2001) — canonical individual stock formulation:**

HIGH-volume day: formation-day volume ranks in top 10% of prior 49-day reference window
LOW-volume day: formation-day volume ranks in bottom 10% of prior 49-day reference window
Return window: subsequent 20 trading days (~1 calendar month)
Benchmark: NYSE equal-weighted index return

**Baker & Stein (2004) — aggregate sentiment (OPPOSING at portfolio level):**

r_{m,t+k} = α + β × TURNOVER_t + ε,  β < 0 at aggregate level
TURNOVER_t = V_t / shares_outstanding_t  (detrended)
Horizon k: 6–12 months ahead

**Chen, Hong & Stein (2001) — crash risk (6-month leading):**

ΔTURNOVER_{t−6,t} = mean_turnover(t−6:t) − mean_turnover(t−18:t−7)
NCSKEW_{t+1} = α + β₁ × ΔTURNOVER_t + β₂ × NCSKEW_t + controls
β₁ > 0: rising volume predicts greater negative skewness (crash risk)

**Direction conflict resolution (Baker & Stein 2004, explicit):**
Gervais = spike (not level), individual stock, 1-month horizon → BULLISH SHORT-TERM
Baker & Stein = level/trend, aggregate market, 6–12-month horizon → BEARISH LONGER-TERM
At portfolio-aggregate level in H006's proposed application, Baker & Stein's prediction
is operative. A portfolio-level volume spike, if it carries signal, is more likely a
BEARISH indicator — the opposite of H006's stated hypothesis direction.

No canonical threshold definition exists for monthly-bar "volume spike" in ETF markets.
The entire academic evidence base uses daily or weekly data.

### Intuition
The High-Volume Return Premium posits that a volume spike increases investor
attention to an individual stock (visibility), broadening its demand base and generating
a short-term price premium. This is a real and widely replicated phenomenon for
individual equities. However, two opposing forces limit its applicability to ETF regime
detection: (1) ETFs have no individual visibility dynamics — they are already fully
visible instruments — so the attention mechanism cannot operate; (2) at the aggregate
portfolio level, the literature (Baker & Stein) shows that high turnover predicts
LOWER subsequent returns via overvaluation/sentiment, directly inverting the expected
signal direction for H006's proposed application.

### Assumptions
1. Volume spike is measurable and interpretable on Canadian ETF secondary markets
   (challenged: contamination from creation/redemption arbitrage flows — Ben-David et al.)
2. Volume spikes in ETF markets are driven by informed trading conviction (challenged:
   Canadian TSX ETF volume is primarily retail and AP arbitrage, not institutional conviction)
3. The HVRP visibility mechanism transfers from individual equities to ETF portfolios
   (challenged: mechanism requires per-security investor attention dynamics absent in ETFs)
4. A portfolio-level volume spike is a BULLISH regime signal (directly challenged:
   Baker & Stein show aggregate turnover predicts lower returns)
5. Monthly-sampled volume retains spike detection resolution (challenged: a spike
   visible at daily resolution is invisible in monthly aggregation)
6. HVRP is unconditional (challenged: Wang 2021 shows it is business-cycle dependent;
   Kang 2024 shows it requires institutional investor decomposition to be monotonic)

### Known Failure Modes
- ETF volume contamination: creation/redemption arbitrage flows inflate ETF secondary volume with non-informational noise indistinguishable from informed spikes. (Independent: Ben-David, Franzoni & Moussawi 2018)
- Mechanism failure: Gervais et al. visibility mechanism requires individual-stock investor recognition dynamics; ETFs have no individual-company visibility shocks. (Council deliberation; Empiricist)
- Direction inversion at portfolio-aggregate level: Baker & Stein (2004) show aggregate high turnover predicts LOWER future returns. Applying a bullish volume-spike regime signal at portfolio level may systematically increase exposure before reversals. (Independent: Baker & Stein 2004 — acknowledged explicitly in their paper)
- Retail-dominated market reversal: HVRP reverses in markets dominated by retail volume; Canadian TSX ETF secondary market is primarily retail-driven. (Independent: Chae & Kang 2019; Kang 2024)
- Measurement sensitivity: The monotonic HVRP relationship disappears when normalizing by daily trading value (standard) vs. market cap; the common implementation form destroys the effect. (Independent: Kang 2024)
- Monthly frequency resolution loss: all academic timing evidence uses daily/weekly bars; a monthly aggregate volume figure is unable to detect within-month spikes. (Academic Agent gap finding)
- Factor zoo base rate: Hou, Xue & Zhang (2017) find 93% failure in the trading frictions/liquidity anomaly category — the category containing volume-based signals. (Independent: Hou et al. 2017)
- Business-cycle conditioning required: HVRP is not unconditional; premium is modulated by macroeconomic state. (Independent: Wang 2021)

### Source Coverage
**Academic databases checked:** SSRN, arXiv q-fin, NBER, Google Scholar, Journal of Portfolio Management, Financial Analysts Journal, Journal of Finance
**Practitioner sites with content:** Bank of Canada (partial — monitors volume as COINCIDENT bond-market stress indicator only, paired with liquidity compression; not a leading ETF signal); Alpha Architect (partial — uses volume as ADV capacity/cost constraint only)
**Practitioner sites with no content:** AQR, Man Institute, Verdad, Research Affiliates, Flirting with Models/Newfound, Robeco, NAAIM, Vanguard
**Replication studies found:** 6 (Kaniel et al. 2012, Chae & Kang 2019, Kang 2024, Wang 2021, Conrad et al. 1994, Ben-David et al. 2018)
**Factor zoo check:**
  - Hou, Xue & Zhang (2017): does not appear by name; trading frictions/liquidity category fails at 93% — unfavorable base rate applies
  - McLean & Pontiff (2016): does not appear in 97-predictor dataset; structural post-publication decay applies by inference
  - Harvey, Liu & Zhu (2016): does not appear; trading patterns listed as susceptible category; t > 3.0 bar applies

### Replication Evidence

| Study | Geography | Period | Result |
|-------|-----------|--------|--------|
| Kaniel, Ozoguz & Starks (2012) | 41 countries (equities) | Multi-decade | HVRP CONFIRMED — pervasive in developed markets, mechanism is investor recognition |
| Chae & Kang (2019) | Korea (equities) | Multi-year | HVRP REVERSED — Low-Volume Return Premium found in retail-dominated market |
| Kang (2024) | Korea (equities) | 2020–2024 | CONFIRMED conditionally — only with institutional investor decomposition and nonstandard normalization; naive implementation fails |
| Wang (2021) | US (equities) | Multi-decade | Mixed — HVRP is business-cycle dependent, not unconditional |
| Ben-David et al. (2018) | US (ETFs) | Multi-decade | Failure mode confirmed — ETF ownership introduces noise, contaminating volume signal |
| Conrad, Hameed & Niden (1994) | US (equities) | 1980s–1990s | CONFIRMED for short-horizon reversal channel |

**Overall replication status:** Mixed (individual equities) / No independent evidence (ETF regime application)
**Notes:** HVRP is robustly replicated for individual developed-market equities but the mechanism is investor-composition-dependent, nonlinear, and measurement-sensitive. Zero published studies test volume-spike as a leading regime indicator for ETF portfolios. The Ben-David et al. (2018) ETF-specific study provides the only direct ETF evidence — and it documents noise contamination, not a usable signal.

### Practitioner Consensus
**Sources with content:** Bank of Canada (volume as coincident bond-market stress indicator, paired with liquidity compression); Alpha Architect (volume as ADV capacity constraint)
**Summary:** No institutional quant practitioner among the 10 verified sources uses volume spikes as a leading regime detection signal for ETF portfolios. The Bank of Canada's framework — the closest finding — treats elevated bond-market volume as a coincident stress indicator when paired with liquidity compression, not as a leading directional signal for equity ETF regimes. All 10 sources use volatility regimes, credit spreads, moving-average signals, or macro indicators for regime detection.
**Divergence from academic consensus:** The academic microstructure literature (Blume et al., Gervais et al.) shows volume carries information quality signals in individual equity markets. The practitioner divergence is that institutional quant shops have not translated this into regime detection workflows — the practitioner silence likely reflects that the ETF contamination and direction-inversion problems are known and have foreclosed practical application.

### Council Deliberation Summary
Configuration G (5 members). The Mathematician established that the Gervais/Baker & Stein direction conflict is resolved at the aggregate portfolio level in Baker & Stein's favor — a portfolio-level volume spike is more likely a BEARISH indicator than a bullish regime flag, inverting H006's stated hypothesis direction. The Empiricist documented three independent ETF-specific failure mechanisms: contaminated volume (Ben-David et al.), absent visibility mechanism, and retail-dominated Canadian ETF markets where HVRP reverses (Chae & Kang). The Skeptic added the 7% factor zoo base rate (trading frictions/liquidity fails at 93% per Hou et al.) and the monthly frequency resolution problem. The Engineer acknowledged that a within-month daily-spike-count formulation could preserve temporal resolution but noted that ~531 available (ticker, month) pairs are insufficient for meaningful statistical testing at Harvey et al.'s t > 3.0 threshold. The Risk Manager flagged asymmetric risk: if direction is wrong, the Engine would increase allocation before reversals — a systematically adverse error, not a neutral one.

**Key Agreement:** H006 as stated (volume spike as leading bullish regime indicator for 9-ETF Canadian portfolio at monthly rebalancing) has no affirmative support in academic, practitioner, or replication evidence, and every major assumption underlying the effect fails at the ETF level.
**Key Tension:** The Skeptic and Mathematician argued for KILLED status based on the direction conflict plus 7% base rate. The Engineer and Risk Manager argued for SHELVED to preserve the hypothesis for re-evaluation at Tier 2+ (individual equities) where the HVRP mechanism could become operative. Resolved as SHELVED.

### Minority Report
**Member:** The Mathematician and The Skeptic (joint minority)
**Position:** SHELVED overstates the residual optionality. The direction inversion (Baker & Stein dominates at portfolio-aggregate level) means the hypothesis as stated is likely wrong in direction, not merely unproven. The 7% factor zoo base rate in the liquidity/trading-frictions category and the complete ETF mechanism failure constitute sufficient evidence for KILLED status. Filing as SHELVED for Tier 2+ is only valid if Tier 2+ involves individual equity holdings where the Gervais visibility mechanism could operate — at which point a new hypothesis (H006v2) should be filed with the correct mechanism specification, not the ETF-level logic of H006.
**Falsification:** A peer-reviewed study demonstrating that portfolio-level ETF volume spikes (on a universe of ≥5 ETFs, monthly rebalancing) predict higher forward returns at t > 3.0, after controlling for price momentum and volatility regime, with a theoretical mechanism that overcomes the Baker & Stein inversion, would change their position.

### Quant Engine Integration
**Module affected:** Not applicable — SHELVED
**Dependencies:** Daily OHLCV data already in quant.db; no new data sources required if re-evaluated
**Implementation complexity:** Medium — requires within-month spike detection (daily resolution), rolling baseline computation, threshold specification; direction of signal needs empirical determination before use
**Interaction with existing signals:** Direction conflict with vol_regime_score unresolved; could compound regime error if applied in wrong direction

### Implementation Notes
Not applicable — Status: SHELVED.

**Conditions for re-evaluation (all must hold):**
1. Portfolio scales to Tier 2+ with individual equity holdings, where the Gervais visibility mechanism can operate
2. A directional test on available data establishes whether volume spike predicts higher or lower forward returns (Baker & Stein inversion must be empirically addressed)
3. A volume measurement methodology is established that separates informed trading from creation/redemption arbitrage noise
4. Minimum 5 years of individual-equity daily data available for the holdings universe

If re-evaluated for individual equity holdings, file as H006v2 with the HVRP individual-stock mechanism (not the ETF regime mechanism) and the Gervais et al. formation-window spec as the starting point.

**Adjacent mechanism preserved — volume as BEARISH aggregate signal:**
Baker & Stein (2004) establish that high aggregate turnover LEVEL predicts lower subsequent returns at the market level. If the Engine later needs a sentiment-overvaluation warning signal, Baker & Stein's aggregate turnover measure (not spike, not daily, but 6-month detrended turnover level) is the academically grounded direction to explore — opposite the original H006 direction.

### Cross-References
- Related DEEPER_LEARNING entries: DL-011 (VWSR — adjacent idea preserved in that entry; same ETF volume contamination failure mode); DL-007 (volatility targeting — the vol_regime_score that currently serves regime detection; Baker & Stein aggregate turnover could complement this if pursued as a bearish overlay); DL-012 (H005 RSI momentum filter — shares the pattern of practitioner silence and ETF inapplicability)
- Related LEARNING.md entries: H006 hypothesis file in docs/research/hypotheses/
- Supersedes: N/A
