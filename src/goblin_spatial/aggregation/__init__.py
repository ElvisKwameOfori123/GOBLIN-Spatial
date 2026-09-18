"""Cross-scale aggregation utilities for validated GOBLIN-Spatial outputs."""

from goblin_spatial.aggregation.catchments import (
    COLM_CATCHMENTS,
    DEFAULT_ADDITIVE_COLUMNS,
    aggregate_to_catchments,
    aggregate_to_counties,
    build_ed_catchment_crosswalk,
    canonical_catchment_name,
    validate_aggregation_closure,
)

__all__ = [
    "COLM_CATCHMENTS",
    "DEFAULT_ADDITIVE_COLUMNS",
    "aggregate_to_catchments",
    "aggregate_to_counties",
    "build_ed_catchment_crosswalk",
    "canonical_catchment_name",
    "validate_aggregation_closure",
]
