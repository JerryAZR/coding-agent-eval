# Manager Pseudocode

## Invariants

- **Tests never enter the worker volume.**  The tester receives the benchmark
  path and runs with `cwd` set to the benchmark's tests directory.  Relative
  fixture paths resolve; the agent cannot see tests or fixtures.
- **Worker sees only the current phase.**  `task.json` contains exactly one
  prompt — the phase currently in flight.
- **Feedback drives the worker.**  The worker polls `feedback.json`.  When it
  changes the worker knows: (a) retry same task, (b) advance to next task, or
  (c) benchmark is over — exit.

## Architecture

```
┌─────────────┐     spawn      ┌──────────┐
│   Manager   │───────────────▶│  Worker  │
│             │                │ (agent)  │
│  state      │◀── feedback───│          │
│  machine    │                └──────────┘
│             │
│   ┌─────────┴─────────┐
│   │  ready marker     │
│   └───────────────────┘
│             │
│   ┌─────────┴─────────┐
│   │  Tester (isolated)│  ←─ cwd = benchmark/tests/
│   │  read-only view   │      reads agent artifacts from volume
│   │  of volume        │      writes results/latest.json
│   └───────────────────┘
└─────────────┘
```

## State Machine (single benchmark)

```
function RUN_MANAGER(benchmark, volume_path, mode, max_time, agent_cmd):
    volume = Volume(volume_path)
    volume.ensure_dirs()

    score = init_score(benchmark)
    volume.write_score(score)

    phase  = benchmark.phases[0]
    attempt = 1
    setup_volume(volume, benchmark, phase, attempt)

    worker_proc = spawn_worker(mode, volume, agent_cmd)
    deadline    = now() + max_time

    loop:
        if not wait_for_ready(volume, worker_proc, deadline):
            break                                   # timeout or worker died

        result = run_tester(volume, benchmark, phase)
        record_attempt(score, phase, attempt, result)
        volume.write_score(score)

        next_phase = benchmark.next_phase(phase.id)

        if result.passed and next_phase exists:
            # ── ADVANCE ──
            write_feedback(volume,
                phase_complete=true,
                next_phase_id=next_phase.id,
                message="All tests passed. Moving to next phase.")
            volume.clear_ready()
            phase   = next_phase
            attempt = 1
            setup_volume(volume, benchmark, phase, attempt)
            continue

        if result.passed and next_phase is nil:
            # ── DONE (success) ──
            write_feedback(volume,
                phase_complete=true,
                next_phase_id=nil,
                message="All tests passed. Benchmark complete.")
            break

        if not result.passed and attempt < phase.max_attempts:
            # ── RETRY ──
            write_feedback(volume,
                phase_complete=false,
                next_phase_id=nil,
                message=result.details)
            volume.clear_ready()
            attempt += 1
            update_task_attempt(volume, attempt)
            continue

        if not result.passed and attempt >= phase.max_attempts:
            # ── DONE (failure) ──
            write_feedback(volume,
                phase_complete=true,
                next_phase_id=nil,
                message="Failed after {attempt} attempts.\n{result.details}")
            break

    cleanup(worker_proc)
    return score
```

## Sub-procedures

### `wait_for_ready(volume, worker_proc, deadline)`

```
while not volume.is_ready():
    if now() > deadline:
        print "TIMEOUT"
        return false
    if worker_proc is dead:
        print "Worker exited early"
        return false
    sleep(1)
return true
```

### `run_tester(volume, benchmark, phase)`

```
print "Evaluating {phase.id} attempt {attempt}..."

# Spawn tester with cwd at benchmark/tests/ so relative fixtures resolve.
# Tester receives --volume (for reading agent artifacts)
#               --task   (for benchmark spec)
#               --phase  (phase id to evaluate)
spawn_tester(mode, volume, benchmark, phase.id)

result = volume.read_result()
if result is nil:
    result = synthetic_failure("No result file produced by tester")

print result summary
return result
```

### `record_attempt(score, phase, attempt, result)`

```
phase_score = score.phases[phase.id] or {points:0, attempts:0, best:false}
phase_score.attempts = attempt

if result.passed:
    earned = compute_phase_score(
        points_available = phase.points,
        attempt          = attempt,
        penalty_per_attempt = benchmark.scoring.penalty_per_attempt,
        penalty_floor       = benchmark.scoring.penalty_floor)
    phase_score.points = earned
    phase_score.best   = true
    score.total_points += earned

score.phases[phase.id] = phase_score
```

## Multi-Benchmark (task-group) Orchestration

A *task group* = one benchmark with N phases.

```
function RUN_BENCHMARKS(benchmarks, volume_factory, mode, max_time, agent_cmd_factory):
    for benchmark in benchmarks:
        volume_path = volume_factory(benchmark.id)
        agent_cmd   = agent_cmd_factory(benchmark.id)

        score = run_manager(
            benchmark        = benchmark,
            volume_path      = volume_path,
            mode             = mode,
            max_total_time   = max_time,
            agent_cmd        = agent_cmd)

        persist_score(benchmark.id, score)
        print "Benchmark {benchmark.id}: {score.total_points} points"

    return aggregate_scores()
```

Each benchmark gets its own **fresh volume**.  The agent starts from scratch for
every benchmark.  The manager is single-benchmark; the orchestration loop is a
thin wrapper above it.

## Volume Layout (agent view)

```
volume/
  .cae/               ← hidden from agent (convention, not enforcement)
    task.json          ← manager writes, worker reads
    feedback.json      ← manager writes, worker reads
    score.json         ← manager writes, worker reads
    ready              ← worker creates, manager consumes
    results/
      latest.json      ← tester writes, manager reads
  # everything else is the agent's workspace
  # agent reads task.json, writes artifacts here, reads feedback.json
```

Note: **Tests and fixtures live in the benchmark package, not in the volume.**
```
benchmarks/
  nlm-eval/
    task.json
    prompts/
    tests/
      run.sh           ← tester executes this
      fixtures/        ← tester reads these (relative to tests/)
```

## Worker Loop (for reference)

```
function WORKER(volume, agent_cmd):
    while true:
        task = volume.read_task()
        if task is nil:
            sleep(1)
            continue

        # Run agent on the current task
        agent_result = run_agent(task.prompt, agent_cmd, cwd=volume.root)

        # Signal manager that work is ready for evaluation
        volume.set_ready()

        # Wait for manager feedback
        feedback = volume.read_feedback()
        while feedback is nil or feedback is stale:
            feedback = volume.read_feedback()
            sleep(1)

        if feedback.phase_complete:
            if feedback.next_phase_id is nil:
                break                           # benchmark done
            else:
                continue                        # new task.json already written
        else:
            continue                            # retry: task.json already updated
```

## Tester Flow (for reference)

```
function TESTER(volume_path, task_path, phase_id):
    volume    = Volume(volume_path)
    benchmark = Benchmark.load(task_path)

    # Current phase
    result = run_test_script(benchmark.tests_script, phase_id, volume.root)

    # Regression: all prior phases must still pass
    for prior_phase in benchmark.phases before phase_id:
        reg = run_test_script(benchmark.tests_script, prior_phase.id, volume.root)
        if not reg.passed:
            result.passed  = false
            result.details += "\n--- REGRESSION {prior_phase.id} ---\n" + reg.details
            break

    volume.write_result(result)
    return 0 if result.passed else 1
```
