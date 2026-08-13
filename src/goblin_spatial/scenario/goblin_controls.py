"""External national GOBLIN controls for spatial transition studies.

This module is an input contract, not a scenario generator. National GOBLIN
supplies the quantities. GOBLIN-Spatial locates those quantities across the
validated ED baseline without changing national totals.

The contract supports three levels of cattle control:

1. adult dairy/suckler targets only;
2. adult targets plus an authoritative national total-cattle target;
3. exact national targets for all 21 cattle cohorts.

No missing national quantities are invented here. National livestock-land
release, future land-use targets and residual available land are carried as
separate fields because they have different accounting meanings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.dynamics.baseline import SUPPORTED_SCENARIO_BASE_YEARS


def _as_non_negative_int(label: str, value: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer")
    number = int(value)
    if number != value or number < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return number


def _as_non_negative_float(label: str, value: float) -> float:
    number = float(value)
    if number < 0.0:
        raise ValueError(f"{label} must be non-negative")
    return number


@dataclass(frozen=True)
class GoblinNationalMilestone:
    """One externally supplied national GOBLIN milestone.

    ``dairy_cows`` and ``suckler_cows`` are the adult scenario controls.
    ``total_cattle`` is an optional hard closure target for the complete
    21-cohort cattle state. ``cattle_cohorts`` is the stronger optional control
    and, when supplied, must contain every member of ``FINAL_21_COHORTS``.

    ``livestock_land_release_ha`` is gross national land release attributable to
    the livestock transition when the originating pathway supplies it.
    ``available_land_residual_ha`` is kept separately and must not be treated as
    the same quantity.
    """

    year: int
    dairy_cows: int
    suckler_cows: int
    total_cattle: int | None = None
    cattle_cohorts: Mapping[str, int] | None = None
    livestock_land_release_ha: float | None = None
    land_use_targets_ha: Mapping[str, float] = field(default_factory=dict)
    available_land_residual_ha: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.year, bool) or int(self.year) != self.year:
            raise ValueError("year must be an integer")
        object.__setattr__(self, "year", int(self.year))

        dairy = _as_non_negative_int("dairy_cows", self.dairy_cows)
        suckler = _as_non_negative_int("suckler_cows", self.suckler_cows)
        object.__setattr__(self, "dairy_cows", dairy)
        object.__setattr__(self, "suckler_cows", suckler)

        total = None
        if self.total_cattle is not None:
            total = _as_non_negative_int("total_cattle", self.total_cattle)
            if total < dairy + suckler:
                raise ValueError(
                    "total_cattle cannot be smaller than dairy_cows + suckler_cows"
                )
            object.__setattr__(self, "total_cattle", total)

        if self.cattle_cohorts is not None:
            supplied = dict(self.cattle_cohorts)
            expected = set(FINAL_21_COHORTS)
            actual = set(supplied)
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing or extra:
                raise ValueError(
                    "cattle_cohorts must contain the complete 21-cohort set; "
                    f"missing={missing}, extra={extra}"
                )
            validated = {
                cohort: _as_non_negative_int(
                    f"cattle_cohorts[{cohort}]", supplied[cohort]
                )
                for cohort in FINAL_21_COHORTS
            }
            if total is not None and sum(validated.values()) != total:
                raise ValueError(
                    "sum(cattle_cohorts) must equal total_cattle when both are supplied"
                )
            object.__setattr__(
                self, "cattle_cohorts", MappingProxyType(validated)
            )

        if self.livestock_land_release_ha is not None:
            object.__setattr__(
                self,
                "livestock_land_release_ha",
                _as_non_negative_float(
                    "livestock_land_release_ha", self.livestock_land_release_ha
                ),
            )

        targets = {}
        for raw_name, raw_value in dict(self.land_use_targets_ha).items():
            name = str(raw_name).strip()
            if not name:
                raise ValueError("land-use target names cannot be empty")
            targets[name] = _as_non_negative_float(
                f"land_use_targets_ha[{name}]", raw_value
            )
        object.__setattr__(
            self, "land_use_targets_ha", MappingProxyType(targets)
        )

        if self.available_land_residual_ha is not None:
            object.__setattr__(
                self,
                "available_land_residual_ha",
                _as_non_negative_float(
                    "available_land_residual_ha", self.available_land_residual_ha
                ),
            )


@dataclass(frozen=True)
class GoblinPathwayControls:
    """National controls for one internally consistent pathway identifier.

    The class does not hard-code SI_SG or BE_SG so the package remains reusable.
    The principal study can use those exact identifiers and must keep livestock,
    land-release and land-use controls from the same scenario package.
    """

    scenario_id: str
    baseline_year: int
    milestones: tuple[GoblinNationalMilestone, ...]
    source_note: str | None = None

    def __post_init__(self) -> None:
        scenario_id = str(self.scenario_id).strip()
        if not scenario_id:
            raise ValueError("scenario_id cannot be empty")
        object.__setattr__(self, "scenario_id", scenario_id)

        if self.baseline_year not in SUPPORTED_SCENARIO_BASE_YEARS:
            raise ValueError(
                f"baseline_year must be one of {SUPPORTED_SCENARIO_BASE_YEARS}"
            )

        milestones = tuple(self.milestones)
        if not milestones:
            raise ValueError("at least one national milestone is required")
        years = tuple(m.year for m in milestones)
        if years != tuple(sorted(set(years))):
            raise ValueError("milestone years must be unique and ascending")
        if years[0] <= int(self.baseline_year):
            raise ValueError("all milestone years must follow baseline_year")
        object.__setattr__(self, "milestones", milestones)

    @property
    def target_year(self) -> int:
        return self.milestones[-1].year

    def milestone(self, year: int) -> GoblinNationalMilestone:
        """Return one exact milestone or raise if the pathway does not supply it."""

        year = int(year)
        for milestone in self.milestones:
            if milestone.year == year:
                return milestone
        raise KeyError(f"no GOBLIN national milestone for year {year}")

    def total_cattle_targets_by_year(self) -> dict[int, int]:
        """Return only explicitly supplied national total-cattle targets."""

        return {
            milestone.year: int(milestone.total_cattle)
            for milestone in self.milestones
            if milestone.total_cattle is not None
        }

    def cattle_cohort_targets_by_year(self) -> dict[int, dict[str, int]]:
        """Return only explicitly supplied exact 21-cohort targets."""

        return {
            milestone.year: dict(milestone.cattle_cohorts)
            for milestone in self.milestones
            if milestone.cattle_cohorts is not None
        }

    def livestock_land_release_by_year(self) -> dict[int, float]:
        """Return only explicitly supplied national livestock-land release."""

        return {
            milestone.year: float(milestone.livestock_land_release_ha)
            for milestone in self.milestones
            if milestone.livestock_land_release_ha is not None
        }
