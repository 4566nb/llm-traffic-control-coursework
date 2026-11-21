"""One-second observations and bounded decision tables for simulated vehicle 30."""
import math
from collections import deque
from statistics import mean

from stage1_single_vehicle import CONTROLLED

FEATURES = {"position", "ego", "ahead", "leader", "gap", "zone_speed", "entry_rate"}


def validate(rule):
    """Accept only the finite, causal rule grammar used in this search."""
    if set(rule) != {"id", "start", "duration", "end_m", "target", "drop", "release"}:
        raise ValueError("Unexpected rule fields")
    if not rule["start"] or not 1 <= rule["duration"] <= 300 or not 0 < rule["end_m"] <= 4500:
        raise ValueError("Invalid trigger, time or upstream boundary")
    for name, op, threshold in rule["start"] + rule["release"]:
        if name not in FEATURES or op not in {"<", ">"} or not math.isfinite(threshold):
            raise ValueError("Invalid condition")
    feature, gain, offset, low, high = rule["target"]
    if feature not in FEATURES or not all(map(math.isfinite, [gain, offset, low, high])):
        raise ValueError("Invalid target")
    if not 2 <= low <= high <= 30 or not 0 < rule["drop"] <= 30:
        raise ValueError("Invalid desired speed or slew rate")


def matches(conditions, observation):
    for name, op, threshold in conditions:
        value = observation[name]
        if value is None or not (value < threshold if op == "<" else value > threshold):
            return False
    return bool(conditions)


class TablePolicy:
    def __init__(self, rule):
        validate(rule)
        self.rule = rule
        self.state = "waiting"
        self.start_time = None
        self.previous_cap = None
        self.zone = deque(maxlen=5)
        self.previous_entries = 0

    def decide(self, t, obs):
        rule = self.rule
        if obs["position"] >= rule["end_m"] or (
            self.state == "active" and (
                t - self.start_time >= rule["duration"] or matches(rule["release"], obs)
            )
        ):
            self.state = "done"
        elif self.state == "waiting" and matches(rule["start"], obs):
            self.state = "active"
            self.start_time = t
        if self.state != "active":
            self.previous_cap = None
            return None

        feature, gain, offset, low, high = rule["target"]
        signal = obs[feature]
        if gain != 0 and signal is None:
            return self.previous_cap
        target = max(low, min(high, offset + gain * (signal or 0)))
        anchor = self.previous_cap if self.previous_cap is not None else obs["ego"]
        self.previous_cap = max(target, anchor - rule["drop"])
        return self.previous_cap

    def sample(self, t, vehicles, active, decisions):
        # At integer t, positions are sampled before any motion for [t, t+0.1].
        zone_speeds = [v.speed for v in active if 4300 <= v.position < 4500]
        entries = sum(v.position >= 4500 for v in vehicles)
        self.zone.append((sum(zone_speeds), len(zone_speeds), entries - self.previous_entries))
        self.previous_entries = entries
        ego = next((v for v in active if v.id == CONTROLLED), None)
        if ego is None:
            return
        ahead = [v.speed for v in active if ego.position < v.position <= ego.position + 800]
        leader = ego.vehicle_front
        has_leader = leader is not None and leader.active
        zone_count = sum(n for _, n, _ in self.zone)
        obs = {
            "position": ego.position, "ego": ego.speed, "ahead": mean(ahead) if ahead else None,
            "leader": leader.speed if has_leader else None,
            "gap": leader.position - ego.position - ego.vehicle_length if has_leader else None,
            "zone_speed": sum(s for s, _, _ in self.zone) / zone_count if zone_count else None,
            "entry_rate": sum(n for _, _, n in self.zone) / len(self.zone),
        }
        cap = self.decide(t, obs)
        ego.policy_cap = cap
        road = ego.current_speed_limit
        decisions.append(dict(t=t, **obs, state=self.state, cap=cap, road=road,
                              effective_target=road if cap is None else min(cap, road)))
