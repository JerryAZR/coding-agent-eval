"""Module-level tests for manager state transitions.

These mock out the Runtime to test decision logic in isolation.
The mock worker runs in a thread and properly simulates the ready/feedback loop.
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

    def spawn_worker(self, volume, agent_cmd=None, agent_mode="pi"):
        return self.worker_proc

    def spawn_tester(self, volume, benchmark, phase_id):
        if self.result_factory:
            result = self.result_factory(phase_id)
            volume.write_result(result)
            return MagicMock(returncode=0 if result.passed else 1)
        return MagicMock(returncode=0)


class MockWorker:
    """A threaded mock worker that simulates the real worker's ready/feedback loop."""

    def __init__(self, volume: Volume):
        self.volume = volume
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        """Monitor feedback and rewrite ready when appropriate."""
        last_feedback = None
        while not self._stop.is_set():
            fb = self.volume.read_feedback()
            if fb is not None:
                if last_feedback is None or fb.to_dict() != last_feedback.to_dict():
                    last_feedback = fb
                    if fb.phase_complete and fb.next_phase_id is None:
                        break
                    time.sleep(0.1)
                    if not self._stop.is_set():
                        try:
                            self.volume.set_ready()
                        except OSError:
                            break
            else:
                if not self.volume.is_ready() and not self._stop.is_set():
                    try:
                        self.volume.set_ready()
                    except OSError:
                        break
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
        fb = volume.read_feedback()
        self.assertIsNotNone(fb)
        self.assertTrue(fb.phase_complete)
        self.assertIsNone(fb.next_phase_id)

    def test_worker_exits_early(self):
        proc = MagicMock()
        proc.poll.return_value = 0
        runtime = MockRuntime(worker_proc=proc)

        score = run_group(
            self.benchmark, self.volume_path, runtime=runtime, max_total_time=5
        )

        self.assertEqual(score.total_points, 0)

    def test_feedback_written_on_pass(self):
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

        fb = volume.read_feedback()
        self.assertIsNotNone(fb)
        self.assertTrue(fb.phase_complete)
        self.assertIsNone(fb.next_phase_id)


if __name__ == "__main__":
    unittest.main()
