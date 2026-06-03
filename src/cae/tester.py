"""Tester support process.

Runs inside the tester container. Receives a read-only view of the agent's
implementation directory plus a writable test-results directory. Executes the
test script for the current phase and writes results.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .benchmark import Benchmark
from .protocol import Volume, TestResult


def run_tests(impl_dir: Path, benchmark: Benchmark, phase_id: str) -> TestResult:
    """Run the test script for the given phase."""
    env = {
        **dict(subprocess.os.environ),
        "CAE_ARTIFACT_ROOT": str(impl_dir),
        "CAE_PHASE": phase_id,
    }

    try:
        result = subprocess.run(
            [str(benchmark.tests_script)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return TestResult(
            phase_id=phase_id,
            passed=False,
            details="Test script timed out after 60s",
            exit_code=-1,
        )
    except Exception as e:
        return TestResult(
            phase_id=phase_id,
            passed=False,
            details=f"Failed to run test script: {e}",
            exit_code=-1,
        )

    passed = result.returncode == 0
    details = result.stdout
    if result.stderr:
        details += "\n--- stderr ---\n" + result.stderr

    return TestResult(
        phase_id=phase_id,
        passed=passed,
        details=details.strip(),
        exit_code=result.returncode,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CAE tester support process")
    parser.add_argument("--volume", required=True, help="Run directory (parent of .cae/, impl/, test/)")
    parser.add_argument("--task", required=True, help="Path to task.json (benchmark spec)")
    parser.add_argument("--phase", required=True, help="Phase ID to evaluate")
    args = parser.parse_args(argv)

    run_dir = Path(args.volume)
    impl_dir = run_dir / "impl"
    test_dir = run_dir / "test"
    volume = Volume(run_dir, results_dir=test_dir / "results")
    volume.ensure_dirs()
    benchmark = Benchmark.load(Path(args.task))

    # Run tests for current phase
    test_result = run_tests(impl_dir, benchmark, args.phase)
    volume.write_result(test_result)

    # Also run regression tests for all prior phases
    for phase in benchmark.phases:
        if phase.id == args.phase:
            break
        reg_result = run_tests(impl_dir, benchmark, phase.id)
        if not reg_result.passed:
            test_result.passed = False
            test_result.details += f"\n--- REGRESSION {phase.id} ---\n{reg_result.details}"
            volume.write_result(test_result)
            return 1

    volume.write_result(test_result)
    return 0 if test_result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
