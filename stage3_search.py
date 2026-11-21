"""Replay one predeclared candidate batch on the three open development inputs."""
import argparse
import csv
import gzip
import io
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean

from evaluate import METRICS, score
from stage1_single_vehicle import CONTROLLED, DT, metrics, run
from stage3_policy import TablePolicy

OUT = Path(__file__).resolve().parent / "experiments" / "stage3"
SEEDS = (1, 2, 3)
GROUPS = ("grid", "round1", "round2", "round3")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def attach_diagnostics(vehicles, decisions):
    """Align each action with the worst realised acceleration before the next decision."""
    history = vehicles[CONTROLLED - 1].history
    for row in decisions:
        index = round((row["t"] - history[0]["t"]) / DT)
        assert history[index]["t"] == row["t"]
        interval = history[index + 1:index + 1 + round(1 / DT)]
        row["min_ego_accel_next_s"] = min(x["acceleration"] for x in interval)
    active = [i for i, row in enumerate(decisions) if row["state"] == "active"]
    if not active:
        return {"active_s_samples": 0, "strongest_brake_window": [], "release": None}
    worst = min(active, key=lambda i: decisions[i]["min_ego_accel_next_s"])
    end = active[-1] + 1
    return {"active_s_samples": len(active),
            "strongest_brake_window": decisions[max(0, worst-1):worst+2],
            "release": decisions[end] if end < len(decisions) else None}


def evaluate_seed(work):
    group, rules, seed = work
    archived = load_json(OUT.parent / "stage2" / "development_scores.json")
    prior = next(row for row in archived["per_seed"] if row["seed"] == seed)
    baseline, arrivals, flags, _, _ = run(seed, "baseline")
    reference = metrics(baseline, arrivals)
    if reference != prior["baseline"]:
        raise ValueError(f"Stage 2 baseline mismatch on seed {seed}")
    del baseline
    rows = []
    trace_dir = OUT / "traces"
    trace_dir.mkdir(exist_ok=True)
    with (trace_dir / f"{group}-s{seed}.csv.gz").open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as stream:
                writer = None
                for rule in rules:
                    vehicles, demand, assignments, _, decisions = run(
                        seed, "candidate", TablePolicy(rule))
                    if arrivals != demand or flags != assignments:
                        raise ValueError(f"Paired input mismatch for {rule['id']}")
                    values = metrics(vehicles, demand)
                    if rule["id"] == "H20_30" and values != prior["candidate"]:
                        raise ValueError("Fixed-rule control must match phase 2 exactly")
                    diag = attach_diagnostics(vehicles, decisions)
                    if writer is None:
                        writer = csv.DictWriter(stream, fieldnames=["rule", *decisions[0].keys()])
                        writer.writeheader()
                    writer.writerows(dict(rule=rule["id"], **row) for row in decisions)
                    rows.append({"id": rule["id"], "seed": seed, "raw": values,
                                 "sampled_overlap": values["min_sampled_gap_m"] < 0,
                                 "score": score(reference, values), "diagnostic": diag})
                    del vehicles
    return {"seed": seed, "baseline": reference, "runs": rows}


def summarize(by_seed, rules):
    summary = []
    for rule in rules:
        runs = [next(row for row in record["runs"] if row["id"] == rule["id"])
                for record in by_seed]
        valid = [r for r in runs if r["score"]["status"] == "eligible"]
        result = {"id": rule["id"], "eligible_seeds": len(valid),
                  "mean_reward": None, "mean_improvement_percent": None,
                  "joint_mean_time_and_variation_improved": None,
                  "min_gap_m": min(r["raw"]["min_sampled_gap_m"] for r in runs)}
        if len(valid) == len(runs):
            result["mean_reward"] = mean(r["score"]["reward"] for r in runs)
            result["mean_improvement_percent"] = {
                k: mean(r["score"]["improvements_percent"][k] for r in runs) for k in METRICS}
            result["joint_mean_time_and_variation_improved"] = all(
                mean(s["baseline"][k] - r["raw"][k] for s, r in zip(by_seed, runs)) > 0
                for k in ("total_travel_s", "follower_variation_per_km"))
        summary.append(result)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=GROUPS)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    rules = load_json(OUT / "proposals" / f"{args.group}.json")
    if len(set(r["id"] for r in rules)) != len(rules) or len(rules) != (9 if args.group == "grid" else 3):
        raise ValueError("Invalid candidate budget or duplicate rule")
    jobs = [(args.group, rules, seed) for seed in SEEDS]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        by_seed = list(pool.map(evaluate_seed, jobs))
    summary = summarize(by_seed, rules)
    save_json(OUT / f"{args.group}-results.json", {"group": args.group, "summary": summary,
                                                  "by_seed": by_seed})
    for row in summary:
        print(row["id"], "reward", row["mean_reward"], "eligible", row["eligible_seeds"],
              "min gap", round(row["min_gap_m"], 4), "gains", row["mean_improvement_percent"])


if __name__ == "__main__":
    main()
