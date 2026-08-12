"""Definitions for ED livestock-reduction scenarios.

A scenario never rebuilds the ED livestock population from scratch. GOBLIN (or
another national pathway source) supplies the national reduction or endpoint;
GOBLIN-Spatial allocates the implied reduction from the selected 2020 or 2025
ED baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from goblin_spatial.dynamics.baseline import SUPPORTED_SCENARIO_BASE_YEARS


class AllocationRule(str, Enum):
    """Alternative rules for deciding where a fixed national reduction lands."""

    PRORATA = "PRORATA"
    DAIRY_PROTECTION = "DAIRY_PROTECTION"
    PRODUCTIVITY_PROTECTION = "PRODUCTIVITY_PROTECTION"
    VULNERABILITY_PROTECTION = "VULNERABILITY_PROTECTION"
    HYBRID_BALANCED = "HYBRID_BALANCED"
    SCORE_WEIGHTED = "SCORE_WEIGHTED"


@dataclass(frozen=True)
class ScenarioDefinition:
    """National livestock reductions to subtract from an ED baseline.

    Reduction values are fractions of the selected baseline population, e.g.
    ``dairy_reduction=0.30`` means that the national dairy-cow population must
    fall by 30% relative to the chosen baseline year. The allocation rule then
    decides which existing ED animals comprise that reduction.

    Protection rules interpret a *higher* score as stronger protection (a
    smaller proportional cut). ``protection_strength`` controls how strongly
    the score changes the allocation. At the default 0.8, an ED at score 1 has
    one-fifth of the raw cut weight of an otherwise identical ED at score 0.
    """

    name: str
    baseline_year: int
    target_year: int
    dairy_reduction: float = 0.0
    suckler_reduction: float = 0.0
    sheep_reduction: float = 0.0
    allocation_rule: AllocationRule = AllocationRule.PRORATA

    # Generic protection score used by SCORE_WEIGHTED.
    score_column: str | None = None

    # Pre-scenario indicators used by named rules. Higher must mean more
    # productive / more vulnerable, respectively, because higher = protected.
    productivity_score_column: str | None = None
    vulnerability_score_column: str | None = None

    protection_strength: float = 0.8

    # Negotiated hybrid weights: proportionality, productivity, dairy-core,
    # vulnerability. These are scenario assumptions, not estimated parameters.
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
