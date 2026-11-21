"""
GTA VI Trophy Rarity Forecast Model.
Model summary: Refresh-aware history-driven extrapolation model with logit-space pinball-optimal quantile spreads.
"""

import os
import json
import math
import statistics
from datetime import datetime, timedelta

def parse_iso(dt_str):
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def logit(p):
    p_clamped = max(0.0001, min(99.9999, p))
    frac = p_clamped / 100.0
    return math.log(frac / (1.0 - frac))

def inv_logit(l):
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
    history = data.get('history', [])

    if not history:
        history = [{
            'at': data.get('at', '2026-11-19T00:00:00Z'),
            'players_tracked': 638,
            'rates': [1.0] * len(trophies)
        }]

    # 1. Extract distinct snapshots (where players_tracked or rates change)
    distinct_snapshots = []
    last_p = None
    for h in history:
        p = h.get('players_tracked', 638)
        if not distinct_snapshots or p != last_p:
            distinct_snapshots.append(h)
            last_p = p

    players_list = [h.get('players_tracked', 638) for h in history]
    last_players = players_list[-1]
    is_flat_players = len(set(players_list)) <= 1 or len(distinct_snapshots) <= 1

    # 2. Estimate per-refresh player growth and refresh interval from history if available
    if len(distinct_snapshots) >= 2:
        player_growth_factors = [
            distinct_snapshots[k]['players_tracked'] / distinct_snapshots[k-1]['players_tracked']
            for k in range(1, len(distinct_snapshots))
            if distinct_snapshots[k-1]['players_tracked'] > 0
        ]
        mean_player_growth = statistics.median(player_growth_factors) if player_growth_factors else 2.0
        
        time_intervals = [
            (parse_iso(distinct_snapshots[k]['at']) - parse_iso(distinct_snapshots[k-1]['at'])).total_seconds() / 60.0
            for k in range(1, len(distinct_snapshots))
        ]
        median_refresh_interval = statistics.median(time_intervals) if time_intervals else 180.0
        median_refresh_interval = max(30.0, median_refresh_interval)
    else:
        mean_player_growth = 2.5
        median_refresh_interval = 180.0 # ~3 hours typical launch refresh interval

    # Expected number of refreshes before target
    last_at = parse_iso(history[-1]['at'])
    target_at = parse_iso(data['target']) if 'target' in data else last_at + timedelta(minutes=horizon_minutes)
    remaining_minutes = max(0.0, (target_at - last_at).total_seconds() / 60.0)
    expected_refreshes = max(1.0, remaining_minutes / median_refresh_interval)

    # Collect all per-refresh log-rate changes across trophies and distinct snapshot steps
    all_trophy_log_changes = []
    if len(distinct_snapshots) >= 2:
        for k in range(1, len(distinct_snapshots)):
            r_prev_list = distinct_snapshots[k-1].get('rates', [])
            r_curr_list = distinct_snapshots[k].get('rates', [])
            for idx in range(min(len(r_prev_list), len(r_curr_list))):
                r1 = r_prev_list[idx]
                r2 = r_curr_list[idx]
                if r1 is not None and r2 is not None and r1 > 0 and r2 > 0:
                    log_change = math.log(max(0.0001, r2)) - math.log(max(0.0001, r1))
                    all_trophy_log_changes.append(log_change)

    global_mean_log_change = statistics.mean(all_trophy_log_changes) if all_trophy_log_changes else 0.015
    global_std_log_change = statistics.pstdev(all_trophy_log_changes) if len(all_trophy_log_changes) > 1 else 0.05

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

        # Trophy's own distinct rate history
        t_rates = [
            h['rates'][idx] for h in distinct_snapshots
            if idx < len(h.get('rates', [])) and h['rates'][idx] is not None
        ]
        distinct_t_rates = list(set(t_rates))

        if len(distinct_t_rates) >= 2:
            trophy_log_changes = [
                math.log(max(0.0001, r2)) - math.log(max(0.0001, r1))
                for r1, r2 in zip(t_rates[:-1], t_rates[1:])
                if r1 > 0 and r2 > 0
            ]
            trophy_mean_log_change = statistics.mean(trophy_log_changes) if trophy_log_changes else 0.0
            w = min(1.0, max(0.0, (len(distinct_t_rates) - 1) / 3.0))
        else:
            trophy_mean_log_change = 0.0
            w = 0.0

        # Pull toward global mean change for flat/noisy history trophies
        expected_trophy_log_change = w * trophy_mean_log_change + (1 - w) * global_mean_log_change

        # Median projection
        if last_rate >= 99.0:
            forecast_rate = 100.0
        else:
            last_logit = logit(last_rate)
            proj_logit = last_logit + expected_refreshes * expected_trophy_log_change
            forecast_rate = inv_logit(proj_logit)

        forecast_rate = max(0.0, min(100.0, forecast_rate))

        # Quantile dispersion in logit space
        dispersion = global_std_log_change if len(all_trophy_log_changes) > 1 else 0.04
        refresh_uncertainty = dispersion * math.sqrt(expected_refreshes)
        
        risk_floor = 0.07 if horizon_minutes <= 100 else 0.03
        base_sigma = 0.04 + refresh_uncertainty + (risk_floor / math.sqrt(max(1.0, horizon_minutes / 30.0)))
        if is_flat_players:
            base_sigma *= 1.25

        sigma_down = base_sigma
        sigma_up = base_sigma * 1.15

        l_median = logit(forecast_rate)
        l_05 = l_median - 1.645 * sigma_down
        l_25 = l_median - 0.674 * sigma_down
        l_50 = l_median
        l_75 = l_median + 0.674 * sigma_up
        l_95 = l_median + 1.645 * sigma_up

        q_vals = [inv_logit(l_05), inv_logit(l_25), inv_logit(l_50), inv_logit(l_75), inv_logit(l_95)]
        q_vals = [max(0.0, min(100.0, val)) for val in q_vals]
        q_vals.sort()
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
