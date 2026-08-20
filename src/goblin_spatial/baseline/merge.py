"""Merge independently validated cattle and sheep baselines."""

from __future__ import annotations

import pandas as pd

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
    if len(merged) != len(cattle) or len(merged) != len(sheep):
        raise AssertionError("cattle/sheep merge did not preserve the complete panel")
    if "LSU" in merged.columns:
        raise AssertionError("stale baseline LSU survived livestock merge")

    return canonical_order(merged)
