"""Agent client abstraction for different harness types.

The worker uses an AgentClient to communicate with the agent harness.
Built-in clients cover the two common paradigms:

- RpcAgentClient: long-lived process, multiple prompts (e.g. pi --mode rpc)
- OneShotAgentClient: fresh process per turn (e.g. claude, aider)
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TurnResult:
    """Outcome of one agent turn."""

    success: bool
    details: str = ""


class AgentClient(ABC):
    """Abstract interface for an agent harness."""

    @abstractmethod
    def run_turn(self, prompt: str, env: dict, cwd: Path) -> TurnResult:
        """Execute one turn: deliver prompt, wait for agent to finish.

        The worker calls this once per prompt (initial, retry, next phase).
        The client handles all agent-specific lifecycle internally.
        """
        ...

    def cleanup(self) -> None:
        """Release resources when the benchmark ends. Optional."""
        pass


# ---------------------------------------------------------------------------
# Pi RPC helpers (internal)
# ---------------------------------------------------------------------------

class _PiRpcClient:
    """Minimal JSONL RPC client for pi --mode rpc."""

    def __init__(self, proc: subprocess.Popen[str]):
        self.proc = proc
        self._lock = threading.Lock()
        self._seq = 0

    def _send(self, cmd: dict) -> None:
        with self._lock:
            self._seq += 1
            cmd["id"] = self._seq
            self.proc.stdin.write(json.dumps(cmd) + "\n")
            self.proc.stdin.flush()

    def prompt(self, message: str) -> None:
        self._send({"type": "prompt", "message": message})

    def steer(self, message: str) -> None:
        self._send({"type": "steer", "message": message})

    def abort(self) -> None:
        self._send({"type": "abort"})


def _monitor_events(
    pi_proc: subprocess.Popen[str],
    idle_event: threading.Event,
    idle_timeout: float,
) -> None:
    """Read pi's stdout and detect when the agent goes idle."""
    last_activity = time.time()
    in_tool_execution = False
    agent_ended = False
    pending_timer: threading.Timer | None = None

    def _set_idle():
        idle_event.set()

    for line in pi_proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")
        if etype == "turn_start":
            agent_ended = False
            if pending_timer is not None:
                pending_timer.cancel()
                pending_timer = None
            last_activity = time.time()
        elif etype == "tool_execution_start":
            in_tool_execution = True
            last_activity = time.time()
        elif etype == "tool_execution_end":
            in_tool_execution = False
            last_activity = time.time()
            if agent_ended:
                if pending_timer is not None:
                    pending_timer.cancel()
                pending_timer = threading.Timer(idle_timeout, _set_idle)
                pending_timer.start()
        elif etype == "agent_end":
            agent_ended = True
            if not in_tool_execution:
                if pending_timer is not None:
                    pending_timer.cancel()
                pending_timer = threading.Timer(idle_timeout, _set_idle)
                pending_timer.start()
            last_activity = time.time()


# ---------------------------------------------------------------------------
# Built-in clients
# ---------------------------------------------------------------------------

class RpcAgentClient(AgentClient):
    """Client for RPC-style agents (e.g. pi --mode rpc).

    Starts the process once and reuses it across turns.
    Monitors stdout for idle events.
    """

    def __init__(
        self,
        agent_cmd: list[str] | None = None,
        idle_timeout: float = 5.0,
        **kwargs,
    ):
        self.agent_cmd = agent_cmd or [
            "pi",
            "--mode", "rpc",
            "--no-session",
            "--name", "cae-worker",
        ]
        self.idle_timeout = idle_timeout
        self._proc: subprocess.Popen[str] | None = None
        self._idle_event: threading.Event | None = None
        self._client: _PiRpcClient | None = None

    def run_turn(self, prompt: str, env: dict, cwd: Path) -> TurnResult:
        if self._proc is None:
            self._proc = subprocess.Popen(
                self.agent_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(cwd),
            )
            self._idle_event = threading.Event()
            monitor_thread = threading.Thread(
                target=_monitor_events,
                args=(self._proc, self._idle_event, self.idle_timeout),
                daemon=True,
            )
            monitor_thread.start()
            self._client = _PiRpcClient(self._proc)

        self._client.prompt(prompt)
        self._idle_event.wait()
        self._idle_event.clear()
        return TurnResult(success=True)

    def cleanup(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()


class OneShotAgentClient(AgentClient):
    """Client for one-shot CLI agents (e.g. claude, aider).

    Runs a fresh subprocess per turn. Subclasses override build_cmd().
    """

    def __init__(self, agent_cmd: list[str] | None = None, **kwargs):
        self.agent_cmd = agent_cmd or []
        self.state = None

    def build_cmd(self, prompt: str) -> list[str]:
        """Return the command to run for this turn.

        agent_cmd is prepended as the base command.
        """
        return [*self.agent_cmd, prompt]

    def extract_state(self, result: subprocess.CompletedProcess):
        """Parse state from stdout for the next turn. Optional."""
        return None

    def run_turn(self, prompt: str, env: dict, cwd: Path) -> TurnResult:
        cmd = self.build_cmd(prompt)
        try:
            result = subprocess.run(
                cmd,
                env=env,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.state = self.extract_state(result)
            success = result.returncode == 0
            details = result.stdout
            if result.stderr:
                details += "\n--- stderr ---\n" + result.stderr
            return TurnResult(success=success, details=details.strip())
        except subprocess.TimeoutExpired:
            return TurnResult(success=False, details="Agent timed out after 300s")
        except Exception as e:
            return TurnResult(success=False, details=f"Failed to run agent: {e}")


class EchoClient(AgentClient):
    """Test harness: writes the first prompt to output.txt.

    Used by integration tests to verify the framework protocol without
    requiring a real agent.
    """

    def __init__(self, **kwargs):
        self.first_prompt = None

    def run_turn(self, prompt: str, env: dict, cwd: Path) -> TurnResult:
        if self.first_prompt is None:
            self.first_prompt = prompt
            (cwd / "output.txt").write_text(prompt)
        return TurnResult(success=True)

    def cleanup(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLIENTS: dict[str, type[AgentClient]] = {}


def register_client(name: str):
    """Decorator to register an AgentClient subclass."""

    def decorator(cls: type[AgentClient]):
        _CLIENTS[name] = cls
        return cls

    return decorator


register_client("pi")(RpcAgentClient)
register_client("echo")(EchoClient)


def get_client(
    name: str,
    agent_cmd: list[str] | None = None,
    idle_timeout: float = 5.0,
) -> AgentClient:
    """Return an AgentClient instance for the given mode."""
    if name not in _CLIENTS:
        raise ValueError(
            f"Unknown agent mode: {name!r}. "
            f"Available: {list(_CLIENTS.keys())}"
        )
    return _CLIENTS[name](agent_cmd=agent_cmd, idle_timeout=idle_timeout)
