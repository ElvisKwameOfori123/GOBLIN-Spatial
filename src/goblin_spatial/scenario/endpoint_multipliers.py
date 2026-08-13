"""Parent endpoint multipliers for spatial cattle cohorts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.scenario.cohort_response import _relationship_components


def parent_endpoint_multiplier(
    base_adults: np.ndarray,
    scenario_adults: np.ndarray,
    cohort_base: np.ndarray,
    counties: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Use local parents, county receivers, then national fallback."""

    base_adults = np.asarray(base_adults, dtype=np.int64)
    scenario_adults = np.asarray(scenario_adults, dtype=np.int64)
    cohort_base = np.asarray(cohort_base, dtype=np.int64)
    counties = np.asarray(counties, dtype=object)
    if any(len(x) != len(base_adults) for x in (scenario_adults, cohort_base, counties)):
        raise ValueError("endpoint multiplier arrays must have equal length")

    parts = _relationship_components(base_adults, cohort_base, counties)
    source = np.asarray(parts["source"], dtype=object)
    local = np.divide(
        scenario_adults.astype(float),
        base_adults.astype(float),
        out=np.zeros(len(base_adults), dtype=float),
        where=base_adults > 0,
    )
    network = pd.DataFrame({"County": counties, "B": base_adults, "S": scenario_adults})
    county_base = network.groupby("County", sort=False)["B"].transform("sum").to_numpy(dtype=float)
    county_scenario = network.groupby("County", sort=False)["S"].transform("sum").to_numpy(dtype=float)
    county = np.divide(
        county_scenario,
        county_base,
        out=np.zeros(len(county_base), dtype=float),
        where=county_base > 0,
    )
    national = float(scenario_adults.sum()) / float(base_adults.sum()) if base_adults.sum() else 0.0

    multiplier = np.zeros(len(base_adults), dtype=float)
    multiplier[source == "LOCAL_ED"] = local[source == "LOCAL_ED"]
    multiplier[source == "COUNTY_RECEIVER"] = county[source == "COUNTY_RECEIVER"]
    multiplier[source == "NATIONAL_ORPHAN"] = national
    return multiplier, source


def round_implied_counts(values: np.ndarray) -> np.ndarray:
    """Integerise ED counts while preserving the rounded national total."""

    values = np.maximum(np.asarray(values, dtype=float), 0.0)
    if (~np.isfinite(values)).any():
        raise ValueError("non-finite implied cohort counts")
    out = np.floor(values + 1e-12).astype(np.int64)
    target = int(round(float(values.sum())))
    left = target - int(out.sum())
    if left:
        order = np.argsort(-(values - out), kind="stable")
        out[order[:left]] += 1
    if int(out.sum()) != target:
        raise AssertionError("cohort rounding failed national closure")
    return out
