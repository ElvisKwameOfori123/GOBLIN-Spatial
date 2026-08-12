"""Propagate adult destocking into the 21 GOBLIN cattle cohorts spatially.

National biology and spatial incidence are deliberately separated:

* GOBLIN/COHORTS supplies the national target for every biological cohort.
* GOBLIN-Spatial starts from the selected ED cohort baseline and allocates only
  the implied reduction across EDs.
* Dairy-origin cohorts (DxD and DxB) follow the geography of dairy-cow
  reductions plus existing receiver/rearing locations.
* BxB cohorts follow suckler-cow reductions plus existing receiver/rearing
  locations.
* Bulls follow total adult-cow reductions.

No future cohort is constructed from an ED ratio. ED-specific baseline cohort
composition is used to decide *where* a national biological reduction lands.
This preserves local finishing/rearing differences without allowing them to
change the national GOBLIN biological target.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.allocation import _bounded_integer_allocate


DXD_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxD_"))
DXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("DxB_"))
BXB_COHORTS = tuple(c for c in FINAL_21_COHORTS if c.startswith("BxB_"))
FOLLOWER_COHORTS = tuple(
    c for c in FINAL_21_COHORTS if c not in {"dairy_cows", "suckler_cows"}
)


def _integer_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def _reduction_signal(
    base_adults: np.ndarray,
    adult_reductions: np.ndarray,
    cohort_base: np.ndarray,
) -> np.ndarray:
    """Return an ED adult-reduction signal with support for receiver EDs.

    Breeding EDs use their own realised adult reduction rate. If a cohort is
    present in an ED with no corresponding adult cows, that ED is an observed
    receiver/rearing location; it receives the national adult-reduction rate as
    its signal rather than being excluded.
    """

    base_adults = np.asarray(base_adults, dtype=np.int64)
    adult_reductions = np.asarray(adult_reductions, dtype=np.int64)
    cohort_base = np.asarray(cohort_base, dtype=np.int64)

    if (base_adults < 0).any() or (adult_reductions < 0).any():
        raise ValueError("adult counts and reductions must be non-negative")
    if (adult_reductions > base_adults).any():
        raise AssertionError("adult reduction exceeds adult baseline")

    signal = np.zeros(len(base_adults), dtype=float)
    active = base_adults > 0
    signal[active] = adult_reductions[active] / base_adults[active]

    national_base = int(base_adults.sum())
    national_reduction = int(adult_reductions.sum())
    national_rate = national_reduction / national_base if national_base > 0 else 0.0

    receivers = (~active) & (cohort_base > 0)
    signal[receivers] = national_rate
    return np.clip(signal, 0.0, 1.0)


def _cohort_origin(cohort: str) -> str:
    if cohort in DXD_COHORTS or cohort in DXB_COHORTS:
        return "DAIRY"
    if cohort in BXB_COHORTS:
        return "SUCKLER"
    if cohort == "bulls":
        return "ADULT_COWS"
    raise ValueError(f"cannot identify adult origin for cohort {cohort}")


def allocate_cattle_cohort_response(
    adult_scenario: pd.DataFrame,
    national_cohort_targets: Mapping[str, int],
) -> pd.DataFrame:
    """Subtract GOBLIN/COHORTS cohort reductions from the ED cohort baseline.

    Parameters
    ----------
    adult_scenario:
        Output from :func:`allocate_adult_livestock_scenario`. It must retain
        the selected baseline's 21 GOBLIN cattle cohort columns.
    national_cohort_targets:
        Exact national endpoint for each of the 21 GOBLIN cattle cohorts. In a
        future pathway run these values should come from GOBLIN/COHORTS, not
        from ED ratios.

    Notes
    -----
    This first implementation is reduction-only. A target above the selected
    baseline cohort total is rejected rather than silently creating animals in
    new EDs. Expansion can be added later as an explicit, separate process.
    """

    out = adult_scenario.copy()
    if out["CSOED"].duplicated().any():
        raise AssertionError("cohort response requires one row per CSOED")

    required = [
        "CSOED",
        "BASE_DAIRY_COW",
        "BASE_OTHER_COW",
        "BASE_ADULT_COWS",
        "REDUCTION_DAIRY_COW",
        "REDUCTION_OTHER_COW",
        "REDUCTION_ADULT_COWS",
        "SCENARIO_DAIRY_COW",
        "SCENARIO_OTHER_COW",
        *FINAL_21_COHORTS,
    ]
    missing = [column for column in required if column not in out.columns]
    if missing:
        raise ValueError(f"cattle cohort response missing required columns: {missing}")

    target_keys = set(national_cohort_targets)
    required_targets = set(FINAL_21_COHORTS)
    missing_targets = sorted(required_targets - target_keys)
    extra_targets = sorted(target_keys - required_targets)
    if missing_targets:
        raise ValueError(f"national cohort targets missing: {missing_targets}")
    if extra_targets:
        raise ValueError(f"unknown national cattle cohort targets: {extra_targets}")

    targets: dict[str, int] = {}
    for cohort in FINAL_21_COHORTS:
        value = int(national_cohort_targets[cohort])
        if value < 0:
            raise ValueError(f"negative national target for {cohort}")
        targets[cohort] = value

    # National adult targets must agree with the already-allocated adult layer.
    adult_checks = {
        "dairy_cows": int(out["SCENARIO_DAIRY_COW"].sum()),
        "suckler_cows": int(out["SCENARIO_OTHER_COW"].sum()),
    }
    for cohort, expected in adult_checks.items():
        if targets[cohort] != expected:
            raise AssertionError(
                f"GOBLIN target for {cohort} ({targets[cohort]:,}) does not match "
                f"the adult scenario target ({expected:,})"
            )

    # Adults inherit the spatial allocation already completed.
    adult_mapping = {
        "dairy_cows": ("BASE_DAIRY_COW", "REDUCTION_DAIRY_COW", "SCENARIO_DAIRY_COW"),
        "suckler_cows": ("BASE_OTHER_COW", "REDUCTION_OTHER_COW", "SCENARIO_OTHER_COW"),
    }
    for cohort, (base_col, reduction_col, scenario_col) in adult_mapping.items():
        out[f"BASE_COHORT_{cohort}"] = _integer_array(out, base_col)
        out[f"REDUCTION_COHORT_{cohort}"] = _integer_array(out, reduction_col)
        out[f"SCENARIO_COHORT_{cohort}"] = _integer_array(out, scenario_col)

    base_dairy = _integer_array(out, "BASE_DAIRY_COW")
    base_suckler = _integer_array(out, "BASE_OTHER_COW")
    base_adults = _integer_array(out, "BASE_ADULT_COWS")
    red_dairy = _integer_array(out, "REDUCTION_DAIRY_COW")
    red_suckler = _integer_array(out, "REDUCTION_OTHER_COW")
    red_adults = _integer_array(out, "REDUCTION_ADULT_COWS")

    for cohort in FOLLOWER_COHORTS:
        base = _integer_array(out, cohort)
        base_total = int(base.sum())
        target_total = targets[cohort]
        if target_total > base_total:
            raise ValueError(
                f"reduction-only cohort response cannot expand {cohort}: "
                f"baseline={base_total:,}, target={target_total:,}"
            )
        reduction_total = base_total - target_total

        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            signal = _reduction_signal(base_dairy, red_dairy, base)
        elif origin == "SUCKLER":
            signal = _reduction_signal(base_suckler, red_suckler, base)
        else:
            signal = _reduction_signal(base_adults, red_adults, base)

        # The existing cohort distribution captures ED-specific rearing and
        # finishing propensity. Adult reduction rates tilt the cuts toward the
        # places whose breeding base is actually contracting. A tiny positive
        # floor keeps every existing cohort location available if exact national
        # closure requires spill-over beyond strongly signalled EDs.
        cut_weights = base.astype(float) * (signal + 1e-9)
        reductions = _bounded_integer_allocate(cut_weights, base, reduction_total)
        scenario_values = base - reductions

        if int(reductions.sum()) != reduction_total:
            raise AssertionError(f"national cohort reduction failed for {cohort}")
        if int(scenario_values.sum()) != target_total:
            raise AssertionError(f"national cohort target failed for {cohort}")
        if not np.array_equal(base - reductions, scenario_values):
            raise AssertionError(f"baseline-minus-reduction failed for {cohort}")

        out[f"BASE_COHORT_{cohort}"] = base
        out[f"REDUCTION_SIGNAL_{cohort}"] = signal
        out[f"REDUCTION_COHORT_{cohort}"] = reductions
        out[f"SCENARIO_COHORT_{cohort}"] = scenario_values
        out[f"REDUCTION_PCT_COHORT_{cohort}"] = np.where(
            base > 0,
            100.0 * reductions / base,
            0.0,
        )

    scenario_columns = [f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS]
    reduction_columns = [f"REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS]
    base_columns = [f"BASE_COHORT_{c}" for c in FINAL_21_COHORTS]

    out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_columns].sum(axis=1)
    out["REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[reduction_columns].sum(axis=1)
    out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[scenario_columns].sum(axis=1)

    if not np.array_equal(
        out["BASE_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64)
        - out["REDUCTION_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64),
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("21-cohort ED scenario is not baseline minus reduction")

    expected_national = sum(targets.values())
    if int(out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].sum()) != expected_national:
        raise AssertionError("21-cohort national scenario total failed exact closure")

    return out
