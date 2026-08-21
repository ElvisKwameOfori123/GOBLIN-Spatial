"""Principal SC1 soil-constrained spatialisation of national livestock-land release.

The national released hectares are an external pathway control. Geography is
resolved from the solved 31-cohort livestock state, fixed pasture-DM controls and
the precomputed 08B agricultural-capability cells. The independent 08C mapped
physical-soil layer is never used to move SC1 release.

All principal pathways use the same system-release method. Dairy, beef and sheep
shares are derived from the actual baseline/scenario pasture-DM states and then
rescaled to the authoritative runtime gross release. No pathway receives a
special hard-coded system-land split inside this module.
"""
from __future__ import annotations

from collections.abc import Mapping
import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.pressure.grassland_release import _profile_for_year, _pasture_dm_demand

SYSTEMS = ("DAIRY", "BEEF", "SHEEP")
SOIL_GROUPS = (1, 2, 3)
GOBLIN_NFS_SYSTEM_SOIL_SHARES = {
    "DAIRY": {1: 0.554, 2: 0.393, 3: 0.053},
    "BEEF": {1: 0.420, 2: 0.503, 3: 0.077},
    "SHEEP": {1: 0.335, 2: 0.498, 3: 0.167},
}


def _targets(values: Mapping[int, float], years: list[int]) -> dict[int, float]:
    out = {int(y): float(v) for y, v in values.items()}
    if set(out) != set(years):
        raise ValueError(
            "national land-release targets must exactly match scenario milestones; "
            f"scenario={years}, targets={sorted(out)}"
        )
    previous = 0.0
    for year in years:
        value = out[year]
        if not np.isfinite(value) or value < -1e-12:
            raise ValueError(f"national land-release target for {year} must be finite and non-negative")
        value = max(value, 0.0)
        if value + 1e-9 < previous:
            raise ValueError("cumulative national land release cannot fall between milestones")
        out[year] = value
        previous = value
    return out


def _cohort_dm(frame: pd.DataFrame, state: str, cohorts, profile: Mapping[str, float]) -> np.ndarray:
    demand = np.zeros(len(frame), dtype=float)
    for cohort in cohorts:
        column = f"{state}_COHORT_{cohort}" if cohort in FINAL_21_COHORTS else f"{state}_SHEEP_COHORT_{cohort}"
        if column not in frame.columns:
            raise ValueError(f"SC1 release missing cohort column: {column}")
        values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(values)).any() or (values < 0).any():
            raise ValueError(f"invalid livestock counts in {column}")
        demand += values * float(profile[cohort])
    return demand


def _system_dm(frame: pd.DataFrame, state: str, profile: Mapping[str, float]) -> dict[str, np.ndarray]:
    dairy_followers = [c for c in FINAL_21_COHORTS if c.startswith("DxD_") or c.startswith("DxB_")]
    beef_followers = [c for c in FINAL_21_COHORTS if c.startswith("BxB_")]
    dairy = _cohort_dm(frame, state, ["dairy_cows", *dairy_followers], profile)
    beef = _cohort_dm(frame, state, ["suckler_cows", *beef_followers], profile)
    sheep = _cohort_dm(frame, state, GOBLIN_SHEEP_10, profile)
    bull = _cohort_dm(frame, state, ["bulls"], profile)
    d = pd.to_numeric(frame[f"{state}_COHORT_dairy_cows"], errors="raise").to_numpy(dtype=float)
    b = pd.to_numeric(frame[f"{state}_COHORT_suckler_cows"], errors="raise").to_numpy(dtype=float)
    adults = d + b
    dairy_share = np.divide(d, adults, out=np.zeros(len(frame)), where=adults > 0)
    beef_share = np.divide(b, adults, out=np.zeros(len(frame)), where=adults > 0)
    dairy += bull * dairy_share
    beef += bull * beef_share
    return {"DAIRY": dairy, "BEEF": beef, "SHEEP": sheep}


