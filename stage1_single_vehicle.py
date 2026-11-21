"""Paired experiment 4 with one replaceable IDM target-speed policy."""
import csv
import json
import math
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "teacher-source"))
from config import Config
from vehicle_idm import IDMVehicle

OUT = HERE / "experiments" / "stage1"
DT = 0.1
COHORT = 60
CONTROLLED = 30
HORIZON = 1200


class ControlledIDM(IDMVehicle):
    """Same IDM as the baseline, with an optional temporary target speed."""

    def __init__(self, config, vehicle_id, vehicle_front=None):
        super().__init__(config, vehicle_id, vehicle_front)
        self.policy_cap = None

    def update_acceleration(self):
        road_target = self.current_speed_limit
        if self.policy_cap is not None:
            self.current_speed_limit = min(road_target, self.policy_cap)
        try:
            super().update_acceleration()
        finally:
            self.current_speed_limit = road_target


def scenario(seed):
    arrival_rng = random.Random(seed * 10 + 1)
    flag_rng = random.Random(seed * 10 + 2)
    arrivals = [0.0]
    for _ in range(COHORT - 1):
        arrivals.append(arrivals[-1] + 1 + arrival_rng.expovariate(2))
    flags = [flag_rng.random() < 0.7 for _ in arrivals]
    noise = np.random.default_rng(seed * 10 + 3).normal(
        0, 0.5, (COHORT, round(HORIZON / DT))
    )
    return arrivals, flags, noise


def run(seed, arm):
    arrivals, flags, noise = scenario(seed)
    config = Config(seed=seed, experiment=4, time_max=HORIZON)
    vehicles = []
    events = []
    decisions = []
    state = "waiting"
    start_time = None
    original_gauss = random.gauss
    try:
        for step in range(round(HORIZON / DT)):
            t = round(step * DT, 10)
            active = [v for v in vehicles if v.active]
            if len(vehicles) < COHORT and t + 1e-9 >= arrivals[len(vehicles)]:
                leader = active[-1] if active else None
                if leader is None or leader.position >= 37:
                    vid = len(vehicles) + 1
                    cls = ControlledIDM if vid == CONTROLLED and arm != "baseline" else IDMVehicle
                    vehicle = cls(config, vid, leader)
                    vehicle.influenced_by_bottleneck = flags[vid - 1]
                    vehicle.record_state(t)
                    vehicles.append(vehicle)
                    active.append(vehicle)

            for v in active:
                v.check_road(t)

            if arm == "intervention" and step % 10 == 0:
                controlled = next((v for v in active if v.id == CONTROLLED), None)
                if controlled is not None:
                    # Average current observed speeds in the next 800 m.
                    ahead = [v.speed for v in active
                             if controlled.position < v.position <= controlled.position + 800]
                    mean_speed = sum(ahead) / len(ahead) if ahead else None
                    if state == "waiting" and mean_speed is not None and mean_speed < 20:
                        state, start_time = "active", t
                        controlled.policy_cap = 20.0
                        events.append({"time_s": t, "event": "start", "position_m": controlled.position,
                                       "observed_ahead_speed_mps": mean_speed, "target_cap_mps": 20.0})
                    elif state == "active" and (t - start_time >= 30 or controlled.position >= 4500):
                        state = "done"
                        controlled.policy_cap = None
                        events.append({"time_s": t, "event": "release", "position_m": controlled.position,
                                       "observed_ahead_speed_mps": mean_speed, "target_cap_mps": None})
                    decisions.append({"time_s": t, "position_m": controlled.position,
                                      "speed_mps": controlled.speed, "ahead_count": len(ahead),
                                      "ahead_mean_speed_mps": mean_speed, "state": state,
                                      "policy_cap_mps": controlled.policy_cap,
                                      "road_target_mps": controlled.current_speed_limit})

            for v in active:
                value = float(noise[v.id - 1, step])
                random.gauss = lambda mu, sigma, value=value: value
                v.update_acceleration()
            for v in active:
                v.update_motion()
            for v in active:
                v.record_state(round(t + DT, 10))
            if len(vehicles) == COHORT and not any(v.active for v in vehicles):
                break
    finally:
        random.gauss = original_gauss
    return vehicles, arrivals, flags, events, decisions


