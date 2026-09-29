"""Illustrative livestock-signature perturbation on the frozen baseline.

Not a scenario, forecast or behavioural model, and nothing is rebuilt. A
static endpoint perturbation of the frozen ED cattle system.

Design (agreed; see docs/historical_outputs.md):

* A national reduction (default 30%) of one adult breeding population, dairy
  cows or suckler cows, is allocated pro rata across EDs by their share of that
  population, which is the same as reducing every ED's cows by 30%.
* SIGNATURE method (GOBLIN-Spatial): every linked follower cohort (DxD and DxB
  for dairy, BxB for suckler; 6 age-sex cohorts each) is regenerated from the
  finest valid frozen parent-follower relationship: the ED's own parents; the
  county's where the ED has followers but no parents (COUNTY_RECEIVER); the
  nation's only as a final fallback. Followers stay in their baseline EDs.
* HEADCOUNT attribution benchmark: the national followers-per-parent
  coefficient of each cohort is applied to each ED's adult change, so follower
  change is attributed to the geography of adult cows rather than of followers.
  It is a spatial attribution benchmark, not a feasible alternative ED herd;
  local post-change cohort non-negativity is therefore not imposed.
* Both methods remove the same national number of each follower cohort; the
  difference between them is only where the change lands. Its size is the
  spatial information carried by the ED and county signatures.

Displacement (per arm, year, quantity q in followers, cattle, LU), with
d_i = change_i(SIGNATURE) - change_i(HEADCOUNT) and sum_i d_i = 0:

    TOTAL      = 1/2 sum_i |d_i|                  (at ED, WFD, county scale)
    RECEIVER   = |sum over parent-less EDs of d_i|  (change the benchmark
                 cannot place, because those EDs have no parent cows)
    RATIO      = TOTAL - RECEIVER  (>= 0; within EDs that have parents,
                 caused by follower-per-parent ratios differing from national)
    PURE_RATIO = 1/2 sum over parent EDs |change_i(SIGNATURE) - r_L x adult change_i|
                 with r_L = parent-ED followers / national parents: the
                 displacement if parent-less EDs did not exist (check).

Standard Output coefficients differ by region, so the benchmark also changes
the national SO total: for SO the national method difference is reported and
the half-sum is gross ED difference, not a transfer; it is not decomposed.

The PRO_RATA arm (all 21 cohorts, uniform) is a supplementary reference only.
Livestock units use one fixed schedule; Standard Output the fixed IFS 2020
coefficients by region. Head counts stay fractional (exact transformation).

2020 caveat: 931 EDs report zero dairy cows only in the published 2020 Census,
so 2020 has far more parent-less dairy-follower EDs than any other year. This
raises the 2020 RECEIVER component; 2025 is reported alongside for that reason.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import cohort_origin, parent_follower_multiplier
from goblin_spatial.cattle.annual_age_sex import LSU_COEFFICIENTS
from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS

DEFAULT_CHANGE = -0.30
DEFAULT_YEARS = (2020, 2025)
PARENT_ARMS = ("DAIRY_PARENT", "SUCKLER_PARENT")
SUPPLEMENTARY_ARMS = ("PRO_RATA",)
ARMS = (*PARENT_ARMS, *SUPPLEMENTARY_ARMS)
METHODS = ("SIGNATURE", "HEADCOUNT", "UNIFORM")
ARM_PARENT = {"DAIRY_PARENT": "dairy_cows", "SUCKLER_PARENT": "suckler_cows"}
ARM_ORIGIN = {"DAIRY_PARENT": "DAIRY", "SUCKLER_PARENT": "SUCKLER"}
DXD = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))
FOLLOWERS = (*DXD, *DXB, *BXB)
QUANTITIES = ("FOLLOWERS", "CATTLE", "LU", "CATTLE_SO_2020_EUR")
SUPPORT_CLASSES = ("LOCAL_ED", "COUNTY_RECEIVER", "NATIONAL_ORPHAN")


def arm_followers(arm: str) -> tuple[str, ...]:
    if arm not in PARENT_ARMS:
        raise ValueError(f"parent arm must be one of {PARENT_ARMS}")
    return tuple(c for c in FOLLOWERS if cohort_origin(c) == ARM_ORIGIN[arm])


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
        cohort: np.where(
            region_code.to_numpy() == "381", table.at[cohort, "SOC_EUR_381"], table.at[cohort, "SOC_EUR_382"]
        ).astype(float)
        for cohort in FINAL_21_COHORTS
    }


def perturb_year(frame: pd.DataFrame, arm: str, change: float = DEFAULT_CHANGE) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Signature-aware perturbed head (float) and the support class of each cell.

    Returns (new cohort head, support class per ED x follower cohort). For
    PRO_RATA every cohort is scaled uniformly and the support frame is empty.
    """

    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    if not -1.0 <= change <= 1.0:
        raise ValueError("change must be a proportion between -1 and 1")
    base = frame[list(FINAL_21_COHORTS)].astype(float)
    new = base.copy()
    if arm == "PRO_RATA":
        return new * (1.0 + change), pd.DataFrame(index=frame.index)

    parent = ARM_PARENT[arm]
    new[parent] = base[parent] * (1.0 + change)
    counties = frame["County"].astype(str).to_numpy(dtype=object)
    support = pd.DataFrame(index=frame.index)
    for cohort in arm_followers(arm):
        multiplier, source = parent_follower_multiplier(
            base[parent].to_numpy(), new[parent].to_numpy(), np.rint(base[cohort]).astype(np.int64), counties
        )
        new[cohort] = base[cohort] * multiplier
        support[cohort] = source
    return new, support


