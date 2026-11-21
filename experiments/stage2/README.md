# Phase 2: evaluator

Development runs use common per-vehicle inputs, check a trajectory-identical no-op controller, and compare the hand-written policy with IDM. The provisional reward uses baseline-relative percentage reductions weighted 0.5 travel time, 0.3 follower variation, 0.1 low-speed exposure and 0.1 last exit time. Scores are not percentages of real-world improvement.

On development seeds 1–3, the mean reward is approximately 0.557; all candidate runs satisfy the preliminary 2 m sampled gap criterion. However, all three show zero total travel-time change, so the predefined condition that both time and variation improve is false for every run. No held-out performance or LLM-generated rule has been measured.

Exit checks are at simulation samples; score eligibility does not establish real-world or continuous-time safety. The instantaneous 800 m forward observation and provisional thresholds are experiment assumptions, and both policies share the same underlying IDM physical bounds.
