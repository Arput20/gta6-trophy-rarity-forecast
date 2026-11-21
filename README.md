[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Arput20/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Arput20/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)

# GTA VI Trophy Rarity Forecast

Forecasting Grand Theft Auto VI (PS5) trophy earn rates on Exophase for week one.

## Method Summary

1. **Refresh-Aware Snapshot Analysis**:
   - Detects distinct Exophase refresh events where player tracked counts and trophy earn rates update.
   - Computes empirical per-refresh multiplicative player growth and typical time intervals between refreshes from the history.

2. **History-Driven Rate Extrapolation & Shrinkage**:
   - Models rate changes per refresh using log-rate changes between consecutive distinct snapshots across all trophies.
   - Extrapolates each trophy's median rate by its observed per-refresh log-change (when $\ge 2$ distinct history values exist) pulled toward the all-trophy mean change via empirical shrinkage.

3. **Logit-Space Pinball-Optimal Quantiles**:
   - Computes forecasts and 5 quantiles ($\tau \in \{0.05, 0.25, 0.50, 0.75, 0.95\}$) in logit space.
   - Scales dispersion ($\sigma$) based on per-refresh log-rate dispersion times $\sqrt{\text{expected refreshes}}$ plus an horizon-aware risk floor for unseen refresh volatility, with asymmetric upper bounds for rare trophy upside jumps.
   - Enforces strict monotonicity ($q_{0.05} \le q_{25} \le q_{50} \le q_{75} \le q_{95}$), valid $[0, 100]$ percentage ranges, and finiteness.

## How to Run
```bash
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=output python3 main.py
```