def metrics(vehicles, arrivals):
    completed = [v for v in vehicles if not v.active]
    result = {"vehicles_admitted": len(vehicles), "vehicles_exited": len(completed),
              "exited_by_400s": sum(v.history[-1]["t"] <= 400 for v in completed),
              "all_completed": len(completed) == COHORT}
    if result["all_completed"]:
        result["total_travel_s"] = sum(v.history[-1]["t"] - arrivals[v.id-1] for v in vehicles)
        result["last_exit_s"] = max(v.history[-1]["t"] for v in vehicles)
    variation = distance = low_time = 0.0
    min_gap = math.inf
    for v in vehicles:
        h = v.history
        speeds = np.array([x["speed"] for x in h])
        pos = np.array([x["position"] for x in h])
        low_time += np.count_nonzero(speeds[:-1] < 5) * DT
        if 31 <= v.id <= 40:
            variation += np.abs(np.diff(speeds)).sum()
            distance += pos[-1] - pos[0]
        if v.vehicle_front:
            front = v.vehicle_front.history
            offset = round((h[0]["t"] - front[0]["t"]) / DT)
            count = min(len(pos) - 1, len(front) - offset - 1)
            if count > 0:
                fp = np.array([x["position"] for x in front[offset:offset+count]])
                min_gap = min(min_gap, float(np.min(fp - pos[:count] - v.vehicle_length)))
    result.update(low_speed_vehicle_s=low_time,
                  follower_variation_per_km=variation/(distance/1000) if distance else None,
                  min_sampled_gap_m=min_gap if math.isfinite(min_gap) else None)
    return result


def make_figure(baseline, controlled, events):
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True, sharey=True, constrained_layout=True)
    for ax, (vehicles, title) in zip(axes, [(baseline, "All-IDM baseline"), (controlled, "One controlled vehicle")]):
        for v in vehicles:
            h = v.history[::5]
            if len(h) < 2:
                continue
            points = np.array([(x["t"], x["position"]/1000) for x in h]).reshape(-1, 1, 2)
            segments = np.concatenate((points[:-1], points[1:]), axis=1)
            if v.id == CONTROLLED:
                ax.add_collection(LineCollection(segments, colors="#151515", linewidths=2, zorder=3))
            else:
                coll = LineCollection(segments, cmap="viridis", norm=plt.Normalize(0, 30), linewidths=0.8)
                coll.set_array(np.array([x["speed"] for x in h[:-1]]))
                ax.add_collection(coll)
        ax.set(title=title, ylabel="Position (km)", xlim=(0, 800), ylim=(0, 5))
        ax.grid(alpha=.15)
    for event in events:
        axes[1].scatter(event["time_s"], event["position_m"]/1000, s=55, color="red", zorder=4)
        axes[1].annotate(event["event"], (event["time_s"], event["position_m"]/1000),
                         xytext=(8, -15), textcoords="offset points", color="darkred")
    axes[1].set_xlabel("Simulation time (s)")
    fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 30), cmap="viridis"),
                 ax=axes, label="Speed (m/s)", shrink=.8)
    fig.suptitle("Experiment 4, seed 1 · black line: vehicle 30")
    fig.savefig(OUT / "comparison.png", dpi=170)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for seed in (1, 2, 3):
        baseline, arrivals, flags, _, _ = run(seed, "baseline")
        noop, noop_arrivals, noop_flags, _, _ = run(seed, "noop")
        assert arrivals == noop_arrivals and flags == noop_flags
        assert [v.history for v in baseline] == [v.history for v in noop], "No-op replay differs"
        controlled, c_arrivals, c_flags, events, decisions = run(seed, "intervention")
        assert arrivals == c_arrivals and flags == c_flags
        assert [e["event"] for e in events] == ["start", "release"], (seed, events)
        changed_exits = sum(b.history[-1]["t"] != c.history[-1]["t"] for b, c in zip(baseline, controlled))
        results[str(seed)] = {"baseline": metrics(baseline, arrivals),
                              "intervention": metrics(controlled, arrivals), "events": events,
                              "noop_trajectory_identical": True, "vehicles_with_changed_exit_time": changed_exits}
        if seed == 1:
            make_figure(baseline, controlled, events)
            with (OUT / "controlled_vehicle_trace.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["t", "position", "speed", "acceleration"])
                writer.writeheader()
                writer.writerows(controlled[CONTROLLED - 1].history)
            with (OUT / "policy_decisions.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(decisions[0]))
                writer.writeheader()
                writer.writerows(decisions)
    (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
