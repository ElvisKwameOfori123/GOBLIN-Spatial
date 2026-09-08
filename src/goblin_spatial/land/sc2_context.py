"""SC2 Colm-direct released-land characterisation after a frozen SC1 result.

SC2 never recomputes livestock and never changes the authoritative ED released-
land vector produced by SC1. The legacy 08B/G1-G2-G3 capability representation
is not part of the new production decision chain.

SC2 attaches two distinct baseline evidence layers:

* Colm mapped physical soil: physical resource evidence;
* LPIS 2020: current agricultural-use and management context.

The frozen SC1 release is then proportionally characterised across Colm's seven
physical-soil categories. Optional future-use eligibility rules may be applied,
but only when they are explicit, complete, versioned and evidence-backed.
Opportunity is kept conceptually separate from eligibility. This module exposes
transparent LPIS context and does not create arbitrary composite opportunity
scores.

``PotentialRelease != PhysicalResource != Eligibility != Opportunity != RealisedConversion``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.land.colm_lpis_context import (
    attach_colm_physical_context,
    read_colm_lpis_context,
)
from goblin_spatial.land.context import LAND_CONTEXT_YEAR, PHYSICAL_AREA_COLUMNS
from goblin_spatial.land.lpis import add_ed_lpis_context
from goblin_spatial.land.sc2_colm_direct import (
    COLM_RELEASED_AREA_COLUMNS,
    build_colm_direct_sc2_physical,
)

SC2_CONTEXT_VERSION = "COLM_DIRECT_1.1"


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"SC2 context missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def _assert_release_invariant(
    frame: pd.DataFrame,
    release_before: np.ndarray,
    *,
    release_column: str,
) -> None:
    release_after = _numeric(frame, release_column)
    if not np.array_equal(release_before, release_after):
        raise AssertionError("SC2 changed the frozen SC1 release vector")
    if not all(column in frame.columns for column in COLM_RELEASED_AREA_COLUMNS):
        raise AssertionError("SC2 Colm physical-resource partition is incomplete")
    partition = (
        frame[list(COLM_RELEASED_AREA_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .sum(axis=1)
        .to_numpy(dtype=float)
    )
    if not np.allclose(partition, release_before, atol=1e-7):
        raise AssertionError("SC2 Colm physical-resource partition no longer closes to SC1")


def prepare_sc2_context(
    sc1_ed: pd.DataFrame,
    *,
    land_context: str | Path | pd.DataFrame,
    baseline_year: int,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
    eligibility_rules: Mapping[str, Mapping[str, float]] | None = None,
    rule_version: str | None = None,
    evidence_note: str | None = None,
    apply_opportunity_science: bool | None = None,
) -> pd.DataFrame:
    """Build Colm-direct SC2 from a frozen SC1 ED result.

    ``apply_opportunity_science`` is retained only as a compatibility argument
    for old callers. The Colm-direct architecture does not apply the legacy
    composite Opportunity-v2 equations. LPIS and other context remain explicit
    until a future-use opportunity rule has a documented evidence base.
    """

    baseline_year = int(baseline_year)
    if baseline_year != LAND_CONTEXT_YEAR:
        raise ValueError(
            "Colm-direct SC2 is currently supported only for baseline_year=2020. "
            "A validated frozen 2025 LPIS/physical-soil context has not been supplied."
        )

    required = {"CSOED", "County", "ALL_GRASSLAND", release_column}
    missing = sorted(required - set(sc1_ed.columns))
    if missing:
        raise ValueError(f"SC2 context missing frozen SC1 columns: {missing}")
    if sc1_ed["CSOED"].duplicated().any():
        raise ValueError("SC2 endpoint context requires one row per ED")

    release_before = _numeric(sc1_ed, release_column).copy()
    grass = _numeric(sc1_ed, "ALL_GRASSLAND")
    if (release_before < -1e-9).any():
        raise ValueError("frozen SC1 release cannot be negative")
    if (release_before - grass > 1e-7).any():
        raise ValueError("frozen SC1 release exceeds ED ALL_GRASSLAND capacity")
    release_before = np.maximum(release_before, 0.0)

    context = read_colm_lpis_context(land_context)
    out = sc1_ed.copy()
    out["SC2_POTENTIAL_RELEASE_HA"] = release_before

    # LPIS is current agricultural-use context only. It never changes release.
    lpis_columns = [
        column
        for column in context.columns
        if column == "CSOED" or column.startswith("LPIS_")
    ]
    out = add_ed_lpis_context(
        out,
        context[lpis_columns].copy(),
        baseline_year=LAND_CONTEXT_YEAR,
    )
    lpis_year = pd.to_numeric(out["LPIS_PROFILE_YEAR"], errors="raise").astype(int)
    if not lpis_year.eq(LAND_CONTEXT_YEAR).all():
        raise AssertionError("SC2 LPIS context does not match the frozen 2020 runtime")

    # Colm physical soil is attached directly as its seven mapped categories.
    # Do not call the legacy 08C helper here because that helper additionally
    # derives synthetic SG1/SG2/SG3 classes and a farmed-peat fraction.
    physical_context = context[["CSOED", *PHYSICAL_AREA_COLUMNS]].copy()
    out = attach_colm_physical_context(out, physical_context)

    out = build_colm_direct_sc2_physical(
        out,
        rules=eligibility_rules,
        rule_version=rule_version,
        evidence_note=evidence_note,
        release_column=release_column,
    )

    # Transparent LPIS evidence. These are context descriptors, not realised
    # conversion and not composite opportunity scores.
    if "LPIS_CLAIMED_GRASS_TO_MODEL_GRASS_RATIO" in out.columns:
        out["SC2_LPIS_GRASS_COVERAGE_RATIO"] = pd.to_numeric(
            out["LPIS_CLAIMED_GRASS_TO_MODEL_GRASS_RATIO"], errors="coerce"
        )
    for source, destination in (
        ("LPIS_LOW_INPUT_GRASS_SHARE", "SC2_LPIS_LOW_INPUT_GRASS_SHARE"),
        ("LPIS_PEAT_GRASS_SHARE", "SC2_LPIS_PEAT_GRASS_SHARE"),
        ("LPIS_RIPARIAN_GRASS_SHARE", "SC2_LPIS_RIPARIAN_GRASS_SHARE"),
        ("LPIS_COMMONAGE_GRASS_SHARE", "SC2_LPIS_COMMONAGE_GRASS_SHARE"),
        ("LPIS_ORGANIC_GRASS_SHARE", "SC2_LPIS_ORGANIC_GRASS_SHARE"),
    ):
        if source in out.columns:
            out[destination] = pd.to_numeric(out[source], errors="coerce")

    out["SC2_COLM_PHYSICAL_CONTEXT_AVAILABLE"] = True
    out["SC2_LPIS_CONTEXT_AVAILABLE"] = out.get(
        "LPIS_GRASS_CONTEXT_AVAILABLE",
        pd.Series(False, index=out.index),
    ).fillna(False).astype(bool)
    out["SC2_LAND_CONTEXT_YEAR"] = LAND_CONTEXT_YEAR
    out["SC2_LAND_CONTEXT_ROLE"] = "COLM_PHYSICAL_SOIL_PLUS_LPIS_BASELINE_EVIDENCE"
    out["SC2_G1_G2_G3_USED"] = False
    out["SC2_SYNTHETIC_SOIL_GROUPS_USED"] = False
    out["SC2_FARMED_PEAT_FRACTION_ASSUMPTION_USED"] = False
    out["SC2_OPPORTUNITY_STATUS"] = "CONTEXT_EVIDENCE_ONLY_NO_ARBITRARY_COMPOSITE"
    out["SC2_REWETTING_CAPACITY_STATUS"] = (
        "NOT_DERIVED_FROM_SOIL_ALONE_REQUIRES_VALIDATED_DRAINED_ORGANIC_AG_EVIDENCE"
    )
    out["SC2_CONTEXT_VERSION"] = SC2_CONTEXT_VERSION

    _assert_release_invariant(out, release_before, release_column=release_column)
    return out