def _joint_capacity_allocate(capacity: np.ndarray, weights: np.ndarray, targets: np.ndarray, labels: list[str]) -> np.ndarray:
    capacity = np.maximum(np.asarray(capacity, dtype=float), 0.0)
    weights = np.maximum(np.asarray(weights, dtype=float), 0.0)
    targets = np.maximum(np.asarray(targets, dtype=float), 0.0)
    if weights.shape != (len(capacity), len(targets)):
        raise ValueError("SC1 release weights disagree with capacity/targets")
    if (~np.isfinite(capacity)).any() or (~np.isfinite(weights)).any() or (~np.isfinite(targets)).any():
        raise ValueError("SC1 release allocation inputs must be finite")
    if float(targets.sum()) > float(capacity.sum()) + 1e-6:
        raise ValueError("national livestock-land release exceeds ED grassland capacity")
    for j, target in enumerate(targets):
        eligible = weights[:, j] > 1e-15
        if target > float(capacity[eligible].sum()) + 1e-6:
            raise ValueError(f"release target {labels[j]} exceeds eligible 08B capacity")

    allocation = np.zeros_like(weights)
    remaining_capacity = capacity.copy()
    remaining_targets = targets.copy()
    for _ in range(20000):
        if float(remaining_targets.max(initial=0.0)) <= 1e-7:
            break
        proposal = np.zeros_like(weights)
        for j, target in enumerate(remaining_targets):
            if target <= 1e-9:
                continue
            eligible = (remaining_capacity > 1e-12) & (weights[:, j] > 1e-15)
            if not eligible.any():
                raise ValueError(f"no remaining 08B capacity for target {labels[j]}")
            effective = np.where(eligible, weights[:, j] * remaining_capacity, 0.0)
            if float(effective.sum()) <= 1e-20:
                effective = np.where(eligible, weights[:, j], 0.0)
            proposal[:, j] = target * effective / float(effective.sum())
        by_cell = proposal.sum(axis=1)
        scale = np.ones(len(capacity))
        positive = by_cell > 1e-15
        scale[positive] = np.minimum(1.0, remaining_capacity[positive] / by_cell[positive])
        take = proposal * scale[:, None]
        if float(take.sum()) <= 1e-10:
            raise ValueError("SC1 release allocation stalled before closure")
        allocation += take
        remaining_capacity = np.maximum(remaining_capacity - take.sum(axis=1), 0.0)
        remaining_targets = np.maximum(remaining_targets - take.sum(axis=0), 0.0)
    else:
        raise AssertionError("SC1 release allocation did not converge")
    if not np.allclose(allocation.sum(axis=0), targets, atol=1e-5):
        raise AssertionError("SC1 release soil targets failed national closure")
    if (allocation.sum(axis=1) - capacity > 1e-6).any():
        raise AssertionError("SC1 release exceeded an 08B soil cell capacity")
    return allocation


def _ras_allocate(row_totals: np.ndarray, column_targets: np.ndarray, prior: np.ndarray) -> np.ndarray:
    rows = np.maximum(np.asarray(row_totals, dtype=float), 0.0)
    cols = np.maximum(np.asarray(column_targets, dtype=float), 0.0)
    x = np.maximum(np.asarray(prior, dtype=float), 0.0)
    if x.shape != (len(rows), len(cols)):
        raise ValueError("SC1 release RAS prior shape disagrees with margins")
    if not np.isclose(rows.sum(), cols.sum(), atol=1e-5):
        raise ValueError("SC1 release RAS margins disagree")
    if rows.sum() <= 1e-12:
        return np.zeros_like(x)
    support = (rows > 1e-12)[:, None] & (cols > 1e-12)[None, :]
    x = np.where(support, x + 1e-15, 0.0)
    for _ in range(10000):
        csum = x.sum(axis=0)
        for j in range(len(cols)):
            if cols[j] <= 1e-12:
                x[:, j] = 0.0
            elif csum[j] > 0:
                x[:, j] *= cols[j] / csum[j]
        rsum = x.sum(axis=1)
        for i in range(len(rows)):
            if rows[i] <= 1e-12:
                x[i, :] = 0.0
            elif rsum[i] > 0:
                x[i, :] *= rows[i] / rsum[i]
        if np.max(np.abs(x.sum(axis=1) - rows), initial=0.0) <= 1e-7 and np.max(np.abs(x.sum(axis=0) - cols), initial=0.0) <= 1e-7:
            break
    else:
        raise AssertionError("SC1 release RAS attribution did not converge")
    return x


