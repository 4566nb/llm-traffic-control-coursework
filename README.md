# LLM-guided single-vehicle traffic control

Coursework Part II experiment records for an exploratory combination of single-vehicle traffic smoothing and simulation-feedback-guided rule search.

**Current status:** phase 1 paired vehicle controller and phase 2 scoring are implemented. The only intervention evaluated so far is a manually designed rule. LLM candidate generation and held-out evaluation have not started.

## Reproduce

Python 3.12 and Git are required. The course simulator is fetched separately at the original pinned revision; it is not included in this repository.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python bootstrap.py
.venv/Scripts/python stage1_single_vehicle.py
.venv/Scripts/python -m unittest -v test_evaluate.py
.venv/Scripts/python evaluate.py
```

Results are written to `experiments/stage1` and `experiments/stage2`. The finite cohort experiment uses an explicitly paired random stream and is not a bit-for-bit replication of the teacher's default random sequence. A failed or unfinished run is not assigned a misleading score.

## Contents

- `stage1_single_vehicle.py` — 60-vehicle paired simulation, replay check, one hand-written intervention and trajectory plot.
- `evaluate.py` — completion checks, sampled minimum gap, baseline-relative metrics and exploratory reward.
- `test_evaluate.py` — checks scoring and rejection cases.
- `experiments/` — stage 1 artifacts, phase 2 results and the experimental plan.

## Assessment

Total cohort travel time includes waiting from scheduled arrival. The speed variation measurement concerns followers 31–40; low-speed exposure is counted below 5 m/s. Baseline and intervention use common demand, bottleneck assignments, and per-vehicle per-step noise. Safety metrics observe 0.1 s samples and do not prove continuous-time safety. Rewards and weights are provisional and scores must be read alongside the raw metrics. Development seeds 1–3 have been used; they are not held-out results.

## Attribution

The teacher simulator is https://github.com/gotrafficgo/teaching_artificial_intelligence at commit `9a324d9ce9671a11184c4e8f1f9555fb0d8ea2c1`. We use it locally without republishing the source here. He’s jam-absorption driving paper and code provide the single-car intervention inspiration: https://arxiv.org/abs/2602.10234 and https://github.com/gotrafficgo/jam_absorption_driving. The proposed feedback-guided rule generation is inspired by FunSearch: https://www.nature.com/articles/s41586-023-06924-6. The hand-written rule here is a simplified adaptation and is not an implementation of the paper's JAD triangle.
