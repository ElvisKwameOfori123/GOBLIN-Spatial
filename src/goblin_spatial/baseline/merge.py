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


def merge_livestock(
    cattle: pd.DataFrame,
    sheep: pd.DataFrame,
    ed_anchor: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join cattle and sheep on the complete study ED spine.

    Every study ED must exist in every year even when it has zero cattle, zero
    sheep, or both. Species absence is represented by zero counts, never by a
    missing ED row. When the 2020 CSO ED anchor is supplied it is authoritative
    for the ED universe and static naming fields; the livestock panels must
    cover that universe exactly in every year.

    The historical static LSU field is removed because it is not an annually
    reconstructed livestock indicator.
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

    anchor = None
    if ed_anchor is not None:
        anchor = ed_anchor.copy()
        if "CSOED" not in anchor.columns:
            raise ValueError("ED anchor missing CSOED")
        anchor["CSOED"] = anchor["CSOED"].astype(str)
        if anchor["CSOED"].duplicated().any():
            raise AssertionError("ED anchor contains duplicate CSOED rows")
        expected_eds = set(anchor["CSOED"])
        years = sorted(pd.to_numeric(cattle["YEAR"], errors="raise").astype(int).unique())
        for label, frame in (("cattle", cattle), ("sheep", sheep)):
            for year in years:
                got = set(
                    frame.loc[frame["YEAR"] == year, "CSOED"].astype(str)
                )
                if got != expected_eds:
                    missing = sorted(expected_eds - got)
                    extra = sorted(got - expected_eds)
                    raise AssertionError(
                        f"{label} {year} ED coverage differs from the CSO study spine; "
                        f"missing={missing[:10]}, extra={extra[:10]}"
                    )

    overlap = set(cattle.columns).intersection(sheep.columns) - set(MERGE_KEYS)
    replace_from_sheep = sorted(overlap - SHARED_IDENTIFIERS)
    cattle_base = cattle.drop(columns=[*replace_from_sheep, "LSU"], errors="ignore")
    # Shared identifiers come from cattle where cattle carries them and from
    # sheep otherwise, so no identifier is lost when one side is leaner.
    # Where both carry one, they must agree.
    for column in sorted(SHARED_IDENTIFIERS & set(cattle.columns) & set(sheep.columns)):
        if not cattle[column].astype(str).equals(sheep[column].astype(str)):
            raise AssertionError(f"cattle and sheep disagree on identifier {column}")
    sheep_keep = [
        column
        for column in sheep.columns
        if column in MERGE_KEYS
        or column not in SHARED_IDENTIFIERS
        or column not in cattle.columns
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

    if anchor is not None:
        anchor_ids = [
            column
            for column in SHARED_IDENTIFIERS
            if column in anchor.columns
        ]
        lookup = anchor.set_index("CSOED")
        merged["CSOED"] = merged["CSOED"].astype(str)
        for column in anchor_ids:
            canonical = merged["CSOED"].map(lookup[column])
            if canonical.isna().any():
                raise AssertionError(
                    f"canonical ED identifier {column} is missing after anchor mapping"
                )
            if column in merged.columns:
                existing = merged[column]
                comparable = existing.notna() & canonical.notna()
                left = existing.loc[comparable].astype(str).str.strip()
                right = canonical.loc[comparable].astype(str).str.strip()
                if not left.equals(right):
                    raise AssertionError(
                        f"livestock merge disagrees with CSO ED anchor on {column}"
                    )
            merged[column] = canonical.to_numpy()

        # Static identifiers must not vary by year for the same ED.
        for column in anchor_ids:
            if merged.groupby("CSOED")[column].nunique(dropna=False).max() != 1:
                raise AssertionError(
                    f"ED identifier {column} varies across years"
                )
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
