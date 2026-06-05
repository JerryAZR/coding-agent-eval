"""Unit tests for .cae/ volume protocol."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest

from cae.protocol import (
    Volume,
    TestResult,
    Score,
)


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

    def test_write_and_read_prompt(self):
        self.volume.write_prompt("Build a CLI tool.")
        restored = self.volume.read_prompt()
        self.assertIsNotNone(restored)
        self.assertEqual(restored, "Build a CLI tool.")

    def test_read_prompt_missing(self):
        self.assertIsNone(self.volume.read_prompt())

    def test_delete_prompt(self):
        self.volume.write_prompt("test")
        self.assertIsNotNone(self.volume.read_prompt())
        self.volume.delete_prompt()
        self.assertIsNone(self.volume.read_prompt())

    def test_delete_prompt_idempotent(self):
        """Deleting a non-existent prompt should not raise."""
        self.volume.delete_prompt()
        self.assertIsNone(self.volume.read_prompt())

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


if __name__ == "__main__":
    unittest.main()
