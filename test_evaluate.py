"""Checks on the evaluation contract and failure handling."""
import unittest
from evaluate import score
from stage1_single_vehicle import metrics


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.base = dict(all_completed=True, vehicles_admitted=60, min_sampled_gap_m=3,
                         total_travel_s=100, follower_variation_per_km=10,
                         low_speed_vehicle_s=20, last_exit_s=40)

    def test_identical_baseline_scores_zero(self):
        self.assertEqual(score(self.base, self.base)["reward"], 0)

    def test_weighted_improvement(self):
        candidate = dict(self.base, total_travel_s=90, follower_variation_per_km=9,
                         low_speed_vehicle_s=18, last_exit_s=36)
        self.assertAlmostEqual(score(self.base, candidate)["reward"], 10)

    def test_incomplete_and_close_candidates_are_ineligible(self):
        self.assertEqual(score(self.base, dict(self.base, all_completed=False))["status"], "ineligible")
        self.assertEqual(score(self.base, dict(self.base, min_sampled_gap_m=1.9))["status"], "ineligible")

    def test_unsafe_baseline_and_zero_denominator_are_not_ranked(self):
        self.assertEqual(score(dict(self.base, min_sampled_gap_m=1), self.base)["status"], "invalid_baseline")
        self.assertEqual(score(dict(self.base, low_speed_vehicle_s=0), self.base)["status"], "undefined")

    def test_empty_run_is_reported_incomplete(self):
        candidate = metrics([], [])
        self.assertFalse(candidate["all_completed"])
        self.assertEqual(score(self.base, candidate)["status"], "ineligible")


if __name__ == "__main__":
    unittest.main()
