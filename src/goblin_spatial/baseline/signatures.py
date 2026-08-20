"""Stage 09 frozen livestock dependency signatures.

Signatures describe the pre-scenario geography of cattle cohorts relative to
their adult origins. They are accounting relationships used by SC1, not claims
about observed animal movements.
"""

from __future__ import annotations

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.scenario.cohort_response import build_ed_cohort_dependency_profile


def build_signatures(
    baseline: pd.DataFrame,
    config: SpatialConfig,
    *,
    year: int | None = None,
) -> pd.DataFrame:
    """Freeze the ED cattle dependency profile for one scenario baseline year."""

    baseline_year = int(config.base_year if year is None else year)
    if "YEAR" not in baseline.columns:
        raise ValueError("signature construction requires YEAR")

    years = pd.to_numeric(baseline["YEAR"], errors="raise").astype(int)
    selected = baseline.loc[years == baseline_year].copy()
    if len(selected) != config.expected_eds:
        raise AssertionError(
            f"expected {config.expected_eds:,} EDs in signature year {baseline_year}; "
            f"found {len(selected):,}"
        )
    if selected["CSOED"].duplicated().any():
        raise AssertionError("signature baseline contains duplicate CSOED rows")

    signatures = build_ed_cohort_dependency_profile(selected)
    expected_followers = 19  # 21 cattle cohorts minus dairy and suckler adults
    expected_rows = config.expected_eds * expected_followers
    if len(signatures) != expected_rows:
        raise AssertionError(
            f"expected {expected_rows:,} signature rows; found {len(signatures):,}"
        )

    return signatures.sort_values(["CSOED", "COHORT"], kind="stable").reset_index(drop=True)
