"""Worker support process.

Runs inside the worker container. Communicates with the agent harness
via an AgentClient, and manages the submission lifecycle."""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .agent_client import (
    COMPLETION_INSTRUCTION,
    PHASE_COMPLETE_MARKER,
    AgentClient,
    TurnResult,
    get_client,
)
from .protocol import Volume

MAX_CRASH_RETRIES = 3

CONTINUE_PROMPT = (
    "Continue working on the task. Do not ask whether to continue; "
    f"include the marker {PHASE_COMPLETE_MARKER} when you are truly done."
)


def _check_completion(output: str) -> bool:
    """Return True if the last non-empty line equals the completion marker."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines and lines[-1] == PHASE_COMPLETE_MARKER


def run_worker(
    volume: Volume,
    impl_dir: Path,
    client_factory: Callable[[], AgentClient],
) -> int:
    """Main worker loop.

    Drives the agent one turn at a time.  The agent must emit
    ``PHASE_COMPLETE_MARKER`` as the final line of its output to signal
    that it has truly finished the current task.

    - If the marker is missing on a successful turn, the worker sends a
      continue prompt to the **same client object** and loops forever.
    - If the turn itself crashes (non-zero exit, exception, etc.), the
      worker retries up to ``MAX_CRASH_RETRIES`` with the same client.
    - After ``MAX_CRASH_RETRIES`` crashes the worker exits with an error.
    """
    task = volume.read_task()
    if task is None:
        print("No task found in volume", file=sys.stderr)
        return 1

    env = {**os.environ, "CAE_ARTIFACT_ROOT": str(impl_dir)}
    current_prompt = task.prompt
    crash_retries = 0
    client = client_factory()

    while crash_retries < MAX_CRASH_RETRIES:
        try:
            result = client.run_turn(
                current_prompt,
                env,
                impl_dir,
                system_prompt_append=COMPLETION_INSTRUCTION,
            )
        except Exception as exc:  # noqa: BLE001
            result = TurnResult(success=False, details=str(exc), output="")

        if not result.success:
            crash_retries += 1
            print(
                f"Agent turn failed ({crash_retries}/{MAX_CRASH_RETRIES}): {result.details}",
                file=sys.stderr,
            )
            if crash_retries >= MAX_CRASH_RETRIES:
                break
            current_prompt = CONTINUE_PROMPT
            continue

        # Reset crash counter on any successful turn.
        crash_retries = 0

        if not _check_completion(result.output):
            print(
                "Agent did not signal completion; asking it to continue",
                file=sys.stderr,
            )
            current_prompt = CONTINUE_PROMPT
            continue

        # Signal ready for evaluation
        volume.set_ready()

        # Wait for feedback to change
        last_feedback = volume.read_feedback()
        while True:
            time.sleep(1)
            current_feedback = volume.read_feedback()
            if current_feedback is None:
                continue
            if (
                last_feedback is None
                or current_feedback.to_dict() != last_feedback.to_dict()
            ):
                break

        feedback = volume.read_feedback()
        if feedback is None:
            continue

        volume.clear_ready()

        if feedback.phase_complete:
            if feedback.next_phase_id:
                new_task = volume.read_task()
                if new_task is None:
                    print("Next phase task missing", file=sys.stderr)
                    return 1
                current_prompt = new_task.prompt
            else:
                break
        elif not feedback.passed:
            current_prompt = (
                f"Tests failed (attempt {feedback.attempt}).\n{feedback.message}"
            )
        else:
            current_prompt = "Continue working on the task."

    if crash_retries >= MAX_CRASH_RETRIES:
        print(
            f"Agent failed after {MAX_CRASH_RETRIES} crash retries; giving up.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CAE worker support process")
    parser.add_argument(
        "--volume", required=True, help="Run directory (parent of .cae/ and impl/)"
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait after agent_end before submitting",
    )
    parser.add_argument(
        "--agent-mode", default="pi", help="Agent harness mode (pi, echo, ...)"
    )
    parser.add_argument("--agent-cmd", help="Custom agent command (space-separated)")
    args = parser.parse_args(argv)

    run_dir = Path(args.volume)
    impl_dir = run_dir / "impl"
    volume = Volume(run_dir)
    agent_cmd = args.agent_cmd.split() if args.agent_cmd else None

    def client_factory() -> AgentClient:
        return get_client(
            args.agent_mode,
            agent_cmd=agent_cmd,
            idle_timeout=args.idle_timeout,
        )

    return run_worker(volume, impl_dir, client_factory)


if __name__ == "__main__":
    sys.exit(main())
