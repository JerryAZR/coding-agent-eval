"""Manager orchestration logic.

Hierarchy (smallest → largest):

1. ``run_single_attempt`` — evaluate **one attempt** of one phase.
2. ``run_single_step`` — evaluate **one phase** (all attempts, with retry loop).
3. ``run_group`` — evaluate **one benchmark** (multi-phase).  Runs until all
   phases pass or one phase exhausts its attempts.
4. ``run_suite`` — evaluate **multiple benchmarks** sequentially.

The manager is agnostic to local vs container execution — that is handled by
the ``Runtime`` abstraction in :mod:`cae.runtime`.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .benchmark import Benchmark, Phase
from .protocol import Volume, Score, TestResult
from .runtime import Runtime
from .scoring import ScoringRules, compute_phase_score
from .template import apply_template


def _init_score(benchmark: Benchmark) -> Score:
    """Create a fresh Score for a benchmark run."""
    return Score(
        benchmark_id=benchmark.id,
        total_points=0,
        phases={},
    )


def _make_run_dir(parent: Path, suite_name: str) -> Path:
    """Create a timestamped run directory under *parent*.

    Returns the path to the newly created directory.
    """
    ts = datetime.now().isoformat().replace(":", "-")
    run_dir = parent / f"{ts}_{suite_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_suite_summary(run_dir: Path, suite_name: str, scores: list[Score]) -> None:
    """Write ``suite-summary.json`` at the root of a benchmark run."""
    summary = {
        "suite_name": suite_name,
        "timestamp": datetime.now().isoformat(),
        "benchmarks": [score.to_dict() for score in scores],
        "suite_total": sum(score.total_points for score in scores),
    }
    with open(run_dir / "suite-summary.json", "w") as f:
        json.dump(summary, f, indent=2)


def _wait_for_ready(
    volume: Volume,
    worker_proc: subprocess.Popen | None,
    deadline: float,
) -> bool:
    """Block until the worker signals ready, dies, or the deadline hits.

    Returns ``True`` when the ready marker is present, ``False`` when the
    worker exited early or the deadline was reached.
    """
    while not volume.is_ready():
        if time.time() > deadline:
            print("TIMEOUT: deadline exceeded")
            return False
        if worker_proc and worker_proc.poll() is not None:
            print("Worker exited early")
            return False
        time.sleep(1)
    return True


def _run_tester(
    volume: Volume,
    benchmark: Benchmark,
    phase: Phase,
    attempt: int,
    runtime: Runtime,
) -> TestResult:
    """Spawn the tester and return the parsed result."""
    print(f"Evaluating {phase.id} attempt {attempt}...")

    runtime.spawn_tester(volume, benchmark, phase.id)

    result = volume.read_result()
    if result is None:
        result = TestResult(
            phase_id=phase.id,
            passed=False,
            details="No result file produced by tester",
            exit_code=-1,
        )

    print(f"  Result: {'PASS' if result.passed else 'FAIL'}")
    if not result.passed:
        print(f"  Details:\n{result.details}")

    return result


def _record_attempt(
    score: Score,
    phase: Phase,
    attempt: int,
    result: TestResult,
    rules: ScoringRules,
) -> None:
    """Update *score* in-place with the outcome of one attempt."""
    phase_score = score.phases.get(phase.id, {
        "points": 0,
        "attempts": 0,
        "best": False,
    })
    phase_score["attempts"] = attempt

    if result.passed:
        earned = compute_phase_score(
            points_available=phase.points,
            attempt=attempt,
            rules=rules,
        )
        phase_score["points"] = earned
        phase_score["best"] = True
        score.total_points += earned
        print(f"  Earned {earned}/{phase.points} points")

    score.phases[phase.id] = phase_score


def _build_retry_prompt(original_prompt: str, attempt: int, max_attempts: int, details: str) -> str:
    """Construct the prompt for a retry attempt."""
    return (
        f"{original_prompt}\n\n"
        f"---\n\n"
        f"Tests failed (attempt {attempt}/{max_attempts}):\n"
        f"{details}\n\n"
        "Please fix the issues and try again."
    )


def run_single_attempt(
    volume: Volume,
    benchmark: Benchmark,
    phase: Phase,
    attempt: int,
    worker_proc: subprocess.Popen,
    deadline: float,
    runtime: Runtime,
) -> TestResult | None:
    """Evaluate one attempt of one phase.

    Waits for the worker's ``ready`` marker, spawns the tester, and returns
    the parsed result.  Returns ``None`` if the worker exited or the deadline
    was reached.
    """
    if not _wait_for_ready(volume, worker_proc, deadline):
        return None
    return _run_tester(volume, benchmark, phase, attempt, runtime)


def run_single_step(
    volume: Volume,
    benchmark: Benchmark,
    phase: Phase,
    worker_proc: subprocess.Popen,
    deadline: float,
    rules: ScoringRules,
    score: Score,
    runtime: Runtime,
) -> tuple[bool, int, str] | None:
    """Evaluate one phase (all attempts).

    Runs the retry loop: up to ``phase.max_attempts`` attempts, writing
    retry prompts between failures.  Returns ``(passed, final_attempt,
    details)`` or ``None`` if the worker died or the deadline was reached.
    """
    original_prompt = phase.read_prompt()

    phase_deadline = time.time() + phase.max_time if phase.max_time else float('inf')

    for attempt in range(1, phase.max_attempts + 1):
        effective_deadline = min(deadline, phase_deadline)
        result = run_single_attempt(
            volume, benchmark, phase, attempt, worker_proc, effective_deadline, runtime
        )
        if result is None:
            return None  # worker died or global timeout

        _record_attempt(score, phase, attempt, result, rules)
        volume.write_score(score)

        if result.passed:
            return True, attempt, result.details

        if attempt < phase.max_attempts:
            retry_prompt = _build_retry_prompt(
                original_prompt, attempt, phase.max_attempts, result.details
            )
            volume.clear_ready()
            volume.write_prompt(retry_prompt)

    # Exhausted all attempts
    assert result is not None
    return False, phase.max_attempts, result.details


def run_group(
    benchmark: Benchmark,
    bench_dir: Path,
    runtime: Runtime,
    max_total_time: float = 3600,
    agent_cmd: list[str] | None = None,
    template_dir: Path | str | None = None,
) -> Score:
    """Run a single benchmark (one task group) to completion or first failure.

    The group is a sequence of phases.  Each phase gets up to
    ``max_attempts`` tries.  If all attempts of a phase fail, the group
    ends immediately.

    Directory layout under *bench_dir*::

        bench_dir/
          .cae/     protocol files (prompt.md, score.json, ready)
          impl/     agent workspace (read-write for worker, read-only for tester)
          test/     tester output (read-write for tester only)

    The worker process is spawned once at the start of the group and
    terminated when the group ends.
    """
    bench_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = bench_dir / "impl"
    test_dir = bench_dir / "test"
    impl_dir.mkdir(exist_ok=True)
    test_dir.mkdir(exist_ok=True)

    if template_dir is not None:
        apply_template(impl_dir, Path(template_dir))

    volume = Volume(bench_dir, results_dir=test_dir / "results")
    volume.ensure_dirs()

    score = _init_score(benchmark)
    volume.write_score(score)

    rules = ScoringRules(
        penalty_per_attempt=benchmark.scoring.penalty_per_attempt,
        penalty_floor=benchmark.scoring.penalty_floor,
    )

    start_time = time.time()
    deadline = start_time + max_total_time
    worker_proc = None

    try:
        # Write the first prompt before spawning the worker to avoid a race.
        volume.write_prompt(benchmark.phases[0].read_prompt())
        worker_proc = runtime.spawn_worker(volume, agent_cmd)

        for phase in benchmark.phases:
            outcome = run_single_step(
                volume, benchmark, phase, worker_proc, deadline, rules, score, runtime
            )
            if outcome is None:
                return score  # worker died or global timeout

            passed, attempt, details = outcome

            if passed:
                next_phase = benchmark.next_phase(phase.id)
                if next_phase:
                    volume.clear_ready()
                    volume.write_prompt(next_phase.read_prompt())
                else:
                    volume.clear_ready()
                    print("All tests passed. Group complete.")
            else:
                volume.clear_ready()
                print(f"Failed after {attempt} attempts.\n{details}")
                return score  # group ends on exhausted failure

        return score

    finally:
        if worker_proc and worker_proc.poll() is None:
            worker_proc.terminate()
            try:
                worker_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker_proc.kill()


def run_suite(
    benchmarks: list[Benchmark],
    base_volume_path: Path,
    suite_name: str,
    runtime: Runtime,
    max_total_time: float = 3600,
    agent_cmd: list[str] | None = None,
    template_dir: Path | str | None = None,
) -> list[Score]:
    """Run multiple benchmarks (groups) sequentially.

    Each benchmark gets its own fresh volume under a timestamped run
    directory.  The structure is::

        base_volume_path/
          TIMESTAMP_suite_name/
            benchmark_id/
              impl/     ← agent workspace + .cae/ protocol
              test/     ← test outputs (reserved)
            suite-summary.json

    The agent starts from scratch for every group.
    """
    run_dir = _make_run_dir(base_volume_path, suite_name)
    scores: list[Score] = []

    for benchmark in benchmarks:
        bench_dir = run_dir / benchmark.id
        score = run_group(
            benchmark=benchmark,
            bench_dir=bench_dir,
            runtime=runtime,
            max_total_time=max_total_time,
            agent_cmd=agent_cmd,
            template_dir=template_dir,
        )
        scores.append(score)
        print(f"\n=== {benchmark.id}: {score.total_points} points ===")

    _write_suite_summary(run_dir, suite_name, scores)
    return scores
