"""Definitions for ED livestock scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from goblin_spatial.dynamics.baseline import SUPPORTED_SCENARIO_BASE_YEARS


class AllocationRule(str, Enum):
    PRORATA = "PRORATA"
    SCORE_WEIGHTED = "SCORE_WEIGHTED"


@dataclass(frozen=True)
class ScenarioDefinition:
    """National livestock reductions to distribute across EDs."""

    name: str
    baseline_year: int
    target_year: int
    dairy_reduction: float = 0.0
    suckler_reduction: float = 0.0
    sheep_reduction: float = 0.0
    allocation_rule: AllocationRule = AllocationRule.PRORATA
    score_column: str | None = None

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("scenario name cannot be empty")
        if self.baseline_year not in SUPPORTED_SCENARIO_BASE_YEARS:
            raise ValueError(
                f"baseline_year must be one of {SUPPORTED_SCENARIO_BASE_YEARS}"
            )
        if self.target_year < self.baseline_year:
            raise ValueError("target_year cannot precede baseline_year")
        for label, value in (
            ("dairy_reduction", self.dairy_reduction),
            ("suckler_reduction", self.suckler_reduction),
            ("sheep_reduction", self.sheep_reduction),
        ):
            if float(value) < 0.0 or float(value) > 1.0:
                raise ValueError(f"{label} must lie between 0 and 1")
        if self.allocation_rule == AllocationRule.SCORE_WEIGHTED and not self.score_column:
            raise ValueError("SCORE_WEIGHTED requires score_column")
