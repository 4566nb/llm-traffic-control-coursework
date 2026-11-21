# Phase 1: paired single-vehicle simulation

Run from the repository root after the setup in the main README:

```powershell
.venv/Scripts/python stage1_single_vehicle.py
```

The script uses the original course Config, Vehicle and IDMVehicle implementations. It runs experiment 4 at 0.1 s for 60 scheduled vehicles and keeps the bottleneck active for the full 1200 s horizon. Input demand, per-vehicle bottleneck assignments and per-vehicle/per-step IDM relative-speed noise are generated from independent seeded streams, then replayed across all arms. This is a deliberately paired variant of experiment 4, not bit-identical to the teacher's original random-number sequence.

Vehicle 30 uses a subclass with an optional cap on IDM's desired speed. When the current average speed of vehicles within 800 m ahead becomes less than 20 m/s, a one-shot hand-written rule caps its desired speed at 20 m/s, for up to 30 s or until reaching 4500 m, then releases the cap. The cap is combined with the road's current target using the minimum; it is a desired speed, not a hard limit. Check every 1 s. The input is immediate simulator access to nearby vehicles, not an implemented fixed roadside detector. Vehicles 31–40 are the predefined follower group. This is a simple rule inspired by slow-in and release, not an implementation of the paper's JAD triangle and not an LLM-generated policy.

Outputs: results.json has metrics and event records for seeds 1–3; comparison.png shows seed 1 with identical axes and the controlled vehicle in black; controlled_vehicle_trace.csv records that car each 0.1 s; policy_decisions.csv records the observation and decision state every 1 s. Distance between adjacent vehicles is checked from simultaneous 0.1 s position samples while both are active. A nonnegative sampled gap does not establish continuous-time collision safety.

The no-op controlled subclass produces exactly the same recorded vehicle histories as the matching all-IDM arm in all three runs. The intervention triggers and releases in every run, and all 60 vehicles exit. Each paired arm has exactly the same 0.1 s exit timestamp for every vehicle. Slight reductions in speed variation and low-speed vehicle-seconds are development observations, with no generalization claim. The 5 m/s threshold and speed total variation across the full length of follower trips are proxies, not direct measurements of passenger experience or proof of wave dissipation.

Sources and inspiration:

* He, single-vehicle jam absorption: https://github.com/gotrafficgo/jam_absorption_driving and https://arxiv.org/abs/2602.10234
* Flow project, controllers and traffic simulation: https://github.com/flow-project/flow

The LLM feedback loop, optimization and held-out test seeds belong to later phases.
