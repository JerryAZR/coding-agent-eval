# User Guide: Evaluating Other Agent Harnesses

The CAE framework is not locked to the `pi` coding agent. You can plug in any agent harness by implementing a small Python adapter.

## The Core Insight: Two Agent Paradigms

Most agent harnesses fall into one of two categories:

| Paradigm | Lifetime | Examples |
|----------|----------|----------|
| **One-shot CLI** | Fresh process per turn. Exits when done. | `claude`, `aider`, `codex`, most shell-wrapped LLM calls |
| **RPC / Daemon** | Long-lived process. Multiple prompts over stdin/socket. | `pi --mode rpc`, custom agents with JSONL protocol |

The CAE worker abstracts both into a single **turn-based interface**.

## The Interface

```python
from cae.agent_client import AgentClient, TurnResult
from pathlib import Path

class MyAgentClient(AgentClient):
    def run_turn(self, prompt: str, env: dict, cwd: Path) -> TurnResult:
        """Execute one turn: deliver prompt, wait for agent to finish, return outcome.

        The worker calls this once per prompt:
        - Initial task prompt
        - Retry feedback ("Tests failed, fix this...")
        - Next phase prompt
        """
        ...

    def cleanup(self) -> None:
        """Release resources when the benchmark ends. Optional."""
        ...
```

`TurnResult`:
- `success: bool` — Did the agent complete its turn?
- `details: str` — Optional stdout/stderr for debugging

The worker handles all volume protocol interaction (`.cae/task.json`, `.cae/feedback.json`, `.cae/ready`). Your adapter just runs the agent.

## Built-in Modes

| Mode | Class | Description |
|------|-------|-------------|
| `pi` (default) | `PiOneShotClient` | One-shot `pi -p` with persistent `--session-id`. Fresh process per turn, shared session across retries/phases. |
| `pi-rpc` | `RpcAgentClient` | Long-lived JSONL RPC. Legacy mode, only needed if one-shot is unsuitable. |
| `echo` | `EchoClient` | Test harness. Writes first prompt to `output.txt`. No subprocess. |

You can also implement your own and register it with `@register_client("name")`.

## Pattern A: One-Shot CLI Agent (most common)

Use the built-in base class:

```python
from cae.agent_client import OneShotAgentClient, register_client

@register_client("claude")
class ClaudeClient(OneShotAgentClient):
    def __init__(self, agent_cmd=None, **kwargs):
        super().__init__(agent_cmd)
        self.session_id = None

    def build_cmd(self, prompt: str) -> list[str]:
        cmd = ["claude", "-p", prompt, "--output-format", "json"]
        if self.session_id:
            cmd.extend(["--resume", self.session_id])
        return cmd

    def extract_state(self, result: subprocess.CompletedProcess):
        """Parse session_id from JSON output for next turn."""
        try:
            data = json.loads(result.stdout)
            return data.get("session_id")
        except json.JSONDecodeError:
            return self.session_id
```

`OneShotAgentClient` handles:
- Running `subprocess.run` with your `build_cmd`
- Capturing stdout/stderr
- Calling `extract_state` after each turn
- Returning a `TurnResult`

## Pattern B: RPC / Daemon Agent

Use the built-in base class for long-lived processes:

```python
from cae.agent_client import RpcAgentClient, register_client

@register_client("my-rpc-agent")
class MyRpcClient(RpcAgentClient):
    def __init__(self, agent_cmd=None, idle_timeout=5.0, **kwargs):
        super().__init__(agent_cmd or ["my-agent", "--mode", "rpc"], idle_timeout)
```

`RpcAgentClient` handles:
- Starting the process once, reusing across turns
- Sending prompts via JSONL
- Monitoring stdout for idle events
- Terminating cleanly on cleanup

`pi` uses `PiOneShotClient` by default. Only use `pi-rpc` if you specifically need the long-lived RPC behavior.

## Pattern C: Fully Custom (inline)

For simple agents, implement `AgentClient` directly:

```python
@register_client("echo")
class EchoClient(AgentClient):
    """Test harness: writes the prompt to output.txt."""

    def __init__(self, **kwargs):
        self.first_prompt = None

    def run_turn(self, prompt, env, cwd):
        if self.first_prompt is None:
            self.first_prompt = prompt
            (cwd / "output.txt").write_text(prompt)
        return TurnResult(success=True)

    def cleanup(self):
        pass
```

No subprocess at all. The framework's own integration tests use this mode (`--agent-mode echo`).

## Registration and Usage

Place your adapter in an importable Python module, then reference it at runtime:

```bash
PYTHONPATH=src:my-adapter-dir python -m cae run \
  --suite benchmarks/my-suite/suite.json \
  --agent-mode claude \
  --agent-cmd "claude"   # optional override
```

The `--agent-mode` flag selects which registered client to use. `--agent-cmd` is passed through to the client's constructor as a list of strings (split on whitespace).

## File Locations

- **Agent workspace**: `CAE_ARTIFACT_ROOT` points to `impl/`. Write all code here.
- **Task spec**: Read `.cae/task.json` for the current phase prompt.
- **Feedback**: After evaluation, `.cae/feedback.json` contains pass/fail.
- **Ready signal**: When done, create `.cae/ready`. The worker does this automatically after `run_turn` returns successfully.

## Container Mode

In container mode, your adapter code is part of the worker image. Options:

1. **Layer it**: `FROM cae-worker-base`, add your adapter + harness dependencies
2. **Bind-mount it**: Mount your adapter directory into the container at runtime

See `docs/container-mode.md` (forthcoming) for build instructions.

## Summary

| Step | What you do |
|------|-------------|
| 1 | Choose base class: `OneShotAgentClient`, `RpcAgentClient`, or raw `AgentClient` |
| 2 | Implement `build_cmd` / `extract_state` (one-shot) or configure RPC settings |
| 3 | Register with `@register_client("name")` |
| 4 | Run with `--agent-mode name --agent-cmd "your command"` |

The framework handles orchestration, scoring, retry logic, and result collection.
