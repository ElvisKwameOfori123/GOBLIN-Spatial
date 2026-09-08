"""SC2 spatial response-potential context after a frozen SC1 result.

SC2 never recomputes livestock and never changes the authoritative ED released-
land vector produced by SC1. It attaches two distinct 2020 evidence layers:

* Colm mapped physical soil, describing the released physical resource;
* LPIS, describing current agricultural-use and management context.

The frozen SC1 release is proportionally characterised across the seven physical
soil categories. Optional future-use eligibility rules are applied only when
they are explicit, complete, versioned and evidence-backed. Opportunity remains
conceptually separate from eligibility and no arbitrary composite score is
created here.

Release != PhysicalResource != Eligibility != Opportunity != Allocation != Adoption.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.land.colm_lpis_context import (
    LAND_CONTEXT_YEAR,
    PHYSICAL_AREA_COLUMNS,
    attach_colm_physical_context,
    read_colm_lpis_context,
)
from goblin_spatial.land.lpis import add_ed_lpis_context
from goblin_spatial.land.sc2_colm_direct import (
    COLM_RELEASED_AREA_COLUMNS,
    build_colm_direct_sc2_physical,
)

SC2_CONTEXT_VERSION = "COLM_DIRECT_1.2"


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
        raise AssertionError("SC2 physical-resource partition is incomplete")
    partition = (
        frame[list(COLM_RELEASED_AREA_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .sum(axis=1)
        .to_numpy(dtype=float)
    )
    if not np.allclose(partition, release_before, atol=1e-7):
        raise AssertionError("SC2 physical-resource partition no longer closes to SC1")


def prepare_sc2_context(
    sc1_ed: pd.DataFrame,
    *,
    land_context: str | Path | pd.DataFrame,
    baseline_year: int,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
    eligibility_rules: Mapping[str, Mapping[str, float]] | None = None,
    rule_version: str | None = None,
    evidence_note: str | None = None,
) -> pd.DataFrame:
    """Build SC2 from a frozen SC1 ED result and frozen 2020 land context."""

    baseline_year = int(baseline_year)
    if baseline_year != LAND_CONTEXT_YEAR:
        raise ValueError(
            "SC2 is currently supported only for baseline_year=2020. "
            "A validated frozen 2025 land context has not been supplied."
        )

    required = {"CSOED", "County", "ALL_GRASSLAND", release_column}
    missing = sorted(required - set(sc1_ed.columns))
    if missing:
        raise ValueError(f"SC2 context missing frozen SC1 columns: {missing}")
    if sc1_ed["CSOED"].duplicated().any():
        raise ValueError("SC2 context requires one row per ED")

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

    lpis_columns = [
        column for column in context.columns if column == "CSOED" or column.startswith("LPIS_")
    ]
    out = add_ed_lpis_context(
        out,
        context[lpis_columns].copy(),
        baseline_year=LAND_CONTEXT_YEAR,
    )
    lpis_year = pd.to_numeric(out["LPIS_PROFILE_YEAR"], errors="raise").astype(int)
    if not lpis_year.eq(LAND_CONTEXT_YEAR).all():
        raise AssertionError("SC2 LPIS context does not match the frozen 2020 runtime")

    physical_context = context[["CSOED", *PHYSICAL_AREA_COLUMNS]].copy()
    out = attach_colm_physical_context(out, physical_context)
    out = build_colm_direct_sc2_physical(
        out,
        rules=eligibility_rules,
        rule_version=rule_version,
        evidence_note=evidence_note,
        release_column=release_column,
    )

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
    out["SC2_OPPORTUNITY_STATUS"] = "CONTEXT_EVIDENCE_ONLY_NO_ARBITRARY_COMPOSITE"
    out["SC2_REWETTING_CAPACITY_STATUS"] = (
        "REQUIRES_VALIDATED_DRAINED_ORGANIC_AGRICULTURAL_EVIDENCE"
    )
    out["SC2_CONTEXT_VERSION"] = SC2_CONTEXT_VERSION

    _assert_release_invariant(out, release_before, release_column=release_column)
    return out
