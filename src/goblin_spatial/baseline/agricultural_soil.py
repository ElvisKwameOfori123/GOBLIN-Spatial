"""Stage 08B agricultural-capability soil enrichment.

Cathal/NFS soil capability is a scenario-ready interpretation layer. It does
not participate in cattle, sheep, crop or land reconstruction and it does not
determine the SC1 livestock transition.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.soil.context_v2 import (
    add_ed_agricultural_soil,
    build_ed_agricultural_soil_profile,
)


def build_agricultural_soil_profile(
    source: str | Path | pd.DataFrame,
) -> pd.DataFrame:
    """Build the validated ED G1/G2/G3 capability profile from the NFS source."""

    return build_ed_agricultural_soil_profile(source)


def add_agricultural_soil(
    baseline: pd.DataFrame,
    config: SpatialConfig,
    *,
    profile: str | Path | pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach Stage-08B soil context without changing historical activities.

    If an ED profile is not supplied explicitly, the configured compact profile
    is used when present. Otherwise the frozen NFS source is aggregated first.
    ``ALL_GRASSLAND`` remains the authoritative hectare total and is merely
    partitioned by the capability shares.
    """

    if profile is None:
        compact = config.files.get("agricultural_soil_profile")
        if compact is not None and compact.exists():
            profile = compact
        else:
            source = config.files.get("agricultural_soil_source")
            if source is None:
                raise KeyError("configuration is missing agricultural_soil_source")
            if not source.exists():
                raise FileNotFoundError(source)
            profile = build_agricultural_soil_profile(source)

    protected = baseline.copy()
    enriched = add_ed_agricultural_soil(baseline, profile)

    common = [column for column in protected.columns if column in enriched.columns]
    if not protected[common].equals(enriched[common]):
        raise AssertionError("Stage 08B changed a pre-existing baseline value")
    if len(enriched) != len(baseline):
        raise AssertionError("Stage 08B changed the baseline row count")

    return enriched
