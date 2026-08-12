"""Describe adult-to-young cattle relationships at Electoral Division level.

These diagnostics are deliberately descriptive. They help identify breeding,
rearing and receiver geographies before a future scenario engine changes adult
herd sizes. The resulting ratios are *not* automatically treated as fixed future
coefficients: national GOBLIN/COHORTS biology remains the authority for future
cohort totals, while GOBLIN-Spatial governs their spatial representation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS


DXD_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))

CALF_COHORTS = tuple(c for c in FINAL_21_COHORTS if "_calves_" in c)
ONE_TO_TWO_COHORTS = tuple(c for c in FINAL_21_COHORTS if "_less_2_yr" in c)
OVER_TWO_COHORTS = tuple(c for c in FINAL_21_COHORTS if "_more_2_yr" in c)

REQUIRED_CATTLE_COLUMNS = (
    "CSOED",
    "DAIRY_COW",
    "OTHER_COW",
    "OTHER_CATTLE",
    "TOTAL_CATTLE",
    "bulls",
    *DXD_COHORTS,
    *DXB_COHORTS,
    *BXB_COHORTS,
)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="raise").astype(float)
    if (~np.isfinite(values)).any() or (values < 0).any():
        raise AssertionError(f"invalid non-negative cattle values in {column}")
    return values


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.astype(float)
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    active = denominator > 0
    out.loc[active] = numerator.loc[active].astype(float) / denominator.loc[active]
    return out


def _classify_roles(
    dairy: pd.Series,
    suckler: pd.Series,
    other_cattle: pd.Series,
    total_cattle: pd.Series,
) -> pd.Series:
    role = pd.Series("NO_CATTLE", index=dairy.index, dtype="object")

    receiver = (dairy == 0) & (suckler == 0) & (other_cattle > 0)
    suckler_only = (dairy == 0) & (suckler > 0)
    dairy_only = (dairy > 0) & (suckler == 0)
    mixed = (dairy > 0) & (suckler > 0)

    role.loc[receiver] = "RECEIVER_REARING"
    role.loc[suckler_only] = "SUCKLER_BREEDING"
    role.loc[dairy_only] = "DAIRY_BREEDING"
    role.loc[mixed] = "MIXED_BREEDING"

    unresolved = (total_cattle > 0) & (role == "NO_CATTLE")
    role.loc[unresolved] = "OTHER_CATTLE_LOCATION"
    return role


def build_cattle_dynamics(baseline: pd.DataFrame) -> pd.DataFrame:
    """Build an ED-level cattle dynamics diagnostic table.

    The input should be one already-selected baseline state (normally 2020 or
    2025) after GOBLIN cattle cohorts have been added. The output preserves one
    row per ED and adds quantities that describe:

    * adult breeding structure;
    * DxD/DxB dairy-origin and BxB suckler-origin follower structure;
    * age progression containers within the 21-cohort representation;
    * explicit evidence of receiver/rearing EDs where young cattle are present
      without the corresponding adult-cow origin.

    No cattle count in the supplied baseline is modified.
    """

    missing = [c for c in REQUIRED_CATTLE_COLUMNS if c not in baseline.columns]
    if missing:
        raise ValueError(f"cattle dynamics missing required columns: {missing}")
    if baseline["CSOED"].duplicated().any():
        raise AssertionError("cattle dynamics requires one row per CSOED")

    out = baseline.copy()
    original_columns = list(out.columns)

    dairy = _numeric(out, "DAIRY_COW")
    suckler = _numeric(out, "OTHER_COW")
    other = _numeric(out, "OTHER_CATTLE")
    total = _numeric(out, "TOTAL_CATTLE")

    dxd = out[list(DXD_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1).astype(float)
    dxb = out[list(DXB_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1).astype(float)
    bxb = out[list(BXB_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1).astype(float)
    bulls = _numeric(out, "bulls")

    dairy_followers = dxd + dxb
    adult_cows = dairy + suckler

    out["DYN_ADULT_COWS"] = adult_cows
    out["DYN_DXD_FOLLOWERS"] = dxd
    out["DYN_DXB_FOLLOWERS"] = dxb
    out["DYN_DAIRY_ORIGIN_FOLLOWERS"] = dairy_followers
    out["DYN_BXB_FOLLOWERS"] = bxb
    out["DYN_BULLS"] = bulls

    out["DYN_CATTLE_UNDER_1"] = (
        out[list(CALF_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    )
    out["DYN_CATTLE_1_2"] = (
        out[list(ONE_TO_TWO_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    )
    out["DYN_CATTLE_2_PLUS_PRE_ADULT"] = (
        out[list(OVER_TWO_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    )

    out["DYN_DXD_PER_DAIRY_COW"] = _ratio(dxd, dairy)
    out["DYN_DXB_PER_DAIRY_COW"] = _ratio(dxb, dairy)
    out["DYN_DAIRY_FOLLOWERS_PER_DAIRY_COW"] = _ratio(dairy_followers, dairy)
    out["DYN_BXB_PER_SUCKLER_COW"] = _ratio(bxb, suckler)
    out["DYN_BULLS_PER_ADULT_COW"] = _ratio(bulls, adult_cows)
    out["DYN_DXD_SHARE_DAIRY_ORIGIN"] = _ratio(dxd, dairy_followers)
    out["DYN_DXB_SHARE_DAIRY_ORIGIN"] = _ratio(dxb, dairy_followers)

    out["DYN_HAS_DAIRY_ORIGIN_FOLLOWERS"] = dairy_followers > 0
    out["DYN_HAS_BXB_FOLLOWERS"] = bxb > 0
    out["DYN_RECEIVER_REARING_CANDIDATE"] = (
        (dairy == 0) & (suckler == 0) & (other > 0)
    )
    out["DYN_DAIRY_ORIGIN_WITHOUT_DAIRY_COW"] = (dairy == 0) & (dairy_followers > 0)
    out["DYN_BXB_WITHOUT_SUCKLER_COW"] = (suckler == 0) & (bxb > 0)
    out["DYN_ED_CATTLE_ROLE"] = _classify_roles(dairy, suckler, other, total)

    reconstructed_other = dxd + dxb + bxb + bulls
    if not np.array_equal(
        np.rint(reconstructed_other).astype(np.int64),
        np.rint(other).astype(np.int64),
    ):
        raise AssertionError(
            "cattle dynamics input does not close: DxD + DxB + BxB + bulls != OTHER_CATTLE"
        )

    # Defensive guarantee: this module is diagnostic only.
    for column in original_columns:
        if not out[column].equals(baseline[column]):
            raise AssertionError(f"cattle dynamics changed baseline column {column}")

    return out
