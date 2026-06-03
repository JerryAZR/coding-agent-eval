"""Unit tests for .cae/ volume protocol."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest

from cae.protocol import (
    Volume,
    TaskState,
    TestResult,
    Feedback,
    Score,
)


class TestTaskStateSerialization(unittest.TestCase):
    def test_roundtrip(self):
        original = TaskState(
            benchmark_id="bench-1",
            phase_id="phase-1",
            attempt=2,
            prompt="Build a CLI tool.",
            max_attempts=3,
            points=10,
        )
        d = original.to_dict()
        restored = TaskState.from_dict(d)
        self.assertEqual(restored.benchmark_id, "bench-1")
        self.assertEqual(restored.phase_id, "phase-1")
        self.assertEqual(restored.attempt, 2)
        self.assertEqual(restored.prompt, "Build a CLI tool.")
        self.assertEqual(restored.max_attempts, 3)
        self.assertEqual(restored.points, 10)


class TestTestResultSerialization(unittest.TestCase):
    def test_roundtrip(self):
        original = TestResult(
            phase_id="phase-1",
            passed=True,
            details="All tests passed",
            exit_code=0,
        )
        d = original.to_dict()
        restored = TestResult.from_dict(d)
        self.assertEqual(restored.phase_id, "phase-1")
        self.assertTrue(restored.passed)
        self.assertEqual(restored.details, "All tests passed")
        self.assertEqual(restored.exit_code, 0)

    def test_defaults_on_missing_fields(self):
        d = {"phaseId": "p1", "passed": False}
        restored = TestResult.from_dict(d)
        self.assertEqual(restored.details, "")
        self.assertEqual(restored.exit_code, 1)


class TestFeedbackSerialization(unittest.TestCase):
    def test_roundtrip(self):
        original = Feedback(
            phase_id="phase-1",
            attempt=2,
            passed=False,
            message="Syntax error",
            phase_complete=False,
            next_phase_id="phase-2",
        )
        d = original.to_dict()
        restored = Feedback.from_dict(d)
        self.assertEqual(restored.phase_id, "phase-1")
        self.assertFalse(restored.passed)
        self.assertEqual(restored.message, "Syntax error")
        self.assertFalse(restored.phase_complete)
        self.assertEqual(restored.next_phase_id, "phase-2")

    def test_next_phase_none(self):
        original = Feedback(
            phase_id="phase-1",
            attempt=1,
            passed=True,
            message="Done",
            phase_complete=True,
            next_phase_id=None,
        )
        d = original.to_dict()
        restored = Feedback.from_dict(d)
        self.assertIsNone(restored.next_phase_id)


class TestScoreSerialization(unittest.TestCase):
    def test_roundtrip(self):
        original = Score(
            benchmark_id="bench-1",
            total_points=30,
            phases={"p1": {"points": 10, "attempts": 1, "best": True}},
        )
        d = original.to_dict()
        restored = Score.from_dict(d)
        self.assertEqual(restored.benchmark_id, "bench-1")
        self.assertEqual(restored.total_points, 30)
        self.assertEqual(restored.phases["p1"]["points"], 10)


class TestVolumeOperations(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.volume = Volume(self.tmpdir.name)
        self.volume.ensure_dirs()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ensure_dirs_creates_structure(self):
        self.assertTrue(self.volume.cae.exists())
        self.assertTrue(self.volume.results.exists())

    def test_write_and_read_task(self):
        task = TaskState(
            benchmark_id="b1",
            phase_id="p1",
            attempt=1,
            prompt="Build it",
            max_attempts=3,
            points=10,
        )
        self.volume.write_task(task)
        restored = self.volume.read_task()
        self.assertIsNotNone(restored)
        self.assertEqual(restored.phase_id, "p1")
        self.assertEqual(restored.prompt, "Build it")

    def test_read_task_missing(self):
        self.assertIsNone(self.volume.read_task())

    def test_write_and_read_feedback(self):
        fb = Feedback(
            phase_id="p1",
            attempt=1,
            passed=True,
            message="OK",
            phase_complete=True,
            next_phase_id=None,
        )
        self.volume.write_feedback(fb)
        restored = self.volume.read_feedback()
        self.assertTrue(restored.passed)
        self.assertTrue(restored.phase_complete)

    def test_read_feedback_missing(self):
        self.assertIsNone(self.volume.read_feedback())

    def test_write_and_read_score(self):
        score = Score(
            benchmark_id="b1",
            total_points=20,
            phases={},
        )
        self.volume.write_score(score)
        restored = self.volume.read_score()
        self.assertEqual(restored.total_points, 20)

    def test_write_and_read_result(self):
        result = TestResult(
            phase_id="p1",
            passed=True,
            details="good",
            exit_code=0,
        )
        self.volume.write_result(result)
        restored = self.volume.read_result()
        self.assertTrue(restored.passed)

    def test_read_result_missing(self):
        self.assertIsNone(self.volume.read_result())

    def test_ready_marker(self):
        self.assertFalse(self.volume.is_ready())
        self.volume.set_ready()
        self.assertTrue(self.volume.is_ready())
        self.volume.clear_ready()
        self.assertFalse(self.volume.is_ready())

    def test_clear_ready_idempotent(self):
        """Clearing a non-existent marker should not raise."""
        self.volume.clear_ready()
        self.assertFalse(self.volume.is_ready())

    def test_feedback_change_detection(self):
        """Two feedback writes with same content should produce identical dicts."""
        fb1 = Feedback("p1", 1, True, "ok", True, None)
        fb2 = Feedback("p1", 1, True, "ok", True, None)
        self.volume.write_feedback(fb1)
        d1 = self.volume.read_feedback().to_dict()
        self.volume.write_feedback(fb2)
        d2 = self.volume.read_feedback().to_dict()
        self.assertEqual(d1, d2)


if __name__ == "__main__":
    unittest.main()
