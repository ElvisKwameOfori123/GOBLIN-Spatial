"""CSO sheep hierarchy and annual ED sheep-panel construction.

The sheep module is independent of cattle. It owns the validated region ->
county -> ED reconciliation and the DAFM composition enrichment used before
GOBLIN sheep cohort disaggregation.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig


def build_sheep_panel(config: SpatialConfig) -> pd.DataFrame:
    """Build the CSO-controlled annual sheep ED panel.

    Contract
    --------
    * annual regional sheep controls are authoritative at region level;
    * county totals are reconciled within regions;
    * ED totals are reconciled within counties;
    * 2020 ED geography is the spatial anchor;
    * sheep totals must close exactly at every required level.

    The validated research implementation is being migrated into this module.
    """

    raise NotImplementedError(
        "Sheep reference logic has not yet been migrated into the modular API."
    )
