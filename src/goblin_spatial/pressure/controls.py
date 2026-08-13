"""Frozen and year-specific GOBLIN pasture dry-matter controls.

The cattle study changes livestock populations, not feed-management parameters.
For that principal experiment the repository carries one audited 2020 GOBLIN
per-head pasture-DM profile and reuses it at the selected baseline and future
milestones.  This is explicitly a *fixed-2020 management/feed assumption*; it is
not a claim that future feed coefficients are observed.

Studies that alter productivity, feeding, grazing or grass utilisation can
instead supply an explicit ``YEAR`` x 31-cohort table generated from the
corresponding upstream GOBLIN animal frames.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


EXPECTED_PASTURE_COHORTS = tuple(FINAL_21_COHORTS) + tuple(GOBLIN_SHEEP_10)
VALUE_COLUMN = "PASTURE_DM_T_PER_HEAD_YEAR"


def _validated_profile(frame: pd.DataFrame, *, label: str) -> dict[str, float]:
    required = {"COHORT", VALUE_COLUMN}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} pasture-DM control missing columns: {missing}")
    if frame["COHORT"].duplicated().any():
        duplicated = sorted(frame.loc[frame["COHORT"].duplicated(), "COHORT"].astype(str).unique())
        raise ValueError(f"{label} duplicate pasture-DM cohorts: {duplicated}")

    cohorts = set(frame["COHORT"].astype(str))
    expected = set(EXPECTED_PASTURE_COHORTS)
    missing_cohorts = sorted(expected - cohorts)
    extra_cohorts = sorted(cohorts - expected)
    if missing_cohorts or extra_cohorts:
        raise ValueError(
            f"{label} must contain exactly the 31 GOBLIN-Spatial cohorts; "
            f"missing={missing_cohorts}, extra={extra_cohorts}"
        )

    values = pd.to_numeric(frame[VALUE_COLUMN], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any() or (values < 0).any():
        raise ValueError(f"{label} pasture-DM coefficients must be finite and non-negative")

    return dict(zip(frame["COHORT"].astype(str), values))


def load_pasture_dm_control(
    path: str | Path,
    *,
    required_years: Iterable[int] | None = None,
) -> dict[int, dict[str, float]]:
    """Load either a fixed parameter profile or explicit year-specific controls.

    Accepted contracts
    ------------------
    Fixed profile:
        ``PARAMETER_YEAR, COHORT, PASTURE_DM_T_PER_HEAD_YEAR``.  When
        ``required_years`` is supplied, the same validated per-head profile is
        copied to each requested model year.

    Year-specific profile:
        ``YEAR, COHORT, PASTURE_DM_T_PER_HEAD_YEAR``.  Every requested year must
        be present explicitly and every year must contain exactly 31 cohorts.
    """

    frame = pd.read_csv(path)
    requested = None
    if required_years is not None:
        requested = sorted({int(year) for year in required_years})
        if not requested:
            raise ValueError("required_years cannot be empty")

    if "YEAR" in frame.columns:
        frame["YEAR"] = pd.to_numeric(frame["YEAR"], errors="raise").astype(int)
        if frame[["YEAR", "COHORT"]].duplicated().any():
            raise ValueError("duplicate YEAR-COHORT rows in pasture-DM controls")
        profiles: dict[int, dict[str, float]] = {}
        for year, block in frame.groupby("YEAR", sort=True):
            profiles[int(year)] = _validated_profile(block, label=f"YEAR={int(year)}")
        if requested is not None:
            missing_years = sorted(set(requested) - set(profiles))
            if missing_years:
                raise ValueError(f"pasture-DM controls missing requested years: {missing_years}")
            profiles = {year: profiles[year] for year in requested}
        return profiles

    if "PARAMETER_YEAR" not in frame.columns:
        raise ValueError(
            "pasture-DM control requires either YEAR or PARAMETER_YEAR plus COHORT and "
            f"{VALUE_COLUMN}"
        )

    parameter_years = pd.to_numeric(frame["PARAMETER_YEAR"], errors="raise").astype(int).unique()
    if len(parameter_years) != 1:
        raise ValueError("fixed pasture-DM control must contain exactly one PARAMETER_YEAR")
    parameter_year = int(parameter_years[0])
    profile = _validated_profile(frame, label=f"PARAMETER_YEAR={parameter_year}")

    years = [parameter_year] if requested is None else requested
    # Copy dictionaries so callers cannot mutate one year's profile and thereby
    # silently change all other years.
    return {year: dict(profile) for year in years}


def fixed_parameter_year(path: str | Path) -> int | None:
    """Return the fixed control's parameter year, or ``None`` for explicit YEAR tables."""

    frame = pd.read_csv(path, usecols=lambda column: column in {"YEAR", "PARAMETER_YEAR"})
    if "YEAR" in frame.columns:
        return None
    if "PARAMETER_YEAR" not in frame.columns:
        raise ValueError("pasture-DM control has neither YEAR nor PARAMETER_YEAR")
    values = pd.to_numeric(frame["PARAMETER_YEAR"], errors="raise").astype(int).unique()
    if len(values) != 1:
        raise ValueError("fixed pasture-DM control must contain exactly one PARAMETER_YEAR")
    return int(values[0])
