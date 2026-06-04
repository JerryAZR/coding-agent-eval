# Agent Template Contract

An **agent template** is a directory that packages everything an agent needs to run inside the CAE evaluation environment: configuration files, environment variables, a Python virtual environment, a startup script, and optionally its Python adapter.

The framework copies the template into the agent's workspace (`impl/`) before the benchmark begins and sets `$HOME` to that workspace. This means agent configs, session histories, and virtual environments all live in the same persistent directory that survives across turns and phases.

## Directory Layout

```
template/
├── .cae-env              # Environment variables (sourced before worker starts)
├── .cae-startup.sh       # Optional: one-time setup script (runs before worker loop)
├── .venv/                # Optional: pre-built Python virtual environment
│   ├── bin/
│   │   ├── python
│   │   ├── pip
│   │   └── my-agent      # Agent binary installed in venv
│   └── lib/python3.11/site-packages/
├── agent/                # Optional: Python adapter module (added to PYTHONPATH)
│   ├── __init__.py
│   └── my_adapter.py     # @register_client("my-agent") class lives here
├── .pi/                  # Agent config/session storage (example: pi sessions)
│   └── agent/
│       └── sessions/
├── .claude/              # Agent config (example: Claude Code settings)
│   └── settings.json
├── .aider.conf.yml       # Agent config (example: Aider config)
└── README.md             # Human documentation (ignored by framework)
```