def _system_land_controls(
    *,
    baseline_grassland_ha: float,
    target_livestock_land_ha: float,
    total_release_ha: float,
    base_system_dm: dict[str, np.ndarray],
    scenario_system_dm: dict[str, np.ndarray],
) -> dict:
    """Derive one symmetric dairy/beef/sheep split and preserve gross release."""

    base_dm = {s: float(np.sum(base_system_dm[s])) for s in SYSTEMS}
    scenario_dm = {s: float(np.sum(scenario_system_dm[s])) for s in SYSTEMS}
    base_sum = float(sum(base_dm.values()))
    scenario_sum = float(sum(scenario_dm.values()))
    if base_sum <= 0 or scenario_sum <= 0:
        raise AssertionError("cannot derive system land controls from zero pasture DM")

    base = {s: baseline_grassland_ha * base_dm[s] / base_sum for s in SYSTEMS}
    target = {s: target_livestock_land_ha * scenario_dm[s] / scenario_sum for s in SYSTEMS}
    positive = {s: max(0.0, base[s] - target[s]) for s in SYSTEMS}
    psum = float(sum(positive.values()))
    if total_release_ha > 0 and psum <= 0:
        raise AssertionError("positive runtime land release has no positive system release")
    release = (
        {s: total_release_ha * positive[s] / psum for s in SYSTEMS}
        if psum > 0
        else {s: 0.0 for s in SYSTEMS}
    )
    return {
        "BASE": base,
        "TARGET": target,
        "RELEASE": release,
        "AUTHORITY": "RUNTIME_GROSS_RELEASE_FROM_SELECTED_BASELINE",
        "SYSTEM_SPLIT_SOURCE": "DERIVED_ACTUAL_DM_WEIGHT_ROUTE_RESCALED_ALL_PATHWAYS",
    }


def _system_release_propensity(base_system_dm, scenario_system_dm, controls):
    n = len(next(iter(base_system_dm.values())))
    provisional = {}
    for system in SYSTEMS:
        b = np.maximum(np.asarray(base_system_dm[system], dtype=float), 0.0)
        s = np.maximum(np.asarray(scenario_system_dm[system], dtype=float), 0.0)
        wb = b / float(b.sum()) if float(b.sum()) > 0 else np.zeros(n)
        ws = s / float(s.sum()) if float(s.sum()) > 0 else np.zeros(n)
        signed = wb * float(controls["BASE"][system]) - ws * float(controls["TARGET"][system])
        q = np.maximum(signed, 0.0)
        target = float(controls["RELEASE"][system])
        if target > 0 and float(q.sum()) <= 1e-12:
            q = b.copy()
        provisional[system] = q * (target / float(q.sum())) if target > 0 and float(q.sum()) > 0 else np.zeros(n)
    return provisional


def _soil_targets(total_release, base_system_dm, scenario_system_dm, controls):
    raw = {}
    for system in SYSTEMS:
        b = float(np.sum(base_system_dm[system]))
        s = float(np.sum(scenario_system_dm[system]))
        raw[system] = max(0.0, 1.0 - s / b) if b > 0 else 0.0
    raw_sum = float(sum(raw.values()))
    if raw_sum > 1e-15:
        weights = {s: raw[s] / raw_sum for s in SYSTEMS}
        source = "GOBLIN_WEIGHTED_DM_REDUCTION_CONTRIBUTION"
    else:
        rel_sum = float(sum(controls["RELEASE"].values()))
        weights = {s: controls["RELEASE"][s] / rel_sum if rel_sum > 0 else 0.0 for s in SYSTEMS}
        source = "SYSTEM_RELEASE_SHARE_FALLBACK"
    shares = {g: sum(weights[s] * GOBLIN_NFS_SYSTEM_SOIL_SHARES[s][g] for s in SYSTEMS) for g in SOIL_GROUPS}
    ssum = float(sum(shares.values()))
    if ssum > 0:
        shares = {g: shares[g] / ssum for g in SOIL_GROUPS}
    return {
        "TARGET_HA": {g: float(total_release) * shares[g] for g in SOIL_GROUPS},
        "SHARE": shares,
        "SYSTEM_WEIGHT": weights,
        "SOURCE": source,
    }


