# Shared Volume Protocol

The manager and worker communicate through a **shared directory** (the *volume*).  The worker is a *dumb pipe*: it reads whatever plain-text prompt the manager writes, runs the agent to completion, and signals readiness.  All orchestration intelligence (phases, attempts, retries, scoring) lives in the manager.

## Philosophy

| Old protocol | Dumb-pipe protocol |
|---|---|
| Structured JSON (`task.json`, `feedback.json`) | Plain text (`prompt.md`) |
| Worker parsed phase/attempt state | Worker reads prompt, runs agent, sets `ready` |
| Manager wrote "advance / retry / exit" signals | Manager writes the **actual retry prompt text** |
| Worker decided what to do next | Manager decides, constructs prompt, writes it |

This eliminates race conditions (no identical-content rewrite), simplifies the worker, and makes the system easier to reason about.

## Directory Layout

```
volume/                     # benchmark run directory
  .cae/                     # protocol files
    prompt.md               ← manager writes, worker reads+deletes
    score.json              ← manager writes, worker ignores
    ready                   ← worker creates, manager clears
    results/
      latest.json           ← tester writes, manager reads
  impl/                     ← agent workspace (template copied here)
    agent/                  # adapter package
    output.txt              # agent artifacts
    ...
  test/                     ← tester scratch space
    results/
```

## Protocol Files

| File | Writer | Reader | Semantics |
|------|--------|--------|-----------|
| `.cae/prompt.md` | Manager | Worker | Plain-text prompt for the current turn. Worker **deletes** after reading to avoid re-reading stale content. |
| `.cae/ready` | Worker | Manager | Empty marker file. Worker creates it after agent signals completion. Manager removes it to grant the next turn. |
| `.cae/score.json` | Manager | — | External inspection / checkpoint. The worker never reads this. |
| `.cae/results/latest.json` | Tester | Manager | Structured test result (`TestResult`). |

## Lifecycle

```
Manager                              Worker
─────────────────────────────────────────────────────────
write prompt.md (phase 1)
spawn worker ──────────────────────▶  read prompt.md
                                      delete prompt.md
                                      run agent to completion
                                      set ready
wait for ready ◀────────────────────  wait for ready to clear
spawn tester
read results/latest.json
clear ready

[if retry]
write prompt.md (retry text) ─────▶  read prompt.md
                                      ... (same loop)

[if advance]
write prompt.md (next phase) ─────▶  read prompt.md
                                      ... (same loop)

[if done]
kill worker
```

### Prompt Content

The manager constructs **all** prompts:

- **Initial turn**: raw contents of the phase's `promptFile`.
- **Retry turn**: original prompt + separator + failure details + "Please fix the issues and try again."
- **Advance turn**: raw contents of the next phase's `promptFile`.

The worker never sees phase IDs, attempt counts, or scoring rules.

### Ready Handshake

1. Worker finishes agent turn → creates `.cae/ready`.
2. Manager sees `ready` → spawns **tester**. The tester calls `tests/run.sh` **exactly once** with `CAE_PHASE` set to the current phase. Designers decide what to test (regression is their responsibility).
3. Manager decides next action → **clears** `ready` → writes new `prompt.md`.
4. Worker sees `ready` gone → loops back to waiting for `prompt.md`.
If the manager never writes another prompt (benchmark ends), the worker waits indefinitely. The manager's `finally` block terminates the worker process.

### No "Exit" Marker

The old protocol had an `exit` feedback type. The new protocol has none. When the benchmark ends, the manager simply kills the worker process (`proc.terminate()` / `proc.kill()`).

## Worker Loop (Pseudocode)

```
function WORKER(volume, agent_client):
    while true:
        prompt = volume.read_prompt()
        while prompt is nil:
            sleep(1)
            prompt = volume.read_prompt()

        volume.delete_prompt()

        # Drive agent to completion (may need multiple turns)
        crash_retries = 0
        while crash_retries < MAX_CRASH_RETRIES:
            result = agent_client.run_turn(prompt, ...)
            if not result.success:
                crash_retries += 1
                if crash_retries >= MAX_CRASH_RETRIES:
                    return 1          # fatal: too many crashes
                prompt = CONTINUE_PROMPT
                continue
            crash_retries = 0
            if completion_marker_in(result.output):
                break
            prompt = CONTINUE_PROMPT

        volume.set_ready()

        while volume.is_ready():
            sleep(1)                  # wait for manager to clear
```

## Manager Loop (Pseudocode)

```
function RUN_GROUP(benchmark, volume, runtime):
    volume.write_prompt(benchmark.phases[0].read_prompt())
    worker_proc = runtime.spawn_worker(volume)
    deadline = now() + max_total_time

    for phase in benchmark.phases:
        for attempt in 1 .. phase.max_attempts:
            if not wait_for_ready(volume, worker_proc, deadline):
                return score          # timeout or worker died

            result = run_tester(volume, benchmark, phase, attempt)
            record_attempt(score, phase, attempt, result)
            volume.write_score(score)

            if result.passed:
                next = benchmark.next_phase(phase.id)
                volume.clear_ready()
                if next:
                    volume.write_prompt(next.read_prompt())
                else:
                    return score      # all phases passed
                break                 # out of attempt loop

            if attempt < phase.max_attempts:
                retry_prompt = build_retry_prompt(phase, attempt, result)
                volume.clear_ready()
                volume.write_prompt(retry_prompt)
            else:
                volume.clear_ready()
                return score          # exhausted attempts

    cleanup(worker_proc)
    return score
```

## Completion Marker

The worker appends the following instruction to every agent turn's system prompt:

> "When you are truly done with this task, output exactly `<CAE_PHASE_COMPLETE/>` as the final line of your response."

The worker checks the **last non-empty line** of the agent's output. If it equals `<CAE_PHASE_COMPLETE/>`, the turn is considered complete and the `ready` marker is set. Otherwise, the worker sends a `CONTINUE_PROMPT` ("Continue working on the task...") and waits for the marker.

## Crash Retry

If the agent client throws an exception or returns `success=false`, the worker increments a crash counter and retries with the continue prompt. After `MAX_CRASH_RETRIES` (3) consecutive crashes, the worker exits with code 1. A successful turn resets the crash counter.

## Comparison: Manager vs Worker Responsibilities

| Concern | Manager | Worker |
|---------|---------|--------|
| Phase sequencing | ✅ | ❌ |
| Attempt counting | ✅ | ❌ |
| Retry prompt construction | ✅ | ❌ |
| Scoring | ✅ | ❌ |
| Prompt file I/O | ✅ writes | ❌ reads+deletes |
| Ready marker I/O | ❌ clears | ✅ creates |
| Agent execution | ❌ | ✅ |
| Completion detection | ❌ | ✅ (marker check) |
| Crash retry | ❌ | ✅ |
