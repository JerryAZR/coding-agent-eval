# User Guide: Evaluating Other Agent Harnesses

The CAE framework is not locked to any single coding agent. You can plug in any agent harness by creating a template directory with a small Python adapter.

## The Core Insight: Two Agent Paradigms

Most agent harnesses fall into one of two categories:

| Paradigm | Lifetime | Examples |
|----------|----------|----------|
| **One-shot CLI** | Fresh process per turn. Exits when done. | `claude`, `aider`, `codex`, most shell-wrapped LLM calls |
| **RPC / Daemon** | Long-lived process. Multiple prompts over stdin/socket. | Custom agents with JSONL protocol |

The CAE worker abstracts both into a single **turn-based interface**.

## The Interface

```python
from cae.agent_client import AgentClient, TurnResult
from pathlib import Path

class MyAgentClient(AgentClient):
    def run_turn(self, prompt: str, env: dict, cwd: Path, system_prompt_append: str = "") -> TurnResult:
        """Execute one turn: deliver prompt, wait for agent to finish, return outcome.

        The worker calls this once per prompt:
        - Initial task prompt
        - Retry feedback ("Tests failed, fix this...")
        - Next phase prompt
        """
        ...
```

`TurnResult`:
- `success: bool` — Did the agent complete its turn?
- `output: str` — The agent's visible output (last non-empty line checked for `<CAE_PHASE_COMPLETE/>`)
- `details: str` — Optional stdout/stderr for debugging

The worker handles all volume protocol interaction (`.cae/prompt.md`, `.cae/ready`). Your adapter just runs the agent.

## How Discovery Works

The framework discovers your agent **automatically** from the template:

1. You pass `--agent-template ./templates/my-agent/` to `cae run`
2. The framework copies the template into `impl/` and adds `impl/agent/` to `PYTHONPATH`
3. The worker imports every `.py` file in `agent/`, executing any `@register_client` decorators
4. The worker checks how many clients were registered:
   - **Exactly 1** → use it
   - **0 or >1** → fail immediately

This means built-in agents (pi, echo) and custom agents all go through the same loading process. There is no `--agent-mode` flag.

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

## Pattern C: Fully Custom (inline)

For simple agents, implement `AgentClient` directly:

```python
@register_client("echo")
class EchoClient(AgentClient):
    """Test harness: writes the prompt to output.txt."""

    def __init__(self, **kwargs):
        self.first_prompt = None

    def run_turn(self, prompt, env, cwd, system_prompt_append=""):
        if self.first_prompt is None:
            self.first_prompt = prompt
            (cwd / "output.txt").write_text(prompt)
        return TurnResult(success=True, output=prompt + "\n<CAE_PHASE_COMPLETE/>")
```

No subprocess at all. The framework's own integration tests use this via `templates/echo/`.

## Template Directory

Place your adapter in `templates/my-agent/agent/my_adapter.py` alongside any config, venv, or startup script:

```
templates/my-agent/
├── .cae-env
├── .cae-startup.sh
├── .venv/
└── agent/
    ├── __init__.py
    └── my_adapter.py   # @register_client("my-agent") goes here
```

Run it:

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/my-suite/suite.json \
  --agent-template ./templates/my-agent/ \
  --agent-cmd "claude"   # optional override
```

## Container Mode

For isolated evaluation, run worker and tester in rootless Podman containers:

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/nlm-eval/suite.json \
  --agent-template ./templates/my-agent/
```

See `docs/container-mode.md` for full details on building images, layering agents, and security configuration.

## Summary

| Step | What you do |
|------|-------------|
| 1 | Create `templates/my-agent/` with `.cae-env`, `.venv/`, etc. |
| 2 | Implement adapter in `agent/my_adapter.py` |
| 3 | Register with `@register_client("name")` |
| 4 | Run with `--agent-template ./templates/my-agent/ --agent-cmd "your command"` |

The framework handles orchestration, scoring, retry logic, and result collection.
