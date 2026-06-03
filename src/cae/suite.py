"""Suite configuration loading."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .benchmark import Benchmark


@dataclass
class SuiteConfig:
    """A suite is a named collection of benchmarks to run sequentially."""

    name: str
    benchmark_paths: list[Path]

    def load_benchmarks(self) -> list[Benchmark]:
        """Load all benchmarks specified by this suite."""
        return [Benchmark.load(p) for p in self.benchmark_paths]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SuiteConfig:
        return cls(
            name=d["name"],
            benchmark_paths=[Path(p) for p in d["benchmarks"]],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "benchmarks": [str(p) for p in self.benchmark_paths],
        }

    @classmethod
    def load(cls, path: Path) -> SuiteConfig:
        path = Path(path)
        with open(path) as f:
            obj = cls.from_dict(json.load(f))
        base = path.parent
        obj.benchmark_paths = [p if p.is_absolute() else base / p for p in obj.benchmark_paths]
        return obj

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
