"""Protocol definitions for .cae/ shared volume communication."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VOLUME_DIR = ".cae"
PROMPT_FILE = "prompt.md"
SCORE_FILE = "score.json"
READY_MARKER = "ready"
RESULTS_DIR = "results"
LATEST_RESULT = "latest.json"



@dataclass
class TestResult:
    """What the tester writes."""

    phase_id: str
    passed: bool
    details: str
    exit_code: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "phaseId": self.phase_id,
            "passed": self.passed,
            "details": self.details,
            "exitCode": self.exit_code,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TestResult:
        return cls(
            phase_id=d["phaseId"],
            passed=d["passed"],
            details=d.get("details", ""),
            exit_code=d.get("exitCode", 1),
        )


@dataclass
class Score:
    """Cumulative scoring state."""

    benchmark_id: str
    total_points: int
    phases: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmarkId": self.benchmark_id,
            "totalPoints": self.total_points,
            "phases": self.phases,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Score:
        return cls(
            benchmark_id=d["benchmarkId"],
            total_points=d.get("totalPoints", 0),
            phases=d.get("phases", {}),
        )


class Volume:
    """Accessor for the shared volume protocol files.

    By default results are stored under ``.cae/results/`` inside *root*.
    Pass *results_dir* to redirect result I/O elsewhere (e.g. a separate
    ``test/`` directory so the agent cannot read tester output).
    """

    def __init__(self, root: Path | str, results_dir: Path | str | None = None):
        self.root: Path = Path(root)
        self.cae = self.root / VOLUME_DIR
        self.results = Path(results_dir) if results_dir else self.cae / RESULTS_DIR

    def ensure_dirs(self) -> None:
        self.cae.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Write JSON atomically via a temp file + rename."""
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.rename(path)

    def write_prompt(self, prompt: str) -> None:
        """Write the prompt text atomically."""
        path = self.cae / PROMPT_FILE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(prompt, encoding="utf-8")
        tmp.rename(path)

    def read_prompt(self) -> str | None:
        """Read the prompt text if present."""
        path = self.cae / PROMPT_FILE
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def delete_prompt(self) -> None:
        """Remove the prompt file."""
        path = self.cae / PROMPT_FILE
        if path.exists():
            path.unlink()
    def write_score(self, score: Score) -> None:
        self._atomic_write_json(self.cae / SCORE_FILE, score.to_dict())
    def read_score(self) -> Score | None:
        path = self.cae / SCORE_FILE
        if not path.exists():
            return None
        with open(path) as f:
            return Score.from_dict(json.load(f))

    def write_result(self, result: TestResult) -> None:
        self._atomic_write_json(self.results / LATEST_RESULT, result.to_dict())
    def read_result(self) -> TestResult | None:
        path = self.results / LATEST_RESULT
        if not path.exists():
            return None
        with open(path) as f:
            return TestResult.from_dict(json.load(f))

    def is_ready(self) -> bool:
        return (self.cae / READY_MARKER).exists()

    def set_ready(self) -> None:
        (self.cae / READY_MARKER).touch()

    def clear_ready(self) -> None:
        path = self.cae / READY_MARKER
        if path.exists():
            path.unlink()
