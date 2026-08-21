"""SC2 evidence and opportunity science after a frozen principal SC1 result.

SC2 never recomputes livestock or the land released in SC1. Principal SC1 has
already used precomputed 08B agricultural capability as a capacity constraint
and supplies the soil-resolved release columns ``GOBLIN_RELEASED_G1_HA`` to
``GOBLIN_RELEASED_G3_HA``. SC2 carries those hectares forward exactly, attaches
the baseline-matched compact LPIS profile and the independent precomputed 08C
mapped physical-soil context, then applies the mature SC2 v3.1 opportunity and
physical-eligibility science.

08C remains robustness/physical context. It is never blended with 08B and never
changes the frozen SC1 release or the principal Opportunity-v2 score equations.

``PotentialRelease != Opportunity != RealisedConversion``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.land.lpis import add_ed_lpis_context
from goblin_spatial.land.sc2_opportunity import SC2_VERSION, build_sc2_opportunity
from goblin_spatial.soil import add_principal_08c_context


SC1_SOIL_RELEASE_COLUMNS = tuple(f"GOBLIN_RELEASED_G{i}_HA" for i in (1, 2, 3))
SC2_SOIL_RELEASE_COLUMNS = tuple(f"SC2_RELEASED_G{i}_HA" for i in (1, 2, 3))


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
    if not np.allclose(
        frame[list(SC2_SOIL_RELEASE_COLUMNS)].sum(axis=1).to_numpy(dtype=float),
        release_before,
        atol=1e-7,
    ):
        raise AssertionError("SC2 soil release no longer closes to frozen SC1 release")


def prepare_sc2_context(
    sc1_ed: pd.DataFrame,
    *,
    lpis_profile: str | Path | pd.DataFrame,
    baseline_year: int,
    physical_soil_context: str | Path | pd.DataFrame,
    release_column: str = "GOBLIN_RELEASED_GRASSLAND_HA",
    apply_opportunity_science: bool = True,
) -> pd.DataFrame:
    """Build the mature SC2 evidence/opportunity frame from one frozen SC1 run.

    Required scientific invariants
    ------------------------------
    * the SC1 ED release vector is immutable;
    * G1/G2/G3 released hectares are copied from the 08B-constrained SC1 solve;
    * LPIS 2020 is attached only to a 2020 run and LPIS 2025 only to a 2025 run;
    * 08C remains independent mapped physical-soil evidence;
    * mature Opportunity-v2 and Class1-6 eligibility append fields only.

    ``apply_opportunity_science=False`` is retained only for lightweight
    context-level debugging. Principal SC2 runs should use the default ``True``.
    """

    required = {
        "CSOED",
        "County",
        "ALL_GRASSLAND",
        release_column,
        *SC1_SOIL_RELEASE_COLUMNS,
    }
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

    sc1_by_soil = np.column_stack(
        [_numeric(sc1_ed, column) for column in SC1_SOIL_RELEASE_COLUMNS]
    )
    if (sc1_by_soil < -1e-9).any():
        raise ValueError("SC1 soil-resolved release cannot be negative")
    if not np.allclose(sc1_by_soil.sum(axis=1), release_before, atol=1e-7):
        raise AssertionError(
            "SC1 G1/G2/G3 released hectares do not close to frozen ED release"
        )

    out = sc1_ed.copy()
    out["SC2_POTENTIAL_RELEASE_HA"] = release_before
    for source, target in zip(
        SC1_SOIL_RELEASE_COLUMNS,
        SC2_SOIL_RELEASE_COLUMNS,
        strict=True,
    ):
        out[target] = pd.to_numeric(out[source], errors="raise").to_numpy(dtype=float)
    out["SC2_08B_RELEASE_PARTITION_METHOD"] = "FROZEN_SC1_08B_CAPACITY_SOLVE"

    # Agricultural organic-soil evidence is a source-UAA-weighted proxy. It is
    # not an observed joint map of the exact hectares released from livestock.
    if "IFS_PEAT_CUTOVER_UAA_SHARE" in out.columns:
        peat_share = pd.to_numeric(
            out["IFS_PEAT_CUTOVER_UAA_SHARE"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(peat_share)
        peat_share = np.where(valid, np.clip(peat_share, 0.0, 1.0), np.nan)
        out["SC2_08B_PEAT_CUTOVER_RELEASE_CONTEXT_HA_PROXY"] = (
            release_before * peat_share
        )
        out["SC2_08B_PEAT_CUTOVER_CONTEXT_AVAILABLE"] = valid

    out = add_ed_lpis_context(
        out,
        lpis_profile,
        baseline_year=int(baseline_year),
    )
    lpis_year = pd.to_numeric(out["LPIS_PROFILE_YEAR"], errors="raise").astype(int)
    if not lpis_year.eq(int(baseline_year)).all():
        raise AssertionError("SC2 LPIS context does not match selected run baseline year")

    # LPIS peat-grass is parcel context. Multiplying its share by ED release is
    # retained only as an explicitly labelled proxy, not an observed released-
    # peat hectare estimate.
    if "LPIS_PEAT_GRASS_SHARE" in out.columns:
        peat_grass = pd.to_numeric(
            out["LPIS_PEAT_GRASS_SHARE"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(peat_grass)
        peat_grass = np.where(valid, np.clip(peat_grass, 0.0, 1.0), np.nan)
        out["SC2_LPIS_PEAT_GRASS_RELEASE_CONTEXT_HA_PROXY"] = (
            release_before * peat_grass
        )
        out["SC2_LPIS_PEAT_GRASS_CONTEXT_AVAILABLE"] = valid

    if physical_soil_context is None:
        raise ValueError(
            "principal SC2 requires the compact 08C physical-soil profile; "
            "heavy source processing is never triggered automatically"
        )
    out = add_principal_08c_context(out, physical_soil_context)
    out["SC2_PHYSICAL_SOIL_CONTEXT_AVAILABLE"] = True

    _assert_release_invariant(out, release_before, release_column=release_column)

    if apply_opportunity_science:
        out, qa = build_sc2_opportunity(out)
        for key, value in qa.items():
            out[f"SC2_QA_{key}"] = value
        out["SC2_OPPORTUNITY_VERSION"] = SC2_VERSION
        out["SC2_OPPORTUNITY_SCIENCE_APPLIED"] = True
    else:
        out["SC2_OPPORTUNITY_VERSION"] = pd.NA
        out["SC2_OPPORTUNITY_SCIENCE_APPLIED"] = False

    _assert_release_invariant(out, release_before, release_column=release_column)
    out["SC2_CONTEXT_VERSION"] = "3.1"
    return out
