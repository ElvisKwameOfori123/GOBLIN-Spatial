"""Derive national 21-cohort cattle targets from a GOBLIN reference profile.

The national GOBLIN/COHORTS profile supplies the biological relationship between
adult breeding cows and follower cohorts.  It does not determine ED geography.
GOBLIN-Spatial uses these national targets as hard margins while the selected
2020 or 2025 ED baseline supplies the heterogeneous local cohort signatures.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS


ADULT_COHORTS = {"dairy_cows", "suckler_cows"}
FOLLOWER_COHORTS = tuple(c for c in FINAL_21_COHORTS if c not in ADULT_COHORTS)


def _origin(cohort: str) -> str:
    if cohort.startswith("DxD_") or cohort.startswith("DxB_"):
        return "DAIRY"
    if cohort.startswith("BxB_"):
        return "SUCKLER"
    if cohort == "bulls":
        return "ADULT_COWS"
    raise ValueError(f"cannot identify adult origin for cohort {cohort}")


def _non_negative_int(label: str, value: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer")
    number = int(value)
    if number != value or number < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return number


def _hamilton(weights: np.ndarray, target: int) -> np.ndarray:
    """Integerise non-negative weights to an exact total without capacity caps."""

    weights = np.asarray(weights, dtype=float)
    target = _non_negative_int("target", target)
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("weights must be finite and non-negative")
    if target == 0:
        return np.zeros(len(weights), dtype=np.int64)
    total = float(weights.sum())
    if total <= 0.0:
        raise ValueError("positive target requires positive biological weights")

    fractional = target * weights / total
    out = np.floor(fractional + 1e-12).astype(np.int64)
    left = target - int(out.sum())
    if left:
        order = np.argsort(-(fractional - out), kind="stable")
        out[order[:left]] += 1
    if int(out.sum()) != target:
        raise AssertionError("Hamilton integerisation failed exact closure")
    return out


def load_goblin_cohort_reference(
    path: str | Path,
    *,
    reference_year: int = 2020,
) -> dict[str, float]:
    """Load one national GOBLIN cattle-cohort reference year.

    The source file may be expressed in thousands of head, as in the historical
    GOBLIN control table.  Only ratios are used downstream, so no unit conversion
    is required as long as all cohort rows use the same unit.
    """

    frame = pd.read_csv(Path(path))
    frame.columns = [str(c).strip() for c in frame.columns]
    cohort_columns = [c for c in frame.columns if c.lower() == "cohorts"]
    if len(cohort_columns) != 1:
        raise ValueError("could not uniquely identify the GOBLIN Cohorts column")
    cohort_col = cohort_columns[0]
    year_col = str(int(reference_year))
    if year_col not in frame.columns:
        raise ValueError(f"GOBLIN cohort reference missing year {reference_year}")

    frame[cohort_col] = frame[cohort_col].astype(str).str.strip()
    values: dict[str, float] = {}
    for cohort in FINAL_21_COHORTS:
        rows = frame.loc[frame[cohort_col] == cohort, year_col]
        if len(rows) != 1:
            raise ValueError(
                f"expected exactly one GOBLIN reference row for {cohort}; found {len(rows)}"
            )
        value = float(pd.to_numeric(rows.iloc[0], errors="raise"))
        if not np.isfinite(value) or value < 0.0:
            raise ValueError(f"invalid GOBLIN reference value for {cohort}")
        values[cohort] = value
    return values


def derive_national_cohort_targets(
    *,
    dairy_cows: int,
    suckler_cows: int,
    reference_counts: Mapping[str, float],
    total_cattle_target: int | None = None,
) -> dict[str, int]:
    """Convert adult endpoints into a complete national 21-cohort target.

    DxD and DxB cohorts follow dairy cows, BxB cohorts follow suckler cows, and
    bulls follow the combined adult-cow population.  These national biological
    margins are independent of the ED spatial allocation.  The ED engine later
    places each target while preserving local/county receiver signatures.

    If ``total_cattle_target`` is supplied, it is treated as the stronger hard
    national closure.  Adult targets remain fixed and all follower targets are
    proportionally reconciled to the required remaining cattle total.
    """

    dairy = _non_negative_int("dairy_cows", dairy_cows)
    suckler = _non_negative_int("suckler_cows", suckler_cows)
    supplied = dict(reference_counts)
    missing = sorted(set(FINAL_21_COHORTS) - set(supplied))
    extra = sorted(set(supplied) - set(FINAL_21_COHORTS))
    if missing or extra:
        raise ValueError(
            "reference_counts must contain the complete 21-cohort set; "
            f"missing={missing}, extra={extra}"
        )

    reference = {cohort: float(supplied[cohort]) for cohort in FINAL_21_COHORTS}
    if any((not np.isfinite(v) or v < 0.0) for v in reference.values()):
        raise ValueError("reference_counts must be finite and non-negative")
    ref_dairy = reference["dairy_cows"]
    ref_suckler = reference["suckler_cows"]
    ref_adults = ref_dairy + ref_suckler
    if ref_dairy <= 0.0 or ref_suckler <= 0.0 or ref_adults <= 0.0:
        raise ValueError("reference adult-cow populations must be positive")

    raw_followers: list[float] = []
    for cohort in FOLLOWER_COHORTS:
        origin = _origin(cohort)
        if origin == "DAIRY":
            raw = reference[cohort] / ref_dairy * dairy
        elif origin == "SUCKLER":
            raw = reference[cohort] / ref_suckler * suckler
        else:
            raw = reference[cohort] / ref_adults * (dairy + suckler)
        raw_followers.append(float(raw))

    adult_total = dairy + suckler
    if total_cattle_target is None:
        follower_total = int(round(float(sum(raw_followers))))
    else:
        total = _non_negative_int("total_cattle_target", total_cattle_target)
        if total < adult_total:
            raise ValueError("total_cattle_target cannot be smaller than adult targets")
        follower_total = total - adult_total

    follower_counts = _hamilton(np.asarray(raw_followers, dtype=float), follower_total)
    targets: dict[str, int] = {
        "dairy_cows": dairy,
        "suckler_cows": suckler,
    }
    targets.update(
        {
            cohort: int(value)
            for cohort, value in zip(FOLLOWER_COHORTS, follower_counts, strict=True)
        }
    )
    ordered = {cohort: int(targets[cohort]) for cohort in FINAL_21_COHORTS}

    expected_total = adult_total + follower_total
    if sum(ordered.values()) != expected_total:
        raise AssertionError("derived national 21-cohort targets failed exact closure")
    if total_cattle_target is not None and sum(ordered.values()) != int(total_cattle_target):
        raise AssertionError("derived national cohorts failed external total-cattle closure")
    return ordered
