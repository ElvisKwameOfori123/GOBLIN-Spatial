"""Supported land API for the Colm-direct GOBLIN-Spatial workflow.

The active scientific chain is:

* historical land/farm-structure reconstruction;
* soil-independent SC1 livestock transition and released-land geography;
* Colm physical-soil + LPIS SC2 resource characterisation and eligibility;
* SC3 joint target feasibility on finite ED x Colm-soil resource cells;
* optional post-SC3 spatial-flexibility analysis for the same national end use.

Legacy 08B/G1-G2-G3 helpers remain importable only for benchmark/provenance work
and are not part of the Colm-direct production decision chain.
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
from .colm_lpis_context import (
    COLM_PHYSICAL_SHARE_COLUMNS,
    attach_colm_physical_context,
    read_colm_lpis_context,
)
from .colm_rules import load_colm_eligibility_control
from .context_attach import add_frozen_08b_context
from .lpis import add_ed_lpis_context, read_ed_lpis_profile
from .lpis_spatial import build_ed_lpis_profile
from .rewetting_capacity import (
    attach_rewetting_capacity,
    load_rewetting_capacity_control,
)
from .sc2_colm_direct import (
    COLM_PHYSICAL_CATEGORIES,
    COLM_RELEASED_AREA_COLUMNS,
    COLM_STAGE_A_USES,
    add_colm_direct_eligibility,
    add_colm_released_soil_resource,
    build_colm_direct_sc2_physical,
    validate_colm_eligibility_rules,
)
from .sc2_context import SC2_CONTEXT_VERSION, prepare_sc2_context
from .sc3_colm_allocation import (
    REWETTING_USE,
    SC3_COLM_VERSION,
    SC3_USES,
    STAGE_A_USES,
    allocate_colm_sc3_targets,
    summarise_colm_sc3_allocation,
)
from .sc3_feasible_geographies import (
    DEFAULT_SEED as SC3_FEASIBLE_GEOGRAPHY_DEFAULT_SEED,
    FLEX_VERSION as SC3_FEASIBLE_GEOGRAPHY_VERSION,
    FeasibleGeographyEnsemble,
    exact_colm_sc3_ed_use_bounds,
    infer_rewetting_capacity_columns,
    sample_colm_sc3_feasible_geographies,
)

__all__ = [
    "COLM_PHYSICAL_CATEGORIES",
    "COLM_PHYSICAL_SHARE_COLUMNS",
    "COLM_RELEASED_AREA_COLUMNS",
    "COLM_STAGE_A_USES",
    "LAND_CONTEXT_CANONICAL_SHA256",
    "LAND_CONTEXT_EXPECTED_COLUMNS",
    "LAND_CONTEXT_EXPECTED_EDS",
    "LAND_CONTEXT_YEAR",
    "REWETTING_USE",
    "SC2_CONTEXT_VERSION",
    "SC3_COLM_VERSION",
    "SC3_FEASIBLE_GEOGRAPHY_DEFAULT_SEED",
    "SC3_FEASIBLE_GEOGRAPHY_VERSION",
    "SC3_USES",
    "STAGE_A_USES",
    "FeasibleGeographyEnsemble",
    "add_colm_direct_eligibility",
    "add_colm_released_soil_resource",
    "add_ed_lpis_context",
    "add_frozen_08b_context",
    "add_land",
    "allocate_colm_sc3_targets",
    "attach_colm_physical_context",
    "attach_rewetting_capacity",
    "build_colm_direct_sc2_physical",
    "build_ed_lpis_profile",
    "exact_colm_sc3_ed_use_bounds",
    "infer_rewetting_capacity_columns",
    "land_context_sha256",
    "load_colm_eligibility_control",
    "load_rewetting_capacity_control",
    "prepare_sc2_context",
    "read_colm_lpis_context",
    "read_ed_lpis_profile",
    "read_land_context_table",
    "reconstruct_land_context_bytes",
    "sample_colm_sc3_feasible_geographies",
    "summarise_colm_sc3_allocation",
    "validate_colm_eligibility_rules",
    "validate_land_context",
]
