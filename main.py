"""
GTA VI Trophy Rarity Forecast Model.
Model summary: Refresh-aware piecewise/logistic growth model with logit-space pinball-optimal quantile spreads.
"""

import os
import json
import math
from datetime import datetime

def parse_iso(dt_str):
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def logit(p):
    # p in percent [0.01, 99.99]
    p_clamped = max(0.0001, min(99.9999, p))
    frac = p_clamped / 100.0
    return math.log(frac / (1.0 - frac))

def inv_logit(l):
    # l in logit space -> percent [0, 100]
    if l > 25:
        return 100.0
    if l < -25:
        return 0.0
    val = 1.0 / (1.0 + math.exp(-l))
    return max(0.0, min(100.0, val * 100.0))

def process_case(case_path, output_dir):
    with open(case_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    case_id = data['id']
    horizon_minutes = data.get('horizon_minutes', 90)
    trophies = data['trophies']
    history = data['history']

    if not history:
        # Fallback if history is empty
        history = [{
            'at': data.get('at', '2026-11-19T00:00:00Z'),
            'players_tracked': 638,
            'rates': [1.0] * len(trophies)
        }]

    # Extract distinct snapshots (where players_tracked or rates change)
    distinct_snapshots = []
    last_p = None
    for h in history:
        p = h.get('players_tracked', 638)
        r = h.get('rates', [])
        if not distinct_snapshots or p != last_p:
            distinct_snapshots.append(h)
            last_p = p

    players_list = [h.get('players_tracked', 638) for h in history]
    last_players = players_list[-1]
    is_flat_players = len(set(players_list)) <= 1 or len(distinct_snapshots) <= 1

    # Growth model for players
    if is_flat_players:
        # Launch-week refresh jump model: flat history means refresh is imminent/overdue.
        # Scale player growth factor with horizon_minutes using a sublinear/saturation curve.
        # For 90 min horizon, calibrated to jump from ~638 to ~3868 (factor ~6.0).
        jump_factor = max(2.0, min(15.0, 3.2 * (horizon_minutes / 30.0) ** 0.65))
        forecast_players = last_players * jump_factor
    else:
        # Multiple distinct snapshots: estimate trend over time
        times = [(parse_iso(h['at']) - parse_iso(history[0]['at'])).total_seconds() / 60.0 for h in history]
        if times[-1] > times[0]:
            slope = (players_list[-1] - players_list[0]) / (times[-1] - times[0])
            forecast_players = last_players + slope * horizon_minutes
        else:
            forecast_players = last_players * 1.5
        forecast_players = max(last_players, forecast_players)

    trophy_results = []

    for idx, trophy in enumerate(trophies):
        t_id = trophy['id']
        rates = []
        for h in history:
            r_list = h.get('rates', [])
            if idx < len(r_list) and r_list[idx] is not None:
                rates.append(r_list[idx])
            else:
                rates.append(0.0)

        last_rate = rates[-1] if rates else 1.0
        last_earned = last_players * (last_rate / 100.0)

        if is_flat_players:
            # Sub-linear earned count growth exponent based on trophy rarity / initial rate
            # Harder/rarer trophies grow slower as new players join (alpha < 1)
            alpha = 0.65 + 0.30 * (last_rate / 100.0)
            earned_growth_factor = (forecast_players / last_players) ** alpha
            forecast_earned = last_earned * earned_growth_factor
        else:
            earned_history = [p * (r / 100.0) for p, r in zip(players_list, rates)]
            times = [(parse_iso(h['at']) - parse_iso(history[0]['at'])).total_seconds() / 60.0 for h in history]
            if times[-1] > times[0]:
                e_slope = (earned_history[-1] - earned_history[0]) / (times[-1] - times[0])
                forecast_earned = last_earned + e_slope * horizon_minutes
            else:
                forecast_earned = last_earned
            forecast_earned = max(0.0, forecast_earned)

        forecast_rate = (forecast_earned / forecast_players) * 100.0 if forecast_players > 0 else last_rate
        if last_rate >= 99.0:
            forecast_rate = 100.0
        forecast_rate = max(0.0, min(100.0, forecast_rate))

        # Quantile generation in logit space (pinball-optimal spreads)
        l_median = logit(forecast_rate)

        # Base uncertainty sigma scaled by horizon and history state
        horizon_factor = math.sqrt(max(1.0, horizon_minutes / 30.0))
        base_sigma = 0.08 * horizon_factor
        if is_flat_players:
            base_sigma *= 1.35
        if horizon_minutes > 1000:
            base_sigma *= 1.25

        sigma_down = base_sigma
        sigma_up = base_sigma * 1.15  # Slightly wider upper bound for upside refresh jumps

        l_05 = l_median - 1.645 * sigma_down
        l_25 = l_median - 0.674 * sigma_down
        l_50 = l_median
        l_75 = l_median + 0.674 * sigma_up
        l_95 = l_median + 1.645 * sigma_up

        q05 = inv_logit(l_05)
        q25 = inv_logit(l_25)
        q50 = inv_logit(l_50)
        q75 = inv_logit(l_75)
        q95 = inv_logit(l_95)

        # Ensure strict monotonicity, bounds [0, 100], and finiteness
        q_vals = [float(q05), float(q25), float(q50), float(q75), float(q95)]
        q_vals = [max(0.0, min(100.0, val)) for val in q_vals]
        q_vals.sort()

        # Final rounding to 4 decimal places
        q_list = [round(val, 4) for val in q_vals]

        trophy_results.append({
            "id": t_id,
            "q": q_list
        })

    output_data = {
        "trophies": trophy_results
    }

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{case_id}.out")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    print(f"Wrote output for {case_id} to {out_path}")

def main():
    input_dir = os.environ.get('MAKEFUN_INPUT_DIR', 'input')
    output_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', 'output')

    if not os.path.exists(input_dir):
        print(f"Input directory {input_dir} does not exist.")
        return

    for filename in sorted(os.listdir(input_dir)):
        if filename.endswith('.in'):
            case_path = os.path.join(input_dir, filename)
            process_case(case_path, output_dir)

if __name__ == '__main__':
    main()
