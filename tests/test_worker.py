"""Unit tests for worker support process components.

PiRpcClient and monitor_events are now in cae.agent_client.
These tests verify that the pi-specific protocol layer still works.
"""
import io
import json
import sys
import threading
import time
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cae.agent_client import _PiRpcClient, _monitor_events


class FakeProcess:
    """Fake subprocess.Popen for testing."""

    def __init__(self, stdout_lines: list[str]):
        self.stdout = io.StringIO("\n".join(stdout_lines) + "\n")
        self.stdin = io.StringIO()


class TestPiRpcClient(unittest.TestCase):
    def test_prompt_sends_valid_jsonl(self):
        proc = FakeProcess([])
        client = _PiRpcClient(proc)
        client.prompt("hello")
        proc.stdin.seek(0)
        msg = json.loads(proc.stdin.readline())
        self.assertEqual(msg["type"], "prompt")
        self.assertEqual(msg["message"], "hello")
        self.assertIn("id", msg)

    def test_sequential_ids(self):
        proc = FakeProcess([])
        client = _PiRpcClient(proc)
        client.prompt("a")
        client.prompt("b")
        proc.stdin.seek(0)
        msg1 = json.loads(proc.stdin.readline())
        msg2 = json.loads(proc.stdin.readline())
        id1 = msg1["id"]
        id2 = msg2["id"]
        self.assertNotEqual(id1, id2)

    def test_steer_sends_correct_type(self):
        proc = FakeProcess([])
        client = _PiRpcClient(proc)
        client.steer("fix this")
        proc.stdin.seek(0)
        msg = json.loads(proc.stdin.readline())
        self.assertEqual(msg["type"], "steer")

    def test_abort_sends_correct_type(self):
        proc = FakeProcess([])
        client = _PiRpcClient(proc)
        client.abort()
        proc.stdin.seek(0)
        msg = json.loads(proc.stdin.readline())
        self.assertEqual(msg["type"], "abort")


class TestMonitorEvents(unittest.TestCase):
    def test_idle_after_agent_end(self):
        events = [
            json.dumps({"type": "agent_end"}),
        ]
        proc = FakeProcess(events)
        idle_event = threading.Event()
        _monitor_events(proc, idle_event, idle_timeout=0.1)
        fired = idle_event.wait(timeout=1)
        self.assertTrue(fired, "idle_event should fire after agent_end")

    def test_no_idle_during_tool_execution(self):
        events = [
            json.dumps({"type": "agent_end"}),
            json.dumps({"type": "tool_execution_start"}),
            "sleep",  # simulate tool running
            json.dumps({"type": "tool_execution_end"}),
        ]
        proc = FakeProcess(events)
        idle_event = threading.Event()
        _monitor_events(proc, idle_event, idle_timeout=0.5)
        # Should fire after tool_execution_end + timeout
        fired = idle_event.wait(timeout=3)
        self.assertTrue(fired, "idle_event should fire after tool_execution_end")

    def test_idle_after_tool_execution_end(self):
        events = [
            json.dumps({"type": "tool_execution_start"}),
            json.dumps({"type": "tool_execution_end"}),
            json.dumps({"type": "agent_end"}),
        ]
        proc = FakeProcess(events)
        idle_event = threading.Event()
        _monitor_events(proc, idle_event, idle_timeout=0.1)
        fired = idle_event.wait(timeout=1)
        self.assertTrue(fired, "idle_event should fire after tool_execution_end + agent_end")

    def test_working_resets_idle(self):
        """If a new turn starts, idle should be cleared."""
        events = [
            json.dumps({"type": "agent_end"}),
            json.dumps({"type": "turn_start"}),
        ]
        proc = FakeProcess(events)
        idle_event = threading.Event()
        _monitor_events(proc, idle_event, idle_timeout=0.5)
        time.sleep(0.1)
        self.assertFalse(idle_event.is_set(), "idle should be cleared by turn_start")
        # Also verify it doesn't fire after timeout since turn_start resets
        time.sleep(1)
        self.assertFalse(idle_event.is_set(), "idle_event should NOT fire after turn_start")

    def test_ignores_non_json_lines(self):
        events = [
            "some debug output",
            json.dumps({"type": "agent_end"}),
        ]
        proc = FakeProcess(events)
        idle_event = threading.Event()
        _monitor_events(proc, idle_event, idle_timeout=0.1)
        fired = idle_event.wait(timeout=1)
        self.assertTrue(fired, "should still detect idle after valid agent_end")

    def test_empty_stdout(self):
        proc = FakeProcess([])
        idle_event = threading.Event()
        _monitor_events(proc, idle_event, idle_timeout=0.1)
        self.assertFalse(idle_event.is_set(), "no events means no idle detection")


if __name__ == "__main__":
    unittest.main()
