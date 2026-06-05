"""Unit tests for tester support process components."""
import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cae.tester import run_tests, main
from cae.benchmark import Benchmark, Phase, Scoring
from cae.protocol import Volume, TestResult

class TestRunTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.volume = Volume(self.tmpdir.name)
        self.volume.ensure_dirs()

    def tearDown(self):
        self.tmpdir.cleanup()

    def create_benchmark(self, script_content: str, exit_code: int = 0) -> Benchmark:
        base = Path(self.tmpdir.name) / "benchmark"
        base.mkdir()

        script = base / "tests" / "run.sh"
        script.parent.mkdir(parents=True)
        script.write_text(script_content)
        script.chmod(0o755)

        # Write task.json
        task = {
            "id": "test-bench",
            "phases": [{"id": "phase-1", "promptFile": "prompts/p1.md"}],
            "tests": {"script": str(script.relative_to(base))},
        }
        with open(base / "task.json", "w") as f:
            json.dump(task, f)

        return Benchmark.load(base / "task.json")

    def test_passing_tests(self):
        bm = self.create_benchmark("#!/bin/bash\necho 'All good'\nexit 0")
        result = run_tests(Path(self.tmpdir.name), bm, "phase-1")
        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All good", result.details)

    def test_failing_tests(self):
        bm = self.create_benchmark("#!/bin/bash\necho 'Error' >&2\nexit 1")
        result = run_tests(Path(self.tmpdir.name), bm, "phase-1")
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error", result.details)

    def test_timeout(self):
        bm = self.create_benchmark("#!/bin/bash\nsleep 120\n")
        result = run_tests(Path(self.tmpdir.name), bm, "phase-1")
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, -1)
        self.assertIn("timed out", result.details)

    def test_env_vars_set(self):
        bm = self.create_benchmark("#!/bin/bash\necho \"ARTIFACT=$CAE_ARTIFACT_ROOT\"\necho \"PHASE=$CAE_PHASE\"\nexit 0")
        result = run_tests(Path(self.tmpdir.name), bm, "phase-1")
        self.assertIn(f"ARTIFACT={self.tmpdir.name}", result.details)
        self.assertIn("PHASE=phase-1", result.details)

    def test_captures_stdout_and_stderr(self):
        bm = self.create_benchmark("#!/bin/bash\necho 'stdout line'\necho 'stderr line' >&2\nexit 0")
        result = run_tests(Path(self.tmpdir.name), bm, "phase-1")
        self.assertIn("stdout line", result.details)
        self.assertIn("stderr line", result.details)
        self.assertIn("--- stderr ---", result.details)

    def test_missing_script(self):
        """If the test script does not exist, run_tests should handle it gracefully."""
        base = Path(self.tmpdir.name) / "bad-bench"
        base.mkdir()
        with open(base / "task.json", "w") as f:
            json.dump({
                "id": "bad",
                "phases": [{"id": "p1", "promptFile": "p.md"}],
                "tests": {"script": "tests/nonexistent.sh"},
            }, f)
        bm = Benchmark.load(base / "task.json")
        result = run_tests(Path(self.tmpdir.name), bm, "phase-1")
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, -1)


class TestTesterMain(unittest.TestCase):
    """Tests for tester.main() orchestration."""

    def _create_benchmark(self, tmpdir: str, phases: list[dict], script_content: str) -> tuple[Path, Path]:
        """Create a benchmark directory and return (base_dir, task_json_path)."""
        base = Path(tmpdir) / "benchmark"
        base.mkdir()

        script = base / "tests" / "run.sh"
        script.parent.mkdir(parents=True)
        script.write_text(script_content)
        script.chmod(0o755)

        task = {
            "id": "test-bench",
            "phases": phases,
            "tests": {"script": "tests/run.sh"},
        }
        task_path = base / "task.json"
        with open(task_path, "w") as f:
            json.dump(task, f)

        return base, task_path

    def test_calls_script_once_for_current_phase(self):
        """main() should invoke the test script exactly once with CAE_PHASE set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            impl_dir = run_dir / "impl"
            impl_dir.mkdir()

            phases = [
                {"id": "phase-1", "promptFile": "prompts/p1.md"},
                {"id": "phase-2", "promptFile": "prompts/p2.md"},
            ]
            # Script logs each invocation to a file so we can count calls.
            log_file = run_dir / "call_log.txt"
            script = f'''#!/bin/bash
echo "$CAE_PHASE" >> {log_file}
exit 0
'''
            _base, task_path = self._create_benchmark(tmpdir, phases, script)

            rc = main([
                "--volume", str(run_dir),
                "--task", str(task_path),
                "--phase", "phase-2",
            ])

            self.assertEqual(rc, 0)
            calls = log_file.read_text().strip().splitlines()
            self.assertEqual(len(calls), 1, f"Expected 1 call, got: {calls}")
            self.assertEqual(calls[0], "phase-2")

    def test_no_forced_regression(self):
        """Designer controls regression; framework does not call prior phases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            impl_dir = run_dir / "impl"
            impl_dir.mkdir()

            phases = [
                {"id": "phase-1", "promptFile": "prompts/p1.md"},
                {"id": "phase-2", "promptFile": "prompts/p2.md"},
            ]
            # Script fails for phase-1, passes for phase-2.
            # If framework forced regression, phase-2 would fail.
            log_file = run_dir / "call_log.txt"
            script = f'''#!/bin/bash
echo "$CAE_PHASE" >> {log_file}
if [ "$CAE_PHASE" = "phase-1" ]; then exit 1; fi
exit 0
'''
            _base, task_path = self._create_benchmark(tmpdir, phases, script)

            rc = main([
                "--volume", str(run_dir),
                "--task", str(task_path),
                "--phase", "phase-2",
            ])

            self.assertEqual(rc, 0, "Framework should not force prior-phase test runs")
            calls = log_file.read_text().strip().splitlines()
            self.assertEqual(calls, ["phase-2"])

    def test_writes_result_file(self):
        """main() should write results/latest.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            impl_dir = run_dir / "impl"
            impl_dir.mkdir()

            phases = [{"id": "phase-1", "promptFile": "prompts/p1.md"}]
            script = "#!/bin/bash\necho 'OK'\nexit 0\n"
            _base, task_path = self._create_benchmark(tmpdir, phases, script)

            rc = main([
                "--volume", str(run_dir),
                "--task", str(task_path),
                "--phase", "phase-1",
            ])

            self.assertEqual(rc, 0)
            volume = Volume(run_dir, results_dir=run_dir / "test" / "results")
            result = volume.read_result()
            self.assertIsNotNone(result)
            self.assertTrue(result.passed)
            self.assertIn("OK", result.details)

if __name__ == "__main__":
    unittest.main()
