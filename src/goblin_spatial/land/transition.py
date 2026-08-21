"""Resolve the controlling released-land column for transition analysis."""

from __future__ import annotations

import pandas as pd

from goblin_spatial.land.envelope import add_spared_land_opportunity_envelope, summarise_spared_land_opportunity_envelope
from goblin_spatial.land.targets import allocate_spared_land_to_cumulative_targets, summarise_land_target_allocation


AUTHORITATIVE_RELEASE_COLUMN = "GOBLIN_RELEASED_GRASSLAND_HA"
DIAGNOSTIC_RELEASE_COLUMN = "POTENTIAL_SPARED_GRASSLAND_HA"


def transition_release_column(frame: pd.DataFrame) -> str:
    """Prefer the GOBLIN-controlled release; otherwise use the internal diagnostic."""
    if AUTHORITATIVE_RELEASE_COLUMN in frame.columns:
        return AUTHORITATIVE_RELEASE_COLUMN
    if DIAGNOSTIC_RELEASE_COLUMN in frame.columns:
        return DIAGNOSTIC_RELEASE_COLUMN
    raise ValueError(
        "transition analysis requires GOBLIN_RELEASED_GRASSLAND_HA or "
        "POTENTIAL_SPARED_GRASSLAND_HA"
    )


def add_transition_land_opportunity_envelope(frame: pd.DataFrame, **kwargs) -> pd.DataFrame:
    column = transition_release_column(frame)
    return add_spared_land_opportunity_envelope(frame, spared_column=column, **kwargs)


def summarise_transition_land_opportunity_envelope(frame: pd.DataFrame) -> pd.DataFrame:
    column = transition_release_column(frame)
    return summarise_spared_land_opportunity_envelope(frame, spared_column=column)


def allocate_transition_land_targets(frame: pd.DataFrame, targets, **kwargs) -> pd.DataFrame:
    column = transition_release_column(frame)
    return allocate_spared_land_to_cumulative_targets(frame, targets, spared_column=column, **kwargs)


def summarise_transition_land_targets(frame: pd.DataFrame) -> pd.DataFrame:
    column = transition_release_column(frame)
    return summarise_land_target_allocation(frame, spared_column=column)
