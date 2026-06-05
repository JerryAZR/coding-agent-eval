"""Module-level tests for manager state transitions.

These mock out the Runtime to test decision logic in isolation.
The mock worker runs in a thread and properly simulates the ready loop.
"""
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cae.benchmark import Benchmark
from cae.protocol import Volume, TestResult
from cae.manager import run_group
from cae.runtime import Runtime


class MockRuntime(Runtime):
    """A test Runtime that delegates worker and tester to callables."""

    def __init__(
        self,
        worker_proc: subprocess.Popen | None = None,
        result_factory=None,
    ):
        self.worker_proc = worker_proc
        self.result_factory = result_factory

    def spawn_worker(self, volume, agent_cmd=None):
        return self.worker_proc

    def spawn_tester(self, volume, benchmark, phase_id):
        if self.result_factory:
            result = self.result_factory(phase_id)
            volume.write_result(result)
            return MagicMock(returncode=0 if result.passed else 1)
        return MagicMock(returncode=0)


class MockWorker:
    """A threaded mock worker that simulates the real worker's ready loop."""

    def __init__(self, volume: Volume):
        self.volume = volume
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        """Monitor prompt and rewrite ready when appropriate."""
        while not self._stop.is_set():
            prompt = self.volume.read_prompt()
            if prompt is not None:
                self.volume.delete_prompt()
                time.sleep(0.1)
                if not self._stop.is_set():
                    try:
                        self.volume.set_ready()
                    except OSError:
                        break
                # Wait for ready to clear
                while self.volume.is_ready() and not self._stop.is_set():
                    time.sleep(0.1)
            else:
                time.sleep(0.1)

    def stop(self):
        self._stop.set()

    def poll(self):
        """Return None if running, 0 if stopped."""
        if self._thread.is_alive():
            return None
        return 0


