"""Tests for Runtime implementations."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cae.runtime import LocalRuntime, ContainerRuntime, runtime_for_mode
from cae.benchmark import Benchmark
from cae.protocol import Volume


class TestRuntimeFactory(unittest.TestCase):
    def test_local_mode(self):
        rt = runtime_for_mode("local")
        self.assertIsInstance(rt, LocalRuntime)

    def test_container_mode(self):
        rt = runtime_for_mode("container")
        self.assertIsInstance(rt, ContainerRuntime)

    def test_container_mode_with_kwargs(self):
        rt = runtime_for_mode("container", engine="docker", worker_image="custom")
        self.assertEqual(rt.engine, "docker")
        self.assertEqual(rt.worker_image, "custom")

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            runtime_for_mode("vm")


class TestContainerRuntimeCommandConstruction(unittest.TestCase):
    """Verify ContainerRuntime builds correct podman commands without running them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / "run"
        self.run_dir.mkdir()
        (self.run_dir / "impl").mkdir()
        (self.run_dir / ".cae").mkdir()

        self.benchmark_dir = Path(self.tmp.name) / "benchmark"
        self.benchmark_dir.mkdir()
        (self.benchmark_dir / "tests").mkdir()
        (self.benchmark_dir / "task.json").write_text(
            '{"id":"test","phases":[],"tests":{"script":"tests/run.sh"}}'
        )
        (self.benchmark_dir / "tests" / "run.sh").write_text("#!/bin/bash\nexit 0")

        self.benchmark = Benchmark.load(self.benchmark_dir / "task.json")
        self.volume = Volume(self.run_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def _capture_worker_cmd(self, **rt_kwargs):
        """Monkey-patch Popen to capture the command instead of running."""
        captured = {}
        original_popen = __import__("subprocess", fromlist=["Popen"]).Popen

        def fake_popen(cmd, **popen_kwargs):
            captured["cmd"] = cmd
            class MockProc:
                def poll(self): return None
                def terminate(self): pass
                def kill(self): pass
                def wait(self, timeout=None): return 0
            return MockProc()

        import subprocess
        subprocess.Popen = fake_popen
        try:
            rt = ContainerRuntime(**rt_kwargs)
            rt.spawn_worker(self.volume, agent_mode="echo")
        finally:
            subprocess.Popen = original_popen
        return captured["cmd"]

    def _capture_tester_cmd(self, **rt_kwargs):
        """Monkey-patch run to capture the command instead of running."""
        captured = {}
        original_run = __import__("subprocess", fromlist=["run"]).run

        def fake_run(cmd, **run_kwargs):
            captured["cmd"] = cmd
            class MockResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return MockResult()

        import subprocess
        subprocess.run = fake_run
        try:
            rt = ContainerRuntime(**rt_kwargs)
            rt.spawn_tester(self.volume, self.benchmark, "phase-1")
        finally:
            subprocess.run = original_run
        return captured["cmd"]

    def test_worker_uses_podman(self):
        cmd = self._capture_worker_cmd()
        self.assertEqual(cmd[0], "podman")
        self.assertEqual(cmd[1], "run")
        self.assertEqual(cmd[2], "--rm")
        self.assertEqual(cmd[3], "--userns=keep-id")

    def test_worker_mounts_run_dir(self):
        cmd = self._capture_worker_cmd()
        self.assertIn(f"-v{self.run_dir}:/run:Z", cmd)

    def test_worker_mounts_src_dir(self):
        cmd = self._capture_worker_cmd()
        src_dir = str(Path(__file__).parent.parent / "src")
        self.assertIn(f"-v{src_dir}:/cae/src:Z", cmd)

    def test_worker_sets_pythonpath(self):
        cmd = self._capture_worker_cmd()
        idx = cmd.index("-e")
        self.assertEqual(cmd[idx + 1], "PYTHONPATH=/cae/src")

    def test_worker_sets_cae_artifact_root(self):
        cmd = self._capture_worker_cmd()
        idx = cmd.index("-e")
        self.assertEqual(cmd[idx + 3], "CAE_ARTIFACT_ROOT=/run/impl")

    def test_worker_passes_agent_mode(self):
        cmd = self._capture_worker_cmd()
        idx = cmd.index("--agent-mode")
        self.assertEqual(cmd[idx + 1], "echo")

    def test_worker_uses_custom_engine(self):
        cmd = self._capture_worker_cmd(engine="docker")
        self.assertEqual(cmd[0], "docker")

    def test_worker_uses_custom_image(self):
        cmd = self._capture_worker_cmd(worker_image="custom-worker")
        self.assertIn("custom-worker", cmd)

    def test_worker_includes_agent_mounts(self):
        cmd = self._capture_worker_cmd(agent_mounts=[("/host/bin", "/usr/local/bin")])
        self.assertIn("-v/host/bin:/usr/local/bin:Z", cmd)

    def test_worker_passes_agent_cmd(self):
        captured = {}
        original_popen = __import__("subprocess", fromlist=["Popen"]).Popen

        def fake_popen(cmd, **popen_kwargs):
            captured["cmd"] = cmd
            class MockProc:
                def poll(self): return None
                def terminate(self): pass
                def kill(self): pass
                def wait(self, timeout=None): return 0
            return MockProc()

        import subprocess
        subprocess.Popen = fake_popen
        try:
            rt = ContainerRuntime()
            rt.spawn_worker(self.volume, agent_cmd=["claude", "-p"], agent_mode="echo")
        finally:
            subprocess.Popen = original_popen
        cmd = captured["cmd"]
        idx = cmd.index("--agent-cmd")
        self.assertEqual(cmd[idx + 1], "claude -p")

    def test_tester_uses_podman(self):
        cmd = self._capture_tester_cmd()
        self.assertEqual(cmd[0], "podman")

    def test_tester_has_net_none(self):
        cmd = self._capture_tester_cmd()
        self.assertIn("--net=none", cmd)

    def test_tester_mounts_benchmark_dir(self):
        cmd = self._capture_tester_cmd()
        self.assertIn(f"-v{self.benchmark_dir}:/benchmark:Z", cmd)

    def test_tester_sets_working_dir(self):
        cmd = self._capture_tester_cmd()
        idx = cmd.index("-w")
        self.assertEqual(cmd[idx + 1], "/benchmark/tests")

    def test_tester_passes_correct_paths(self):
        cmd = self._capture_tester_cmd()
        idx = cmd.index("--task")
        self.assertEqual(cmd[idx + 1], "/benchmark/task.json")
        idx = cmd.index("--tests")
        self.assertEqual(cmd[idx + 1], "/benchmark/tests/run.sh")

    def test_tester_uses_custom_image(self):
        cmd = self._capture_tester_cmd(tester_image="custom-tester")
        self.assertIn("custom-tester", cmd)


if __name__ == "__main__":
    unittest.main()
