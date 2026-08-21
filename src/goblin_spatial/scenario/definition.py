"""Definitions for ED livestock-reduction scenarios.

A scenario never rebuilds the ED livestock population from scratch. GOBLIN (or
another national pathway source) supplies the national reduction or endpoint;
GOBLIN-Spatial allocates the implied change from the selected 2020 or 2025 ED
baseline.

The four principal SC1 policies are preserved explicitly. Additional rules are
retained for experimental/sensitivity work and are not substituted silently for
the principal study design.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from goblin_spatial.dynamics.baseline import SUPPORTED_SCENARIO_BASE_YEARS


class AllocationRule(str, Enum):
    """Alternative rules for deciding where a fixed national change lands."""

    # Validated principal SC1 policy set.
    PRORATA = "PRORATA"
    DAIRY_PROTECTION = "DAIRY_PROTECTION"
    ECONOMIC_CAPACITY_PROTECTION = "ECONOMIC_CAPACITY_PROTECTION"
    SOCIAL_VULNERABILITY_PROTECTION = "SOCIAL_VULNERABILITY_PROTECTION"

    # Experimental/sensitivity rules retained for backwards compatibility.
    RANDOMISED = "RANDOMISED"
    PRODUCTIVITY_PROTECTION = "PRODUCTIVITY_PROTECTION"
    VULNERABILITY_PROTECTION = "VULNERABILITY_PROTECTION"
    HYBRID_BALANCED = "HYBRID_BALANCED"
    SCORE_WEIGHTED = "SCORE_WEIGHTED"


@dataclass(frozen=True)
class ScenarioDefinition:
    """Generic fractional livestock-reduction scenario definition.

    This class supports the older generic reduction engine. The principal
    sourced-endpoint study uses category-consistent absolute endpoints through
    ``principal_allocation`` and therefore does not reinterpret these generic
    rules as its scientific allocation design.
    """

    name: str
    baseline_year: int
    target_year: int
    dairy_reduction: float = 0.0
    suckler_reduction: float = 0.0
    sheep_reduction: float = 0.0
    allocation_rule: AllocationRule = AllocationRule.PRORATA
    random_seed: int = 42

    score_column: str | None = None
    productivity_score_column: str | None = None
    vulnerability_score_column: str | None = None

    protection_strength: float = 0.8
    hybrid_weights: tuple[float, float, float, float] = (0.40, 0.25, 0.20, 0.15)

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

        if not isinstance(self.random_seed, int):
            raise ValueError("random_seed must be an integer")

        if not 0.0 <= float(self.protection_strength) < 1.0:
            raise ValueError("protection_strength must lie in [0, 1)")

        if self.allocation_rule == AllocationRule.SCORE_WEIGHTED and not self.score_column:
            raise ValueError("SCORE_WEIGHTED requires score_column")
        if (
            self.allocation_rule == AllocationRule.PRODUCTIVITY_PROTECTION
            and not self.productivity_score_column
        ):
            raise ValueError("PRODUCTIVITY_PROTECTION requires productivity_score_column")
        if (
            self.allocation_rule == AllocationRule.VULNERABILITY_PROTECTION
            and not self.vulnerability_score_column
        ):
            raise ValueError("VULNERABILITY_PROTECTION requires vulnerability_score_column")
        if self.allocation_rule == AllocationRule.HYBRID_BALANCED:
            if not self.productivity_score_column or not self.vulnerability_score_column:
                raise ValueError(
                    "HYBRID_BALANCED requires productivity_score_column and "
                    "vulnerability_score_column"
                )

        weights = tuple(float(x) for x in self.hybrid_weights)
        if len(weights) != 4 or any(x < 0 for x in weights):
            raise ValueError("hybrid_weights must contain four non-negative values")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("hybrid_weights must sum to 1")
