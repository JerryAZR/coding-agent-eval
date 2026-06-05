# Benchmark Distribution Format

A benchmark is a self-contained directory consumed by the framework via `--suite`.

## Directory Structure

```
<benchmark-name>/
  task.json          # Task specification
  prompts/           # Phase prompts (read by manager)
    phase-1.md
    phase-2.md
    ...
  tests/             # Test sources
    run.sh           # Entry point; invoked by tester support process
    fixtures/        # Test data, expected outputs, etc.
  ref-impl.py        # Reference implementation (optional, for validation)
```

## `task.json` Format

```json
{
  "id": "nlm-eval",
  "name": "Natural Language Math Evaluator",
  "description": "Build a CLI tool that evaluates arithmetic expressions.",
  "phases": [
    {
      "id": "phase-1",
      "name": "Simple Binary Operations",
      "promptFile": "prompts/phase-1.md",
      "points": 10,
      "maxAttempts": 3
    },
    {
      "id": "phase-2",
      "name": "Chained Operations",
      "promptFile": "prompts/phase-2.md",
      "points": 20,
      "maxAttempts": 3
    }
  ],
  "tests": {
    "script": "tests/run.sh"
  },
  "scoring": {
    "penaltyPerAttempt": 2,
    "penaltyFloor": 0
  }
}
```

## Test Execution Contract

The tester support process:
1. Receives the path to `task.json` and the current phase ID
2. Sets `CAE_ARTIFACT_ROOT` to the `impl/` directory (agent workspace)
3. Sets `CAE_PHASE` to the current phase ID
4. Runs `tests/run.sh` **once** with the current phase ID
5. `run.sh` must exit 0 on success, non-zero on failure
6. Results are written by the tester to `test/results/latest.json`

**Regression testing is the designer's responsibility.** If phase 2 builds on phase 1, your `run.sh` should validate both when called with `CAE_PHASE=phase-2`. The framework does not automatically re-run prior phases.
## Suite Config

A suite references one or more benchmarks:

```json
{
  "name": "my-suite",
  "benchmarks": [
    "benchmarks/nlm-eval/task.json",
    "benchmarks/log-stats/task.json"
  ]
}
```

Paths are resolved relative to the suite config file.

## Run

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/my-suite/suite.json \
  --volume ./runs \
  --agent-cmd "python3 /path/to/agent.py"
```
## Dummy Benchmarks

Quick smoke tests for verifying the end-to-end loop:

| Benchmark | Purpose |
|-----------|---------|
| `dummy-smoke` | Always-passes sanity check |
| `dummy-retry` | Vague prompt → feedback → retry loop |
| `dummy-multi` | Two phases, second builds on first |
| `dummy-suite` | Combines all dummy benchmarks |

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/dummy-suite/suite.json \
  --volume /tmp/dummy-runs \
  --agent-template templates/pi
```
