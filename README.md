# CAE — Coding Agent Evaluation Framework

A minimal, containerized framework for evaluating coding agents against multi-phase benchmarks.  The agent runs in an isolated environment, produces code, and a separate tester process evaluates the results.

## Quick Start

### 1. Build container images

```bash
./scripts/build-images.sh
```

This creates `cae-worker-base`, `cae-tester-base`, `cae-worker-fat`, and
`cae-tester-fat` images.  Use the `-fat` variants for benchmarks that should
not bias agents toward Python.  See [`docs/container-mode.md`](docs/container-mode.md)
for image details.

### 2. Run a smoke benchmark

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/dummies/dummy-smoke/suite.json \
  --volume /tmp/cae-runs
```

Check `/tmp/cae-runs/` for the run directory and `suite-summary.json`.

### 3. Run with a real agent template

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/dummies/dummy-smoke/suite.json \
  --volume /tmp/cae-runs \
  --agent-template templates/pi \
  --agent-cmd "pi"
```

## Project Layout

```
.
├── src/cae/              # Framework source
│   ├── cli.py            # Entry point
│   ├── worker.py         # Agent driver (dumb pipe)
│   ├── manager.py        # Orchestration
│   ├── tester.py         # Test runner
│   ├── runtime.py        # Local / container runtime
│   ├── protocol.py       # Shared volume I/O
│   ├── agent_client.py   # Adapter base classes
│   ├── benchmark.py      # Benchmark loader
│   ├── scoring.py        # Score computation
│   ├── suite.py          # Suite loader
│   └── template.py       # Template copy / env merge
├── benchmarks/           # Benchmark definitions
│   ├── README.md         # Benchmark authoring guide
│   └── dummy-smoke/      # Minimal example benchmark
├── templates/            # Agent templates
│   └── pi/               # Example: pi coding agent
├── docs/
│   ├── protocol.md       # Shared volume protocol (manager ⟷ worker)
│   ├── container-mode.md # Container image build & runtime
│   ├── agent-template.md # Template layout & contract
│   └── user-guide-other-harnesses.md  # Adapter authoring for other agents
├── images/
│   └── Dockerfile        # Base images (worker, tester, pi layer)
└── tests/                # Unit & integration tests
```

## Evaluating Your Own Agent

1. **Create a template directory** with your agent's config, venv, and adapter.
   See [`docs/agent-template.md`](docs/agent-template.md) for the full contract.

2. **Implement a Python adapter** in `templates/my-agent/agent/my_adapter.py`:
   ```python
   from cae.agent_client import OneShotAgentClient, register_client

   @register_client("my-agent")
   class MyClient(OneShotAgentClient):
       def build_cmd(self, prompt: str) -> list[str]:
           return ["my-agent", "--prompt", prompt]
   ```
   See [`docs/user-guide-other-harnesses.md`](docs/user-guide-other-harnesses.md) for patterns (one-shot CLI, RPC, fully custom).

3. **Run**:
   ```bash
   PYTHONPATH=src python -m cae run \
     --suite benchmarks/my-suite/suite.json \
     --volume /tmp/cae-runs \
     --agent-template templates/my-agent/
   ```

## Designing Your Own Benchmark

A benchmark is a self-contained directory consumed via `--suite`.

Minimal structure:
```
my-benchmark/
  task.json          # phase definitions, scoring rules
  prompts/
    phase-1.md       # prompt text for phase 1
  tests/
    run.sh           # entry point; exits 0 on pass, non-zero on fail
    fixtures/        # test data
```

See [`benchmarks/README.md`](benchmarks/README.md) for `task.json` schema, test execution contract, and suite configuration.

## Architecture

```
Host                    Container (rootless Podman)
─────────────────────────────────────────────────────
Manager ──▶ Worker      cae-worker-base
             (agent)     ├─ impl/  ← agent workspace ($HOME)
             ↕           └─ .cae/  ← protocol files
           ready marker
Manager ──▶ Tester      cae-tester-base (--net=none)
             (isolated)  ├─ benchmark/tests/ ← read-only
                        └─ impl/ ← read-only agent artifacts
```

- **Manager** orchestrates phases, constructs prompts, and scores results.
- **Worker** is a dumb pipe: reads `prompt.md`, drives the agent, sets `ready`.
- **Tester** runs in isolation with no network. It cannot see the agent's source code; it only reads artifacts from the shared volume.

For protocol details see [`docs/protocol.md`](docs/protocol.md).  For container security and image variants see [`docs/container-mode.md`](docs/container-mode.md).

## Development

```bash
# Run tests
PYTHONPATH=src python -m unittest discover -s tests -t . -v

# Type check
mypy src/cae --ignore-missing-imports

# Lint
ruff check src/cae tests
```

Configuration lives in [`pyproject.toml`](pyproject.toml).

## License

MIT
