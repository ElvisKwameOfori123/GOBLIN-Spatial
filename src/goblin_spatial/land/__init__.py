"""Supported land API for the validated baseline and principal SC1-SC3 workflow.

The production land framework is intentionally separated into three roles:

* historical land/farm-structure reconstruction;
* one frozen 2020 ED land context used as neutral spatial evidence;
* downstream SC2 opportunity/eligibility and SC3 target allocation.

Potential release, opportunity and realised conversion are distinct quantities.
The frozen land context never changes livestock allocation. Heavy LPIS, soil and
geometry reconstruction remains an explicit provenance workflow, not a normal
scenario dependency.
"""

from .panel import add_land
from .context import (
    LAND_CONTEXT_CANONICAL_SHA256,
    LAND_CONTEXT_EXPECTED_COLUMNS,
    LAND_CONTEXT_EXPECTED_EDS,
    LAND_CONTEXT_YEAR,
    land_context_sha256,
    read_land_context_table,
    reconstruct_land_context_bytes,
    validate_land_context,
)
from .context_attach import add_frozen_08b_context
from .lpis import add_ed_lpis_context, read_ed_lpis_profile
from .lpis_spatial import build_ed_lpis_profile
from .sc2_context import (
    SC1_SOIL_RELEASE_COLUMNS,
    SC2_SOIL_RELEASE_COLUMNS,
    prepare_sc2_context,
)
from .sc2_opportunity import (
    SC2_VERSION as SC2_OPPORTUNITY_VERSION,
    build_sc2_opportunity,
)
from .sc3_allocation import (
    NATIONAL_DRAINED_ORGANIC_GRASSLAND_HA,
    REWETTING_USE,
    SC3_USES,
    STAGE_A_USES,
    allocate_sc3_targets,
    summarise_sc3_allocation,
)

__all__ = [
    "LAND_CONTEXT_CANONICAL_SHA256",
    "LAND_CONTEXT_EXPECTED_COLUMNS",
    "LAND_CONTEXT_EXPECTED_EDS",
    "LAND_CONTEXT_YEAR",
    "NATIONAL_DRAINED_ORGANIC_GRASSLAND_HA",
    "REWETTING_USE",
    "SC1_SOIL_RELEASE_COLUMNS",
    "SC2_OPPORTUNITY_VERSION",
    "SC2_SOIL_RELEASE_COLUMNS",
    "SC3_USES",
    "STAGE_A_USES",
    "add_ed_lpis_context",
    "add_frozen_08b_context",
    "add_land",
    "allocate_sc3_targets",
    "build_ed_lpis_profile",
    "build_sc2_opportunity",
    "land_context_sha256",
    "prepare_sc2_context",
    "read_ed_lpis_profile",
    "read_land_context_table",
    "reconstruct_land_context_bytes",
    "summarise_sc3_allocation",
    "validate_land_context",
]
