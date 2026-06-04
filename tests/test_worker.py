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
    EchoClient,
    PHASE_COMPLETE_MARKER,
    TurnResult,
    AgentClient,
)
from cae.protocol import Feedback, TaskState, Volume
from cae.worker import run_worker, _check_completion, MAX_CRASH_RETRIES


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


class TestEchoClient(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_writes_session_file(self):
        client = EchoClient()
        client.run_turn("hello", {}, self.cwd)
        session_file = self.cwd / ".cae-echo-session"
        self.assertTrue(session_file.exists())
        self.assertEqual(len(session_file.read_text()), 36)  # UUID length

    def test_writes_output_txt(self):
        client = EchoClient()
        client.run_turn("hello", {}, self.cwd)
        output_file = self.cwd / "output.txt"
        self.assertTrue(output_file.exists())
        self.assertEqual(output_file.read_text(), "hello")

    def test_output_excludes_system_prompt_append(self):
        client = EchoClient()
        client.run_turn("hello", {}, self.cwd, system_prompt_append="EXTRA")
        output_file = self.cwd / "output.txt"
        self.assertEqual(output_file.read_text(), "hello")

    @patch("cae.agent_client.random.random", return_value=0.5)
    def test_returns_no_marker_when_random_high(self, _mock):
        client = EchoClient()
        result = client.run_turn("hello", {}, self.cwd)
        self.assertNotIn(PHASE_COMPLETE_MARKER, result.output)

    @patch("cae.agent_client.random.random", return_value=0.1)
    def test_returns_marker_when_random_low(self, _mock):
        client = EchoClient()
        result = client.run_turn("hello", {}, self.cwd)
        self.assertIn(PHASE_COMPLETE_MARKER, result.output)

    @patch("cae.agent_client.random.random", side_effect=[0.5, 0.1])
    def test_first_prompt_only_writes_once(self, _mock):
        client = EchoClient()
        client.run_turn("hello", {}, self.cwd)
        client.run_turn("continue", {}, self.cwd)
        output_file = self.cwd / "output.txt"
        self.assertEqual(output_file.read_text(), "hello")


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
        self.volume.write_task(
            TaskState(
                benchmark_id="test",
                phase_id="phase-1",
                attempt=1,
                prompt="Do something",
                max_attempts=3,
                points=10,
            )
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_feedback_after_ready(self, feedback, delay=0.5):
        """Return a thread that waits for ready, sleeps *delay*, then writes feedback."""

        def _writer():
            for _ in range(int(delay * 2 / 0.01) + 100):  # generous timeout
                if self.volume.is_ready():
                    time.sleep(delay)
                    self.volume.write_feedback(feedback)
                    return
                time.sleep(0.01)

        t = threading.Thread(target=_writer)
        t.start()
        return t

    @patch("cae.worker.time")
    def test_sets_ready_when_marker_present(self, mock_time):
        _apply_fast_sleep(mock_time)
        client = FakeClient(["work done\n<CAE_PHASE_COMPLETE/>"])
        fb = Feedback(
            phase_id="phase-1",
            attempt=1,
            passed=True,
            message="Good",
            phase_complete=True,
            next_phase_id=None,
        )
        t = self._write_feedback_after_ready(fb)
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        t.join(timeout=5)
        self.assertEqual(result, 0)

    @patch("cae.worker.time")
    def test_continues_without_marker(self, mock_time):
        _apply_fast_sleep(mock_time)
        client = FakeClient([
            "should I continue?",
            "done\n<CAE_PHASE_COMPLETE/>",
        ])
        fb = Feedback(
            phase_id="phase-1",
            attempt=1,
            passed=True,
            message="Good",
            phase_complete=True,
            next_phase_id=None,
        )
        t = self._write_feedback_after_ready(fb)
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        t.join(timeout=5)
        self.assertEqual(result, 0)
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("Continue working", client.prompts[1])

    @patch("cae.worker.time")
    def test_retries_on_crash(self, mock_time):
        _apply_fast_sleep(mock_time)
        client = FakeClient([
            TurnResult(success=False, details="crash", output=""),
            "done\n<CAE_PHASE_COMPLETE/>",
        ])
        fb = Feedback(
            phase_id="phase-1",
            attempt=1,
            passed=True,
            message="Good",
            phase_complete=True,
            next_phase_id=None,
        )
        t = self._write_feedback_after_ready(fb)
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        t.join(timeout=5)
        self.assertEqual(result, 0)
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("Continue working", client.prompts[1])

    def test_exits_after_max_crash_retries(self):
        responses = [
            TurnResult(success=False, details="crash", output="")
        ] * (MAX_CRASH_RETRIES + 1)
        client = FakeClient(responses)
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        self.assertEqual(result, 1)
        self.assertEqual(len(client.prompts), MAX_CRASH_RETRIES)

    @patch("cae.worker.time")
    def test_resets_crash_counter_after_success(self, mock_time):
        _apply_fast_sleep(mock_time)
        client = FakeClient([
            TurnResult(success=False, details="crash", output=""),
            "not done yet",
            TurnResult(success=False, details="crash", output=""),
            "done\n<CAE_PHASE_COMPLETE/>",
        ])
        fb = Feedback(
            phase_id="phase-1",
            attempt=1,
            passed=True,
            message="Good",
            phase_complete=True,
            next_phase_id=None,
        )
        t = self._write_feedback_after_ready(fb)
        result = run_worker(self.volume, self.impl_dir, lambda: client)
        t.join(timeout=5)
        self.assertEqual(result, 0)
        self.assertEqual(len(client.prompts), 4)


if __name__ == "__main__":
    unittest.main()
