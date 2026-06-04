"""Tests for Runtime implementations."""
from __future__ import annotations

import sys
import os
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
        self.assertIn("PYTHONPATH=/cae/src", cmd)

    def test_worker_sets_cae_artifact_root(self):
        cmd = self._capture_worker_cmd()
        self.assertIn("CAE_ARTIFACT_ROOT=/run/impl", cmd)

    def test_worker_sets_home(self):
        cmd = self._capture_worker_cmd()
        self.assertIn("HOME=/run/impl", cmd)

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

    def test_worker_includes_python_module(self):
        cmd = self._capture_worker_cmd()
        idx = cmd.index("/usr/bin/python")
        self.assertEqual(cmd[idx + 1], "-m")
        self.assertEqual(cmd[idx + 2], "cae.worker")

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

    def test_worker_passes_env_file(self):
        env_file = self.run_dir / "impl" / ".cae-env"
        env_file.write_text("FOO=bar\n")
        cmd = self._capture_worker_cmd()
        idx = cmd.index("--env-file")
        self.assertEqual(cmd[idx + 1], str(env_file))

    def test_worker_uses_venv_python(self):
        venv_python = self.run_dir / "impl" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.touch()
        cmd = self._capture_worker_cmd()
        self.assertIn(str(venv_python), cmd)

    def test_worker_prepends_agent_to_pythonpath(self):
        agent_init = self.run_dir / "impl" / "agent" / "__init__.py"
        agent_init.parent.mkdir(parents=True, exist_ok=True)
        agent_init.touch()
        cmd = self._capture_worker_cmd()
        self.assertIn("PYTHONPATH=/run/impl/agent:/cae/src", cmd)

    def test_worker_prepends_venv_to_path(self):
        venv_python = self.run_dir / "impl" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.touch()
        cmd = self._capture_worker_cmd()
        self.assertIn("PATH=/run/impl/.venv/bin:/usr/local/bin:/usr/bin:/bin", cmd)

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
        idx = cmd.index("--phase")
        self.assertEqual(cmd[idx + 1], "phase-1")

    def test_tester_includes_python_module(self):
        cmd = self._capture_tester_cmd()
        idx = cmd.index("/usr/bin/python")
        self.assertEqual(cmd[idx + 1], "-m")
        self.assertEqual(cmd[idx + 2], "cae.tester")

    def test_tester_uses_custom_image(self):
        cmd = self._capture_tester_cmd(tester_image="custom-tester")
        self.assertIn("custom-tester", cmd)


class TestLocalRuntimeTemplate(unittest.TestCase):
    """Verify LocalRuntime builds correct commands and env from the template."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / "run"
        self.run_dir.mkdir()
        (self.run_dir / "impl").mkdir()
        (self.run_dir / ".cae").mkdir()
        self.volume = Volume(self.run_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def _capture_worker(self):
        captured = {}
        original_popen = __import__("subprocess", fromlist=["Popen"]).Popen

        def fake_popen(cmd, **popen_kwargs):
            captured["cmd"] = cmd
            captured["env"] = popen_kwargs.get("env")
            class MockProc:
                def poll(self): return None
                def terminate(self): pass
                def kill(self): pass
                def wait(self, timeout=None): return 0
            return MockProc()

        import subprocess
        subprocess.Popen = fake_popen
        try:
            rt = LocalRuntime()
            rt.spawn_worker(self.volume, agent_mode="echo")
        finally:
            subprocess.Popen = original_popen
        return captured["cmd"], captured["env"]

    def test_local_sets_home(self):
        cmd, env = self._capture_worker()
        self.assertEqual(env["HOME"], str(self.run_dir / "impl"))

    def test_local_loads_env(self):
        env_file = self.run_dir / "impl" / ".cae-env"
        env_file.write_text("TEST_KEY=value\n")
        cmd, env = self._capture_worker()
        self.assertEqual(env["TEST_KEY"], "value")

    def test_local_uses_venv_python(self):
        venv_python = self.run_dir / "impl" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.touch()
        cmd, env = self._capture_worker()
        self.assertEqual(cmd[0], str(venv_python))

    def test_local_agent_in_pythonpath(self):
        agent_path = self.run_dir / "impl" / "agent"
        agent_path.mkdir(parents=True, exist_ok=True)
        cmd, env = self._capture_worker()
        self.assertIn("impl/agent", env["PYTHONPATH"])

    def test_local_prepends_venv_to_path(self):
        venv_python = self.run_dir / "impl" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.touch()
        cmd, env = self._capture_worker()
        path_entries = env["PATH"].split(os.pathsep)
        self.assertEqual(path_entries[0], str(self.run_dir / "impl" / ".venv" / "bin"))

if __name__ == "__main__":
    unittest.main()
