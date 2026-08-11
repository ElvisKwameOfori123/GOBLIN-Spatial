"""GOBLIN sheep cohort disaggregation."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig


def add_sheep_cohorts(sheep_panel: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Express the fixed ED sheep population in the 10 GOBLIN sheep cohorts.

    The function may enrich composition, but it must never change TOTAL_SHEEP.
    """

    raise NotImplementedError(
        "Validated GOBLIN sheep cohort logic has not yet been migrated."
    )
