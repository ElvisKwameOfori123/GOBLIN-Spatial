"""Annual ED social-economic reconstruction around the fixed 2020 baseline."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig


def add_se(master: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Add farm-structure and holder-age indicators.

    Current SE indicators
    ---------------------
    * AGRICULTURAL_HOLDINGS
    * AVERAGE_SIZE_OF_HOLDINGS
    * AVERAGE_AGE_OF_HOLDER
    * MEDIAN_AGE_OF_HOLDER

    Contract
    --------
    * 2020 ED values remain exactly unchanged;
    * non-2020 values are controlled reconstructions from official FSS/Census
      structural and demographic controls;
    * this module must not alter livestock or land values.
    """

    raise NotImplementedError(
        "Validated SE reconstruction logic has not yet been migrated."
    )