def headcount_benchmark(frame: pd.DataFrame, arm: str, change: float = DEFAULT_CHANGE) -> pd.DataFrame:
    """National-coefficient spatial attribution benchmark.

    The returned pseudo-state is used only to obtain the benchmark change
    allocation. It is not a feasible alternative ED herd and is not constrained
    to keep every implied local follower level non-negative.
    """

    base = frame[list(FINAL_21_COHORTS)].astype(float)
    new = base.copy()
    parent = ARM_PARENT[arm]
    parent_change = base[parent] * change
    new[parent] = base[parent] + parent_change
    national_parents = float(base[parent].sum())
    if national_parents <= 0:
        raise AssertionError(f"{arm}: no national parent population")
    for cohort in arm_followers(arm):
        coefficient = float(base[cohort].sum()) / national_parents
        new[cohort] = base[cohort] + coefficient * parent_change
    return new


def _quantities(delta: pd.DataFrame, followers: tuple[str, ...], lu: dict, soc: dict) -> dict[str, pd.Series]:
    return {
        "FOLLOWERS": delta[list(followers)].sum(axis=1),
        "CATTLE": delta.sum(axis=1),
        "LU": sum(delta[c] * lu[c] for c in FINAL_21_COHORTS),
        "CATTLE_SO_2020_EUR": sum(delta[c] * soc[c] for c in FINAL_21_COHORTS),
    }


