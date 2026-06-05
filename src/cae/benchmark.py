"""Benchmark loading and validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Phase:
    id: str
    name: str
    prompt_file: Path
    max_attempts: int
    points: int
    max_time: float | None = None

    def read_prompt(self) -> str:
        """Return the contents of this phase's prompt file."""
        with open(self.prompt_file, encoding="utf-8") as f:
            return f.read()

    @classmethod
    def from_dict(cls, d: dict[str, Any], base_dir: Path) -> Phase:
        max_time_raw = d.get("maxTime")
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            prompt_file=base_dir / d["promptFile"],
            max_attempts=d.get("maxAttempts", 3),
            points=d.get("points", 0),
            max_time=float(max_time_raw) if max_time_raw is not None else None,
        )


@dataclass(frozen=True)
class Scoring:
    penalty_per_attempt: int
    penalty_floor: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Scoring:
        return cls(
            penalty_per_attempt=d.get("penaltyPerAttempt", 0),
            penalty_floor=d.get("penaltyFloor", 0),
        )


@dataclass(frozen=True)
class Benchmark:
    id: str
    name: str
    phases: list[Phase]
    tests_script: Path
    scoring: Scoring
    base_dir: Path

    @classmethod
    def load(cls, path: Path) -> Benchmark:
        base_dir = path.parent
        with open(path) as f:
            data = json.load(f)

        tests = data.get("tests", {})
        script = base_dir / tests.get("script", "tests/run.sh")

        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            phases=[Phase.from_dict(p, base_dir) for p in data.get("phases", [])],
            tests_script=script,
            scoring=Scoring.from_dict(data.get("scoring", {})),
            base_dir=base_dir,
        )

    def phase_by_id(self, phase_id: str) -> Phase | None:
        for p in self.phases:
            if p.id == phase_id:
                return p
        return None

    def next_phase(self, current_phase_id: str) -> Phase | None:
        for i, p in enumerate(self.phases):
            if p.id == current_phase_id and i + 1 < len(self.phases):
                return self.phases[i + 1]
        return None