Everything is copied into `impl/` (the agent's `$HOME`). Files and directories starting with `.` are treated the same as any other file — they become dotfiles in the agent's home directory.

## Special Files

### `.cae-env`

A shell-sourcable file of `KEY=value` pairs. Loaded once when the worker container/process starts.

Example:
```bash
# API endpoints and keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
AIDER_MODEL=gpt-4o

# Agent-specific tuning
PI_MAX_TOKENS=8192
CAE_LOG_LEVEL=debug
```

**Container mode**: The framework passes this to `podman run --env-file`.
**Local mode**: The framework sources it into the worker subprocess environment.

> **Security note**: `.cae-env` is copied into `impl/`, which is visible to the tester container (mounted at `/run/impl`). Do not put irrecoverable secrets in benchmark templates unless you trust the benchmark's test code. For high-sensitivity keys, inject via host environment (`export` before running `cae run`) and reference them in `.cae-env` indirectly.

### `.cae-startup.sh`

An optional bash script executed **once** when the worker starts, before the worker loop begins. Runs with `$HOME` (i.e., `impl/`) as the working directory. The virtual environment is activated before the script runs, so `python` and `pip` resolve to the venv.

Example:
```bash
#!/usr/bin/env bash
set -euo pipefail

# Install non-Python system dependencies
apt-get update && apt-get install -y --no-install-recommends ripgrep fd-find

# Verify the agent binary is available
my-agent --version

# Warm up any caches
python -c "import anthropic; print('API client import OK')"
```

**Semantics**:
- Runs exactly once per benchmark (worker starts once per benchmark)
- If the script exits non-zero, the worker exits immediately and the benchmark fails
- stdout/stderr are forwarded to the manager's console
- The script must be idempotent — the framework does not guarantee a clean filesystem on retry (though the worker container itself is fresh)
- **Use for**: instant or non-Python preparations (`apt-get`, `npm install -g`, symlink creation)
- **Do not use for**: heavy Python dependency installation (use `.venv` instead)

### `.venv/` (pre-built virtual environment)

An optional pre-built Python virtual environment. If present, the framework:

1. Uses `.venv/bin/python` to run the worker (so the adapter can import venv packages)
2. Prepends `.venv/bin` to `PATH` (so the agent binary is available)
3. Sets `VIRTUAL_ENV=/run/impl/.venv`
4. Activates the venv before running `.cae-startup.sh`

**How to build** (must match the container's platform):

```bash
# Build venv inside the target container to ensure compatibility
podman run --rm -v $(pwd)/template:/t -w /t cae-worker-base \
  bash -c "python -m venv .venv && .venv/bin/pip install -r requirements.txt"
```

> **Platform warning**: A venv built on macOS ARM64 will not run in a Linux AMD64 container. Always build the venv using the target base image (or the same architecture/OS).

**When to use**:

| Dependency Size | Recommendation |
|-----------------|----------------|
| Small (few packages, < 50 MB) | ✅ `.venv` in template — fast copy, fast startup |
| Moderate (tens of packages, < 500 MB) | ⚠️ `.venv` in template — acceptable if you accept the copy cost |
| Large (PyTorch, CUDA, > 1 GB) | ❌ Bake into a custom image layer — copy cost per benchmark is prohibitive |

For large dependencies, create a layered image:
```dockerfile
FROM cae-worker-base
RUN python -m venv /opt/agent-venv \
    && /opt/agent-venv/bin/pip install torch transformers
ENV PATH="/opt/agent-venv/bin:${PATH}"
```

Then in your template, create a symlink or add `/opt/agent-venv/bin` to PATH via `.cae-env`.

### `agent/` (optional Python adapter)

If present, the framework adds this directory to `PYTHONPATH` before importing the agent client. The directory must be a valid Python package (contains `__init__.py` or is a namespace package).

Example `agent/my_adapter.py`:
```python
from cae.agent_client import OneShotAgentClient, register_client

@register_client("my-agent")
class MyAgentClient(OneShotAgentClient):
    def build_cmd(self, prompt: str) -> list[str]:
        return ["my-agent", "--prompt", prompt]
```

The agent mode name passed via `--agent-mode` must match the `@register_client` decorator. See `docs/user-guide-other-harnesses.md` for the full adapter authoring guide.

## Execution Order

When a benchmark starts, the framework performs these steps in order:

1. **Create workspace**: `bench_dir/impl/`, `bench_dir/test/`, `bench_dir/.cae/`
2. **Copy template**: Recursively copy template directory contents into `impl/`
3. **Set `$HOME`**: `$HOME=/run/impl` (container) or `bench_dir/impl/` (local)
4. **Detect venv**: If `impl/.venv/` exists, use `.venv/bin/python` for the worker and prepend `.venv/bin` to `PATH`
5. **Load env**: Parse `.cae-env` into the worker's environment
6. **Extend PYTHONPATH**: If `impl/agent/` exists, prepend it to PYTHONPATH
7. **Run startup**: Execute `.cae-startup.sh` (if present), with venv activated
8. **Start worker**: Spawn the worker process/container
9. **Start loop**: Manager writes first task, waits for ready marker

## CLI Usage

```bash
# Local mode with template
cae run \
  --mode local \
  --suite benchmarks/my-suite/suite.json \
  --agent-mode my-agent \
  --agent-template ./templates/my-agent/

# Container mode with template
cae run \
  --mode container \
  --suite benchmarks/my-suite/suite.json \
  --agent-mode my-agent \
  --agent-template ./templates/my-agent/ \
  --worker-image cae-worker-base
```

## Design Decisions

### Why `$HOME` in the workspace?

Most agents store session histories and config under `~` (e.g., `~/.pi/agent/sessions/`, `~/.claude/settings.json`). By setting `$HOME` to the workspace volume:

- Session persistence happens automatically across turns and phases
- Template configs just work: copy `.pi/` into the template, it lands at `~/.pi/`
- The agent's state is inspectable on the host after the benchmark ends

### Template vs Image: where does each concern belong?

| Concern | Template | Image Layer | Rationale |
|---------|----------|-------------|-----------|
| Static config (`.pi/`, `.claude/`) | ✅ | ❌ | Changes often, agent-specific |
| Environment variables | ✅ `.cae-env` | ❌ | Per-run, must not be baked |
| Small Python deps (< 50 MB) | ✅ `.venv` | ⚠️ | Fast copy, live reload |
| Moderate Python deps (< 500 MB) | ⚠️ `.venv` | ✅ | Acceptable if copy cost is okay |
| Large Python deps (> 1 GB) | ❌ | ✅ | Copy cost per benchmark is prohibitive |
| Non-Python deps (apt, npm) | ⚠️ `.cae-startup.sh` | ✅ | Slow to install at runtime |
| System tools (git, ripgrep) | ❌ | ✅ | Should be in base image |
| Python adapter code | ✅ `agent/` | ❌ | User code, changes frequently |
| Base CAE framework | ❌ | ✅ | Stable, shared across agents |

The template handles the *fast-changing, agent-specific* parts. The image handles the *slow, stable, heavy* parts. The startup script is the escape hatch for anything that doesn't fit neatly into either category.

### Why pre-built `.venv` instead of `pip install` in startup script?

- **Deterministic**: Same packages every run
- **Offline-capable**: No network needed during benchmark
- **Fast**: Copy a directory vs resolve and download packages
- **Cross-platform-safe**: When built correctly, the venv matches the container exactly

The trade-off is the copy cost per benchmark. For small venvs this is negligible; for large ones, bake into the image.

### Why is the Python wiring loaded dynamically?

Agent adapters are user code. Requiring a Docker rebuild for every adapter change adds friction. By placing the adapter in `template/agent/` and adding it to PYTHONPATH, agent vendors can iterate on adapter logic with the same base image.

The CAE framework itself (`cae.worker`, `cae.agent_client` base classes, `cae.protocol`) remains either bind-mounted (development) or baked into a standalone image (production). Only the *agent-specific subclass* is dynamic.

## Future Extensions

The following are reserved for future use and currently ignored:

- `.cae-startup.py` — Python startup script (alternative to `.sh`)
- `agent/requirements.txt` — auto-installed before startup script runs
- `agent/pyproject.toml` — auto-installed in editable mode
- `agent/package.json` — auto-installed via npm before startup script runs
