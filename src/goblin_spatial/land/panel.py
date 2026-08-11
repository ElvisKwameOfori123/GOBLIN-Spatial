"""Annual ED land reconstruction around the fixed 2020 CSO baseline."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig


def add_land(master: pd.DataFrame, config: SpatialConfig) -> pd.DataFrame:
    """Add annual land indicators without changing livestock.

    Contract
    --------
    * 2020 ED land values remain exactly unchanged;
    * annual regional CSO land statistics control temporal change;
    * AREA_FARMED is the ED row total;
    * ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA = AREA_FARMED;
    * no land component may be negative.
    """

    raise NotImplementedError(
        "Validated land reconstruction logic has not yet been migrated."
    )
