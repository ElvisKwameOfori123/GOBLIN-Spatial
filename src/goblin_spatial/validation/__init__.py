"""Final scientific validation for a GOBLIN-Spatial build."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import SpatialConfig
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

LAND_COLUMNS = ["AREA_FARMED", "ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA"]
SE_COLUMNS = [
    "AVERAGE_SIZE_OF_HOLDINGS",
    "AGRICULTURAL_HOLDINGS",
    "AVERAGE_AGE_OF_HOLDER",
    "MEDIAN_AGE_OF_HOLDER",
]
BASELINE_LOCK_COLUMNS = [*SE_COLUMNS, *LAND_COLUMNS]


def validate_master(
    master: pd.DataFrame, config: SpatialConfig
) -> dict[str, float | int]:
    """Validate dimensions, cohort closure, land accounting and the 2020 lock."""

    expected_years = set(range(config.start_year, config.end_year + 1))
    expected_rows = config.expected_eds * len(expected_years)
    if len(master) != expected_rows:
        raise AssertionError(
            f"expected {expected_rows:,} rows, found {len(master):,}"
        )
    if master["CSOED"].nunique() != config.expected_eds:
        raise AssertionError(f"expected {config.expected_eds:,} EDs")
    if set(master["YEAR"].unique()) != expected_years:
        raise AssertionError("build years do not match the configured period")
    if master[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED rows in final master")

    required = [
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        *FINAL_21_COHORTS,
        *GOBLIN_SHEEP_10,
        *BASELINE_LOCK_COLUMNS,
    ]
    missing = [column for column in required if column not in master.columns]
    if missing:
        raise ValueError(f"final master missing required columns: {missing}")

    cattle_diff = master[FINAL_21_COHORTS].sum(axis=1) - master["TOTAL_CATTLE"]
    sheep_diff = master[GOBLIN_SHEEP_10].sum(axis=1) - master["TOTAL_SHEEP"]
    if int(cattle_diff.abs().max()) != 0:
        raise AssertionError(
            "21 GOBLIN cattle cohorts do not close to TOTAL_CATTLE"
        )
    if int(sheep_diff.abs().max()) != 0:
        raise AssertionError(
            "10 GOBLIN sheep cohorts do not close to TOTAL_SHEEP"
        )

    nonnegative = [
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        *FINAL_21_COHORTS,
        *GOBLIN_SHEEP_10,
        *LAND_COLUMNS,
    ]
    if (master[nonnegative] < -1e-9).any().any():
        raise AssertionError(
            "final master contains negative livestock or land values"
        )

    land_diff = (
        master["ALL_GRASSLAND"]
        + master["TOTAL_CEREALS"]
        + master["OTHER_CROPS_HA"]
        - master["AREA_FARMED"]
    )
    max_land_diff = float(land_diff.abs().max())
    if max_land_diff > 1e-6:
        raise AssertionError("final ED land accounting does not close")

    baseline_path = config.files["cso_ed_2020"]
    if not baseline_path.exists():
        raise FileNotFoundError(baseline_path)
    baseline = pd.read_csv(baseline_path)[
        ["CSOED", *BASELINE_LOCK_COLUMNS]
    ].copy()
    current = master.loc[
        master["YEAR"] == config.base_year,
        ["CSOED", *BASELINE_LOCK_COLUMNS],
    ].copy()
    lock = baseline.merge(
        current,
        on="CSOED",
        how="inner",
        validate="one_to_one",
        suffixes=("_BASE", "_AFTER"),
    )
    if len(lock) != config.expected_eds:
        raise AssertionError("2020 baseline lock does not cover all EDs")

    max_2020_change = 0.0
    for column in BASELINE_LOCK_COLUMNS:
        difference = np.abs(
            pd.to_numeric(lock[f"{column}_BASE"], errors="raise").to_numpy(
                dtype=float
            )
            - pd.to_numeric(lock[f"{column}_AFTER"], errors="raise").to_numpy(
                dtype=float
            )
        )
        max_2020_change = max(
            max_2020_change, float(difference.max())
        )
    if max_2020_change != 0.0:
        raise AssertionError(
            f"2020 land/SE lock changed by up to {max_2020_change}"
        )

    # Diagnostic only. The reported 2020 average-size field is preserved and
    # is not forced to equal AREA_FARMED / AGRICULTURAL_HOLDINGS.
    base_2020 = master.loc[master["YEAR"] == config.base_year]
    implied_size = (
        base_2020["AREA_FARMED"] / base_2020["AGRICULTURAL_HOLDINGS"]
    )
    average_size_gap = float(
        (
            base_2020["AVERAGE_SIZE_OF_HOLDINGS"] - implied_size
        ).abs().max()
    )

    return {
        "rows": int(len(master)),
        "eds": int(master["CSOED"].nunique()),
        "years": int(len(expected_years)),
        "max_cattle_cohort_diff": int(cattle_diff.abs().max()),
        "max_sheep_cohort_diff": int(sheep_diff.abs().max()),
        "max_land_accounting_diff_ha": max_land_diff,
        "max_2020_lock_change": max_2020_change,
        "max_2020_reported_vs_implied_average_size_gap_ha": average_size_gap,
    }
