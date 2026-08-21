"""Baseline-year selection for livestock dynamics and future scenarios."""

from __future__ import annotations

import pandas as pd


SUPPORTED_SCENARIO_BASE_YEARS = (2020, 2025)


def select_baseline_year(
    panel: pd.DataFrame,
    baseline_year: int,
    *,
    expected_eds: int | None = None,
) -> pd.DataFrame:
    """Return one validated ED state for a selectable scenario base year.

    GOBLIN-Spatial retains 2020 as the Census/structural anchor, while allowing
    either 2020 or 2025 to serve as the starting livestock state for a future
    scenario study. The function only selects and validates a state; it never
    modifies livestock values.

    Parameters
    ----------
    panel:
        Annual ED panel containing at least ``YEAR`` and ``CSOED``.
    baseline_year:
        Scenario starting year. Currently 2020 or 2025.
    expected_eds:
        Optional exact ED-count assertion (2,857 in the Irish application).
    """

    if baseline_year not in SUPPORTED_SCENARIO_BASE_YEARS:
        raise ValueError(
            f"baseline_year must be one of {SUPPORTED_SCENARIO_BASE_YEARS}; "
            f"received {baseline_year}"
        )

    missing = [column for column in ("YEAR", "CSOED") if column not in panel.columns]
    if missing:
        raise ValueError(f"baseline selector missing required columns: {missing}")

    years = pd.to_numeric(panel["YEAR"], errors="raise").astype(int)
    selected = panel.loc[years == baseline_year].copy()
    if selected.empty:
        raise ValueError(f"panel contains no rows for baseline year {baseline_year}")

    if selected["CSOED"].isna().any():
        raise AssertionError(f"{baseline_year} baseline contains missing CSOED values")
    if selected["CSOED"].duplicated().any():
        raise AssertionError(f"{baseline_year} baseline contains duplicate CSOED rows")

    if expected_eds is not None:
        if len(selected) != expected_eds or selected["CSOED"].nunique() != expected_eds:
            raise AssertionError(
                f"{baseline_year} baseline must contain exactly {expected_eds:,} EDs"
            )

    return selected.sort_values("CSOED", kind="stable").reset_index(drop=True)
