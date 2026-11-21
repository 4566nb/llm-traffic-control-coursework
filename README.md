# LLM-guided single-vehicle traffic control

Coursework Part II experiment records for an exploratory combination of single-vehicle traffic smoothing and simulation-feedback-guided rule search.

**Current status.** Phase 4 selected R3B and H20_100 on validation and froze both rules before opening six held-out experiment 4 traffic sequences. R3B reduced follower speed variation by 2.67% and whole-cohort low-speed time by 7.18% on average. All 360 individual exit timestamps matched the paired all-IDM baseline. [Frozen test results and evidence](experiments/stage4/README.md) · [Development search](experiments/stage3/README.md)

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

These commands reproduce the stage 1 and 2 references. The finite cohort experiment uses explicitly paired random streams that differ from the teacher's default sequence. The evaluator records completion and sampled-gap failures separately.

## Contents

- `stage1_single_vehicle.py` — 60-vehicle paired simulation, replay check, one hand-written intervention and trajectory plot.
- `evaluate.py` — completion checks, sampled minimum gap, baseline-relative metrics and exploratory reward.
- `test_evaluate.py` — checks scoring and rejection cases.
- `stage3_policy.py`, `stage3_search.py`, `stage3_report.py` — decision tables, development batch replay and shortlist/figures.
- `stage4_freeze.py` and `stage4_report.py` — validation selection, committed-rule testing and archive-based analysis.
- `experiments/` — the experiment plan, paired reference runs, development search, freeze and held-out results.

## Assessment

Total cohort travel time includes waiting from scheduled arrival. Speed variation covers followers 31–40, and low-speed exposure counts vehicle-seconds below 5 m/s. Baseline and intervention use common demand, bottleneck assignments and vehicle-by-step noise. Net gaps are checked at 0.1 s samples. The test uses the reward weights fixed at selection. Seeds 1–3 guided design, 11–12 selected finalists, and 101–106 produced the frozen test comparison.

## Attribution

The teacher simulator is https://github.com/gotrafficgo/teaching_artificial_intelligence at commit `9a324d9ce9671a11184c4e8f1f9555fb0d8ea2c1`. We use it locally without republishing the source here. He’s jam-absorption driving paper and code provide the single-car intervention inspiration: https://arxiv.org/abs/2602.10234 and https://github.com/gotrafficgo/jam_absorption_driving. The proposed feedback-guided rule generation is inspired by FunSearch: https://www.nature.com/articles/s41586-023-06924-6. The hand-written rule here is a simplified adaptation and is not an implementation of the paper's JAD triangle.
