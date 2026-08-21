"""National GOBLIN controls consumed by the principal spatial workflow.

This module is an input contract, not a scenario generator. National GOBLIN
supplies the quantities. GOBLIN-Spatial locates them across the validated ED
baseline without changing national totals.

Supported cattle control depth is deliberately explicit:

1. adult dairy and suckler targets;
2. adult targets plus an authoritative total-cattle target; or
3. exact national targets for all 21 cattle cohorts.

National gross livestock-land release, land-use targets and residual available
land are separate accounting quantities. No pathway-specific dairy/beef/sheep
land-release decomposition is accepted here; the principal spatial engine uses
one symmetric pasture-DM-based spatialisation method for every pathway.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
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
    """One externally supplied national GOBLIN milestone."""

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
            if validated["dairy_cows"] != dairy:
                raise ValueError("cattle_cohorts[dairy_cows] must equal dairy_cows")
            if validated["suckler_cows"] != suckler:
                raise ValueError("cattle_cohorts[suckler_cows] must equal suckler_cows")
            if total is not None and sum(validated.values()) != total:
                raise ValueError(
                    "sum(cattle_cohorts) must equal total_cattle when both are supplied"
                )
            object.__setattr__(
                self,
                "cattle_cohorts",
                MappingProxyType(validated),
            )

        if self.livestock_land_release_ha is not None:
            object.__setattr__(
                self,
                "livestock_land_release_ha",
                _as_non_negative_float(
                    "livestock_land_release_ha",
                    self.livestock_land_release_ha,
                ),
            )

        targets: dict[str, float] = {}
        for raw_name, raw_value in dict(self.land_use_targets_ha).items():
            name = str(raw_name).strip().upper()
            if not name:
                raise ValueError("land-use target names cannot be empty")
            if name in targets:
                raise ValueError(f"duplicate land-use target: {name}")
            targets[name] = _as_non_negative_float(
                f"land_use_targets_ha[{name}]",
                raw_value,
            )
        object.__setattr__(
            self,
            "land_use_targets_ha",
            MappingProxyType(targets),
        )

        if self.available_land_residual_ha is not None:
            object.__setattr__(
                self,
                "available_land_residual_ha",
                _as_non_negative_float(
                    "available_land_residual_ha",
                    self.available_land_residual_ha,
                ),
            )

    def adult_reductions_from_baseline(
        self,
        *,
        baseline_dairy_cows: int,
        baseline_suckler_cows: int,
    ) -> dict[str, int | float]:
        """Describe signed category change and overall adult-cow contraction."""

        baseline_dairy = _as_non_negative_int(
            "baseline_dairy_cows",
            baseline_dairy_cows,
        )
        baseline_suckler = _as_non_negative_int(
            "baseline_suckler_cows",
            baseline_suckler_cows,
        )
        target_dairy = int(self.dairy_cows)
        target_suckler = int(self.suckler_cows)
        baseline_adults = baseline_dairy + baseline_suckler
        target_adults = target_dairy + target_suckler
        if target_adults > baseline_adults:
            raise ValueError(
                "principal pathway requires an overall adult-cow contraction; "
                f"baseline={baseline_adults}, endpoint={target_adults}"
            )

        change_dairy = target_dairy - baseline_dairy
        change_suckler = target_suckler - baseline_suckler
        dairy_reduction = max(0, -change_dairy)
        suckler_reduction = max(0, -change_suckler)
        adult_reduction = baseline_adults - target_adults

        return {
            "baseline_dairy_cows": baseline_dairy,
            "target_dairy_cows": target_dairy,
            "change_dairy_cows": change_dairy,
            "dairy_reduction_n": dairy_reduction,
            "dairy_reduction_fraction": (
                0.0 if baseline_dairy == 0 else dairy_reduction / baseline_dairy
            ),
            "baseline_suckler_cows": baseline_suckler,
            "target_suckler_cows": target_suckler,
            "change_suckler_cows": change_suckler,
            "suckler_reduction_n": suckler_reduction,
            "suckler_reduction_fraction": (
                0.0
                if baseline_suckler == 0
                else suckler_reduction / baseline_suckler
            ),
            "baseline_adult_cows": baseline_adults,
            "target_adult_cows": target_adults,
            "change_adult_cows": target_adults - baseline_adults,
            "adult_reduction_n": adult_reduction,
            "adult_reduction_fraction": (
                0.0
                if baseline_adults == 0
                else adult_reduction / baseline_adults
            ),
        }


@dataclass(frozen=True)
class GoblinPathwayControls:
    """National controls for one internally consistent pathway identifier."""

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
        years = tuple(milestone.year for milestone in milestones)
        if years != tuple(sorted(set(years))):
            raise ValueError("milestone years must be unique and ascending")
        if years[0] <= int(self.baseline_year):
            raise ValueError("all milestone years must follow baseline_year")
        object.__setattr__(self, "milestones", milestones)

    @property
    def target_year(self) -> int:
        return self.milestones[-1].year

    def milestone(self, year: int) -> GoblinNationalMilestone:
        year = int(year)
        for milestone in self.milestones:
            if milestone.year == year:
                return milestone
        raise KeyError(f"no GOBLIN national milestone for year {year}")

    def adult_reductions_from_baseline(
        self,
        *,
        baseline_dairy_cows: int,
        baseline_suckler_cows: int,
        year: int | None = None,
    ) -> dict[str, int | float]:
        milestone = self.milestone(self.target_year if year is None else year)
        return milestone.adult_reductions_from_baseline(
            baseline_dairy_cows=baseline_dairy_cows,
            baseline_suckler_cows=baseline_suckler_cows,
        )

    def total_cattle_targets_by_year(self) -> dict[int, int]:
        return {
            milestone.year: int(milestone.total_cattle)
            for milestone in self.milestones
            if milestone.total_cattle is not None
        }

    def cattle_cohort_targets_by_year(self) -> dict[int, dict[str, int]]:
        return {
            milestone.year: dict(milestone.cattle_cohorts)
            for milestone in self.milestones
            if milestone.cattle_cohorts is not None
        }

    def livestock_land_release_by_year(self) -> dict[int, float]:
        return {
            milestone.year: float(milestone.livestock_land_release_ha)
            for milestone in self.milestones
            if milestone.livestock_land_release_ha is not None
        }


def load_adult_endpoint_controls(
    path: str | Path,
    *,
    scenario_id: str,
    baseline_year: int,
) -> GoblinPathwayControls:
    """Load one adult endpoint without inferring missing national quantities."""

    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    requested = str(scenario_id).strip()
    matches = [
        row
        for row in rows
        if str(row.get("SCENARIO_ID", "")).strip() == requested
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one endpoint row for {requested}; found {len(matches)}"
        )
    row = matches[0]

    try:
        target_year = int(row["TARGET_YEAR"])
        dairy = int(row["DAIRY_COWS"])
        suckler = int(row["SUCKLER_COWS"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("adult endpoint CSV contains invalid required fields") from exc

    reported_ratio = str(row.get("DAIRY_SUCKLER_RATIO", "")).strip()
    if reported_ratio:
        ratio = float(reported_ratio)
        if suckler == 0:
            if dairy != 0:
                raise ValueError(
                    "finite dairy:suckler ratio cannot be validated with zero suckler cows"
                )
        elif abs((dairy / suckler) - ratio) > 1e-9:
            raise ValueError(
                f"reported dairy:suckler ratio does not match endpoint counts for {requested}"
            )

    source_note = str(row.get("SOURCE_NOTE", "")).strip() or None
    return GoblinPathwayControls(
        scenario_id=requested,
        baseline_year=int(baseline_year),
        milestones=(
            GoblinNationalMilestone(
                year=target_year,
                dairy_cows=dairy,
                suckler_cows=suckler,
            ),
        ),
        source_note=source_note,
    )