def run_utility_perturbation(
    ed: pd.DataFrame,
    so_mapping: pd.DataFrame,
    crosswalk: pd.DataFrame,
    years: tuple[int, ...] = DEFAULT_YEARS,
    change: float = DEFAULT_CHANGE,
) -> dict[str, pd.DataFrame]:
    """Run both parent arms by both methods (plus the pro-rata reference)."""

    lu = livestock_unit_schedule()
    weights = crosswalk[["CSOED", "WFD_CATCHMENT_ID", "WFD_CATCHMENT", "ED_CATCHMENT_WEIGHT"]].copy()
    weights["CSOED"] = weights["CSOED"].astype(str)
    wfd_names = weights.drop_duplicates("WFD_CATCHMENT_ID").set_index("WFD_CATCHMENT_ID")["WFD_CATCHMENT"]

    long_rows, comparison_rows, displacement_rows = [], [], []
    for year in years:
        frame = ed.loc[ed["YEAR"] == year].sort_values("CSOED").reset_index(drop=True)
        if frame.empty:
            raise ValueError(f"no ED rows for {year}")
        region = frame["FADN_REGION"].astype(str).str.extract(r"(38[12])")[0]
        if region.isna().any():
            raise AssertionError("EDs without a Standard Output region")
        soc = standard_output_coefficients(so_mapping, region)
        base = frame[list(FINAL_21_COHORTS)].astype(float)
        ids = pd.DataFrame({"YEAR": year, "CSOED": frame["CSOED"].astype(str), "County": frame["County"].astype(str)})
        base_q = {
            "BASE_CATTLE": base.sum(axis=1),
            "BASE_LU": sum(base[c] * lu[c] for c in FINAL_21_COHORTS),
            "BASE_CATTLE_SO_2020_EUR": sum(base[c] * soc[c] for c in FINAL_21_COHORTS),
        }

        for arm in ARMS:
            if arm == "PRO_RATA":
                new, _ = perturb_year(frame, arm, change)
                q = _quantities(new - base, FOLLOWERS, lu, soc)
                long_rows.append(
                    ids.assign(
                        ARM=arm,
                        METHOD="UNIFORM",
                        **base_q,
                        CHANGE_ADULT_COWS=(new - base)[["dairy_cows", "suckler_cows"]].sum(axis=1),
                        **{f"CHANGE_{k}": v for k, v in q.items()},
                    )
                )
                continue

            parent = ARM_PARENT[arm]
            followers = arm_followers(arm)
            signature, support = perturb_year(frame, arm, change)
            headcount = headcount_benchmark(frame, arm, change)
            delta_s, delta_h = signature - base, headcount - base

            # Both methods: identical adult change and identical national change per cohort.
            for cohort in followers:
                target = change * float(base[cohort].sum())
                for label, delta in (("SIGNATURE", delta_s), ("HEADCOUNT", delta_h)):
                    if not np.isclose(delta[cohort].sum(), target, rtol=1e-9, atol=1e-6):
                        raise AssertionError(f"{year} {arm} {label}: national {cohort} change is not {change:+.0%}")
            if not np.allclose(delta_s[parent], delta_h[parent]):
                raise AssertionError("methods must share the adult change")
            untouched = [c for c in FINAL_21_COHORTS if c not in (parent, *followers)]
            if not (np.allclose(delta_s[untouched], 0) and np.allclose(delta_h[untouched], 0)):
                raise AssertionError(f"{arm}: non-targeted cohorts changed")

            q_s = _quantities(delta_s, followers, lu, soc)
            q_h = _quantities(delta_h, followers, lu, soc)
            support_head = {
                f"CHANGE_FOLLOWERS_{role}": sum(delta_s[c].where(support[c] == role, 0.0) for c in followers)
                for role in SUPPORT_CLASSES
            }
            parent_present = base[parent] > 0
            for method, q, extra in (("SIGNATURE", q_s, support_head), ("HEADCOUNT", q_h, {})):
                long_rows.append(
                    ids.assign(
                        ARM=arm,
                        METHOD=method,
                        **base_q,
                        CHANGE_ADULT_COWS=delta_s[parent],
                        **{f"CHANGE_{k}": v for k, v in q.items()},
                        **extra,
                        PARENT_COWS_PRESENT=parent_present.to_numpy(),
                    )
                )

            comparison = ids.assign(ARM=arm, PARENT_COWS_PRESENT=parent_present.to_numpy(), CHANGE_ADULT_COWS=delta_s[parent])
            for key in QUANTITIES:
                comparison[f"SIGNATURE_CHANGE_{key}"] = q_s[key]
                comparison[f"HEADCOUNT_CHANGE_{key}"] = q_h[key]
                comparison[f"DIFFERENCE_{key}"] = q_s[key] - q_h[key]
            comparison_rows.append(comparison)

            # Displacement and its decomposition.
            receiver = ~parent_present
            national_parents = float(base[parent].sum())
            weight_series = {
                "FOLLOWERS": {c: 1.0 for c in followers},
                "CATTLE": {c: 1.0 for c in followers},
                "LU": {c: lu[c] for c in followers},
                "CATTLE_SO_2020_EUR": {c: soc[c] for c in followers},
            }
            # ED position -> catchment weight rows, for aggregating ED differences.
            joined = comparison[["CSOED"]].reset_index().merge(weights, on="CSOED", how="left")
            if joined["ED_CATCHMENT_WEIGHT"].isna().any():
                raise AssertionError("EDs without catchment weights")
            ed_position = joined["index"].to_numpy()
            catchment_weight = joined["ED_CATCHMENT_WEIGHT"].to_numpy()
            for key in QUANTITIES:
                d = q_s[key] - q_h[key]
                # Head and LU coefficients do not vary by place, so both methods
                # remove the same national quantity and d sums to zero. SO
                # coefficients differ by region (381/382), so the benchmark also
                # misstates the national SO change; there the half-sum is not a
                # transfer and no decomposition is reported.
                conserved = key != "CATTLE_SO_2020_EUR"
                national_gap = float(d.sum())
                if conserved and abs(national_gap) > 1e-6 * max(1.0, float(q_s[key].abs().sum())):
                    raise AssertionError(f"{year} {arm} {key}: methods differ in national change")
                total = 0.5 * float(d.abs().sum())
                receiver_part = abs(float(d[receiver].sum())) if conserved else np.nan
                pure_parts = []
                for cohort in followers:
                    local_coefficient = float(base.loc[~receiver, cohort].sum()) / national_parents
                    w = weight_series[key][cohort]
                    pure_parts.append((delta_s[cohort] - local_coefficient * delta_s[parent]) * w)
                pure = 0.5 * float(sum(pure_parts)[~receiver].abs().sum())
                if not conserved:
                    pure = np.nan
                if conserved and receiver_part > total + 1e-6 * max(1.0, total):
                    raise AssertionError(f"{year} {arm} {key}: receiver component exceeds total displacement")
                wfd = pd.DataFrame(
                    {"WFD": joined["WFD_CATCHMENT_ID"].to_numpy(), "d": d.to_numpy()[ed_position] * catchment_weight}
                )
                wfd_total = 0.5 * float(wfd.groupby("WFD")["d"].sum().abs().sum())
                county_total = 0.5 * float(d.groupby(frame["County"]).sum().abs().sum())
                national_change = abs(float(q_s[key].sum()))
                displacement_rows.append(
                    {
                        "YEAR": year,
                        "ARM": arm,
                        "QUANTITY": key,
                        "NATIONAL_CHANGE": float(q_s[key].sum()),
                        "HEADCOUNT_NATIONAL_CHANGE": float(q_h[key].sum()),
                        "NATIONAL_METHOD_DIFFERENCE": national_gap,
                        "CONSERVED_NATIONALLY": conserved,
                        "ED_TOTAL_DISPLACEMENT": total,
                        "ED_RECEIVER_COMPONENT": receiver_part,
                        "ED_RATIO_COMPONENT": total - receiver_part if conserved else np.nan,
                        "ED_PURE_RATIO_DISPLACEMENT": pure,
                        "RECEIVER_SHARE_OF_ED_DISPLACEMENT_PCT": 100.0 * receiver_part / total if conserved and total > 0 else np.nan,
                        "ED_DISPLACEMENT_PCT_OF_NATIONAL_CHANGE": 100.0 * total / national_change if national_change > 0 else np.nan,
                        "WFD_TOTAL_DISPLACEMENT": wfd_total,
                        "WFD_DISPLACEMENT_PCT_OF_NATIONAL_CHANGE": 100.0 * wfd_total / national_change if national_change > 0 else np.nan,
                        "COUNTY_TOTAL_DISPLACEMENT": county_total,
                        "PARENTLESS_EDS_WITH_FOLLOWERS": int((receiver & (base[list(followers)].sum(axis=1) > 0)).sum()),
                    }
                )

    ed_long = pd.concat(long_rows, ignore_index=True)
    for key, base_key in (("CATTLE", "BASE_CATTLE"), ("LU", "BASE_LU"), ("CATTLE_SO_2020_EUR", "BASE_CATTLE_SO_2020_EUR")):
        ed_long[f"CHANGE_{key}_PCT"] = np.where(ed_long[base_key] > 0, 100.0 * ed_long[f"CHANGE_{key}"] / ed_long[base_key], np.nan)
    comparison_ed = pd.concat(comparison_rows, ignore_index=True)

    additive = [c for c in ed_long.columns if c.startswith(("BASE_", "CHANGE_")) and not c.endswith("_PCT")]
    weighted = ed_long.merge(weights, on="CSOED", how="left")
    weighted[additive] = weighted[additive].mul(weighted["ED_CATCHMENT_WEIGHT"], axis=0)

    def aggregate(frame: pd.DataFrame, geography: str, key: str | None) -> pd.DataFrame:
        keys = ["YEAR", "ARM", "METHOD"] + ([key] if key else [])
        out = frame.groupby(keys, as_index=False)[additive].sum()
        out = out.rename(columns={key: "GEOGRAPHY_ID"}) if key else out.assign(GEOGRAPHY_ID="IE")
        out.insert(0, "GEOGRAPHY_TYPE", geography)
        for q, base_key in (("CATTLE", "BASE_CATTLE"), ("LU", "BASE_LU"), ("CATTLE_SO_2020_EUR", "BASE_CATTLE_SO_2020_EUR")):
            out[f"CHANGE_{q}_PCT"] = np.where(out[base_key] > 0, 100.0 * out[f"CHANGE_{q}"] / out[base_key], np.nan)
        return out

    aggregate_table = pd.concat(
        [
            aggregate(weighted, "WFD_CATCHMENT", "WFD_CATCHMENT_ID"),
            aggregate(ed_long, "COUNTY", "County"),
            aggregate(ed_long, "NATIONAL", None),
        ],
        ignore_index=True,
    )
    aggregate_table.insert(
        2,
        "GEOGRAPHY_NAME",
        np.where(
            aggregate_table["GEOGRAPHY_TYPE"] == "WFD_CATCHMENT",
            aggregate_table["GEOGRAPHY_ID"].map(wfd_names),
            np.where(aggregate_table["GEOGRAPHY_TYPE"] == "NATIONAL", "Ireland", aggregate_table["GEOGRAPHY_ID"]),
        ),
    )
    national = aggregate_table.loc[aggregate_table["GEOGRAPHY_TYPE"] == "NATIONAL"]
    for geography in ("WFD_CATCHMENT", "COUNTY"):
        rows = aggregate_table.loc[aggregate_table["GEOGRAPHY_TYPE"] == geography]
        total = rows.groupby(["YEAR", "ARM", "METHOD"])["CHANGE_LU"].sum().sort_index()
        if not np.allclose(total.to_numpy(), national.set_index(["YEAR", "ARM", "METHOD"]).sort_index()["CHANGE_LU"].to_numpy(), rtol=1e-8):
            raise AssertionError(f"{geography} changes do not sum to the national change")

    comparison_cols = [c for c in comparison_ed.columns if c.startswith(("SIGNATURE_", "HEADCOUNT_", "DIFFERENCE_"))] + ["CHANGE_ADULT_COWS"]
    cw = comparison_ed.merge(weights, on="CSOED", how="left")
    cw[comparison_cols] = cw[comparison_cols].mul(cw["ED_CATCHMENT_WEIGHT"], axis=0)
    comparison_wfd = cw.groupby(["YEAR", "ARM", "WFD_CATCHMENT_ID", "WFD_CATCHMENT"], as_index=False)[comparison_cols].sum()

    national_summary = national.drop(columns=["GEOGRAPHY_TYPE", "GEOGRAPHY_ID", "GEOGRAPHY_NAME"]).reset_index(drop=True)
    return {
        "utility_perturbation_ed": ed_long,
        "utility_perturbation_aggregate": aggregate_table,
        "utility_perturbation_national": national_summary,
        "utility_comparison_ed": comparison_ed,
        "utility_comparison_wfd": comparison_wfd,
        "utility_displacement": pd.DataFrame(displacement_rows),
    }
