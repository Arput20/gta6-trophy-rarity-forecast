[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Arput20/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Arput20/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)

# GTA VI Trophy Rarity Forecast

Forecasting Grand Theft Auto VI (PS5) trophy earn rates on Exophase for week one.

## Model Summary
- **Saturation Growth**: Models player base expansion and trophy progression.
- **Refresh-Aware Quantile Spread**: Handles sudden Exophase player refresh jumps with generous upper quantile spreads in logit space.
- **Long-Horizon Scaling**: Scales log-space spread by 1.2 for extended horizons (`horizon_minutes > 1000`).

## How to Run
```bash
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
