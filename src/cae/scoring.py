"""Pure scoring functions, extracted for testability."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringRules:
    penalty_per_attempt: int
    penalty_floor: int


def compute_phase_score(
    points_available: int,
    attempt: int,
    rules: ScoringRules,
) -> int:
    """Return earned points for a phase given the attempt number.

    Attempt 1 = full points. Each subsequent attempt subtracts penalty,
    floored at penalty_floor.
    """
    if attempt <= 0:
        return rules.penalty_floor
    penalty = min(
        (attempt - 1) * rules.penalty_per_attempt,
        points_available - rules.penalty_floor,
    )
    return max(points_available - penalty, rules.penalty_floor)
