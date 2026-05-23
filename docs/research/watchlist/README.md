# Watchlist — Future Tier Research

Background research on asset categories for future capital tiers.
**This is a passive knowledge base. Nothing here interacts with the live trading system.**

---

## Rules

1. One file per sector or theme.
2. Track: key ETFs and stocks, what drives the sector, correlation structure with existing universe, entry conditions.
3. Update opportunistically — when you encounter relevant information during research sessions or Council deliberations.
4. When capital reaches a new tier threshold, review relevant watchlist files to identify candidates for universe expansion. Run candidates through a formal hypothesis (PIPELINE.md) before adding them.
5. No buy signals. No urgency. No FOMO. This is a library, not a trading desk.

---

## Current Tier Thresholds (from `config/universe.yaml`)

| Tier | NAV Trigger | Unlocks |
|------|-------------|---------|
| Tier 1 (current) | $0–$10k | Canadian-listed ETFs only — **ACTIVE** |
| Tier 2 | $10k NAV | + Canadian large-cap dividend stocks |
| Tier 3 | $25k NAV | + US-listed ETFs (FX drag worth it at scale) |
| Tier 4 | $50k NAV | + individual large-cap stocks, sector rotation |

---

## Files in This Watchlist

| File | Tier Relevance | Status |
|------|---------------|--------|
| `ai_semiconductor.md` | Tier 1 (CHPS.TO already live) / Tier 3+ (individual names) | Seeded |
| `canadian_energy.md` | Tier 2+ candidate | Stub |

---

## How to Use This at Tier Transitions

When NAV approaches a tier threshold:
1. Review relevant watchlist files.
2. Identify the strongest candidates by correlation structure, liquidity, and MER.
3. Create a formal hypothesis file in `docs/research/hypotheses/`.
4. Run it through `/quant-research` and Council Config G before any codebase change.
5. Only add to `config/universe.yaml` after the hypothesis is PROMOTED.
