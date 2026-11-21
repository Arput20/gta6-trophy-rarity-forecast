[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Arput20/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Arput20/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)

# GTA VI Trophy Rarity Forecast

Forecasting Grand Theft Auto VI (PS5) trophy earn rates on Exophase for week one.

## Method Summary

1. **Refresh-Aware Snapshot Analysis**:
   - Detects distinct Exophase refresh events where player tracked counts and trophy earn rates update.
   - For flat histories (where a page refresh is imminent or overdue during launch week), models realistic launch-week player expansion (scaling with horizon) and accounts for rate dilution as new players join.

2. **Sublinear Growth Model for Earned Counts**:
   - Extrapolates player base growth and trophy earned counts.
   - Applies a trophy-specific sublinear exponent ($\alpha_j$) dependent on initial rarity/tier, reflecting that progression/harder trophies grow slower than total active players during mass adoption.

3. **Logit-Space Pinball-Optimal Quantiles**:
   - Computes forecasts and 5 quantiles ($\tau \in \{0.05, 0.25, 0.50, 0.75, 0.95\}$) in logit space to naturally respect probability bounds ($[0, 100]$).
   - Scales dispersion ($\sigma$) based on horizon length ($\sqrt{\text{horizon}}$) and history volatility, with asymmetric upper bounds to capture upside refresh jumps.
   - Enforces strict monotonicity ($q_{0.05} \le q_{25} \le q_{50} \le q_{75} \le q_{95}$), finiteness, and valid $[0, 100]$ percentage ranges.

## How to Run
```bash
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=output python3 main.py
```
