"""Worker support process.

Runs inside the worker container. Reads prompts from the shared volume,
drives the agent harness, and signals readiness for evaluation.

The worker is a dumb pipe: it reads whatever prompt the manager writes,
runs the agent to completion, and sets the ready marker.  It has no
knowledge of phases, attempts, or scoring.
"""
from __future__ import annotations

import argparse
import os
import subprocess
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
    if not lines:
        return False
    return lines[-1] == PHASE_COMPLETE_MARKER


def _run_startup_script(impl_dir: Path) -> int:
    """Execute ``.cae-startup.sh`` if present.

    Runs with *impl_dir* as the working directory and the current process
    environment.  Returns the script's exit code (0 if no script exists).
    """
    script = impl_dir / ".cae-startup.sh"
    if not script.exists():
        return 0

    print(f"Running startup script: {script}", file=sys.stderr)
    result = subprocess.run(
        ["bash", str(script)],
        cwd=impl_dir,
        env=os.environ,
    )
    return result.returncode


def _discover_clients(agent_dir: Path) -> dict[str, type[AgentClient]]:
    """Import agent adapters from *agent_dir* and return registered clients.

    Each ``.py`` file (except those starting with ``_``) is executed as a
    module so that any ``@register_client`` decorators are executed.  Files
    are loaded with synthetic module names to avoid shadowing stdlib packages.
    """
    import importlib.util

    for py_file in agent_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module_name = f"_cae_adapter_{py_file.stem}"
        # Remove any stale cached module with the same synthetic name.
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            print(
                f"Warning: failed to import adapter {py_file.name}: {exc}",
                file=sys.stderr,
            )

    from .agent_client import _CLIENTS
    return dict(_CLIENTS)

def run_worker(
    volume: Volume,
    impl_dir: Path,
    client_factory: Callable[[], AgentClient],
) -> int:
    """Main worker loop.
    Drives the agent one turn at a time.  The agent must emit
    ``PHASE_COMPLETE_MARKER`` as the final line of its output to signal
    that it has truly finished the current task.

    The worker waits for the manager to write ``prompt.md``, runs the
    agent until it signals completion, then sets the ``ready`` marker.
    It loops forever (or until crash retries are exhausted), waiting for
    the manager to clear ``ready`` and write the next prompt.
    """
    # Run agent-specific startup script inside the container/process.
    startup_rc = _run_startup_script(impl_dir)
    if startup_rc != 0:
        print(
            f"Startup script failed with exit code {startup_rc}",
            file=sys.stderr,
        )
        return 1

    env = {**os.environ, "CAE_ARTIFACT_ROOT": str(impl_dir)}
    client = client_factory()

    while True:
        # Wait for the manager to provide a prompt.
        prompt = volume.read_prompt()
        while prompt is None:
            time.sleep(1)
            prompt = volume.read_prompt()

        volume.delete_prompt()

        # Drive the agent to completion.  The agent may need multiple turns
        # (e.g. if it asks a question instead of emitting the marker).
        crash_retries = 0
        while crash_retries < MAX_CRASH_RETRIES:
            try:
                result = client.run_turn(
                    prompt,
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
                    return 1
                prompt = CONTINUE_PROMPT
                continue

            # Reset crash counter on any successful turn.
            crash_retries = 0

            if _check_completion(result.output):
                break

            print(
                "Agent did not signal completion; asking it to continue",
                file=sys.stderr,
            )
            prompt = CONTINUE_PROMPT
            continue

        # Signal ready for evaluation.
        volume.set_ready()

        # Wait for the manager to clear ready.
        while volume.is_ready():
            time.sleep(1)


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
    parser.add_argument("--agent-cmd", help="Custom agent command (space-separated)")
    args = parser.parse_args(argv)

    run_dir = Path(args.volume)
    impl_dir = run_dir / "impl"
    volume = Volume(run_dir)
    agent_cmd = args.agent_cmd.split() if args.agent_cmd else None

    # Auto-import agent adapters from impl/agent/ so @register_client
    # decorators are executed.
    agent_dir = impl_dir / "agent"
    clients: dict = {}
    if agent_dir.exists() and agent_dir.is_dir():
        clients = _discover_clients(agent_dir)

    if len(clients) == 0:
        print(
            "Error: no agent client registered. "
            "Ensure your template's agent/ package contains a @register_client decorated class.",
            file=sys.stderr,
        )
        return 1
    if len(clients) > 1:
        print(
            f"Error: multiple agents registered: {list(clients.keys())}. "
            "Only one agent per template is allowed.",
            file=sys.stderr,
        )
        return 1

    mode = next(iter(clients))

    def client_factory() -> AgentClient:
        return get_client(
            mode,
            agent_cmd=agent_cmd,
            idle_timeout=args.idle_timeout,
        )

    return run_worker(volume, impl_dir, client_factory)


if __name__ == "__main__":
    sys.exit(main())
