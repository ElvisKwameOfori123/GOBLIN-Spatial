"""Cattle side of the GOBLIN-Spatial historical baseline.

Stages represented
------------------
01  Reconciled 2020 ED cattle anchor.
02  Annual 2015-2025 ED cattle panel.
05C Biological disaggregation to the 21 GOBLIN cattle cohorts.

The implementation delegates to the already validated cattle modules. This
keeps the scientific allocation mathematics unchanged while establishing the
final v1 module boundary.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.cattle import add_cattle_cohorts, build_cattle_panel
from goblin_spatial.config import SpatialConfig


def _canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def build_cattle_baseline(config: SpatialConfig) -> pd.DataFrame:
    """Build the complete 2015-2025 cattle baseline and 21 cohorts.

    No sheep, land, farm-structure, soil or scenario information is introduced
    here. The returned table retains the validated cattle accounting and is
    ready for one-to-one merge with the independently constructed sheep panel.
    """

    panel = build_cattle_panel(config)
    cattle = add_cattle_cohorts(panel, config)
    cattle = _canonical_order(cattle)

    required = {"YEAR", "CSOED", "TOTAL_CATTLE"}
    missing = sorted(required - set(cattle.columns))
    if missing:
        raise AssertionError(f"cattle baseline missing required fields: {missing}")
    if cattle[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("cattle baseline contains duplicate YEAR-CSOED rows")

    return cattle
