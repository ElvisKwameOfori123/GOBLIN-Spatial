"""Spatialise category-resolved national livestock-land release across EDs.

The originating GOBLIN pathway remains authoritative for national hectares.
GOBLIN-Spatial supplies geography.  This allocator is designed for pathway
controls such as Styles Table S3 where gross livestock-land release can be
resolved into dairy, beef and sheep components.

The three spatial signals deliberately differ:

* dairy release is allocated over the baseline dairy-system pasture footprint,
  because national dairy land can fall even when dairy cow numbers rise;
* beef release follows positive decline in suckler/BxB pasture pressure, with a
  baseline beef-footprint fallback if the decline signal is degenerate;
* sheep release is allocated over the baseline sheep pasture footprint when the
  pathway changes sheep land requirement without changing sheep head numbers.

These are transparent spatialisation proxies.  They do not claim observed
parcel-level intensification or movement of particular hectares.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.pressure.grassland_release import _profile_for_year
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


SYSTEMS = ("DAIRY", "BEEF", "SHEEP")
DAIRY_FOLLOWERS = tuple(
    c for c in FINAL_21_COHORTS if c.startswith("DxD_") or c.startswith("DxB_")
)
BEEF_FOLLOWERS = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"category land-release input missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any() or (values < 0).any():
        raise ValueError(f"{column} must be finite and non-negative")
    return values


def _cohort_dm(
    frame: pd.DataFrame,
    *,
    state: str,
    cohorts: tuple[str, ...],
    profile: Mapping[str, float],
) -> np.ndarray:
    demand = np.zeros(len(frame), dtype=float)
    for cohort in cohorts:
        if cohort in FINAL_21_COHORTS:
            column = f"{state}_COHORT_{cohort}"
        else:
            column = f"{state}_SHEEP_COHORT_{cohort}"
        demand += _numeric(frame, column) * float(profile[cohort])
    return demand


def _system_dm(
    frame: pd.DataFrame,
    *,
    state: str,
    profile: Mapping[str, float],
) -> dict[str, np.ndarray]:
    """Return parent-origin pasture-DM proxies for dairy, beef and sheep systems."""

    dairy = _cohort_dm(
        frame,
        state=state,
        cohorts=("dairy_cows", *DAIRY_FOLLOWERS),
        profile=profile,
    )
    beef = _cohort_dm(
        frame,
        state=state,
        cohorts=("suckler_cows", *BEEF_FOLLOWERS),
        profile=profile,
    )
    sheep = _cohort_dm(
        frame,
        state=state,
        cohorts=tuple(GOBLIN_SHEEP_10),
        profile=profile,
    )

    # Breeding bulls serve the adult cattle system as a whole.  Allocate their
    # pasture demand between dairy and beef according to each ED's adult-cow mix
    # so bull feed is not double counted and remains spatially local.
    bull = _cohort_dm(
        frame,
        state=state,
        cohorts=("bulls",),
        profile=profile,
    )
    dairy_adults = _numeric(frame, f"{state}_COHORT_dairy_cows")
    beef_adults = _numeric(frame, f"{state}_COHORT_suckler_cows")
    adults = dairy_adults + beef_adults
    dairy_share = np.divide(
        dairy_adults,
        adults,
        out=np.zeros(len(frame), dtype=float),
        where=adults > 0,
    )
    beef_share = np.divide(
        beef_adults,
        adults,
        out=np.zeros(len(frame), dtype=float),
        where=adults > 0,
    )
    dairy += bull * dairy_share
    beef += bull * beef_share
    return {"DAIRY": dairy, "BEEF": beef, "SHEEP": sheep}


def _validated_targets(targets: Mapping[str, float]) -> dict[str, float]:
    supplied = {str(k).strip().upper(): float(v) for k, v in dict(targets).items()}
    if set(supplied) != set(SYSTEMS):
        raise ValueError(
            "category land-release targets must contain exactly DAIRY, BEEF and SHEEP"
        )
    for system, value in supplied.items():
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{system} land-release target must be finite and non-negative")
    return supplied


def _joint_capacity_allocate(
    capacity: np.ndarray,
    weights: np.ndarray,
    targets: np.ndarray,
) -> np.ndarray:
    """Meet category column totals while respecting a shared ED capacity.

    The iterative proportional allocator treats all three systems simultaneously,
    avoiding an arbitrary dairy-first, beef-first or sheep-first priority.  Each
    category retains its own non-negative spatial weights.  Structural zeros in
    the weights remain zero throughout.
    """

    capacity = np.maximum(np.asarray(capacity, dtype=float), 0.0)
    weights = np.maximum(np.asarray(weights, dtype=float), 0.0)
    targets = np.maximum(np.asarray(targets, dtype=float), 0.0)
    if weights.ndim != 2 or weights.shape[0] != len(capacity):
        raise ValueError("category weights must be an ED x system matrix")
    if weights.shape[1] != len(targets):
        raise ValueError("category weights and targets disagree on system count")
    if (~np.isfinite(weights)).any() or (~np.isfinite(capacity)).any():
        raise ValueError("category allocation inputs must be finite")
    if float(targets.sum()) > float(capacity.sum()) + 1e-7:
        raise ValueError("national category land release exceeds total ED grassland capacity")

    for idx, target in enumerate(targets):
        eligible_capacity = float(capacity[weights[:, idx] > 1e-12].sum())
        if target > eligible_capacity + 1e-7:
            raise ValueError(
                f"system {SYSTEMS[idx]} release cannot fit within its eligible ED footprint"
            )

    allocation = np.zeros_like(weights, dtype=float)
    remaining_capacity = capacity.copy()
    remaining_targets = targets.copy()

    for _ in range(10000):
        if float(remaining_targets.max(initial=0.0)) <= 1e-8:
            break
        proposal = np.zeros_like(weights, dtype=float)
        for col, target in enumerate(remaining_targets):
            if target <= 1e-10:
                continue
            eligible = (remaining_capacity > 1e-12) & (weights[:, col] > 1e-12)
            if not eligible.any():
                raise ValueError(
                    f"no remaining ED capacity for {SYSTEMS[col]} category release"
                )
            effective = np.where(
                eligible,
                weights[:, col] * remaining_capacity,
                0.0,
            )
            if float(effective.sum()) <= 1e-15:
                effective = np.where(eligible, weights[:, col], 0.0)
            proposal[:, col] = target * effective / float(effective.sum())

        proposed_by_ed = proposal.sum(axis=1)
        scale = np.ones(len(capacity), dtype=float)
        positive = proposed_by_ed > 1e-15
        scale[positive] = np.minimum(
            1.0,
            remaining_capacity[positive] / proposed_by_ed[positive],
        )
        take = proposal * scale[:, None]
        progress = float(take.sum())
        if progress <= 1e-12:
            raise ValueError("category land-release allocation stalled before closure")

        allocation += take
        remaining_capacity = np.maximum(remaining_capacity - take.sum(axis=1), 0.0)
        remaining_targets = np.maximum(remaining_targets - take.sum(axis=0), 0.0)
    else:
        raise AssertionError("category land-release allocation did not converge")

    if not np.allclose(allocation.sum(axis=0), targets, atol=1e-6):
        raise AssertionError("category national land-release targets did not close")
    if (allocation.sum(axis=1) - capacity > 1e-7).any():
        raise AssertionError("category land release exceeded an ED grassland capacity")
    return allocation


def allocate_category_resolved_goblin_land_release(
    livestock_endpoint: pd.DataFrame,
    national_release_ha_by_system: Mapping[str, float],
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]],
    *,
    grassland_column: str = "ALL_GRASSLAND",
) -> pd.DataFrame:
    """Spatialise dairy/beef/sheep GOBLIN land-release controls exactly.

    This function currently represents one endpoint year, matching the principal
    Styles SI_SG / BE_SG route.  The national category controls must sum to the
    authoritative gross livestock-land release supplied by the pathway.
    """

    out = livestock_endpoint.copy().sort_values("CSOED", kind="stable").reset_index(drop=True)
    required = {
        "CSOED",
        "PATHWAY_BASELINE_YEAR",
        "MILESTONE_YEAR",
        grassland_column,
    }
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(f"category land-release allocation missing columns: {missing}")
    years = pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).unique()
    if len(years) != 1:
        raise ValueError("category-resolved endpoint allocator currently requires one milestone")
    base_years = pd.to_numeric(out["PATHWAY_BASELINE_YEAR"], errors="raise").astype(int).unique()
    if len(base_years) != 1:
        raise ValueError("category-resolved release requires one pathway baseline year")

    base_year = int(base_years[0])
    target_year = int(years[0])
    base_profile = _profile_for_year(pasture_dm_t_per_head_by_year, base_year)
    target_profile = _profile_for_year(pasture_dm_t_per_head_by_year, target_year)
    base_dm = _system_dm(out, state="BASE", profile=base_profile)
    scenario_dm = _system_dm(out, state="SCENARIO", profile=target_profile)

    targets = _validated_targets(national_release_ha_by_system)
    weights = {
        # A baseline-footprint allocation is intentional here.  It represents a
        # spatialised national land-efficiency shift and remains valid when dairy
        # head numbers increase, as in SI_SG.
        "DAIRY": np.maximum(base_dm["DAIRY"], 0.0),
        # Beef land release is tied to the realised fall in suckler/BxB pressure.
        "BEEF": np.maximum(base_dm["BEEF"] - scenario_dm["BEEF"], 0.0),
        # Sheep heads are fixed in the principal experiment, while Table S3 still
        # releases a small sheep-land area.  Use the baseline sheep footprint.
        "SHEEP": np.maximum(base_dm["SHEEP"], 0.0),
    }
    if float(weights["BEEF"].sum()) <= 1e-12 and targets["BEEF"] > 0:
        weights["BEEF"] = np.maximum(base_dm["BEEF"], 0.0)

    grass = _numeric(out, grassland_column)
    matrix = np.column_stack([weights[system] for system in SYSTEMS])
    target_vector = np.asarray([targets[system] for system in SYSTEMS], dtype=float)
    allocation = _joint_capacity_allocate(grass, matrix, target_vector)

    for col, system in enumerate(SYSTEMS):
        out[f"BASE_{system}_SYSTEM_PASTURE_DM_T"] = base_dm[system]
        out[f"SCENARIO_{system}_SYSTEM_PASTURE_DM_T"] = scenario_dm[system]
        out[f"{system}_RELEASE_SPATIAL_WEIGHT"] = weights[system]
        out[f"GOBLIN_RELEASED_{system}_LAND_HA"] = allocation[:, col]
        out[f"GOBLIN_NATIONAL_{system}_LAND_RELEASE_TARGET_HA"] = targets[system]
        out[f"GOBLIN_NATIONAL_{system}_LAND_RELEASE_ACTUAL_HA"] = float(
            allocation[:, col].sum()
        )

    out["GOBLIN_RELEASED_GRASSLAND_HA"] = allocation.sum(axis=1)
    out["GOBLIN_RELEASED_GRASSLAND_SHARE_OF_ED"] = np.divide(
        out["GOBLIN_RELEASED_GRASSLAND_HA"].to_numpy(dtype=float),
        grass,
        out=np.zeros(len(out), dtype=float),
        where=grass > 0,
    )
    total_target = float(target_vector.sum())
    actual = float(out["GOBLIN_RELEASED_GRASSLAND_HA"].sum())
    out["GOBLIN_NATIONAL_RELEASE_TARGET_HA"] = total_target
    out["GOBLIN_NATIONAL_RELEASE_ACTUAL_HA"] = actual
    out["GOBLIN_NATIONAL_RELEASE_DIFFERENCE_HA"] = actual - total_target
    out["GOBLIN_RELEASE_ACCOUNTING_ROLE"] = "AUTHORITATIVE_CATEGORY_RESOLVED_NATIONAL_TOTAL_SPATIALISED"
    out["DAIRY_RELEASE_WEIGHT_METHOD"] = "BASELINE_PARENT_ORIGIN_PASTURE_DM_FOOTPRINT"
    out["BEEF_RELEASE_WEIGHT_METHOD"] = "POSITIVE_PARENT_ORIGIN_PASTURE_DM_REDUCTION"
    out["SHEEP_RELEASE_WEIGHT_METHOD"] = "BASELINE_SHEEP_PASTURE_DM_FOOTPRINT"

    if abs(actual - total_target) > 1e-6:
        raise AssertionError("gross category-resolved national land release failed closure")
    return out
