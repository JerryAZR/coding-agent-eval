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
  ref/               # Reference implementation (optional, for validation)
```

## `task.json` Format

```json
{
  "id": "cinterp",
  "name": "C Interpreter",
  "description": "Build an interpreter for a restricted subset of C.",
  "phases": [
    {
      "id": "phase-1",
      "name": "Expressions and Control Flow",
      "promptFile": "prompts/phase-1.md",
      "points": 10,
      "maxAttempts": 3,
      "maxTime": 900
    },
    {
      "id": "phase-2",
      "name": "User-Defined Functions",
      "promptFile": "prompts/phase-2.md",
      "points": 20,
      "maxAttempts": 3,
      "maxTime": 900
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
    "cinterp/task.json"
  ]
}
```

Paths are resolved relative to the suite config file.

## Run

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/my-suite/suite.json \
  --volume ./runs \
  --agent-template templates/pi
```
## Dummy Benchmarks

Quick smoke tests for verifying the end-to-end loop live in `dummies/`:

| Benchmark | Purpose |
|-----------|---------|
| `dummy-smoke` | Always-passes sanity check |
| `dummy-retry` | Vague prompt → feedback → retry loop |
| `dummy-multi` | Two phases, second builds on first |
| `dummy-suite` | Combines all dummy benchmarks |

```bash
PYTHONPATH=src python -m cae run \
  --suite benchmarks/dummies/dummy-suite/suite.json \
  --volume /tmp/dummy-runs \
  --agent-template templates/pi
```

## Benchmark Roster

### `cinterp` — C Interpreter
Build an interpreter for a restricted subset of C, extended incrementally across phases.

| Phase | Topic | Status |
|-------|-------|--------|
| 1 | Expressions and Control Flow | ✅ Implemented |
| 2 | User-Defined Functions | ✅ Implemented |
| 3 | Arrays and Pointers | ✅ Implemented |
| 4 | Function Pointers | ✅ Implemented |

**Future growth directions** (not yet implemented):
- **Structs**: Composite types, field offsets, nested structs, pointer-to-struct (`p->x`)
- **`malloc`/`free`**: Heap allocation, use-after-free detection, memory leaks
- **`char` and strings**: Character literals, string constants, `print_str()`, null termination
- **`goto` and labels**: Unstructured control flow, basic blocks
- **C++ classes**: `class`, methods, implicit `this`, constructors
- **C++ inheritance**: Base classes, `virtual`, vtables, dynamic dispatch
- **C++ templates**: Parametric polymorphism, compile-time instantiation

### `httpsrv` — HTTP Server *(in design)*
Build an HTTP server incrementally, from a basic responder to a full-featured web server.

| Phase | Topic | Status |
|-------|-------|--------|
| 1 | Basic GET | 📝 In design |
| 2 | Routing and Query Parameters | 📝 In design |
| 3 | POST and JSON | 📝 In design |
| 4 | Static File Serving | 📝 In design |

## Ideas for Additional Benchmarks

- **Regex engine**: NFA/DFA construction, matching, capture groups
- **JSON parser + query tool**: Recursive descent parsing, path queries, filtering
- **Markdown renderer**: Block/inline parsing, HTML generation
- **Shell**: Command parsing, process spawning, pipes, redirection
- **Key-value store**: Persistence, indexing, transactions
- **Spreadsheet engine**: Formula parsing, dependency graph, recalculation
- **Build system**: Dependency graphs, incremental builds, file watching
