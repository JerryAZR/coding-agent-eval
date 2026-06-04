"""Echo agent adapter for CAE.

A test harness that writes the prompt to output.txt and randomly signals
completion.  Registered dynamically like any other agent template.
"""
import os
import random
from pathlib import Path

from cae.agent_client import (
    AgentClient,
    COMPLETION_INSTRUCTION,
    PHASE_COMPLETE_MARKER,
    TurnResult,
    register_client,
)


@register_client("echo")
class EchoClient(AgentClient):
    """Test harness: writes the prompt to output.txt and randomly signals completion."""

    def __init__(self, **kwargs):
        self._wrote_output = False

    def run_turn(self, prompt: str, env: dict, cwd: Path, system_prompt_append: str = "") -> TurnResult:
        output_file = cwd / "output.txt"

        # Strip completion instruction before writing
        clean = prompt
        if COMPLETION_INSTRUCTION in clean:
            clean = clean.replace(COMPLETION_INSTRUCTION, "").strip()

        if not self._wrote_output:
            output_file.write_text(clean)
            self._wrote_output = True

        # Randomly decide whether to signal completion
        if random.random() < 0.5:
            output = prompt + "\n" + PHASE_COMPLETE_MARKER
        else:
            output = prompt

        return TurnResult(success=True, output=output)
