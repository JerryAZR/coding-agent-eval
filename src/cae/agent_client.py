"""Agent client abstraction for different harness types.

The worker uses an AgentClient to communicate with the agent harness.
One AgentClient instance = one agent session. Subclasses must implement
session persistence internally (e.g. via --session-id, state files in cwd,
etc.).

Built-in clients cover the two common paradigms:

- OneShotAgentClient: fresh process per turn (e.g. pi -p, claude, aider)
"""
from __future__ import annotations

import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


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

    def __init__(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def run_turn(
        self,
        prompt: str,
        env: dict[str, str],
        cwd: Path,
        system_prompt_append: str = "",
    ) -> TurnResult:
        """Execute one turn within this session.

        ``system_prompt_append`` is text the agent must treat as part of
        its system instructions. Returns TurnResult where ``output`` is
        the agent's final visible response (thinking traces stripped).
        """
        ...


class OneShotAgentClient(AgentClient):
    """Client for one-shot CLI agents (e.g. claude, aider).

    Runs a fresh subprocess per turn. Subclasses override ``build_cmd()``.
    Session persistence must be implemented by the subclass (e.g.
    ``--session-id`` or state files written to *cwd*).
    """

    def __init__(self, agent_cmd: list[str] | None = None, **kwargs: Any) -> None:
        self.agent_cmd = agent_cmd or []
        self.state = None

    def build_cmd(self, prompt: str) -> list[str]:
        """Return the command to run for this turn.

        ``agent_cmd`` is prepended as the base command.
        """
        return [*self.agent_cmd, prompt]

    def extract_state(self, result: subprocess.CompletedProcess[str]) -> Any:
        """Parse state from stdout for the next turn. Optional."""
        return None

    def run_turn(
        self,
        prompt: str,
        env: dict[str, str],
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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLIENTS: dict[str, type[AgentClient]] = {}


def register_client(name: str) -> Callable[[type[AgentClient]], type[AgentClient]]:
    """Decorator to register an AgentClient subclass."""

    def decorator(cls: type[AgentClient]) -> type[AgentClient]:
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
