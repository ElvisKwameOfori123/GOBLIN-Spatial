"""Cross-scale aggregation utilities for validated GOBLIN-Spatial outputs."""

from goblin_spatial.aggregation.catchments import (
    COLM_CATCHMENTS,
    DEFAULT_ADDITIVE_COLUMNS,
    EXPECTED_WFD_CATCHMENTS,
    aggregate_to_catchments,
    aggregate_to_counties,
    aggregate_to_wfd_catchments,
    aggregate_wfd_to_colm,
    build_ed_catchment_crosswalk,
    canonical_catchment_name,
    canonical_wfd_catchment_name,
    to_colm_catchment_name,
    validate_aggregation_closure,
)

__all__ = [
    "COLM_CATCHMENTS",
    "DEFAULT_ADDITIVE_COLUMNS",
    "EXPECTED_WFD_CATCHMENTS",
    "aggregate_to_catchments",
    "aggregate_to_counties",
    "aggregate_to_wfd_catchments",
    "aggregate_wfd_to_colm",
    "build_ed_catchment_crosswalk",
    "canonical_catchment_name",
    "canonical_wfd_catchment_name",
    "to_colm_catchment_name",
    "validate_aggregation_closure",
]
