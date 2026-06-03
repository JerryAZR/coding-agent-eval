"""User-facing CLI entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CAE - Coding Agent Evaluation Framework")
    subparsers = parser.add_subparsers(dest="command")

    # run command — evaluates a suite of benchmarks
    run_parser = subparsers.add_parser("run", help="Run a benchmark suite")
    run_parser.add_argument("--suite", required=True, help="Path to suite config JSON")
    run_parser.add_argument("--volume", default=".", help="Parent directory for benchmark runs")
    run_parser.add_argument("--mode", default="local", choices=["local", "container"])
    run_parser.add_argument("--agent-mode", default="pi", help="Agent harness mode (pi, echo, ...)")
    run_parser.add_argument("--max-time", type=float, default=3600)
    run_parser.add_argument("--agent-cmd", help="Custom agent command for local mode (space-separated)")

    args = parser.parse_args(argv)

    if args.command == "run":
        from .manager import run_suite
        from .runtime import runtime_for_mode
        from .suite import SuiteConfig

        suite = SuiteConfig.load(Path(args.suite))
        benchmarks = suite.load_benchmarks()

        parent = Path(args.volume)
        parent.mkdir(parents=True, exist_ok=True)

        runtime = runtime_for_mode(args.mode)
        agent_cmd = args.agent_cmd.split() if args.agent_cmd else None
        scores = run_suite(
            benchmarks=benchmarks,
            base_volume_path=parent,
            suite_name=suite.name,
            runtime=runtime,
            max_total_time=args.max_time,
            agent_cmd=agent_cmd,
            agent_mode=args.agent_mode,
        )
        print(json.dumps([s.to_dict() for s in scores], indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
