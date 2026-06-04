#!/usr/bin/env python3
"""E2E integration tests for the CAE framework."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PYTHONPATH = str(Path(__file__).parent.parent / "src")
BASE = Path(__file__).parent.parent


def run_suite(suite_path: str, agent_mode: str = "echo", agent_cmd: str | None = None) -> tuple[bool, list, str]:
    """Run a suite, return (ok, parsed_scores, stderr)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            sys.executable, "-m", "cae",
            "run",
            "--suite", suite_path,
            "--volume", tmpdir,
            "--agent-mode", agent_mode,
            "--max-time", "120",
        ]
        if agent_cmd:
            cmd += ["--agent-cmd", agent_cmd]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**dict(subprocess.os.environ), "PYTHONPATH": PYTHONPATH},
        )
        if result.returncode != 0:
            return False, [], result.stderr

        stdout = result.stdout.strip()
        last_bracket = stdout.rfind("[")
        if last_bracket == -1:
            return False, [], result.stderr
        try:
            scores = json.loads(stdout[last_bracket:])
        except json.JSONDecodeError:
            return False, [], result.stderr
        return True, scores, result.stderr


def check_invariants(run_dir: Path, suite_name: str) -> list[str]:
    """Check filesystem invariants; return list of errors."""
    errors: list[str] = []

    run_dirs = list(Path(run_dir).glob("*"))
    if not run_dirs:
        errors.append("No run directory created")
        return errors

    rd = run_dirs[0]
    summary = rd / "suite-summary.json"
    if not summary.exists():
        errors.append("suite-summary.json missing")

    for bench_id in ("test-pass", "test-retry", "test-fail"):
        bench_dir = rd / bench_id
        if not bench_dir.exists():
            errors.append(f"{bench_id}: benchmark dir missing")
            continue

        cae = bench_dir / ".cae"
        impl = bench_dir / "impl"
        test_dir = bench_dir / "test"

        if not cae.exists():
            errors.append(f"{bench_id}: .cae/ missing")
        if not impl.exists():
            errors.append(f"{bench_id}: impl/ missing")
        if not test_dir.exists():
            errors.append(f"{bench_id}: test/ missing")

        task = cae / "task.json"
        if not task.exists():
            errors.append(f"{bench_id}: .cae/task.json missing")

        score = cae / "score.json"
        if not score.exists():
            errors.append(f"{bench_id}: .cae/score.json missing")

        results = test_dir / "results" / "latest.json"
        if not results.exists():
            errors.append(f"{bench_id}: test/results/latest.json missing")

    return errors


def main() -> int:
    suite_path = str(BASE / "benchmarks" / "test-suite" / "suite.json")

    ok, scores, stderr = run_suite(suite_path, agent_mode="echo")
    if not ok:
        print("FAIL: Could not parse suite output")
        print(stderr)
        return 1

    all_passed = True

    # Verify each benchmark's score
    expected = {
        "test-pass": {"totalPoints": 10, "attempts": 1},
        "test-retry": {"totalPoints": 8, "attempts": 2},   # 10 - 2 penalty
        "test-fail": {"totalPoints": 0, "attempts": 3},
    }

    for score in scores:
        bench_id = score["benchmarkId"]
        exp = expected.get(bench_id)
        if not exp:
            print(f"FAIL: unexpected benchmark {bench_id}")
            all_passed = False
            continue

        actual_points = score["totalPoints"]
        actual_attempts = sum(p["attempts"] for p in score["phases"].values())

        if actual_points != exp["totalPoints"]:
            print(f"FAIL: {bench_id} expected {exp['totalPoints']} points, got {actual_points}")
            all_passed = False
        elif actual_attempts != exp["attempts"]:
            print(f"FAIL: {bench_id} expected {exp['attempts']} attempts, got {actual_attempts}")
            all_passed = False
        else:
            print(f"PASS: {bench_id} = {actual_points} points, {actual_attempts} attempts")

    # Verify suite total
    suite_total = sum(s["totalPoints"] for s in scores)
    if suite_total != 18:
        print(f"FAIL: suite total expected 18, got {suite_total}")
        all_passed = False
    else:
        print(f"PASS: suite total = {suite_total}")

    # Check filesystem invariants by re-running and inspecting directory
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable, "-m", "cae", "run",
                "--suite", suite_path,
                "--volume", tmpdir,
                "--agent-mode", "echo",
                "--max-time", "120",
            ],
            env={**os.environ, "PYTHONPATH": PYTHONPATH},
            capture_output=True,
            text=True,
        )
        errors = check_invariants(tmpdir, "test-suite")
        if errors:
            for e in errors:
                print(f"FAIL (invariant): {e}")
            all_passed = False
        else:
            print("PASS: all filesystem invariants hold")

    if all_passed:
        print("\nAll e2e tests passed!")
        return 0
    else:
        print("\nSome e2e tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
