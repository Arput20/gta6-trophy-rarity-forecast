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
    p_clamped = max(0.01, min(99.99, p))
    frac = p_clamped / 100.0
    return math.log(frac / (1.0 - frac))

def inv_logit(l):
    # l in logit space -> percent [0, 100]
    # To prevent overflow:
    if l > 20:
        return 100.0
    if l < -20:
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

    # Analyze history
    # If history is flat (e.g. all players_tracked are identical), we need to model the refresh jump.
    players_list = [h['players_tracked'] for h in history]
    is_flat_players = len(set(players_list)) <= 1

    # Estimate player growth
    last_players = players_list[-1] if players_list else 638
    if is_flat_players:
        # On launch night / early flat history, Exophase refresh typically jumps players significantly.
        # Scale factor based on horizon or default launch growth. For 90m horizon, jump factor ~ 4x to 6x.
        # Let's project players using exponential growth or a jump factor proportional to horizon.
        growth_factor = max(1.5, min(10.0, 1.0 + (horizon_minutes / 30.0) * 1.5))
        forecast_players = last_players * growth_factor
    else:
        # Fit linear trend to players over time
        times = [(parse_iso(h['at']) - parse_iso(history[0]['at'])).total_seconds() / 60.0 for h in history]
        if times[-1] > times[0]:
            slope = (players_list[-1] - players_list[0]) / (times[-1] - times[0])
            forecast_players = last_players + slope * horizon_minutes
        else:
            forecast_players = last_players * 1.2
        forecast_players = max(last_players, forecast_players)

    trophy_results = []

    for idx, trophy in enumerate(trophies):
        t_id = trophy['id']
        # Gather historical rates for this trophy
        rates = []
        for h in history:
            r_list = h['rates']
            if idx < len(r_list) and r_list[idx] is not None:
                rates.append(r_list[idx])
            else:
                rates.append(0.0)

        last_rate = rates[-1] if rates else 1.0
        
        # Estimate earned players growth
        # E = players * rate / 100
        earned_history = [p * (r / 100.0) for p, r in zip(players_list, rates)]
        last_earned = earned_history[-1] if earned_history else (last_players * last_rate / 100.0)

        if is_flat_players:
            # When history is flat, earned players grow with players, but maybe slightly slower or faster depending on trophy type
            # For launch night, early players have higher rates, refresh brings in broader player base so rates might drop slightly or earned count scales sublinearly / linearly.
            earned_growth_factor = (forecast_players / last_players) ** 0.85
            forecast_earned = last_earned * earned_growth_factor
        else:
            # Fit linear trend to earned counts
            times = [(parse_iso(h['at']) - parse_iso(history[0]['at'])).total_seconds() / 60.0 for h in history]
            if times[-1] > times[0]:
                e_slope = (earned_history[-1] - earned_history[0]) / (times[-1] - times[0])
                forecast_earned = last_earned + e_slope * horizon_minutes
            else:
                forecast_earned = last_earned
            forecast_earned = max(0.0, forecast_earned)

        # Forecast rate
        forecast_rate = (forecast_earned / forecast_players) * 100.0 if forecast_players > 0 else last_rate
        forecast_rate = max(0.0, min(100.0, forecast_rate))

        # If last rate was 100 (like tutorial trophy), forecast 100 or high
        if last_rate >= 99.0:
            forecast_rate = 100.0

        # Generate quantiles [q05, q25, q50, q75, q95]
        # Since prompt instructs: "so your model must handle a sudden refresh jump: spread your upper quantiles generously on early flat histories."
        median_rate = forecast_rate
        
        # Determine spread / uncertainty
        # On early flat histories, uncertainty is asymmetric and wide, especially upward.
        base_spread = 0.5 * (horizon_minutes / 90.0)
        if is_flat_players:
            # Spread upper quantiles generously
            spread_down = max(0.2, median_rate * 0.3 + base_spread)
            spread_up = max(1.0, (100.0 - median_rate) * 0.4 + base_spread * 2.0)
        else:
            spread_down = max(0.1, median_rate * 0.15)
            spread_up = max(0.2, (100.0 - median_rate) * 0.15)

        q50 = median_rate
        q05 = max(0.0, q50 - spread_down * 1.5)
        q25 = max(0.0, q50 - spread_down * 0.6)
        q75 = min(100.0, q50 + spread_up * 0.8)
        q95 = min(100.0, q50 + spread_up * 2.0)

        # Ensure monotonicity: q05 <= q25 <= q50 <= q75 <= q95
        q05 = min(q05, q25, q50, q75, q95)
        q25 = max(q05, min(q25, q50, q75, q95))
        q50 = max(q25, min(q50, q75, q95))
        q75 = max(q50, min(q75, q95))
        q95 = max(q75, q95)

        q_list = [round(float(q05), 4), round(float(q25), 4), round(float(q50), 4), round(float(q75), 4), round(float(q95), 4)]
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
