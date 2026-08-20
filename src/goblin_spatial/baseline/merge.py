"""Merge independently validated cattle and sheep baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

MERGE_KEYS = ["YEAR", "CSOED"]
SHARED_IDENTIFIERS = {
    "ELECTORAL_DIVISIONS",
    "ED",
    "County",
    "EDID",
    "CSOED_RAW",
    "EDNAME",
    "COUNTYNAME",
}


def canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the stable YEAR-CSOED order used by the frozen pipeline."""

    return frame.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def merge_livestock(cattle: pd.DataFrame, sheep: pd.DataFrame) -> pd.DataFrame:
    """Join cattle and sheep without recalculating either livestock system.

    Cattle supplies the shared ED/static context. Sheep is authoritative for
    sheep fields. The historical static LSU field is removed because it is not
    an annually reconstructed livestock indicator.
    """

    cattle = canonical_order(cattle)
    sheep = canonical_order(sheep)

    for label, frame in (("cattle", cattle), ("sheep", sheep)):
        missing = [key for key in MERGE_KEYS if key not in frame.columns]
        if missing:
            raise ValueError(f"{label} panel missing merge keys: {missing}")
        if frame[MERGE_KEYS].duplicated().any():
            raise ValueError(f"{label} panel contains duplicate YEAR-CSOED rows")

    if len(cattle) != len(sheep):
        raise AssertionError("cattle and sheep panels have different row counts")
    if not cattle[MERGE_KEYS].equals(sheep[MERGE_KEYS]):
        raise AssertionError("cattle and sheep YEAR-CSOED coverage differs")

    overlap = set(cattle.columns).intersection(sheep.columns) - set(MERGE_KEYS)
    replace_from_sheep = sorted(overlap - SHARED_IDENTIFIERS)
    cattle_base = cattle.drop(columns=[*replace_from_sheep, "LSU"], errors="ignore")
    sheep_keep = [
        column
        for column in sheep.columns
        if column in MERGE_KEYS or column not in SHARED_IDENTIFIERS
    ]
    sheep_keep = list(dict.fromkeys(sheep_keep))

    merged = cattle_base.merge(
        sheep[sheep_keep],
        on=MERGE_KEYS,
        how="inner",
        sort=False,
        validate="one_to_one",
    )
    merged = canonical_order(merged)

    if len(merged) != len(cattle) or len(merged) != len(sheep):
        raise AssertionError("cattle/sheep merge did not preserve the complete panel")
    if "LSU" in merged.columns:
        raise AssertionError("stale baseline LSU survived livestock merge")

    required = {
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        *FINAL_21_COHORTS,
        *GOBLIN_SHEEP_10,
    }
    missing = sorted(required - set(merged.columns))
    if missing:
        raise AssertionError(f"31-cohort livestock merge missing fields: {missing}")
    if len(FINAL_21_COHORTS) + len(GOBLIN_SHEEP_10) != 31:
        raise AssertionError("livestock cohort contract must contain exactly 31 cohorts")

    cattle_sum = merged[FINAL_21_COHORTS].apply(
        pd.to_numeric, errors="raise"
    ).sum(axis=1).to_numpy(dtype=float)
    sheep_sum = merged[GOBLIN_SHEEP_10].apply(
        pd.to_numeric, errors="raise"
    ).sum(axis=1).to_numpy(dtype=float)
    cattle_total = pd.to_numeric(
        merged["TOTAL_CATTLE"], errors="raise"
    ).to_numpy(dtype=float)
    sheep_total = pd.to_numeric(
        merged["TOTAL_SHEEP"], errors="raise"
    ).to_numpy(dtype=float)

    if not np.array_equal(np.rint(cattle_sum).astype(np.int64), np.rint(cattle_total).astype(np.int64)):
        raise AssertionError("merged 21 cattle cohorts do not reproduce TOTAL_CATTLE")
    if not np.array_equal(np.rint(sheep_sum).astype(np.int64), np.rint(sheep_total).astype(np.int64)):
        raise AssertionError("merged 10 sheep cohorts do not reproduce TOTAL_SHEEP")

    return merged