def allocate_national_goblin_land_release(
    livestock_pathway: pd.DataFrame,
    national_release_ha_by_year: Mapping[int, float],
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]],
    *,
    grassland_column: str = "ALL_GRASSLAND",
) -> pd.DataFrame:
    """Spatialise authoritative release through solved livestock pressure and 08B capacity."""
    required = {"CSOED", "PATHWAY_BASELINE_YEAR", "MILESTONE_YEAR", "PATHWAY_NAME", grassland_column}
    required.update({f"GOBLIN_SOIL_G{i}_SHARE" for i in SOIL_GROUPS})
    required.update({f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in SOIL_GROUPS})
    missing = sorted(required - set(livestock_pathway.columns))
    if missing:
        raise ValueError(f"principal SC1 release missing columns: {missing}")
    if livestock_pathway[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("principal SC1 release requires one row per ED and milestone")

    out = livestock_pathway.copy()
    years = sorted(pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).unique())
    targets = _targets(national_release_ha_by_year, years)
    base_years = pd.to_numeric(out["PATHWAY_BASELINE_YEAR"], errors="raise").astype(int).unique()
    scenario_ids = out["PATHWAY_NAME"].astype(str).unique()
    if len(base_years) != 1 or len(scenario_ids) != 1:
        raise ValueError("principal SC1 release requires one baseline year and scenario")
    baseline_year = int(base_years[0])

    rows = []
    for year in years:
        block = out.loc[pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).eq(year)].sort_values("CSOED", kind="stable").reset_index(drop=True)
        grass = pd.to_numeric(block[grassland_column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(grass)).any() or (grass < -1e-12).any():
            raise ValueError(f"{grassland_column} must be finite and non-negative")
        target_release = float(targets[year])
        baseline_grass = float(grass.sum())
        target_land = baseline_grass - target_release
        if target_land < -1e-6:
            raise ValueError("runtime release exceeds selected baseline grassland")

        base_profile = _profile_for_year(pasture_dm_t_per_head_by_year, baseline_year)
        scenario_profile = _profile_for_year(pasture_dm_t_per_head_by_year, int(year))
        base_system_dm = _system_dm(block, "BASE", base_profile)
        scenario_system_dm = _system_dm(block, "SCENARIO", scenario_profile)
        controls = _system_land_controls(
            baseline_grassland_ha=baseline_grass,
            target_livestock_land_ha=target_land,
            total_release_ha=target_release,
            base_system_dm=base_system_dm,
            scenario_system_dm=scenario_system_dm,
        )
        provisional = _system_release_propensity(base_system_dm, scenario_system_dm, controls)
        provisional_system = np.column_stack([provisional[s] for s in SYSTEMS])
        if abs(float(provisional_system.sum()) - target_release) > 1e-5:
            raise AssertionError("SC1 provisional system release does not close")

        soil_control = _soil_targets(target_release, base_system_dm, scenario_system_dm, controls)
        soil_capacity = block[[f"GOBLIN_SOIL_G{i}_GRASSLAND_HA" for i in SOIL_GROUPS]].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
        shares = block[[f"GOBLIN_SOIL_G{i}_SHARE" for i in SOIL_GROUPS]].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
        if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-8):
            raise AssertionError("08B G1/G2/G3 shares do not close to one")
        if not np.allclose(soil_capacity.sum(axis=1), grass, atol=1e-7):
            raise AssertionError("08B G1/G2/G3 capacity does not close to ALL_GRASSLAND")

        group_signal = np.zeros((len(block), 3), dtype=float)
        for sidx, system in enumerate(SYSTEMS):
            for gidx, group in enumerate(SOIL_GROUPS):
                group_signal[:, gidx] += provisional_system[:, sidx] * GOBLIN_NFS_SYSTEM_SOIL_SHARES[system][group]
        cell_capacity = soil_capacity.reshape(-1)
        weights = np.zeros((len(cell_capacity), 3), dtype=float)
        for gidx, group in enumerate(SOIL_GROUPS):
            matrix = np.zeros_like(soil_capacity)
            matrix[:, gidx] = group_signal[:, gidx]
            w = matrix.reshape(-1)
            group_cells = np.tile(np.arange(3), len(block)) == gidx
            w = np.where(group_cells & (cell_capacity > 1e-12), w + 1e-12, 0.0)
            weights[:, gidx] = w
        allocation = _joint_capacity_allocate(
            cell_capacity,
            weights,
            np.asarray([soil_control["TARGET_HA"][g] for g in SOIL_GROUPS]),
            [f"G{g}" for g in SOIL_GROUPS],
        )
        allocation_cells = allocation.reshape(len(block), 3, 3)
        released_by_soil = allocation_cells.sum(axis=2)
        released_total = released_by_soil.sum(axis=1)
        if abs(float(released_total.sum()) - target_release) > 1e-5:
            raise AssertionError("SC1 ED release does not close to national target")
        if (released_by_soil - soil_capacity > 1e-6).any():
            raise AssertionError("SC1 release exceeds 08B soil capacity")

        system_targets = np.asarray([controls["RELEASE"][s] for s in SYSTEMS])
        system_attribution = _ras_allocate(released_total, system_targets, provisional_system)

        base_dm = _pasture_dm_demand(block, state="BASE", profile=base_profile)
        scenario_dm = _pasture_dm_demand(block, state="SCENARIO", profile=scenario_profile)
        effective_supply = np.divide(base_dm, grass, out=np.full(len(block), np.nan), where=grass > 0)
        diagnostic_required = np.divide(scenario_dm, effective_supply, out=np.zeros(len(block)), where=np.isfinite(effective_supply) & (effective_supply > 0))
        no_base = (grass > 0) & (base_dm <= 1e-12)
        diagnostic_required[no_base] = grass[no_base]
        diagnostic_signed = grass - diagnostic_required

        for gidx, group in enumerate(SOIL_GROUPS):
            block[f"GOBLIN_RELEASED_G{group}_HA"] = released_by_soil[:, gidx]
            block[f"GOBLIN_NATIONAL_RELEASE_G{group}_TARGET_HA"] = float(soil_control["TARGET_HA"][group])
            block[f"GOBLIN_NATIONAL_RELEASE_G{group}_ACTUAL_HA"] = float(released_by_soil[:, gidx].sum())
        for sidx, system in enumerate(SYSTEMS):
            block[f"GOBLIN_RELEASED_{system}_LAND_HA"] = system_attribution[:, sidx]
            block[f"GOBLIN_DERIVED_SYSTEM_RELEASE_TARGET_{system}_HA"] = float(system_targets[sidx])

        block["GOBLIN_RELEASED_GRASSLAND_HA"] = released_total
        block["POTENTIAL_SPARED_GRASSLAND_HA"] = released_total
        block["POTENTIAL_SPARED_GRASSLAND_SHARE"] = np.divide(released_total, grass, out=np.zeros(len(block)), where=grass > 0)
        block["GOBLIN_NATIONAL_RELEASE_TARGET_HA"] = target_release
        block["GOBLIN_NATIONAL_RELEASE_ACTUAL_HA"] = float(released_total.sum())
        block["GOBLIN_NATIONAL_RELEASE_DIFFERENCE_HA"] = float(released_total.sum()) - target_release
        block["GOBLIN_RELEASE_ACCOUNTING_ROLE"] = "AUTHORITATIVE_RUNTIME_TOTAL_SPATIALISED_WITH_08B_CAPACITY"
        block["GOBLIN_RELEASE_SYSTEM_CONTROL_AUTHORITY"] = controls["AUTHORITY"]
        block["GOBLIN_RELEASE_SYSTEM_SPLIT_SOURCE"] = controls["SYSTEM_SPLIT_SOURCE"]
        block["GOBLIN_RELEASE_SOIL_TARGET_SOURCE"] = soil_control["SOURCE"]
        block["GOBLIN_RELEASE_08C_USED"] = False
        block["DM_DIAGNOSTIC_BASELINE_PASTURE_DM_T"] = base_dm
        block["DM_DIAGNOSTIC_SCENARIO_PASTURE_DM_T"] = scenario_dm
        block["DM_DIAGNOSTIC_REQUIRED_GRASSLAND_HA"] = diagnostic_required
        block["DM_DIAGNOSTIC_SPARED_GRASSLAND_HA"] = np.maximum(diagnostic_signed, 0.0)
        block["ADDITIONAL_GRASSLAND_REQUIRED_HA"] = np.maximum(-diagnostic_signed, 0.0)
        rows.append(block)

    return pd.concat(rows, ignore_index=True).sort_values(["MILESTONE_YEAR", "CSOED"], kind="stable").reset_index(drop=True)
