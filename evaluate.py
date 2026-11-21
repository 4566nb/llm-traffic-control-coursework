"""Paired score for finite-cohort single-vehicle experiments."""
import json
import math
from pathlib import Path
from statistics import mean

from stage1_single_vehicle import run, metrics

METRICS = {
    "total_travel_s": 0.5,
    "follower_variation_per_km": 0.3,
    "low_speed_vehicle_s": 0.1,
    "last_exit_s": 0.1,
}
MIN_GAP = 2.0


def eligibility(values):
    reasons = []
    if not values.get("all_completed") or values.get("vehicles_admitted") != 60:
        reasons.append("incomplete cohort")
    gap = values.get("min_sampled_gap_m")
    if gap is None or not math.isfinite(gap):
        reasons.append("minimum gap unavailable")
    elif gap < MIN_GAP:
        reasons.append("minimum sampled gap below 2 m")
    for name in METRICS:
        value = values.get(name)
        if value is None or not math.isfinite(value) or value < 0:
            reasons.append(f"missing or invalid {name}")
    return reasons


def score(reference, candidate):
    issues = eligibility(reference)
    if issues:
        return {"status": "invalid_baseline", "reasons": issues, "reward": None}
    issues = eligibility(candidate)
    if issues:
        return {"status": "ineligible", "reasons": issues, "reward": None}
    improvements = {}
    for name in METRICS:
        if reference[name] == 0:
            return {"status": "undefined", "reasons": [f"zero baseline {name}"], "reward": None}
        improvements[name] = 100 * (reference[name] - candidate[name]) / reference[name]
    return {"status": "eligible", "reasons": [], "reward": sum(
        METRICS[name] * improvements[name] for name in METRICS),
        "improvements_percent": improvements,
        "joint_time_and_variation_improved": (
            improvements["total_travel_s"] > 0 and improvements["follower_variation_per_km"] > 0)}


def main():
    rows = []
    for seed in (1, 2, 3):
        baseline, arrivals, flags, _, _ = run(seed, "baseline")
        noop, noop_arrivals, noop_flags, _, _ = run(seed, "noop")
        if arrivals != noop_arrivals or flags != noop_flags or any(
            left.history != right.history for left, right in zip(baseline, noop)
        ):
            raise RuntimeError(f"no-op mismatch for seed {seed}")
        controlled, c_arrivals, c_flags, events, _ = run(seed, "intervention")
        if arrivals != c_arrivals or flags != c_flags:
            raise RuntimeError(f"paired inputs mismatch for seed {seed}")
        baseline_metrics = metrics(baseline, arrivals)
        controlled_metrics = metrics(controlled, arrivals)
        rows.append({"seed": seed, "baseline": baseline_metrics, "candidate": controlled_metrics,
                     "score": score(baseline_metrics, controlled_metrics), "events": events,
                     "noop_trajectory_identical": True})
    valid = [row["score"]["reward"] for row in rows if row["score"]["status"] == "eligible"]
    result = {"weights": METRICS, "minimum_sampled_gap_m": MIN_GAP,
              "mean_reward_if_all_eligible": mean(valid) if len(valid) == len(rows) else None,
              "per_seed": rows}
    path = Path(__file__).parent / "experiments" / "stage2" / "development_scores.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
