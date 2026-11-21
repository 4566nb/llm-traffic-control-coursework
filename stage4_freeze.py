"""Select on validation, then evaluate the committed rules on six held-out seeds."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import platform
import subprocess
from pathlib import Path

import numpy as np

from bootstrap import COMMIT as TEACHER_COMMIT
from evaluate import METRICS, MIN_GAP, score
from stage1_single_vehicle import COHORT, CONTROLLED, DT, HORIZON, metrics, run
from stage3_policy import TablePolicy
from stage3_search import attach_diagnostics, load_json, summarize

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments/stage4"
SHORTLIST = ROOT / "experiments/stage3/shortlist.json"
VALIDATION = (11, 12)
TEST = (101, 102, 103, 104, 105, 106)
SOURCE_FILES = (
    "stage4_freeze.py", "stage1_single_vehicle.py", "stage3_policy.py", "stage3_search.py",
    "evaluate.py", "bootstrap.py", "requirements.txt", "teacher-source/config.py",
    "teacher-source/vehicle_idm.py", "teacher-source/vehicle.py", "experiments/stage3/shortlist.json",
    "experiments/stage4/protocol.md",
)


def digest_json(obj):
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def contract():
    return {"weights": METRICS, "minimum_sampled_gap_m": MIN_GAP, "experiment": 4,
            "cohort": COHORT, "control_id": CONTROLLED, "follower_ids": list(range(31, 41)),
            "dt_s": DT, "horizon_s": HORIZON, "teacher_commit": TEACHER_COMMIT,
            "validation_seeds": list(VALIDATION), "test_seeds": list(TEST),
            "python": platform.python_version(), "numpy": np.__version__,
            "source_sha256_lf": {f: hashlib.sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                 for f in SOURCE_FILES}}


def exits(vehicles):
    return {str(v.id): v.history[-1]["t"] if not v.active else None for v in vehicles}


def trajectory_columns(vehicles):
    # Rows are vehicle ID, time in seconds, position in metres, speed in m/s.
    return np.array([(v.id, s["t"], s["position"], s["speed"])
                     for v in vehicles for s in v.history[::5]], dtype=np.float64)


def select(validation, families):
    ranked = {r["id"]: r for r in validation["summary"]}
    chosen = {}
    for family, candidates in families.items():
        eligible = [c for c in candidates if ranked[c["rule"]["id"]]["mean_reward"] is not None]
        if not eligible:
            raise ValueError(f"No eligible validation finalist for {family}")
        winner = min(eligible, key=lambda c: (-ranked[c["rule"]["id"]]["mean_reward"], c["rule"]["id"]))
        chosen[family] = {"rule": winner["rule"], "sha256_canonical_json": winner["sha256_canonical_json"],
                          "validation_mean_reward": ranked[winner["rule"]["id"]]["mean_reward"]}
    return chosen


def evaluate_seed(split, seed, rules):
    base, arrivals, flags, _, _ = run(seed, "baseline")
    noop, demand, assigned, _, _ = run(seed, "noop")
    if (arrivals != demand or flags != assigned or exits(base).keys() != exits(noop).keys()
            or any(v.history != w.history for v, w in zip(base, noop))):
        raise RuntimeError(f"No-op trajectory mismatch on {seed}")
    del noop
    reference = metrics(base, arrivals)
    reference_exits = exits(base)
    snapshot = {"IDM": trajectory_columns(base)} if split == "test" and seed == TEST[0] else {}
    del base
    rows = []
    path = OUT / split / f"decisions-{seed}.csv.gz"
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as z:
        with io.TextIOWrapper(z, encoding="utf-8", newline="") as f:
            writer = None
            for rule in rules:
                vehicles, demand, assigned, _, decisions = run(seed, "candidate", TablePolicy(rule))
                if demand != arrivals or assigned != flags:
                    raise RuntimeError(f"Unpaired inputs on {seed} for {rule['id']}")
                result = metrics(vehicles, demand)
                diag = attach_diagnostics(vehicles, decisions)
                if decisions:
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=["rule", *decisions[0]])
                        writer.writeheader()
                    writer.writerows(dict(rule=rule["id"], **d) for d in decisions)
                if snapshot:
                    snapshot[rule["id"]] = trajectory_columns(vehicles)
                gap = result["min_sampled_gap_m"]
                row = {"id": rule["id"], "raw": result, "score": score(reference, result),
                       "savings": {k: reference[k] - result[k] if reference.get(k) is not None
                                   and result.get(k) is not None else None for k in METRICS},
                       "sampled_overlap": None if gap is None else gap < 0,
                       "exit_times_s": exits(vehicles), "diagnostic": diag,
                       "first_active": next((d for d in decisions if d["state"] == "active"), None)}
                rows.append(row)
                del vehicles
    if snapshot:
        np.savez_compressed(OUT / split / f"trajectories-{seed}.npz", **snapshot)
    return {"seed": seed, "baseline": reference, "baseline_score": score(reference, reference),
            "baseline_exit_times_s": reference_exits, "scheduled_arrivals_s": arrivals,
            "bottleneck_flags": flags, "noop_trajectory_identical": True, "runs": rows}


def run_split(split, seeds, rules, binding):
    directory = OUT / split
    directory.mkdir(exist_ok=True)
    by_seed = []
    for seed in seeds:
        path = directory / f"seed-{seed}.json"
        if path.exists():
            row = load_json(path)
            if row["binding"] != binding or row["seed"] != seed:
                raise RuntimeError(f"Existing run uses a different freeze: {path}")
        else:
            row = evaluate_seed(split, seed, rules)
            row["binding"] = binding
            write_json(path, row)
        by_seed.append(row)
    report = {"split": split, "seeds": list(seeds), "binding": binding, "summary": summarize(by_seed, rules)}
    write_json(directory / "summary.json", report)
    return report


def validate_split():
    families = load_json(SHORTLIST)["finalists_for_validation"]
    candidates = [c for pool in families.values() for c in pool]
    if any(digest_json(c["rule"]) != c["sha256_canonical_json"] for c in candidates):
        raise ValueError("Shortlist rule digest mismatch")
    config = contract()
    results = run_split("validation", VALIDATION, [c["rule"] for c in candidates], digest_json(config))
    freeze = {"contract": config, "validation_summary_digest": digest_json(results),
              "selection": "Eligible on both validation seeds, highest unrounded mean reward, then ascending ID",
              "selected": select(results, families)}
    target = OUT / "freeze.json"
    if target.exists() and load_json(target) != freeze:
        raise RuntimeError("Previously frozen selection differs")
    write_json(target, freeze)
    return results


def test_split():
    # Verify that the archived selection was committed before opening a test seed.
    freeze = load_json(OUT / "freeze.json")
    committed = subprocess.check_output(["git", "show", "HEAD:experiments/stage4/freeze.json"], cwd=ROOT)
    if json.loads(committed) != freeze or freeze["contract"] != contract():
        raise ValueError("Frozen contract differs from committed selection or current implementation")
    validation = load_json(OUT / "validation/summary.json")
    families = load_json(SHORTLIST)["finalists_for_validation"]
    if (digest_json(validation) != freeze["validation_summary_digest"]
            or select(validation, families) != freeze["selected"]):
        raise ValueError("Frozen selection differs from validation evidence")
    return run_split("test", TEST, [v["rule"] for v in freeze["selected"].values()], digest_json(freeze))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", choices=("validation", "test"))
    split = parser.parse_args().split
    summary = validate_split() if split == "validation" else test_split()
    print(json.dumps(summary["summary"], indent=2))
