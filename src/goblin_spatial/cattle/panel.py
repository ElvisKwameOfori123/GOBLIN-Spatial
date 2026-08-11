"""CSO cattle baseline and annual ED cattle-panel construction.

This module will contain the validated logic currently represented by the
reference cattle stages: 2020 county reconciliation/age-sex allocation and the
2015-2025 annual ED panel. Cattle is deliberately independent of sheep.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig


def build_cattle_panel(config: SpatialConfig) -> pd.DataFrame:
    """Build the CSO-controlled annual cattle ED panel.

    Contract
    --------
    * 2020 is the fixed ED cattle spatial anchor.
    * annual official county controls determine non-2020 cattle totals.
    * the output must close exactly to all cattle controls.

    The validated research implementation is being migrated into this module.
    """

    raise NotImplementedError(
        "Cattle reference logic has not yet been migrated into the modular API."
    )
