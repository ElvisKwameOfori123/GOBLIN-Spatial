"""GOBLIN cattle cohort disaggregation."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig


def add_cattle_cohorts(cattle_panel: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Express the fixed ED cattle population in the 21 GOBLIN cattle cohorts.

    The GOBLIN cohort structure determines biological subdivision only. This
    function must never change the CSO ED, county or national cattle population.
    """

    raise NotImplementedError(
        "Validated GOBLIN cattle cohort logic has not yet been migrated."
    )
