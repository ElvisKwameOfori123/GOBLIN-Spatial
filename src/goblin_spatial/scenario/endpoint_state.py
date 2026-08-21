"""Build the complete cattle state from category-consistent adult endpoints.

The principal SC1 path preserves the mature v2.1 logic:

* adult dairy and suckler endpoints are already solved exactly;
* the selected baseline's Stage-09 dependency profile is validated in-memory;
* the 19 follower cohorts respond through LOCAL_ED, COUNTY_RECEIVER and
  NATIONAL_ORPHAN parent relationships;
* national GOBLIN/COHORTS margins are imposed exactly when supplied; and
* no cohort is seeded into an ED where that cohort was absent at baseline.

There is deliberately no extra rule forcing every ED's total cattle population
to decline. Such a rule would change the validated category-consistent science
when one adult category expands or when follower composition changes.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.reconciliation import hamilton_allocate
from goblin_spatial.scenario.cohort_response import (
    FOLLOWER_COHORTS,
    _cohort_origin,
    _integer_array,
    build_ed_cohort_dependency_profile,
)
from goblin_spatial.scenario.endpoint_multipliers import (
    parent_endpoint_multiplier,
    round_implied_counts,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


def _allocate_target_by_signature(
    implied: np.ndarray,
    baseline: np.ndarray,
    target: int,
) -> np.ndarray:
    """Allocate one exact national cohort target across its existing ED footprint."""
    implied = np.maximum(np.asarray(implied, dtype=float), 0.0)
    baseline = np.asarray(baseline, dtype=np.int64)
    target = int(target)
    if target < 0:
        raise ValueError("national cohort target cannot be negative")
    if len(implied) != len(baseline):
        raise ValueError("implied and baseline cohort arrays must have equal length")
    if (baseline < 0).any() or (~np.isfinite(implied)).any():
        raise ValueError("invalid cohort signature arrays")
    if target == 0:
        return np.zeros(len(baseline), dtype=np.int64)

    eligible = baseline > 0
    if not eligible.any():
        raise ValueError("positive national cohort target has no baseline ED footprint")
    weights = np.where(eligible, implied, 0.0)
    if float(weights.sum()) <= 0.0:
        weights = np.where(eligible, baseline.astype(float), 0.0)
    out = hamilton_allocate(weights, target)
    if (out[~eligible] != 0).any():
        raise AssertionError("national cohort closure seeded a new ED cohort footprint")
    return out.astype(np.int64)


def _validated_national_targets(
    targets: Mapping[str, int],
    *,
    scenario_dairy: int,
    scenario_suckler: int,
    total_cattle_target: int | None,
) -> dict[str, int]:
    supplied = dict(targets)
    expected = set(FINAL_21_COHORTS)
    actual = set(supplied)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(
            "national_cohort_targets must contain the complete 21-cohort set; "
            f"missing={missing}, extra={extra}"
        )
    out = {cohort: int(supplied[cohort]) for cohort in FINAL_21_COHORTS}
    if any(value < 0 for value in out.values()):
        raise ValueError("national cohort targets cannot be negative")
    if out["dairy_cows"] != int(scenario_dairy):
        raise AssertionError("national dairy cohort target does not match adult endpoint")
    if out["suckler_cows"] != int(scenario_suckler):
        raise AssertionError("national suckler cohort target does not match adult endpoint")
    if total_cattle_target is not None and sum(out.values()) != int(total_cattle_target):
        raise AssertionError("national cohort targets do not close to total_cattle_target")
    return out


def _stage09_roles(out: pd.DataFrame) -> dict[str, np.ndarray]:
    """Build and validate the selected-year Stage-09 relationship contract."""
    signature = build_ed_cohort_dependency_profile(out)
    expected_rows = len(out) * len(FOLLOWER_COHORTS)
    if len(signature) != expected_rows:
        raise AssertionError(
            f"Stage09 signature row count failed: {len(signature)} != {expected_rows}"
        )
    if signature[["CSOED", "COHORT"]].duplicated().any():
        raise AssertionError("Stage09 signature contains duplicate ED-cohort rows")

    roles: dict[str, np.ndarray] = {}
    ed_order = out["CSOED"].astype(str).to_numpy()
    for cohort in FOLLOWER_COHORTS:
        block = signature.loc[signature["COHORT"].eq(cohort)].sort_values(
            "CSOED", kind="stable"
        )
        if not np.array_equal(block["CSOED"].astype(str).to_numpy(), ed_order):
            raise AssertionError(f"Stage09 ED order mismatch for {cohort}")
        baseline = _integer_array(out, cohort)
        signature_base = pd.to_numeric(
            block["BASE_COHORT_HEAD"], errors="raise"
        ).to_numpy(dtype=np.int64)
        if not np.array_equal(signature_base, baseline):
            raise AssertionError(f"Stage09 baseline cohort mismatch for {cohort}")
        roles[cohort] = block["COHORT_SPATIAL_ROLE"].astype(str).to_numpy(dtype=object)
    return roles


def build_endpoint_cattle_state(
    adult_endpoint: pd.DataFrame,
    *,
    total_cattle_target: int | None = None,
    national_cohort_targets: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """Propagate category-consistent adults through all 21 cattle cohorts."""

    out = adult_endpoint.copy().sort_values("CSOED", kind="stable").reset_index(drop=True)
    required = {
        "CSOED",
        "County",
        "BASE_DAIRY_COW",
        "BASE_OTHER_COW",
        "SCENARIO_DAIRY_COW",
        "SCENARIO_OTHER_COW",
        *FINAL_21_COHORTS,
    }
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(f"endpoint cattle state missing columns: {missing}")
    if out["CSOED"].duplicated().any():
        raise ValueError("endpoint cattle state requires one row per ED")

    counties = out["County"].astype(str).to_numpy(dtype=object)
    bd = _integer_array(out, "BASE_DAIRY_COW")
    bs = _integer_array(out, "BASE_OTHER_COW")
    sd = _integer_array(out, "SCENARIO_DAIRY_COW")
    ss = _integer_array(out, "SCENARIO_OTHER_COW")
    ba, sa = bd + bs, sd + ss
    base = {cohort: _integer_array(out, cohort) for cohort in FINAL_21_COHORTS}
    if not np.array_equal(base["dairy_cows"], bd):
        raise AssertionError("baseline dairy cohort does not close to adult dairy")
    if not np.array_equal(base["suckler_cows"], bs):
        raise AssertionError("baseline suckler cohort does not close to adult suckler")

    roles = _stage09_roles(out)
    targets = None
    if national_cohort_targets is not None:
        targets = _validated_national_targets(
            national_cohort_targets,
            scenario_dairy=int(sd.sum()),
            scenario_suckler=int(ss.sum()),
            total_cattle_target=total_cattle_target,
        )

    scenario: dict[str, np.ndarray] = {
        "dairy_cows": sd.copy(),
        "suckler_cows": ss.copy(),
    }
    multipliers: dict[str, np.ndarray] = {}
    sources: dict[str, np.ndarray] = {}
    source_counts = {"LOCAL_ED": 0, "COUNTY_RECEIVER": 0, "NATIONAL_ORPHAN": 0}

    for cohort in FOLLOWER_COHORTS:
        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            multiplier, source = parent_endpoint_multiplier(bd, sd, base[cohort], counties)
        elif origin == "SUCKLER":
            multiplier, source = parent_endpoint_multiplier(bs, ss, base[cohort], counties)
        else:
            multiplier, source = parent_endpoint_multiplier(ba, sa, base[cohort], counties)

        # The scenario multiplier helper must reproduce the frozen Stage-09 role.
        if not np.array_equal(np.asarray(source, dtype=object), roles[cohort]):
            raise AssertionError(f"Stage09 relationship role changed for {cohort}")

        implied = base[cohort].astype(float) * multiplier
        if targets is None:
            scenario[cohort] = round_implied_counts(implied)
        else:
            scenario[cohort] = _allocate_target_by_signature(
                implied,
                base[cohort],
                targets[cohort],
            )
        multipliers[cohort] = multiplier
        sources[cohort] = source
        has_cohort = base[cohort] > 0
        for label in source_counts:
            source_counts[label] += int(np.sum(has_cohort & (source == label)))

    if targets is not None:
        for cohort in FINAL_21_COHORTS:
            if int(scenario[cohort].sum()) != int(targets[cohort]):
                raise AssertionError(f"exact national cohort closure failed for {cohort}")

    base_columns: list[str] = []
    scenario_columns: list[str] = []
    for cohort in FINAL_21_COHORTS:
        bcol = f"BASE_COHORT_{cohort}"
        scol = f"SCENARIO_COHORT_{cohort}"
        base_columns.append(bcol)
        scenario_columns.append(scol)
        out[bcol] = base[cohort]
        out[scol] = scenario[cohort]
        out[f"CHANGE_COHORT_{cohort}"] = scenario[cohort] - base[cohort]
        if cohort in multipliers:
            out[f"ENDPOINT_MULTIPLIER_{cohort}"] = multipliers[cohort]
            out[f"ENDPOINT_MULTIPLIER_SOURCE_{cohort}"] = sources[cohort]
        if (scenario[cohort][base[cohort] == 0] != 0).any():
            raise AssertionError(f"endpoint seeded a new ED footprint for {cohort}")

    out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_columns].sum(axis=1).astype(np.int64)
    out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[scenario_columns].sum(axis=1).astype(np.int64)
    out["BASE_TOTAL_CATTLE"] = out["BASE_GOBLIN_21_CATTLE_TOTAL"]
    out["SCENARIO_TOTAL_CATTLE"] = out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"]
    out["CHANGE_TOTAL_CATTLE"] = out["SCENARIO_TOTAL_CATTLE"] - out["BASE_TOTAL_CATTLE"]
    out["CATTLE_REDUCTION_HEAD"] = out["BASE_TOTAL_CATTLE"] - out["SCENARIO_TOTAL_CATTLE"]
    out["CUMULATIVE_REDUCTION_TOTAL_CATTLE"] = out["CATTLE_REDUCTION_HEAD"]
    out["CATTLE_REDUCTION_PCT"] = np.divide(
        100.0 * out["CATTLE_REDUCTION_HEAD"].to_numpy(dtype=float),
        out["BASE_TOTAL_CATTLE"].to_numpy(dtype=float),
        out=np.zeros(len(out), dtype=float),
        where=out["BASE_TOTAL_CATTLE"].to_numpy(dtype=float) > 0,
    )
    out["ED_CATTLE_EXPANSION"] = out["SCENARIO_TOTAL_CATTLE"] > out["BASE_TOTAL_CATTLE"]
    out["STAGE09_SIGNATURE_VALIDATED"] = True
    out["LOCAL_PARENT_RELATIONSHIP_COUNT_AUDIT"] = source_counts["LOCAL_ED"]
    out["COUNTY_RECEIVER_RELATIONSHIP_COUNT_AUDIT"] = source_counts["COUNTY_RECEIVER"]
    out["NATIONAL_ORPHAN_RELATIONSHIP_COUNT_AUDIT"] = source_counts["NATIONAL_ORPHAN"]
    out["NATIONAL_COHORT_TARGETS_APPLIED"] = bool(targets is not None)

    if "TOTAL_CATTLE" in out.columns:
        if not np.array_equal(
            _integer_array(out, "TOTAL_CATTLE"),
            out["BASE_TOTAL_CATTLE"].to_numpy(dtype=np.int64),
        ):
            raise AssertionError("baseline cohorts do not close to historical TOTAL_CATTLE")
    if total_cattle_target is not None and int(out["SCENARIO_TOTAL_CATTLE"].sum()) != int(total_cattle_target):
        raise AssertionError("external national total-cattle endpoint failed")
    if targets is not None and int(out["SCENARIO_TOTAL_CATTLE"].sum()) != sum(targets.values()):
        raise AssertionError("national 21-cohort endpoint total failed")
    return out


def add_fixed_sheep_context(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach unchanged ten sheep cohorts and explicit sheep totals."""
    out = frame.copy()
    base_columns: list[str] = []
    scenario_columns: list[str] = []
    for cohort in GOBLIN_SHEEP_10:
        values = _integer_array(out, cohort)
        bcol = f"BASE_SHEEP_COHORT_{cohort}"
        scol = f"SCENARIO_SHEEP_COHORT_{cohort}"
        base_columns.append(bcol)
        scenario_columns.append(scol)
        out[bcol] = values
        out[scol] = values
    out["BASE_GOBLIN_10_SHEEP_TOTAL"] = out[base_columns].sum(axis=1).astype(np.int64)
    out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"] = out[scenario_columns].sum(axis=1).astype(np.int64)
    if not np.array_equal(
        out["BASE_GOBLIN_10_SHEEP_TOTAL"].to_numpy(dtype=np.int64),
        out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("principal SC1 changed sheep")
    return out
