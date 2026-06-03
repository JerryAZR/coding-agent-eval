"""Worker support process.

Runs inside the worker container. Communicates with the agent harness
via an AgentClient, and manages the submission lifecycle."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .agent_client import AgentClient, get_client
from .protocol import Volume


def run_worker(
    volume: Volume,
    impl_dir: Path,
    client: AgentClient,
) -> int:
    """Main worker loop."""
    task = volume.read_task()
    if task is None:
        print("No task found in volume", file=sys.stderr)
        return 1

    env = {**os.environ, "CAE_ARTIFACT_ROOT": str(impl_dir)}
    current_prompt = task.prompt

    try:
        while True:
            result = client.run_turn(current_prompt, env, impl_dir)
            if not result.success:
                print(f"Agent turn failed: {result.details}", file=sys.stderr)
                break

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
    finally:
        client.cleanup()

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
    client = get_client(args.agent_mode, agent_cmd=agent_cmd, idle_timeout=args.idle_timeout)
    return run_worker(volume, impl_dir, client)


if __name__ == "__main__":
    sys.exit(main())
