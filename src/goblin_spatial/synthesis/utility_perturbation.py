"""Controlled 10% cohort-perturbation utility test on the frozen baseline.

Not a scenario and not a forecast. The frozen baseline is not rebuilt: each
arm reduces a breeding population, and every follower cohort linked to it
changes by the proportion its parents change, through the frozen ED
parent-follower relationship (``baseline.signatures.parent_follower_multiplier``).
Followers stay where the baseline places them.

Arms (``change`` = -0.10 by default):

DAIRY_PARENT    dairy cows, DxD and DxB followers
SUCKLER_PARENT  suckler cows, BxB followers
PRO_RATA        all 21 cattle cohorts, including bulls (the static-structure
                benchmark: the same proportional change for every cohort)

Bulls change only in PRO_RATA. Sheep never change. Livestock units use one
fixed schedule for all arms (the IFS/Eurostat coefficients of the CSO age-sex
groups); Standard Output uses the fixed IFS 2020 coefficients by region. Head
counts are kept fractional (no rounding) so that each arm is exactly the
stated transformation (Eq. 8 of the methods).

With a uniform change every targeted cohort changes by exactly ``change``.
The national effect of a parent arm is therefore ``change`` x that system's
share of cattle; the content of the test is spatial: where the removed
animals, livestock units and Standard Output are.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import cohort_origin, parent_follower_multiplier
from goblin_spatial.cattle.annual_age_sex import LSU_COEFFICIENTS
from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS

ARMS = ("DAIRY_PARENT", "SUCKLER_PARENT", "PRO_RATA")
ARM_PARENT = {"DAIRY_PARENT": "dairy_cows", "SUCKLER_PARENT": "suckler_cows"}
ARM_ORIGIN = {"DAIRY_PARENT": "DAIRY", "SUCKLER_PARENT": "SUCKLER"}
DXD = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))
FOLLOWERS = (*DXD, *DXB, *BXB)


def livestock_unit_schedule() -> dict[str, float]:
    """One fixed LU coefficient per cattle cohort, from its CSO age-sex group."""

    schedule = {
        "dairy_cows": LSU_COEFFICIENTS["DAIRY_COW"],
        "suckler_cows": LSU_COEFFICIENTS["OTHER_COW"],
        "bulls": LSU_COEFFICIENTS["BULLS"],
    }
    for container, mapping in CONTAINERS.items():
        for cohort in mapping.values():
            schedule[cohort] = LSU_COEFFICIENTS[container]
    if set(schedule) != set(FINAL_21_COHORTS):
        raise AssertionError("LU schedule must cover exactly the 21 cattle cohorts")
    return schedule


def standard_output_coefficients(mapping: pd.DataFrame, region_code: pd.Series) -> dict[str, np.ndarray]:
    table = mapping.set_index("MODEL_VARIABLE")
    return {
        cohort: np.where(region_code.to_numpy() == "381", table.at[cohort, "SOC_EUR_381"], table.at[cohort, "SOC_EUR_382"]).astype(float)
        for cohort in FINAL_21_COHORTS
    }


def perturb_year(frame: pd.DataFrame, arm: str, change: float = -0.10) -> pd.DataFrame:
    """Return perturbed cohort head (float) for one year of the ED baseline."""

    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    if not -1.0 <= change <= 1.0:
        raise ValueError("change must be a proportion between -1 and 1")
    base = frame[list(FINAL_21_COHORTS)].astype(float)
    new = base.copy()
    if arm == "PRO_RATA":
        return new * (1.0 + change)

    parent = ARM_PARENT[arm]
    new[parent] = base[parent] * (1.0 + change)
    counties = frame["County"].astype(str).to_numpy(dtype=object)
    for cohort in FOLLOWERS:
        if cohort_origin(cohort) != ARM_ORIGIN[arm]:
            continue
        multiplier, _ = parent_follower_multiplier(
            base[parent].to_numpy(), new[parent].to_numpy(), np.rint(base[cohort]).astype(np.int64), counties
        )
        new[cohort] = base[cohort] * multiplier
    return new


def run_utility_perturbation(
    ed: pd.DataFrame,
    so_mapping: pd.DataFrame,
    crosswalk: pd.DataFrame,
    years: tuple[int, ...] = (2020, 2025),
    change: float = -0.10,
) -> dict[str, pd.DataFrame]:
    """Run the three arms and return ED, aggregate and national tables."""

    lu = livestock_unit_schedule()
    ed_rows = []
    for year in years:
        frame = ed.loc[ed["YEAR"] == year].sort_values("CSOED").reset_index(drop=True)
        region = frame["FADN_REGION"].astype(str).str.extract(r"(38[12])")[0]
        if region.isna().any():
            raise AssertionError("EDs without a Standard Output region")
        soc = standard_output_coefficients(so_mapping, region)
        base = frame[list(FINAL_21_COHORTS)].astype(float)
        base_head = base.sum(axis=1)
        base_lu = sum(base[c] * lu[c] for c in FINAL_21_COHORTS)
        base_so = sum(base[c] * soc[c] for c in FINAL_21_COHORTS)
        changes = {}
        for arm in ARMS:
            new = perturb_year(frame, arm, change)
            delta = new - base
            row = pd.DataFrame(
                {
                    "ARM": arm,
                    "YEAR": year,
                    "CSOED": frame["CSOED"].astype(str),
                    "County": frame["County"].astype(str),
                    "BASE_CATTLE": base_head,
                    "BASE_LU": base_lu,
                    "BASE_CATTLE_SO_2020_EUR": base_so,
                    "CHANGE_CATTLE": delta.sum(axis=1),
                    "CHANGE_ADULT_COWS": delta["dairy_cows"] + delta["suckler_cows"],
                    "CHANGE_DXD_FOLLOWERS": delta[list(DXD)].sum(axis=1),
                    "CHANGE_DXB_FOLLOWERS": delta[list(DXB)].sum(axis=1),
                    "CHANGE_BXB_FOLLOWERS": delta[list(BXB)].sum(axis=1),
                    "CHANGE_BULLS": delta["bulls"],
                    "CHANGE_LU": sum(delta[c] * lu[c] for c in FINAL_21_COHORTS),
                    "CHANGE_CATTLE_SO_2020_EUR": sum(delta[c] * soc[c] for c in FINAL_21_COHORTS),
                    "DAIRY_COWS_PRESENT": frame["dairy_cows"].to_numpy() > 0,
                    "SUCKLER_COWS_PRESENT": frame["suckler_cows"].to_numpy() > 0,
                }
            )
            changes[arm] = row
            ed_rows.append(row)

        # Identity: the two parent arms plus the bull change reproduce the pro-rata arm.
        parts = changes["DAIRY_PARENT"]["CHANGE_CATTLE"] + changes["SUCKLER_PARENT"]["CHANGE_CATTLE"] + change * base["bulls"]
        if not np.allclose(parts, changes["PRO_RATA"]["CHANGE_CATTLE"], atol=1e-6):
            raise AssertionError(f"{year}: dairy + suckler + bull changes do not reproduce the pro-rata arm")

    ed_changes = pd.concat(ed_rows, ignore_index=True)
    for column, base_column in (
        ("CHANGE_CATTLE", "BASE_CATTLE"),
        ("CHANGE_LU", "BASE_LU"),
        ("CHANGE_CATTLE_SO_2020_EUR", "BASE_CATTLE_SO_2020_EUR"),
    ):
        ed_changes[f"{column}_PCT"] = np.where(
            ed_changes[base_column] > 0, 100.0 * ed_changes[column] / ed_changes[base_column], np.nan
        )

    additive = [c for c in ed_changes.columns if c.startswith(("BASE_", "CHANGE_")) and not c.endswith("_PCT")]

    def aggregate(frame: pd.DataFrame, geography: str, key: str | None) -> pd.DataFrame:
        keys = ["ARM", "YEAR"] + ([key] if key else [])
        out = frame.groupby(keys, as_index=False)[additive].sum()
        out = out.rename(columns={key: "GEOGRAPHY_ID"}) if key else out.assign(GEOGRAPHY_ID="IE")
        out.insert(0, "GEOGRAPHY_TYPE", geography)
        for column, base_column in (
            ("CHANGE_CATTLE", "BASE_CATTLE"),
            ("CHANGE_LU", "BASE_LU"),
            ("CHANGE_CATTLE_SO_2020_EUR", "BASE_CATTLE_SO_2020_EUR"),
        ):
            out[f"{column}_PCT"] = np.where(out[base_column] > 0, 100.0 * out[column] / out[base_column], np.nan)
        return out

    weights = crosswalk[["CSOED", "WFD_CATCHMENT_ID", "COLM_CATCHMENT", "ED_CATCHMENT_WEIGHT"]].copy()
    weights["CSOED"] = weights["CSOED"].astype(str)
    weighted = ed_changes.merge(weights, on="CSOED", how="left")
    if weighted["ED_CATCHMENT_WEIGHT"].isna().any():
        raise AssertionError("EDs without catchment weights")
    weighted[additive] = weighted[additive].mul(weighted["ED_CATCHMENT_WEIGHT"], axis=0)

    aggregates = pd.concat(
        [
            aggregate(ed_changes, "COUNTY", "County"),
            aggregate(weighted, "WFD_CATCHMENT", "WFD_CATCHMENT_ID"),
            aggregate(weighted, "COLM_CATCHMENT", "COLM_CATCHMENT"),
            aggregate(ed_changes, "NATIONAL", None),
        ],
        ignore_index=True,
    )
    names = {
        **{str(k): str(v) for k, v in crosswalk[["WFD_CATCHMENT_ID", "WFD_CATCHMENT"]].drop_duplicates().itertuples(index=False)},
    }
    aggregates.insert(
        2,
        "GEOGRAPHY_NAME",
        np.where(
            aggregates["GEOGRAPHY_TYPE"] == "WFD_CATCHMENT",
            aggregates["GEOGRAPHY_ID"].astype(str).map(names),
            np.where(aggregates["GEOGRAPHY_TYPE"] == "NATIONAL", "Ireland", aggregates["GEOGRAPHY_ID"].astype(str)),
        ),
    )
    if aggregates["GEOGRAPHY_NAME"].isna().any():
        raise AssertionError("WFD catchments without a name in the perturbation aggregate")
    national = aggregates.loc[aggregates["GEOGRAPHY_TYPE"] == "NATIONAL"].drop(columns=["GEOGRAPHY_TYPE", "GEOGRAPHY_ID", "GEOGRAPHY_NAME"])
    for geography in ("COUNTY", "WFD_CATCHMENT", "COLM_CATCHMENT"):
        total = aggregates.loc[aggregates["GEOGRAPHY_TYPE"] == geography].groupby(["ARM", "YEAR"])["CHANGE_LU"].sum()
        if not np.allclose(total.sort_index().to_numpy(), national.set_index(["ARM", "YEAR"]).sort_index()["CHANGE_LU"].to_numpy(), rtol=1e-8):
            raise AssertionError(f"{geography} perturbation changes do not sum to the national change")

    # Spatial footprint of each arm.
    footprint = []
    for (arm, year), frame in ed_changes.groupby(["ARM", "YEAR"]):
        loss = -frame["CHANGE_LU"]
        total = loss.sum()
        ranked = np.sort(loss.to_numpy())[::-1]
        top = int(np.ceil(0.10 * len(ranked)))
        followers = -(frame["CHANGE_DXD_FOLLOWERS"] + frame["CHANGE_DXB_FOLLOWERS"] + frame["CHANGE_BXB_FOLLOWERS"])
        parent_flag = {"DAIRY_PARENT": "DAIRY_COWS_PRESENT", "SUCKLER_PARENT": "SUCKLER_COWS_PRESENT"}.get(arm)
        away = float(followers[~frame[parent_flag]].sum() / followers.sum() * 100.0) if parent_flag and followers.sum() > 0 else np.nan
        footprint.append(
            {
                "ARM": arm,
                "YEAR": year,
                "EDS_AFFECTED": int((frame["CHANGE_CATTLE"] < 0).sum()),
                "TOP_DECILE_EDS_SHARE_OF_LU_REDUCTION_PCT": float(ranked[:top].sum() / total * 100.0) if total > 0 else np.nan,
                "FOLLOWERS_REMOVED_IN_EDS_WITHOUT_PARENT_COWS_PCT": away,
            }
        )
    footprint = pd.DataFrame(footprint)
    pivot = ed_changes.pivot_table(index=["YEAR", "CSOED"], columns="ARM", values="CHANGE_LU")
    divergence = (
        pivot.assign(DAIRY_LARGER=pivot["DAIRY_PARENT"] < pivot["SUCKLER_PARENT"])
        .groupby("YEAR")["DAIRY_LARGER"].sum().rename("EDS_WHERE_DAIRY_ARM_REMOVES_MORE_LU")
        .reset_index()
    )
    footprint = footprint.merge(divergence, on="YEAR", how="left")
    national = national.merge(footprint, on=["ARM", "YEAR"], how="left")
    return {
        "utility_perturbation_ed": ed_changes,
        "utility_perturbation_aggregate": aggregates,
        "utility_perturbation_national": national,
    }