class TestManagerTransitions(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

        bench_dir = self.base / "benchmark"
        bench_dir.mkdir()
        (bench_dir / "prompts").mkdir()
        (bench_dir / "prompts" / "p1.md").write_text("Phase 1 prompt")
        (bench_dir / "prompts" / "p2.md").write_text("Phase 2 prompt")

        tests_dir = bench_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "run.sh").write_text("#!/bin/bash\nexit 0\n")
        (tests_dir / "run.sh").chmod(0o755)

        task = {
            "id": "test-bench",
            "phases": [
                {"id": "phase-1", "promptFile": "prompts/p1.md", "maxAttempts": 3, "points": 10},
                {"id": "phase-2", "promptFile": "prompts/p2.md", "maxAttempts": 3, "points": 20},
            ],
            "tests": {"script": "tests/run.sh"},
            "scoring": {"penaltyPerAttempt": 2, "penaltyFloor": 0},
        }
        with open(bench_dir / "task.json", "w") as f:
            json.dump(task, f)

        self.benchmark = Benchmark.load(bench_dir / "task.json")
        self.volume_path = self.base / "volume"
        self.worker = None

    def tearDown(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker._thread.join(timeout=1)
        self.tmpdir.cleanup()

    def _make_worker(self, volume: Volume):
        worker = MockWorker(volume)
        self.worker = worker
        worker.start()
        proc = MagicMock()
        proc.poll = worker.poll
        return proc

    def test_happy_path_all_phases(self):
        volume = Volume(self.volume_path)
        volume.ensure_dirs()

        proc = self._make_worker(volume)
        runtime = MockRuntime(
            worker_proc=proc,
            result_factory=lambda pid: TestResult(
                phase_id=pid, passed=True, details="ok", exit_code=0
            ),
        )

        score = run_group(
            self.benchmark, self.volume_path, runtime=runtime, max_total_time=30
        )

        self.assertEqual(score.total_points, 30)
        self.assertTrue(score.phases["phase-1"]["best"])
        self.assertTrue(score.phases["phase-2"]["best"])

    def test_retry_then_pass(self):
        volume = Volume(self.volume_path)
        volume.ensure_dirs()

        call_count = [0]

        def factory(pid):
            call_count[0] += 1
            passed = call_count[0] > 1
            return TestResult(
                phase_id=pid,
                passed=passed,
                details="ok" if passed else "fail",
                exit_code=0 if passed else 1,
            )

        proc = self._make_worker(volume)
        runtime = MockRuntime(worker_proc=proc, result_factory=factory)

        score = run_group(
            self.benchmark, self.volume_path, runtime=runtime, max_total_time=30
        )

        self.assertEqual(score.total_points, 28)
        self.assertEqual(score.phases["phase-1"]["attempts"], 2)
        self.assertEqual(score.phases["phase-1"]["points"], 8)

    def test_all_attempts_fail_ends_benchmark(self):
        """All attempts fail; benchmark terminates, next phase is NOT given."""
        volume = Volume(self.volume_path)
        volume.ensure_dirs()

        proc = self._make_worker(volume)
        runtime = MockRuntime(
            worker_proc=proc,
            result_factory=lambda pid: TestResult(
                phase_id=pid, passed=False, details="fail", exit_code=1
            ),
        )

        score = run_group(
            self.benchmark, self.volume_path, runtime=runtime, max_total_time=60
        )

        self.assertEqual(score.total_points, 0)
        self.assertEqual(score.phases["phase-1"]["attempts"], 3)
        self.assertFalse(score.phases["phase-1"]["best"])
        self.assertNotIn("phase-2", score.phases)
    def test_phase_timeout_ends_benchmark(self):
        """A phase with a short max_time times out if worker hangs."""
        bench_dir = self.base / "timed-benchmark"
        bench_dir.mkdir()
        (bench_dir / "prompts").mkdir()
        (bench_dir / "prompts" / "p1.md").write_text("Phase 1 prompt")

        tests_dir = bench_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "run.sh").write_text("#!/bin/bash\nexit 0\n")
        (tests_dir / "run.sh").chmod(0o755)

        task = {
            "id": "timed-bench",
            "phases": [
                {"id": "phase-1", "promptFile": "prompts/p1.md", "maxAttempts": 3, "points": 10, "maxTime": 0.1},
                {"id": "phase-2", "promptFile": "prompts/p2.md", "maxAttempts": 3, "points": 20},
            ],
            "tests": {"script": "tests/run.sh"},
            "scoring": {"penaltyPerAttempt": 0, "penaltyFloor": 0},
        }
        with open(bench_dir / "task.json", "w") as f:
            json.dump(task, f)

        benchmark = Benchmark.load(bench_dir / "task.json")

        # Worker that never sets ready (simulates hung agent)
        proc = MagicMock()
        proc.poll.return_value = None
        runtime = MockRuntime(worker_proc=proc)

        score = run_group(
            benchmark, self.volume_path, runtime=runtime, max_total_time=30
        )

        self.assertEqual(score.total_points, 0)
        # Phase timed out before any attempt completed
        self.assertEqual(score.phases.get("phase-1", {}).get("attempts", 0), 0)
        self.assertNotIn("phase-2", score.phases)

    def test_worker_exits_early(self):
        proc = MagicMock()
        proc.poll.return_value = 0
        runtime = MockRuntime(worker_proc=proc)

        score = run_group(
            self.benchmark, self.volume_path, runtime=runtime, max_total_time=5
        )

        self.assertEqual(score.total_points, 0)

    def test_score_written_on_pass(self):
        volume = Volume(self.volume_path)
        volume.ensure_dirs()

        proc = self._make_worker(volume)
        runtime = MockRuntime(
            worker_proc=proc,
            result_factory=lambda pid: TestResult(
                phase_id=pid, passed=True, details="ok", exit_code=0
            ),
        )

        run_group(
            self.benchmark, self.volume_path, runtime=runtime, max_total_time=30
        )

        score = volume.read_score()
        self.assertIsNotNone(score)
        self.assertEqual(score.total_points, 30)


if __name__ == "__main__":
    unittest.main()
