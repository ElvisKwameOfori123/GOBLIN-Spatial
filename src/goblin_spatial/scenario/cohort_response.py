"""Propagate adult destocking into the 21 GOBLIN cattle cohorts spatially.

National biology and spatial incidence are deliberately separated:

* GOBLIN/COHORTS supplies the national target for every biological cohort.
* GOBLIN-Spatial starts from the selected ED cohort baseline and allocates only
  the implied reduction across EDs.
* Breeding EDs respond first through their own adult-to-cohort relationship.
* Receiver/rearing/finishing EDs with no corresponding adult cows inherit the
  reduction signal from breeding activity within the same county.
* National fallback is reserved for sparse orphan cases where a cohort exists
  in a county with no corresponding adult breeding stock at all.

For an active breeding ED, the core signal is equivalent to the direct marginal
relationship discussed in the model design::

    cohort_base * (adult_reduction / adult_base)
      = adult_reduction * (cohort_base / adult_base)

Thus adult and follower changes are one linked herd adjustment, while the county
layer preserves observed separation between breeding and finishing geography.
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
    counties: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ED-first, county-second adult reduction signals.

    Active breeding EDs use their own realised adult reduction rate. Cohort
    locations with no corresponding adults are treated as receiver/rearing or
    finishing EDs and inherit the reduction rate of the same county. Only if the
    county itself has no corresponding adults does the function use the national
    rate as an explicit orphan fallback.

    Returns
    -------
    signal:
        Reduction-rate signal in [0, 1].
    source:
        Diagnostic source label: ``LOCAL_ED``, ``COUNTY_RECEIVER``,
        ``NATIONAL_ORPHAN`` or ``NONE``.
    """

    base_adults = np.asarray(base_adults, dtype=np.int64)
    adult_reductions = np.asarray(adult_reductions, dtype=np.int64)
    cohort_base = np.asarray(cohort_base, dtype=np.int64)
    counties = np.asarray(counties, dtype=object)

    n = len(base_adults)
    if any(len(x) != n for x in (adult_reductions, cohort_base, counties)):
        raise ValueError("adult, cohort and county arrays must have equal length")
    if (base_adults < 0).any() or (adult_reductions < 0).any() or (cohort_base < 0).any():
        raise ValueError("adult, reduction and cohort counts must be non-negative")
    if (adult_reductions > base_adults).any():
        raise AssertionError("adult reduction exceeds adult baseline")
    if pd.isna(counties).any():
        raise ValueError("county is required for receiver/rearing cohort propagation")

    signal = np.zeros(n, dtype=float)
    source = np.full(n, "NONE", dtype=object)

    active = base_adults > 0
    signal[active] = adult_reductions[active] / base_adults[active]
    source[active] = "LOCAL_ED"

    network = pd.DataFrame(
        {
            "County": counties,
            "BASE_ADULTS": base_adults,
            "ADULT_REDUCTION": adult_reductions,
        }
    )
    county_base = network.groupby("County", sort=False)["BASE_ADULTS"].transform("sum").to_numpy(dtype=float)
    county_reduction = network.groupby("County", sort=False)["ADULT_REDUCTION"].transform("sum").to_numpy(dtype=float)
    county_rate = np.divide(
        county_reduction,
        county_base,
        out=np.zeros(n, dtype=float),
        where=county_base > 0,
    )

    receivers = (~active) & (cohort_base > 0)
    county_receivers = receivers & (county_base > 0)
    signal[county_receivers] = county_rate[county_receivers]
    source[county_receivers] = "COUNTY_RECEIVER"

    national_base = int(base_adults.sum())
    national_reduction = int(adult_reductions.sum())
    national_rate = national_reduction / national_base if national_base > 0 else 0.0

    orphan = receivers & (county_base <= 0)
    signal[orphan] = national_rate
    source[orphan] = "NATIONAL_ORPHAN"

    return np.clip(signal, 0.0, 1.0), source


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

    This function represents one milestone/endpoint. Adult reductions and
    follower reductions belong to the same herd state. Breeding EDs are linked
    directly through their own adult reduction rate and baseline cohort/adult
    relationship. Receiver/rearing/finishing EDs are linked through the same
    county before any national orphan fallback is allowed.

    ``national_cohort_targets`` remains authoritative for national biology. ED
    and county relationships determine spatial incidence only.
    """

    out = adult_scenario.copy()
    if out["CSOED"].duplicated().any():
        raise AssertionError("cohort response requires one row per CSOED")

    required = [
        "CSOED",
        "County",
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
    counties = out["County"].astype(str).to_numpy(dtype=object)

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
            signal, source = _reduction_signal(base_dairy, red_dairy, base, counties)
        elif origin == "SUCKLER":
            signal, source = _reduction_signal(base_suckler, red_suckler, base, counties)
        else:
            signal, source = _reduction_signal(base_adults, red_adults, base, counties)

        # For a breeding ED this weight is algebraically the direct marginal
        # adult-to-cohort response: adult_reduction * cohort_base/adult_base.
        # Receiver EDs use the corresponding county reduction rate instead.
        # The tiny floor is used only for exact finite-population closure after
        # the ED/county signal has been applied; true orphan support is flagged.
        cut_weights = base.astype(float) * (signal + 1e-12)
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
        out[f"REDUCTION_SIGNAL_SOURCE_{cohort}"] = source
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
