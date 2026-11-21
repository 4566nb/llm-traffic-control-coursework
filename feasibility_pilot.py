"""Time and score a finite all-IDM cohort using the course simulator."""
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "teacher-source"))
from config import Config
from simulator import Simulator


class FiniteCohort(Simulator):
    def __init__(self, config, size):
        super().__init__(config)
        self.size = size
        self.demand_times = []

    def _generate_vehicle(self, current_time):
        count = len(self.vehicles)
        if count < self.size:
            scheduled = self.next_generation_time
            super()._generate_vehicle(current_time)
            if len(self.vehicles) > count:
                self.demand_times.append(scheduled)


def pilot(seed):
    start = perf_counter()
    config = Config(seed=seed, experiment=4, time_max=1200)
    sim = FiniteCohort(config, 60)
    sim.run(verbose=False)
    assert len(sim.vehicles) == sim.size and all(not v.active for v in sim.vehicles)
    total_time = low_speed = variation = distance = 0.0
    minimum_gap = float("inf")
    previous = None
    exits = []
    for vehicle, scheduled in zip(sim.vehicles, sim.demand_times):
        history = vehicle.history
        exit_time = history[-1]["t"]
        exits.append(exit_time)
        total_time += exit_time - scheduled
        speeds = np.array([s["speed"] for s in history])
        positions = np.array([s["position"] for s in history])
        low_speed += np.count_nonzero(speeds[:-1] < 5) * config.time_step
        if 31 <= vehicle.id <= 40:
            variation += np.abs(np.diff(speeds)).sum()
            distance += positions[-1] - positions[0]
        first = round(history[0]["t"] / config.time_step)
        if previous is not None:
            prev_first, prev_positions = previous
            offset = first - prev_first
            leader = prev_positions[offset:-1]
            n = min(len(leader), len(positions) - 1)
            if n:
                minimum_gap = min(minimum_gap, (leader[:n] - positions[:n]).min() - config.vehicle_length)
        previous = first, positions
    return dict(seed=seed, cohort=sim.size, exited=sum(t <= 400 for t in exits),
                exit_count_window_s=400, total_vehicle_s=round(total_time, 2),
                clearance_s=max(exits), low_speed_vehicle_s=round(low_speed, 2),
                follower_speed_variation_per_km=round(variation / (distance / 1000), 3),
                min_sampled_gap_m=round(float(minimum_gap), 3),
                elapsed_wall_s=round(perf_counter() - start, 2))


if __name__ == "__main__":
    print(json.dumps([pilot(s) for s in (1, 2)], indent=2))
