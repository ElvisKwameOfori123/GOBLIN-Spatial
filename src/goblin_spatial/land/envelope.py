"""Policy-neutral ED opportunity envelope for potentially spared grassland.

This module deliberately stops before land conversion.  It answers a narrower
question than :mod:`goblin_spatial.land.opportunity`: given the hectares that the
livestock/grassland engine identifies as potentially spared, how much of that
released area lies in EDs with evidence relevant to each alternative land use?

The outputs are *screening envelopes*, not mutually exclusive land allocations.
A hectare can therefore appear in several opportunity envelopes at once.  The
land-use-specific envelope columns must never be summed across uses.  Actual
conversion remains a separate policy/scenario decision.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .opportunity import (
    LAND_USES,
    OPPORTUNITY_SCORE_COLUMNS,
    add_ed_land_opportunity_scores,
)


OPPORTUNITY_ENVELOPE_NOTE = (
    "Land-use opportunity envelopes overlap and must not be summed across uses; "
    "score-weighted hectares are screening indices, not realised conversion."
)


def add_spared_land_opportunity_envelope(
    frame: pd.DataFrame,
    *,
    spared_column: str = "POTENTIAL_SPARED_GRASSLAND_HA",
    eligibility_threshold: float = 1e-12,
    attach_scores: bool = True,
) -> pd.DataFrame:
    """Attach overlapping ED opportunity envelopes to spared-grassland results.

    Parameters
    ----------
    frame:
        ED x milestone scenario output.  It must already contain potential
        spared grassland.  When ``attach_scores`` is true, the function also
        derives the transparent ED soil/opportunity scores if they are absent.
    spared_column:
        Potentially spared grassland column produced by the grassland-release
        engine.
    eligibility_threshold:
        A score above this threshold is treated as evidence that the land use
        is eligible for the broad first-stage screen.  The default is strictly
        positive evidence.
    attach_scores:
        If true, derive missing score columns from the attached ED soil profile.

    Returns
    -------
    pandas.DataFrame
        The original rows plus, for every alternative land use:

        ``ELIGIBLE_<USE>_SPARED_GRASSLAND_HA``
            Potentially spared hectares in EDs with a positive opportunity
            score.  This is an upper screening envelope, not allocated area.

        ``SCORE_WEIGHTED_<USE>_OPPORTUNITY_HA``
            Potentially spared hectares multiplied by the 0-1 opportunity
            score.  This is an index-weighted diagnostic, not physical hectares
            converted to the land use.
    """

    if not np.isfinite(float(eligibility_threshold)) or float(eligibility_threshold) < 0:
        raise ValueError("eligibility_threshold must be finite and non-negative")

    required = {"CSOED", "MILESTONE_YEAR", spared_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"opportunity envelope missing columns: {missing}")

    out = frame.copy()
    if attach_scores and any(
        column not in out.columns for column in OPPORTUNITY_SCORE_COLUMNS.values()
    ):
        out = add_ed_land_opportunity_scores(out)

    missing_scores = sorted(
        column
        for column in OPPORTUNITY_SCORE_COLUMNS.values()
        if column not in out.columns
    )
    if missing_scores:
        raise ValueError(
            "opportunity envelope requires ED opportunity scores: "
            f"{missing_scores}"
        )

    spared = pd.to_numeric(out[spared_column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(spared)).any() or (spared < -1e-10).any():
        raise ValueError("potential spared grassland must be finite and non-negative")
    spared = np.maximum(spared, 0.0)

    threshold = float(eligibility_threshold)
    for land_use in LAND_USES:
        score_column = OPPORTUNITY_SCORE_COLUMNS[land_use]
        score = pd.to_numeric(out[score_column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(score)).any() or ((score < -1e-12) | (score > 1.0 + 1e-12)).any():
            raise ValueError(f"{score_column} must lie in [0, 1]")
        score = np.clip(score, 0.0, 1.0)

        eligible = score > threshold
        out[f"ELIGIBLE_{land_use}_SPARED_GRASSLAND_HA"] = np.where(
            eligible, spared, 0.0
        )
        out[f"SCORE_WEIGHTED_{land_use}_OPPORTUNITY_HA"] = spared * score
        out[f"{land_use}_OPPORTUNITY_ELIGIBLE"] = eligible

    return out


def summarise_spared_land_opportunity_envelope(
    frame: pd.DataFrame,
    *,
    spared_column: str = "POTENTIAL_SPARED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Return a national milestone summary of overlapping opportunity envelopes."""

    required = {"CSOED", "MILESTONE_YEAR", spared_column}
    for land_use in LAND_USES:
        required.update(
            {
                f"ELIGIBLE_{land_use}_SPARED_GRASSLAND_HA",
                f"SCORE_WEIGHTED_{land_use}_OPPORTUNITY_HA",
                f"{land_use}_OPPORTUNITY_ELIGIBLE",
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"opportunity-envelope summary missing columns: {missing}")

    rows: list[dict[str, object]] = []
    for year, block in frame.groupby("MILESTONE_YEAR", sort=True):
        spared = pd.to_numeric(block[spared_column], errors="raise")
        row: dict[str, object] = {
            "MILESTONE_YEAR": int(year),
            "POTENTIAL_SPARED_GRASSLAND_HA": float(spared.sum()),
            "EDS_WITH_SPARED_GRASSLAND": int((spared > 1e-9).sum()),
            "OPPORTUNITY_ENVELOPE_NOTE": OPPORTUNITY_ENVELOPE_NOTE,
        }
        for land_use in LAND_USES:
            eligible_column = f"ELIGIBLE_{land_use}_SPARED_GRASSLAND_HA"
            weighted_column = f"SCORE_WEIGHTED_{land_use}_OPPORTUNITY_HA"
            flag_column = f"{land_use}_OPPORTUNITY_ELIGIBLE"
            row[eligible_column] = float(
                pd.to_numeric(block[eligible_column], errors="raise").sum()
            )
            row[weighted_column] = float(
                pd.to_numeric(block[weighted_column], errors="raise").sum()
            )
            row[f"EDS_ELIGIBLE_{land_use}"] = int(
                (block[flag_column].astype(bool) & (spared > 1e-9)).sum()
            )
        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        "MILESTONE_YEAR", kind="stable"
    ).reset_index(drop=True)
