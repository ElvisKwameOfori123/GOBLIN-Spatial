"""Describe breeding-to-follower sheep relationships at ED level."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


LOWLAND_COHORTS = tuple(c for c in GOBLIN_SHEEP_10 if c.startswith("Lowland "))
UPLAND_COHORTS = tuple(c for c in GOBLIN_SHEEP_10 if c.startswith("Upland "))
EWE_COHORTS = ("Lowland ewes", "Upland ewes")
RAM_COHORTS = ("Lowland ram", "Upland ram")
FOLLOWER_COHORTS = tuple(c for c in GOBLIN_SHEEP_10 if c not in (*EWE_COHORTS, *RAM_COHORTS))

REQUIRED_SHEEP_COLUMNS = ("CSOED", "TOTAL_SHEEP", *GOBLIN_SHEEP_10)


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    active = denominator > 0
    out.loc[active] = numerator.loc[active].astype(float) / denominator.loc[active]
    return out


def build_sheep_dynamics(baseline: pd.DataFrame) -> pd.DataFrame:
    """Build descriptive ED sheep relationships without changing the baseline.

    The table identifies lowland/upland breeding structure and the local ratio
    between follower cohorts and ewes. These are diagnostics for understanding
    ED structure before scenario design; they are not assumed to be fixed
    biological coefficients for future years.
    """

    missing = [c for c in REQUIRED_SHEEP_COLUMNS if c not in baseline.columns]
    if missing:
        raise ValueError(f"sheep dynamics missing required columns: {missing}")
    if baseline["CSOED"].duplicated().any():
        raise AssertionError("sheep dynamics requires one row per CSOED")

    out = baseline.copy()
    original_columns = list(out.columns)

    for column in ("TOTAL_SHEEP", *GOBLIN_SHEEP_10):
        values = pd.to_numeric(out[column], errors="raise").astype(float)
        if (~np.isfinite(values)).any() or (values < 0).any():
            raise AssertionError(f"invalid non-negative sheep values in {column}")

    lowland = out[list(LOWLAND_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    upland = out[list(UPLAND_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    ewes = out[list(EWE_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    rams = out[list(RAM_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    followers = out[list(FOLLOWER_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    total = pd.to_numeric(out["TOTAL_SHEEP"], errors="raise").astype(float)

    out["DYN_LOWLAND_SHEEP"] = lowland
    out["DYN_UPLAND_SHEEP"] = upland
    out["DYN_EWES"] = ewes
    out["DYN_RAMS"] = rams
    out["DYN_SHEEP_FOLLOWERS"] = followers
    out["DYN_SHEEP_FOLLOWERS_PER_EWE"] = _ratio(followers, ewes)
    out["DYN_LOWLAND_SHARE"] = _ratio(lowland, total)
    out["DYN_UPLAND_SHARE"] = _ratio(upland, total)

    role = pd.Series("NO_SHEEP", index=out.index, dtype="object")
    role.loc[(lowland > 0) & (upland == 0)] = "LOWLAND_ONLY"
    role.loc[(lowland == 0) & (upland > 0)] = "UPLAND_ONLY"
    role.loc[(lowland > 0) & (upland > 0)] = "MIXED_LOWLAND_UPLAND"
    out["DYN_ED_SHEEP_ROLE"] = role

    cohort_total = out[list(GOBLIN_SHEEP_10)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    if not np.array_equal(
        np.rint(cohort_total).astype(np.int64),
        np.rint(total).astype(np.int64),
    ):
        raise AssertionError("sheep dynamics input does not close: 10 cohorts != TOTAL_SHEEP")

    for column in original_columns:
        if not out[column].equals(baseline[column]):
            raise AssertionError(f"sheep dynamics changed baseline column {column}")

    return out
