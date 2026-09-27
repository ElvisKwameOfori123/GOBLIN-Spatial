"""Separate national GOBLIN calibration layer for the 21 cattle cohorts.

The input is the completed CSO-controlled 21-cohort panel. It is never modified.
For 2015-2020, each cohort is scaled nationally to the corresponding COHORTS
head count using one common factor across all EDs, with Hamilton rounding to
preserve the ED spatial distribution as closely as possible while matching the
national target exactly.

COHORTS ends in 2020. For 2021-2025 there is no national GOBLIN/COHORTS target,
so the CSO cohort values are carried through unchanged with factor 1.0.

This module therefore produces a model-calibrated derivative, not a replacement
for the CSO historical reconstruction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS, _goblin_value, _load_goblin
from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate

GOBLIN_CALIBRATION_YEARS = tuple(range(2015, 2021))
CSO_ONLY_YEARS = tuple(range(2021, 2026))
PROVENANCE_GOBLIN = "GOBLIN_COHORTS_NATIONAL_CALIBRATION"
PROVENANCE_CSO = "CSO_NO_GOBLIN_COHORT_TARGET"


def _checked_integer_target(value: float, cohort: str, year: int) -> int:
    """Return a whole-head COHORTS target, failing on non-head-like values."""

    if not np.isfinite(value) or value < 0:
        raise AssertionError(f"{cohort} {year}: invalid COHORTS national value")
    target = int(np.rint(value))
    if abs(float(value) - target) > 1e-6:
        raise AssertionError(
            f"{cohort} {year}: COHORTS national value is not an integer head count"
        )
    return target


def build_goblin_calibrated_cattle(
    config: SpatialConfig,
    cohort_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return calibrated panel and factor table without modifying the source."""

    required = {"YEAR", "CSOED", *FINAL_21_COHORTS}
    missing = sorted(required - set(cohort_panel.columns))
    if missing:
        raise ValueError(f"21-cohort cattle panel missing required columns: {missing}")

    expected_rows = config.expected_eds * 11
    if len(cohort_panel) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} cohort-panel rows")
    if cohort_panel[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR x CSOED rows in cohort panel")
    if set(cohort_panel["YEAR"].unique()) != set(range(2015, 2026)):
        raise AssertionError("cohort panel years are not exactly 2015-2025")

    for cohort in FINAL_21_COHORTS:
        values = pd.to_numeric(cohort_panel[cohort], errors="raise")
        rounded = np.rint(values.to_numpy(dtype=float))
        if np.max(np.abs(values.to_numpy(dtype=float) - rounded)) > 1e-8:
            raise AssertionError(f"{cohort}: non-integer CSO cohort values")
        if (rounded < 0).any():
            raise AssertionError(f"{cohort}: negative CSO cohort values")

    source = cohort_panel.copy(deep=True)
    calibrated = cohort_panel.copy(deep=True)
    goblin = _load_goblin(config.files["goblin_cohorts"])

    factor_rows: list[dict] = []

    for year in range(2015, 2026):
        idx = calibrated.index[calibrated["YEAR"] == year]

        for cohort in FINAL_21_COHORTS:
            model_values = source.loc[idx, cohort].to_numpy(dtype=np.int64)
            model_total = int(model_values.sum())

            if year in GOBLIN_CALIBRATION_YEARS:
                target = _checked_integer_target(
                    _goblin_value(goblin, cohort, year), cohort, year
                )
                if model_total == 0 and target > 0:
                    raise AssertionError(
                        f"{cohort} {year}: positive COHORTS target with zero CSO support"
                    )

                if target == 0:
                    allocation = np.zeros(len(model_values), dtype=np.int64)
                elif model_total > 0:
                    allocation = hamilton_allocate(model_values.astype(float), target)
                else:
                    allocation = np.zeros(len(model_values), dtype=np.int64)

                factor = float(target / model_total) if model_total > 0 else 1.0
                provenance = PROVENANCE_GOBLIN
                target_value = target
            else:
                allocation = model_values.copy()
                factor = 1.0
                provenance = PROVENANCE_CSO
                target_value = np.nan

            calibrated.loc[idx, cohort] = allocation
            factor_rows.append(
                {
                    "YEAR": year,
                    "COHORT": cohort,
                    "CSO_MODEL_TOTAL": model_total,
                    "COHORTS_TARGET": target_value,
                    "FACTOR": factor,
                    "PROVENANCE": provenance,
                }
            )

    for cohort in FINAL_21_COHORTS:
        calibrated[cohort] = pd.to_numeric(
            calibrated[cohort], errors="raise"
        ).astype(np.int64)

    calibrated["GOBLIN_CALIBRATION_PROVENANCE"] = np.where(
        calibrated["YEAR"].isin(GOBLIN_CALIBRATION_YEARS),
        PROVENANCE_GOBLIN,
        PROVENANCE_CSO,
    )
    calibrated["GOBLIN_21_CATTLE_COHORT_TOTAL"] = calibrated[
        FINAL_21_COHORTS
    ].sum(axis=1)

    factors = pd.DataFrame(factor_rows)

    if not cohort_panel.equals(source):
        raise AssertionError("GOBLIN calibration modified the input CSO cohort panel")

    _validate_calibration(source, calibrated, factors, goblin)
    return calibrated, factors


def _validate_calibration(
    source: pd.DataFrame,
    calibrated: pd.DataFrame,
    factors: pd.DataFrame,
    goblin: pd.DataFrame,
) -> None:
    """Hard checks for national closure and post-2020 CSO preservation."""

    if (calibrated[FINAL_21_COHORTS] < 0).any().any():
        raise AssertionError("negative cattle cohort after GOBLIN calibration")
    if len(factors) != 11 * len(FINAL_21_COHORTS):
        raise AssertionError("incomplete GOBLIN calibration factor table")

    for year in GOBLIN_CALIBRATION_YEARS:
        group = calibrated.loc[calibrated["YEAR"] == year]
        for cohort in FINAL_21_COHORTS:
            target = _checked_integer_target(
                _goblin_value(goblin, cohort, year), cohort, year
            )
            if int(group[cohort].sum()) != target:
                raise AssertionError(
                    f"{cohort} {year}: calibrated national total does not match COHORTS"
                )

    for year in CSO_ONLY_YEARS:
        left = source.loc[
            source["YEAR"] == year, ["CSOED", *FINAL_21_COHORTS]
        ].sort_values("CSOED").reset_index(drop=True)
        right = calibrated.loc[
            calibrated["YEAR"] == year, ["CSOED", *FINAL_21_COHORTS]
        ].sort_values("CSOED").reset_index(drop=True)
        if not left.equals(right):
            raise AssertionError(
                f"{year}: CSO cohort values changed without a COHORTS target"
            )
