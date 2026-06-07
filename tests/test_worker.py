"""Tests for worker support process and agent clients."""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cae.agent_client import (
    COMPLETION_INSTRUCTION,
    PHASE_COMPLETE_MARKER,
    TurnResult,
    AgentClient,
)
from cae.protocol import Volume
from cae.worker import run_worker, _check_completion, MAX_CRASH_RETRIES, _run_startup_script, _discover_clients
def _apply_fast_sleep(mock_time):
    mock_time.sleep = lambda _x: None


class TestCheckCompletion(unittest.TestCase):
    def test_marker_on_final_line(self):
        self.assertTrue(_check_completion("some work\n<CAE_PHASE_COMPLETE/>"))

    def test_marker_not_on_final_line(self):
        self.assertFalse(_check_completion("<CAE_PHASE_COMPLETE/>\nmore text"))

    def test_no_marker(self):
        self.assertFalse(_check_completion("some work"))

    def test_whitespace_around_marker(self):
        self.assertTrue(_check_completion("work\n  <CAE_PHASE_COMPLETE/>  \n"))


class FakeClient(AgentClient):
    """Deterministic agent client for testing worker loop behaviour."""

    def __init__(self, responses):
        self._responses = iter(responses)
        self.prompts: list[str] = []

    def run_turn(self, prompt, env, cwd, system_prompt_append=""):
        self.prompts.append(prompt)
        try:
            resp = next(self._responses)
            if isinstance(resp, TurnResult):
                return resp
            return TurnResult(success=True, output=resp)
        except StopIteration:
            return TurnResult(success=False, details="exhausted", output="")


class TestWorkerLoop(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmpdir.name)
        self.impl_dir = self.run_dir / "impl"
        self.impl_dir.mkdir()
        self.volume = Volume(self.run_dir)
        self.volume.ensure_dirs()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run_worker_timeout(self, client, timeout: float = 2.0):
        """Run the worker in a thread and return its result, or None if it times out."""
        result = [None]

        def target():
            result[0] = run_worker(self.volume, self.impl_dir, lambda: client)

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            return None  # Worker is still alive (expected for successful loops)
        return result[0]

    def _write_prompt_after_ready(self, prompts, delay=0.05):
        """Return a thread that writes each prompt after ready is cleared."""

        def _writer():
            for prompt in prompts:
                # Wait for ready
                while not self.volume.is_ready():
                    time.sleep(0.01)
                time.sleep(delay)
                self.volume.clear_ready()
                time.sleep(delay)
                self.volume.write_prompt(prompt)

        t = threading.Thread(target=_writer, daemon=True)
        t.start()
        return t

    @patch("cae.worker.time")
    def test_sets_ready_when_marker_present(self, mock_time):
        _apply_fast_sleep(mock_time)
        self.volume.write_prompt("Do something")
        client = FakeClient(["work done\n<CAE_PHASE_COMPLETE/>"])

        ready_seen = [False]

        def writer():
            while not self.volume.is_ready():
                time.sleep(0.01)
            ready_seen[0] = True
            self.volume.clear_ready()

        t = threading.Thread(target=writer, daemon=True)
        t.start()

        result = self._run_worker_timeout(client)
        t.join(timeout=2)
        self.assertIsNone(result)  # Worker still waiting for next prompt
        self.assertEqual(client.prompts, ["Do something"])
        self.assertTrue(ready_seen[0])  # Worker did set ready

    @patch("cae.worker.time")
    def test_continues_without_marker(self, mock_time):
        _apply_fast_sleep(mock_time)
        self.volume.write_prompt("Do something")
        client = FakeClient([
            "should I continue?",
            "done\n<CAE_PHASE_COMPLETE/>",
        ])

        ready_seen = [False]

        def writer():
            while not self.volume.is_ready():
                time.sleep(0.01)
            ready_seen[0] = True
            self.volume.clear_ready()

        t = threading.Thread(target=writer, daemon=True)
        t.start()

        result = self._run_worker_timeout(client)
        t.join(timeout=2)
        self.assertIsNone(result)
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("Continue working", client.prompts[1])
        self.assertTrue(ready_seen[0])

    @patch("cae.worker.time")
    def test_retries_on_crash(self, mock_time):
        _apply_fast_sleep(mock_time)
        self.volume.write_prompt("Do something")
        client = FakeClient([
            TurnResult(success=False, details="crash", output=""),
            "done\n<CAE_PHASE_COMPLETE/>",
        ])

        ready_seen = [False]

        def writer():
            while not self.volume.is_ready():
                time.sleep(0.01)
            ready_seen[0] = True
            self.volume.clear_ready()

        t = threading.Thread(target=writer, daemon=True)
        t.start()

        result = self._run_worker_timeout(client)
        t.join(timeout=2)
        self.assertIsNone(result)
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("Continue working", client.prompts[1])
        self.assertTrue(ready_seen[0])

    def test_exits_after_max_crash_retries(self):
        responses = [
            TurnResult(success=False, details="crash", output="")
        ] * (MAX_CRASH_RETRIES + 1)
        client = FakeClient(responses)
        self.volume.write_prompt("Do something")
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        self.assertEqual(result, 1)
        self.assertEqual(len(client.prompts), MAX_CRASH_RETRIES)

    @patch("cae.worker.time")
    def test_resets_crash_counter_after_success(self, mock_time):
        _apply_fast_sleep(mock_time)
        self.volume.write_prompt("Do something")
        client = FakeClient([
            TurnResult(success=False, details="crash", output=""),
            "not done yet",
            TurnResult(success=False, details="crash", output=""),
            "done\n<CAE_PHASE_COMPLETE/>",
        ])

        ready_seen = [False]

        def writer():
            while not self.volume.is_ready():
                time.sleep(0.01)
            ready_seen[0] = True
            self.volume.clear_ready()

        t = threading.Thread(target=writer, daemon=True)
        t.start()

        result = self._run_worker_timeout(client)
        t.join(timeout=2)
        self.assertIsNone(result)
        self.assertEqual(len(client.prompts), 4)
        self.assertTrue(ready_seen[0])

    def test_exits_on_startup_failure(self):
        script = self.impl_dir / ".cae-startup.sh"
        script.write_text("#!/bin/bash\nexit 1\n")
        client = FakeClient(["done\n<CAE_PHASE_COMPLETE/>"])
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        self.assertEqual(result, 1)
        self.assertEqual(len(client.prompts), 0)

    @patch("cae.worker.time")
    def test_processes_two_prompts(self, mock_time):
        """Worker handles two prompt cycles in sequence."""
        _apply_fast_sleep(mock_time)
        self.volume.write_prompt("First prompt")
        client = FakeClient([
            "done\n<CAE_PHASE_COMPLETE/>",
            "done\n<CAE_PHASE_COMPLETE/>",
        ])

        t = self._write_prompt_after_ready(["Second prompt"])

        result = self._run_worker_timeout(client, timeout=3)
        t.join(timeout=2)
        self.assertIsNone(result)
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("First prompt", client.prompts[0])
        self.assertIn("Second prompt", client.prompts[1])


