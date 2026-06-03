"""Protocol definitions for .cae/ shared volume communication."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VOLUME_DIR = ".cae"
TASK_FILE = "task.json"
FEEDBACK_FILE = "feedback.json"
SCORE_FILE = "score.json"
READY_MARKER = "ready"
RESULTS_DIR = "results"
LATEST_RESULT = "latest.json"


@dataclass
class TaskState:
    """What the manager writes for the current phase."""

    benchmark_id: str
    phase_id: str
    attempt: int
    prompt: str
    max_attempts: int
    points: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmarkId": self.benchmark_id,
            "phaseId": self.phase_id,
            "attempt": self.attempt,
            "prompt": self.prompt,
            "maxAttempts": self.max_attempts,
            "points": self.points,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskState:
        return cls(
            benchmark_id=d["benchmarkId"],
            phase_id=d["phaseId"],
            attempt=d["attempt"],
            prompt=d["prompt"],
            max_attempts=d["maxAttempts"],
            points=d["points"],
        )


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
class Feedback:
    """What the manager writes after evaluation."""

    phase_id: str
    attempt: int
    passed: bool
    message: str
    phase_complete: bool
    next_phase_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "phaseId": self.phase_id,
            "attempt": self.attempt,
            "passed": self.passed,
            "message": self.message,
            "phaseComplete": self.phase_complete,
            "nextPhaseId": self.next_phase_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Feedback:
        return cls(
            phase_id=d["phaseId"],
            attempt=d["attempt"],
            passed=d["passed"],
            message=d.get("message", ""),
            phase_complete=d.get("phaseComplete", False),
            next_phase_id=d.get("nextPhaseId"),
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
        self.root = Path(root)
        self.cae = self.root / VOLUME_DIR
        self.results = Path(results_dir) if results_dir else self.cae / RESULTS_DIR

    def ensure_dirs(self) -> None:
        self.cae.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    def write_task(self, task: TaskState) -> None:
        path = self.cae / TASK_FILE
        with open(path, "w") as f:
            json.dump(task.to_dict(), f, indent=2)

    def read_task(self) -> TaskState | None:
        path = self.cae / TASK_FILE
        if not path.exists():
            return None
        with open(path) as f:
            return TaskState.from_dict(json.load(f))

    def write_feedback(self, feedback: Feedback) -> None:
        path = self.cae / FEEDBACK_FILE
        with open(path, "w") as f:
            json.dump(feedback.to_dict(), f, indent=2)

    def read_feedback(self) -> Feedback | None:
        path = self.cae / FEEDBACK_FILE
        if not path.exists():
            return None
        with open(path) as f:
            return Feedback.from_dict(json.load(f))

    def write_score(self, score: Score) -> None:
        path = self.cae / SCORE_FILE
        with open(path, "w") as f:
            json.dump(score.to_dict(), f, indent=2)

    def read_score(self) -> Score | None:
        path = self.cae / SCORE_FILE
        if not path.exists():
            return None
        with open(path) as f:
            return Score.from_dict(json.load(f))

    def write_result(self, result: TestResult) -> None:
        path = self.results / LATEST_RESULT
        with open(path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

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
