"""Unit tests for scoring logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest

from cae.scoring import ScoringRules, compute_phase_score


class TestComputePhaseScore(unittest.TestCase):
    """Tests for compute_phase_score — pure function, no I/O."""

    def test_first_attempt_full_points(self):
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, 1, rules), 10)

    def test_second_attempt_penalty(self):
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, 2, rules), 8)

    def test_third_attempt_double_penalty(self):
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, 3, rules), 6)

    def test_penalty_hits_floor(self):
        rules = ScoringRules(penalty_per_attempt=5, penalty_floor=2)
        # attempt 1: 10
        # attempt 2: 10 - 5 = 5
        # attempt 3: 10 - 10 = 0, but floor is 2
        self.assertEqual(compute_phase_score(10, 3, rules), 2)

    def test_penalty_floor_equals_points(self):
        """If floor equals points, every attempt gets the same score."""
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=10)
        self.assertEqual(compute_phase_score(10, 1, rules), 10)
        self.assertEqual(compute_phase_score(10, 5, rules), 10)

    def test_large_penalty_capped(self):
        """Penalty cannot exceed points - floor."""
        rules = ScoringRules(penalty_per_attempt=100, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, 2, rules), 0)

    def test_zero_points(self):
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=0)
        self.assertEqual(compute_phase_score(0, 1, rules), 0)
        self.assertEqual(compute_phase_score(0, 3, rules), 0)

    def test_invalid_attempt_zero(self):
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, 0, rules), 0)

    def test_invalid_attempt_negative(self):
        rules = ScoringRules(penalty_per_attempt=2, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, -1, rules), 0)

    def test_no_penalty(self):
        """Zero penalty per attempt means full points every time."""
        rules = ScoringRules(penalty_per_attempt=0, penalty_floor=0)
        self.assertEqual(compute_phase_score(10, 1, rules), 10)
        self.assertEqual(compute_phase_score(10, 10, rules), 10)


if __name__ == "__main__":
    unittest.main()
