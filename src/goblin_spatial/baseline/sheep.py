"""Sheep side of the GOBLIN-Spatial historical baseline.

Stages represented
------------------
03A  AAA09 detailed-region to corrected county sheep controls.
03B  Corrected county-to-ED annual sheep panel.
05A  Annual DAFM breed-composition controls.
05B  ED sheep breed/type enrichment.
05D  Biological disaggregation to the 10 GOBLIN sheep cohorts.

The production sheep population remains controlled by the CSO 2020 ED anchor
and the raw AAA09 regional hierarchy. DAFM breed anchors supply composition
only. The separate DAFM county-total dataset is retained for independent
validation and does not replace the production sheep population.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.sheep import add_sheep_cohorts, build_sheep_panel


def _canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def build_sheep_baseline(config: SpatialConfig) -> pd.DataFrame:
    """Build the complete 2015-2025 sheep baseline and 10 cohorts.

    The population/spatial hierarchy is CSO/AAA09 controlled. DAFM breed data
    enrich composition without altering sheep totals, and GOBLIN relationships
    are used only for biological cohort subdivision.
    """

    panel = _canonical_order(build_sheep_panel(config))
    sheep = add_sheep_cohorts(panel, config)
    sheep = _canonical_order(sheep)

    required = {"YEAR", "CSOED", "TOTAL_SHEEP"}
    missing = sorted(required - set(sheep.columns))
    if missing:
        raise AssertionError(f"sheep baseline missing required fields: {missing}")
    if sheep[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("sheep baseline contains duplicate YEAR-CSOED rows")

    return sheep
