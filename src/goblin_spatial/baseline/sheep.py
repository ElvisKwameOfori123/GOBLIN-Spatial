"""Sheep side of the GOBLIN-Spatial historical baseline.

Stages represented
------------------
03_0 DAFM county sheep drift/control stage.
03A  County/region sheep reconciliation.
03B  County-to-ED annual sheep panel.
05A  Annual DAFM breed-composition controls.
05B  ED sheep breed/type enrichment.
05D  Biological disaggregation to the 10 GOBLIN sheep cohorts.

The current compatibility entry point delegates to the validated package
implementation. The final v1 migration must explicitly regression-test the
03_0 DAFM dependency before the legacy sheep internals are retired. No new
03_0 formula is introduced in this wrapper.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.sheep import add_sheep_cohorts, build_sheep_panel


def _canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True)


def build_sheep_baseline(config: SpatialConfig) -> pd.DataFrame:
    """Build the complete 2015-2025 sheep baseline and 10 cohorts.

    Population and spatial controls remain CSO/AAA09/DAFM controlled; GOBLIN
    relationships are used only for biological cohort subdivision. This wrapper
    does not alter the existing sheep mathematics.
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
