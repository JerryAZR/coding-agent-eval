"""Agent client abstraction for different harness types.

The worker uses an AgentClient to communicate with the agent harness.
One AgentClient instance = one agent session. Subclasses must implement
session persistence internally (e.g. via --session-id, state files in cwd,
etc.).

Built-in clients cover the two common paradigms:

- OneShotAgentClient: fresh process per turn (e.g. pi -p, claude, aider)
"""
from __future__ import annotations

import random
import subprocess
import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


# Marker the agent must emit in its output when it has truly completed work.
PHASE_COMPLETE_MARKER = "<CAE_PHASE_COMPLETE/>"

# Instruction the worker passes to every turn to solicit the marker.
COMPLETION_INSTRUCTION = (
    "When you have finished the task, include the exact marker "
    f"{PHASE_COMPLETE_MARKER} on the final line of your response."
)


@dataclass
class TurnResult:
    """Outcome of one agent turn."""

    success: bool
    output: str = ""
    details: str = ""


class AgentClient(ABC):
    """Abstract interface for an agent harness.

    One AgentClient instance represents one agent session. The worker
    will call ``run_turn`` repeatedly on the same instance. Subclasses
    must implement session persistence internally.
    """

    @abstractmethod
    def run_turn(
        self,
        prompt: str,
        env: dict,
        cwd: Path,
        system_prompt_append: str = "",
    ) -> TurnResult:
        """Execute one turn within this session.

        ``system_prompt_append`` is text the agent must treat as part of
        its system instructions. Returns TurnResult where ``output`` is
        the agent's final visible response (thinking traces stripped).
        """
        ...


# ---------------------------------------------------------------------------
# Built-in clients
# ---------------------------------------------------------------------------

class OneShotAgentClient(AgentClient):
    """Client for one-shot CLI agents (e.g. claude, aider).

    Runs a fresh subprocess per turn. Subclasses override ``build_cmd()``.
    Session persistence must be implemented by the subclass (e.g.
    ``--session-id`` or state files written to *cwd*).
    """

    def __init__(self, agent_cmd: list[str] | None = None, **kwargs):
        self.agent_cmd = agent_cmd or []
        self.state = None

    def build_cmd(self, prompt: str) -> list[str]:
        """Return the command to run for this turn.

        ``agent_cmd`` is prepended as the base command.
        """
        return [*self.agent_cmd, prompt]

    def extract_state(self, result: subprocess.CompletedProcess):
        """Parse state from stdout for the next turn. Optional."""
        return None

    def run_turn(
        self,
        prompt: str,
        env: dict,
        cwd: Path,
        system_prompt_append: str = "",
    ) -> TurnResult:
        full_prompt = prompt
        if system_prompt_append:
            full_prompt += "\n\n" + system_prompt_append
        cmd = self.build_cmd(full_prompt)
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
            return TurnResult(
                success=success,
                output=result.stdout,
                details=details.strip(),
            )
        except subprocess.TimeoutExpired:
            return TurnResult(
                success=False,
                output="",
                details="Agent timed out after 300s",
            )
        except Exception as e:
            return TurnResult(
                success=False,
                output="",
                details=f"Failed to run agent: {e}",
            )


class PiOneShotClient(OneShotAgentClient):
    """One-shot pi client using -p with persistent --session-id.

    Each turn starts a fresh pi process, but all turns share the same
    session so the agent retains context across retries and phases.
    Sessions are saved to disk for later analysis.
    """

    def __init__(self, agent_cmd: list[str] | None = None, **kwargs):
        # agent_cmd is ignored; pi binary is hardcoded
        super().__init__(agent_cmd=[])
        self.session_id = str(uuid.uuid4())

    def build_cmd(self, prompt: str) -> list[str]:
        return [
            "pi",
            "-p", prompt,
            "--session-id", self.session_id,
            "--name", f"cae-{self.session_id[:8]}",
        ]

    def extract_state(self, result: subprocess.CompletedProcess):
        # Session persistence is handled by pi itself via --session-id
        return None


class EchoClient(AgentClient):
    """Test harness: writes the prompt to output.txt and randomly signals completion.

    Used by integration tests to verify the framework protocol without
    requiring a real agent.  On first ``run_turn`` it writes the clean
    prompt to *cwd*/output.txt.  It also creates a session marker file
    so tests can detect if multiple EchoClient instances were spawned
    for the same benchmark.
    """

    def __init__(self, **kwargs):
        self._wrote_output = False
        self._session_id = str(uuid.uuid4())

    def run_turn(
        self,
        prompt: str,
        env: dict,
        cwd: Path,
        system_prompt_append: str = "",
    ) -> TurnResult:
        if not self._wrote_output:
            self._wrote_output = True
            # Write a session marker to detect accidental respawning.
            (cwd / ".cae-echo-session").write_text(self._session_id)
            # Strip the system_prompt_append before persisting the "impl".
            clean = prompt
            if system_prompt_append and clean.endswith(system_prompt_append):
                clean = clean[: -len(system_prompt_append)].rstrip()
            (cwd / "output.txt").write_text(clean)

        # Randomly include the completion marker (simulates an agent that
        # sometimes asks questions before finishing).
        output = prompt if random.random() > 0.3 else prompt + "\n" + PHASE_COMPLETE_MARKER
        return TurnResult(success=True, output=output)


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
