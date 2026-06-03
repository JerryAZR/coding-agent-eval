"""Unit tests for benchmark loading and navigation."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest

from cae.benchmark import Benchmark, Phase


class TestBenchmarkLoad(unittest.TestCase):
    """Tests for Benchmark.load from JSON files."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def write_task(self, data: dict) -> Path:
        path = self.base / "task.json"
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_minimal_load(self):
        path = self.write_task({
            "id": "test-bench",
            "phases": [{"id": "p1", "promptFile": "prompts/p1.md"}],
        })
        bm = Benchmark.load(path)
        self.assertEqual(bm.id, "test-bench")
        self.assertEqual(bm.name, "test-bench")
        self.assertEqual(len(bm.phases), 1)
        self.assertEqual(bm.phases[0].id, "p1")
        self.assertEqual(bm.phases[0].max_attempts, 3)
        self.assertEqual(bm.phases[0].points, 0)

    def test_full_load(self):
        path = self.write_task({
            "id": "full-bench",
            "name": "Full Benchmark",
            "phases": [
                {"id": "p1", "promptFile": "prompts/1.md", "maxAttempts": 5, "points": 10},
                {"id": "p2", "promptFile": "prompts/2.md", "maxAttempts": 3, "points": 20},
            ],
            "tests": {"script": "tests/run.sh"},
            "scoring": {"penaltyPerAttempt": 2, "penaltyFloor": 1},
        })
        bm = Benchmark.load(path)
        self.assertEqual(bm.name, "Full Benchmark")
        self.assertEqual(bm.phases[0].max_attempts, 5)
        self.assertEqual(bm.phases[1].points, 20)
        self.assertEqual(bm.scoring.penalty_per_attempt, 2)
        self.assertEqual(bm.scoring.penalty_floor, 1)
        self.assertEqual(bm.tests_script, self.base / "tests" / "run.sh")

    def test_phase_defaults(self):
        path = self.write_task({
            "id": "defaults",
            "phases": [{"id": "p1", "promptFile": "prompts/p1.md"}],
        })
        bm = Benchmark.load(path)
        p = bm.phases[0]
        self.assertEqual(p.name, "p1")
        self.assertEqual(p.max_attempts, 3)
        self.assertEqual(p.points, 0)

    def test_default_tests_path(self):
        path = self.write_task({
            "id": "test",
            "phases": [{"id": "p1", "promptFile": "prompts/p1.md"}],
        })
        bm = Benchmark.load(path)
        self.assertEqual(bm.tests_script, self.base / "tests" / "run.sh")

    def test_empty_phases(self):
        path = self.write_task({"id": "empty", "phases": []})
        bm = Benchmark.load(path)
        self.assertEqual(len(bm.phases), 0)

    def test_phase_by_id_found(self):
        path = self.write_task({
            "id": "test",
            "phases": [
                {"id": "p1", "promptFile": "prompts/1.md"},
                {"id": "p2", "promptFile": "prompts/2.md"},
            ],
        })
        bm = Benchmark.load(path)
        self.assertIsNotNone(bm.phase_by_id("p2"))
        self.assertEqual(bm.phase_by_id("p2").id, "p2")

    def test_phase_by_id_not_found(self):
        path = self.write_task({
            "id": "test",
            "phases": [{"id": "p1", "promptFile": "prompts/1.md"}],
        })
        bm = Benchmark.load(path)
        self.assertIsNone(bm.phase_by_id("p99"))

    def test_next_phase_exists(self):
        path = self.write_task({
            "id": "test",
            "phases": [
                {"id": "p1", "promptFile": "prompts/1.md"},
                {"id": "p2", "promptFile": "prompts/2.md"},
            ],
        })
        bm = Benchmark.load(path)
        next_p = bm.next_phase("p1")
        self.assertIsNotNone(next_p)
        self.assertEqual(next_p.id, "p2")

    def test_next_phase_none(self):
        path = self.write_task({
            "id": "test",
            "phases": [
                {"id": "p1", "promptFile": "prompts/1.md"},
                {"id": "p2", "promptFile": "prompts/2.md"},
            ],
        })
        bm = Benchmark.load(path)
        self.assertIsNone(bm.next_phase("p2"))

    def test_next_phase_invalid(self):
        path = self.write_task({
            "id": "test",
            "phases": [{"id": "p1", "promptFile": "prompts/1.md"}],
        })
        bm = Benchmark.load(path)
        self.assertIsNone(bm.next_phase("p99"))


if __name__ == "__main__":
    unittest.main()
