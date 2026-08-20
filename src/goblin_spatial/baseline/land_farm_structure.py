"""Land, crop and farm-structure enrichment for the historical baseline.

This module represents validated Stage 06. The existing land and SE modules
remain the scientific implementations during migration; this file establishes
the final v1 boundary without changing their calculations.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.land import add_land
from goblin_spatial.se import add_se


def add_land_farm_structure(
    livestock: pd.DataFrame,
    config: SpatialConfig,
) -> pd.DataFrame:
    """Attach Stage-06 land, crops, holdings and holder-age indicators.

    Livestock values are inputs to this stage and must not be modified by it.
    The validated component modules retain the exact 2020 ED anchor and annual
    reconstruction rules.
    """

    before = livestock.copy()
    result = add_land(livestock, config)
    result = add_se(result, config)

    key = ["YEAR", "CSOED"]
    if result[key].duplicated().any():
        raise AssertionError("Stage 06 produced duplicate YEAR-CSOED rows")
    if len(result) != len(before):
        raise AssertionError("Stage 06 changed the baseline row count")

    return result.sort_values(key, kind="stable").reset_index(drop=True)
