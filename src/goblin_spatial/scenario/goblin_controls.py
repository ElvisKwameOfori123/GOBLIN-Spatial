"""External national GOBLIN controls for spatial transition studies.

National GOBLIN supplies the pathway quantities. GOBLIN-Spatial locates those
quantities across the validated ED baseline without changing national totals.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True)
class GoblinNationalMilestone:
    """One externally supplied national GOBLIN milestone."""

    year: int
    dairy_cows: int
    suckler_cows: int
    total_cattle: int | None = None
    cattle_cohorts: Mapping[str, int] | None = None
    livestock_land_release_ha: float | None = None
    land_use_targets_ha: Mapping[str, float] | None = None
    available_land_residual_ha: float | None = None


@dataclass(frozen=True)
class GoblinPathwayControls:
    """National controls for one internally consistent pathway identifier."""

    scenario_id: str
    baseline_year: int
    milestones: tuple[GoblinNationalMilestone, ...]
