"""Land, crop and farm-structure enrichment for the historical baseline.

This module represents validated Stage 06. The existing land and SE modules
remain the scientific implementations during migration; this file establishes
the final v1 boundary without changing their calculations.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.land import add_land
from goblin_spatial.land.panel import LAND_COLUMNS
from goblin_spatial.se import add_se
from goblin_spatial.se.panel import SE_COLUMNS


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

    # The finished livestock reconstruction intentionally exposes livestock
    # variables only. Hydrate the fixed 2020 CSO land/structure anchor here so
    # the historical land and SE modules can reconstruct 2015-2025 on the same
    # YEAR x CSOED backbone. These seed values are not treated as annual data.
    seed_columns = [*LAND_COLUMNS, *SE_COLUMNS]
    missing_seed = [column for column in seed_columns if column not in livestock.columns]
    result = livestock.copy()
    if missing_seed:
        anchor = pd.read_csv(config.files["cso_ed_2020"], dtype={"CSOED": str})
        required = {"CSOED", *missing_seed}
        missing_anchor = sorted(required - set(anchor.columns))
        if missing_anchor:
            raise ValueError(
                f"2020 CSO anchor missing land/structure fields: {missing_anchor}"
            )
        if anchor["CSOED"].duplicated().any():
            raise AssertionError("2020 CSO anchor contains duplicate CSOED rows")
        seed = anchor[["CSOED", *missing_seed]].copy()
        seed["CSOED"] = seed["CSOED"].astype(str)
        result["CSOED"] = result["CSOED"].astype(str)
        result = result.merge(seed, on="CSOED", how="left", validate="many_to_one")
        if result[missing_seed].isna().any().any():
            raise AssertionError("failed to attach complete 2020 land/structure anchor")

    result = add_land(result, config)
    result = add_se(result, config)

    key = ["YEAR", "CSOED"]
    if result[key].duplicated().any():
        raise AssertionError("Stage 06 produced duplicate YEAR-CSOED rows")
    if len(result) != len(before):
        raise AssertionError("Stage 06 changed the baseline row count")

    return result.sort_values(key, kind="stable").reset_index(drop=True)
