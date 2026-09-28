"""Cattle side of the GOBLIN-Spatial historical baseline.

Stages represented
------------------
01  Published 2020 ED cattle anchor, unchanged.
02  CSO annual 2015-2025 ED cattle reconstruction.
03  AAA10 age-sex disaggregation with DAFM/AIM spatial prior.
04  Biological/genetic disaggregation to the 21 GOBLIN cattle cohorts.

The scientific allocation mathematics remains in the validated cattle modules.
This wrapper defines the v1 cattle boundary and adds final contract checks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS, add_cattle_cohorts
from goblin_spatial.config import SpatialConfig


def _canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def build_cattle_baseline(config: SpatialConfig) -> pd.DataFrame:
    """Build the complete 2015-2025 cattle baseline and 21 cohorts.

    No sheep, land, farm-structure, soil or scenario information is introduced
    here. The returned table is ready for one-to-one merge with the independently
    constructed sheep baseline.
    """

    panel, _ = build_annual_ed_panel(config)
    age_sex = build_annual_age_sex_panel(config, panel)
    cattle = add_cattle_cohorts(age_sex, config)
    cattle = _canonical_order(cattle)

    required = {"YEAR", "CSOED", "TOTAL_CATTLE", *FINAL_21_COHORTS}
    missing = sorted(required - set(cattle.columns))
    if missing:
        raise AssertionError(f"cattle baseline missing required fields: {missing}")
    if len(FINAL_21_COHORTS) != 21:
        raise AssertionError("cattle baseline contract must contain exactly 21 cohorts")
    if cattle[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("cattle baseline contains duplicate YEAR-CSOED rows")

    cohort_values = cattle[FINAL_21_COHORTS].apply(
        pd.to_numeric, errors="raise"
    ).to_numpy(dtype=float)
    totals = pd.to_numeric(cattle["TOTAL_CATTLE"], errors="raise").to_numpy(dtype=float)
    if (cohort_values < 0).any() or (totals < 0).any():
        raise AssertionError("cattle baseline contains negative animal counts")
    if not np.array_equal(
        np.rint(cohort_values.sum(axis=1)).astype(np.int64),
        np.rint(totals).astype(np.int64),
    ):
        raise AssertionError("21 cattle cohorts do not reproduce TOTAL_CATTLE exactly")

    expected_rows = config.expected_eds * (config.end_year - config.start_year + 1)
    if len(cattle) != expected_rows:
        raise AssertionError(
            f"expected {expected_rows:,} cattle ED-year rows; found {len(cattle):,}"
        )
    if cattle["CSOED"].nunique() != config.expected_eds:
        raise AssertionError("cattle baseline ED coverage changed")

    return cattle
