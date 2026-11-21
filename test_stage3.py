"""Regression checks for the stage 3 adapter, optional sensors and shortlist."""
import unittest

from stage1_single_vehicle import run
from stage3_policy import TablePolicy, validate
from stage3_report import shortlist
from stage3_search import OUT, attach_diagnostics, load_json


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.grid_rule = next(r for r in load_json(OUT / "proposals" / "grid.json")
                              if r["id"] == "H20_30")

    def test_fixed_table_replays_stage1_trajectories(self):
        old, demand, flags, _, _ = run(1, "intervention")
        new, demand2, flags2, _, _ = run(1, "candidate", TablePolicy(self.grid_rule))
        self.assertEqual((demand, flags), (demand2, flags2))
        self.assertEqual([v.history for v in old], [v.history for v in new])

    def test_missing_observation_and_one_shot_release(self):
        obs = dict(position=1000, ahead=None, ego=25)
        rule = dict(self.grid_rule, duration=2, target=["ahead", 0.6, 2, 4, 24], drop=1)
        policy = TablePolicy(rule)
        self.assertIsNone(policy.decide(0, obs))
        self.assertEqual(policy.decide(1, dict(obs, ahead=10)), 24)
        self.assertEqual(policy.decide(2, obs), 24)
        self.assertIsNone(policy.decide(3, dict(obs, ahead=10)))
        self.assertIsNone(policy.decide(4, dict(obs, ahead=10)))

    def test_boundary_prevents_first_activation(self):
        p = TablePolicy(self.grid_rule)
        self.assertIsNone(p.decide(10, dict(position=4500, ahead=3, ego=12)))
        self.assertEqual(p.state, "done")

    def test_rejects_post_decision_information(self):
        with self.assertRaises(ValueError):
            validate(dict(self.grid_rule, start=[["min_ego_accel_next_s", "<", 0]]))

    def test_no_decisions_and_ineligible_or_tied_rules(self):
        self.assertEqual(attach_diagnostics([], [])["active_s_samples"], 0)
        rows = [dict(id=k, mean_reward=v) for k, v in (("Z", None), ("C", .5), ("B", .5))]
        self.assertEqual([r["id"] for r in shortlist(rows)], ["B", "C"])


if __name__ == "__main__":
    unittest.main()