class TestWorkerStartup(unittest.TestCase):
    def test_runs_startup_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            impl_dir = Path(tmpdir)
            marker = impl_dir / "marker.txt"
            script = impl_dir / ".cae-startup.sh"
            script.write_text(f"#!/bin/bash\ntouch {marker}\n")
            rc = _run_startup_script(impl_dir)
            self.assertEqual(rc, 0)
            self.assertTrue(marker.exists())

    def test_no_script_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            impl_dir = Path(tmpdir)
            rc = _run_startup_script(impl_dir)
            self.assertEqual(rc, 0)

    def test_failed_startup_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            impl_dir = Path(tmpdir)
            script = impl_dir / ".cae-startup.sh"
            script.write_text("#!/bin/bash\nexit 42\n")
            rc = _run_startup_script(impl_dir)
            self.assertEqual(rc, 42)


class TestClientDiscovery(unittest.TestCase):
    """Tests for agent client discovery from template directories."""

    def test_discovers_echo_client_from_template(self):
        """_discover_clients should find the echo client from templates/echo/."""
        from cae.agent_client import _CLIENTS
        # Clear any previously registered clients
        _CLIENTS.clear()

        agent_dir = Path(__file__).parent.parent / "templates" / "echo" / "agent"
        clients = _discover_clients(agent_dir)

        self.assertIn("echo", clients)
        self.assertEqual(len(clients), 1)

    def test_no_clients_when_agent_dir_empty(self):
        """_discover_clients should return empty dict when no adapters exist."""
        from cae.agent_client import _CLIENTS
        _CLIENTS.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            clients = _discover_clients(agent_dir)
            self.assertEqual(len(clients), 0)

    def test_discovers_probe_client_from_fixture(self):
        """_discover_clients should find the probe client from test fixtures."""
        from cae.agent_client import _CLIENTS
        _CLIENTS.clear()

        agent_dir = Path(__file__).parent / "fixtures" / "probe-template" / "agent"
        clients = _discover_clients(agent_dir)

        self.assertIn("probe", clients)
        self.assertEqual(len(clients), 1)
    def test_name_collision_avoided(self):
        """Adapter files named like stdlib modules should not shadow them."""
        from cae.agent_client import _CLIENTS, register_client, AgentClient
        _CLIENTS.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            # Create a file named 'json.py' which would shadow stdlib 'json'
            # if discovered via import_module instead of spec_from_file_location.
            adapter = agent_dir / "json.py"
            adapter.write_text(
                'from cae.agent_client import AgentClient, register_client\n'
                '@register_client("collision-test")\n'
                'class CollisionClient(AgentClient):\n'
                '    def run_turn(self, prompt, env, cwd, system_prompt_append=""):\n'
                '        return None\n'
            )
            clients = _discover_clients(agent_dir)

            self.assertIn("collision-test", clients)
            self.assertEqual(len(clients), 1)
            # Ensure stdlib 'json' module is not replaced by our adapter
            import json as stdlib_json  # noqa: F401
            self.assertTrue(hasattr(stdlib_json, 'loads'))

if __name__ == "__main__":
    unittest.main()
