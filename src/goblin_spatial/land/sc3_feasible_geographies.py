"""Alternative feasible SC3 geographies for a fixed national end-use outcome.

This module starts from a completed Colm-direct SC3 reference allocation and
asks a different question from the main optimiser:

    holding the national realised hectares for every future use fixed,
    what other spatial allocations remain feasible?

The reference SC3 allocation is never replaced. Alternative solutions preserve
the same frozen released-land resource, the same use-specific eligibility rules,
the same validated rewetting capacity and the same per-use national realised
hectares. They therefore reveal spatial flexibility within one national outcome,
not new pathways, new targets, adoption probabilities or predicted land-use
maps.

Two complementary diagnostics are provided:

* a deterministic sampled ensemble of alternative feasible geographies for
  national mapping and robustness/flexibility summaries;
* exact minimum/maximum ED-use bounds for an explicit shortlist of ED-use
  queries. Exact bounds are intentionally query-based because solving them for
  every ED x use pair would require many thousands of additional LP solves.

The sampled ensemble must be described as sampled, not as the complete feasible
envelope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from goblin_spatial.land.sc2_colm_direct import (
    COLM_PHYSICAL_CATEGORIES,
    COLM_RELEASED_AREA_COLUMNS,
    validate_colm_eligibility_rules,
)
from goblin_spatial.land.sc3_colm_allocation import (
    HA_TOL,
    LP_METHOD,
    REWETTING_USE,
    SC3_USES,
    STAGE_A_USES,
)

FLEX_VERSION = "1.0"
DEFAULT_SEED = 20260908
POSITIVE_TOL_HA = 1e-6


@dataclass(frozen=True)
class FeasibleGeographyEnsemble:
    """Alternative feasible SC3 geographies and sampled flexibility summary."""

    allocations: pd.DataFrame
    flexibility: pd.DataFrame
    diagnostics: pd.DataFrame


def _scipy():
    try:
        from scipy.optimize import linprog
        from scipy.sparse import coo_matrix
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "SC3 feasible-geography analysis requires scipy. Install with: "
            "pip install 'goblin-spatial[scenario]'"
        ) from exc
    return linprog, coo_matrix


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"feasible-geography input missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def _resource_matrix(frame: pd.DataFrame) -> np.ndarray:
    missing = sorted(set(COLM_RELEASED_AREA_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"feasible-geography input missing Colm resource columns: {missing}")
    resource = (
        frame[list(COLM_RELEASED_AREA_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(dtype=float)
    )
    if (~np.isfinite(resource)).any() or (resource < -1e-10).any():
        raise ValueError("Colm released-resource cells must be finite and non-negative")
    resource = np.maximum(resource, 0.0)
    release = _numeric(frame, "GOBLIN_RELEASED_GRASSLAND_HA")
    if not np.allclose(resource.sum(axis=1), release, atol=1e-7):
        raise AssertionError(
            "feasible-geography resource cells do not close to frozen SC1 release"
        )
    return resource


def _reference_realised(frame: pd.DataFrame) -> dict[str, float]:
    realised: dict[str, float] = {}
    for use in SC3_USES:
        allocated_column = f"SC3_{use}_ALLOCATED_HA"
        total = float(_numeric(frame, allocated_column).sum())
        national_column = f"SC3_{use}_NATIONAL_REALISED_HA"
        if national_column in frame.columns:
            national = _numeric(frame, national_column)
            if not np.allclose(national, national[0], atol=1e-8):
                raise ValueError(f"{national_column} must be constant across ED rows")
            if abs(float(national[0]) - total) > 1e-5:
                raise AssertionError(
                    f"reference SC3 national realised hectares do not close for {use}"
                )
        realised[use] = max(total, 0.0)
    return realised


def _reference_cell_allocation(frame: pd.DataFrame) -> np.ndarray:
    n_ed = len(frame)
    n_category = len(COLM_PHYSICAL_CATEGORIES)
    n_use = len(SC3_USES)
    allocation = np.zeros((n_ed, n_category, n_use), dtype=float)
    for use_index, use in enumerate(SC3_USES):
        for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
            column = f"SC3_{use}_{category}_HA"
            allocation[:, category_index, use_index] = _numeric(frame, column)
    if (allocation < -1e-8).any():
        raise ValueError("reference SC3 allocation contains negative hectares")
    return np.maximum(allocation, 0.0)


def _rewetting_capacity_matrix(
    frame: pd.DataFrame,
    resource: np.ndarray,
    *,
    realised_rewetting: float,
    capacity_columns: Mapping[str, str] | None,
) -> np.ndarray:
    capacity = np.zeros_like(resource)
    if realised_rewetting <= HA_TOL:
        return capacity
    if capacity_columns is None:
        raise ValueError(
            "positive realised REWETTING requires the same validated rewetting "
            "capacity mapping used by the reference SC3 run"
        )

    mapping = {
        str(category).strip().upper(): str(column).strip()
        for category, column in capacity_columns.items()
    }
    extra = sorted(set(mapping) - set(COLM_PHYSICAL_CATEGORIES))
    if extra:
        raise ValueError(f"unknown Colm categories in rewetting mapping: {extra}")

    for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
        column = mapping.get(category)
        if column is None:
            continue
        raw = _numeric(frame, column)
        if (raw < -1e-10).any():
            raise ValueError(f"{column} must be non-negative")
        capacity[:, category_index] = np.minimum(
            np.maximum(raw, 0.0),
            resource[:, category_index],
        )
    if float(capacity.sum()) + 1e-7 < realised_rewetting:
        raise ValueError(
            "validated rewetting capacity cannot support the reference realised hectares"
        )
    return capacity


def infer_rewetting_capacity_columns(frame: pd.DataFrame) -> dict[str, str] | None:
    """Infer standard attached rewetting-capacity columns, if present."""

    mapping: dict[str, str] = {}
    for category in COLM_PHYSICAL_CATEGORIES:
        column = f"REWETTING_CAPACITY_{category}_HA"
        if column in frame.columns:
            mapping[category] = column
    return mapping or None


def _build_fixed_realisation_system(
    frame: pd.DataFrame,
    *,
    eligibility_rules: Mapping[str, Mapping[str, float]],
    rewetting_capacity_columns: Mapping[str, str] | None,
):
    linprog, coo_matrix = _scipy()
    if "CSOED" not in frame.columns:
        raise ValueError("feasible-geography analysis requires CSOED")
    if frame["CSOED"].duplicated().any():
        raise ValueError("feasible-geography analysis requires one row per ED")

    resource = _resource_matrix(frame)
    realised = _reference_realised(frame)
    validated = validate_colm_eligibility_rules(
        eligibility_rules,
        allowed_uses=STAGE_A_USES,
    )
    if set(validated) != set(STAGE_A_USES):
        missing = sorted(set(STAGE_A_USES) - set(validated))
        extra = sorted(set(validated) - set(STAGE_A_USES))
        raise ValueError(
            "feasible-geography analysis requires one explicit rule for every "
            f"Stage-A use; missing={missing}, extra={extra}"
        )

    n_ed, n_category = resource.shape
    n_use = len(SC3_USES)

    def vidx(ed: int, category: int, use: int) -> int:
        return (ed * n_category + category) * n_use + use

    rewet_capacity = _rewetting_capacity_matrix(
        frame,
        resource,
        realised_rewetting=realised[REWETTING_USE],
        capacity_columns=rewetting_capacity_columns,
    )

    bounds: list[tuple[float, float]] = []
    for ed in range(n_ed):
        for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
            cell = float(resource[ed, category_index])
            for use in SC3_USES:
                if use == REWETTING_USE:
                    upper = float(rewet_capacity[ed, category_index])
                else:
                    upper = cell * float(validated[use][category])
                if realised[use] <= HA_TOL:
                    upper = 0.0
                bounds.append((0.0, max(upper, 0.0)))

    eq_r: list[int] = []
    eq_c: list[int] = []
    eq_d: list[float] = []
    beq: list[float] = []
    for use_index, use in enumerate(SC3_USES):
        for ed in range(n_ed):
            for category in range(n_category):
                eq_r.append(use_index)
                eq_c.append(vidx(ed, category, use_index))
                eq_d.append(1.0)
        beq.append(float(realised[use]))
    aeq = coo_matrix(
        (eq_d, (eq_r, eq_c)),
        shape=(n_use, n_ed * n_category * n_use),
    ).tocsr()

    ub_r: list[int] = []
    ub_c: list[int] = []
    ub_d: list[float] = []
    bub: list[float] = []
    row = 0
    for ed in range(n_ed):
        for category in range(n_category):
            for use_index in range(n_use):
                ub_r.append(row)
                ub_c.append(vidx(ed, category, use_index))
                ub_d.append(1.0)
            bub.append(float(resource[ed, category]))
            row += 1
    aub = coo_matrix(
        (ub_d, (ub_r, ub_c)),
        shape=(row, n_ed * n_category * n_use),
    ).tocsr()

    return {
        "linprog": linprog,
        "resource": resource,
        "realised": realised,
        "bounds": bounds,
        "A_eq": aeq,
        "b_eq": np.asarray(beq, dtype=float),
        "A_ub": aub,
        "b_ub": np.asarray(bub, dtype=float),
        "shape": (n_ed, n_category, n_use),
    }


def _validate_solution(
    allocation: np.ndarray,
    *,
    resource: np.ndarray,
    realised: Mapping[str, float],
) -> None:
    if (~np.isfinite(allocation)).any() or (allocation < -1e-7).any():
        raise AssertionError("feasible-geography solver returned invalid allocation")
    if (allocation.sum(axis=2) - resource > 1e-6).any():
        raise AssertionError("alternative geography exceeded a finite resource cell")
    for use_index, use in enumerate(SC3_USES):
        total = float(allocation[:, :, use_index].sum())
        if abs(total - float(realised[use])) > 1e-5:
            raise AssertionError(
                f"alternative geography changed national realised hectares for {use}"
            )


def _aggregate_ed_use(allocation: np.ndarray) -> np.ndarray:
    return allocation.sum(axis=1)


def _signature(aggregated: np.ndarray) -> bytes:
    rounded = np.round(np.asarray(aggregated, dtype=float), 6)
    return rounded.tobytes()


def _long_solution(
    frame: pd.DataFrame,
    aggregated: np.ndarray,
    *,
    solution_id: str,
    is_reference: bool,
) -> pd.DataFrame:
    eds = frame["CSOED"].astype(str).to_numpy()
    n_ed = len(frame)
    n_use = len(SC3_USES)
    out = pd.DataFrame(
        {
            "SOLUTION_ID": np.repeat(solution_id, n_ed * n_use),
            "IS_REFERENCE": np.repeat(bool(is_reference), n_ed * n_use),
            "CSOED": np.repeat(eds, n_use),
            "USE": np.tile(np.asarray(SC3_USES, dtype=object), n_ed),
            "ALLOCATED_HA": aggregated.reshape(-1),
        }
    )
    if "County" in frame.columns:
        county = frame["County"].astype(str).to_numpy()
        out["County"] = np.repeat(county, n_use)
    return out


def _summarise_flexibility(
    allocations: pd.DataFrame,
    *,
    positive_threshold_ha: float,
) -> pd.DataFrame:
    grouped = allocations.groupby(["CSOED", "USE"], sort=False)["ALLOCATED_HA"]
    summary = grouped.agg(
        MIN_SAMPLED_HA="min",
        MAX_SAMPLED_HA="max",
        MEAN_SAMPLED_HA="mean",
        STD_SAMPLED_HA=lambda values: float(np.std(values.to_numpy(float), ddof=0)),
    ).reset_index()
    summary["RANGE_SAMPLED_HA"] = (
        summary["MAX_SAMPLED_HA"] - summary["MIN_SAMPLED_HA"]
    )

    frequency = (
        allocations.assign(
            _POSITIVE=allocations["ALLOCATED_HA"].to_numpy(float)
            > float(positive_threshold_ha)
        )
        .groupby(["CSOED", "USE"], sort=False)["_POSITIVE"]
        .mean()
        .rename("POSITIVE_FREQUENCY_SAMPLED")
        .reset_index()
    )
    reference = (
        allocations.loc[allocations["IS_REFERENCE"]]
        .loc[:, ["CSOED", "USE", "ALLOCATED_HA"]]
        .rename(columns={"ALLOCATED_HA": "REFERENCE_HA"})
    )
    summary = summary.merge(frequency, on=["CSOED", "USE"], how="left")
    summary = summary.merge(reference, on=["CSOED", "USE"], how="left")
    n_solutions = int(allocations["SOLUTION_ID"].nunique())
    summary["N_FEASIBLE_SOLUTIONS_SAMPLED"] = n_solutions
    summary["ROBUST_POSITIVE_SAMPLED"] = (
        summary["POSITIVE_FREQUENCY_SAMPLED"] >= 1.0 - 1e-12
    )
    summary["NEVER_POSITIVE_SAMPLED"] = (
        summary["POSITIVE_FREQUENCY_SAMPLED"] <= 1e-12
    )
    if not (
        (summary["REFERENCE_HA"] >= summary["MIN_SAMPLED_HA"] - 1e-7)
        & (summary["REFERENCE_HA"] <= summary["MAX_SAMPLED_HA"] + 1e-7)
    ).all():
        raise AssertionError("reference allocation lies outside sampled flexibility range")
    return summary


def sample_colm_sc3_feasible_geographies(
    reference_sc3: pd.DataFrame,
    *,
    eligibility_rules: Mapping[str, Mapping[str, float]],
    rewetting_capacity_columns: Mapping[str, str] | None = None,
    n_alternatives: int = 12,
    seed: int = DEFAULT_SEED,
    positive_threshold_ha: float = POSITIVE_TOL_HA,
    max_attempt_multiplier: int = 8,
) -> FeasibleGeographyEnsemble:
    """Sample alternative feasible geographies for the same national end-use vector."""

    n_alternatives = int(n_alternatives)
    if n_alternatives < 0:
        raise ValueError("n_alternatives must be non-negative")
    if float(positive_threshold_ha) < 0:
        raise ValueError("positive_threshold_ha must be non-negative")
    if int(max_attempt_multiplier) < 1:
        raise ValueError("max_attempt_multiplier must be at least one")

    system = _build_fixed_realisation_system(
        reference_sc3,
        eligibility_rules=eligibility_rules,
        rewetting_capacity_columns=rewetting_capacity_columns,
    )
    shape = system["shape"]
    reference_cell = _reference_cell_allocation(reference_sc3)
    _validate_solution(
        reference_cell,
        resource=system["resource"],
        realised=system["realised"],
    )
    reference_agg = _aggregate_ed_use(reference_cell)

    long_solutions = [
        _long_solution(
            reference_sc3,
            reference_agg,
            solution_id="REFERENCE",
            is_reference=True,
        )
    ]
    seen = {_signature(reference_agg)}

    if n_alternatives > 0:
        rng = np.random.default_rng(int(seed))
        n_ed, n_category, n_use = shape
        max_attempts = max(16, int(n_alternatives) * int(max_attempt_multiplier))
        attempts = 0
        unique_alternatives = 0

        while unique_alternatives < n_alternatives and attempts < max_attempts:
            attempts += 1
            if attempts == 1:
                objective = np.where(reference_cell > POSITIVE_TOL_HA, 1.0, -1.0)
            else:
                ed_use = rng.normal(size=(n_ed, n_use))
                jitter = rng.normal(scale=0.05, size=(n_ed, n_category, n_use))
                objective = ed_use[:, None, :] + jitter

            solution = system["linprog"](
                objective.reshape(-1),
                A_ub=system["A_ub"],
                b_ub=system["b_ub"],
                A_eq=system["A_eq"],
                b_eq=system["b_eq"],
                bounds=system["bounds"],
                method=LP_METHOD,
            )
            if not solution.success:
                raise RuntimeError(
                    "SC3 feasible-geography LP failed despite a valid reference "
                    f"solution: {solution.message}"
                )
            allocation = solution.x.reshape(shape)
            _validate_solution(
                allocation,
                resource=system["resource"],
                realised=system["realised"],
            )
            aggregated = _aggregate_ed_use(allocation)
            signature = _signature(aggregated)
            if signature in seen:
                continue
            seen.add(signature)
            unique_alternatives += 1
            long_solutions.append(
                _long_solution(
                    reference_sc3,
                    aggregated,
                    solution_id=f"ALT_{unique_alternatives:03d}",
                    is_reference=False,
                )
            )

    allocations = pd.concat(long_solutions, ignore_index=True)
    flexibility = _summarise_flexibility(
        allocations,
        positive_threshold_ha=float(positive_threshold_ha),
    )
    n_unique_alt = int(
        allocations.loc[~allocations["IS_REFERENCE"], "SOLUTION_ID"].nunique()
    )
    diagnostics_row: dict[str, object] = {
        "SC3_FEASIBLE_GEOGRAPHY_VERSION": FLEX_VERSION,
        "METHOD": "FIXED_REALISATION_RANDOM_LINEAR_OBJECTIVES",
        "REFERENCE_INCLUDED": True,
        "REQUESTED_ALTERNATIVES": n_alternatives,
        "UNIQUE_ALTERNATIVES_FOUND": n_unique_alt,
        "TOTAL_SOLUTIONS_WITH_REFERENCE": int(allocations["SOLUTION_ID"].nunique()),
        "RANDOM_SEED": int(seed),
        "SAMPLED_NOT_EXACT_ENVELOPE": True,
        "PER_USE_NATIONAL_REALISED_VECTOR_FIXED": True,
        "OPPORTUNITY_OBJECTIVE_PRESERVED": False,
        "INTERPRETATION": (
            "ALTERNATIVE_FEASIBLE_GEOGRAPHIES_FOR_THE_SAME_NATIONAL_END_USE_"
            "OUTCOME_NOT_PREDICTIONS_OR_ADOPTION_PROBABILITIES"
        ),
    }
    if "SC3_OPPORTUNITY_RANKING_APPLIED" in reference_sc3.columns:
        diagnostics_row["REFERENCE_OPPORTUNITY_RANKING_APPLIED"] = bool(
            reference_sc3["SC3_OPPORTUNITY_RANKING_APPLIED"].iloc[0]
        )
    for use, value in system["realised"].items():
        diagnostics_row[f"{use}_FIXED_REALISED_HA"] = float(value)

    return FeasibleGeographyEnsemble(
        allocations=allocations,
        flexibility=flexibility,
        diagnostics=pd.DataFrame([diagnostics_row]),
    )


def exact_colm_sc3_ed_use_bounds(
    reference_sc3: pd.DataFrame,
    *,
    eligibility_rules: Mapping[str, Mapping[str, float]],
    queries: Sequence[tuple[str, str]],
    rewetting_capacity_columns: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return exact feasible min/max hectares for selected ED-use pairs."""

    if not queries:
        raise ValueError("queries must contain at least one (CSOED, USE) pair")

    system = _build_fixed_realisation_system(
        reference_sc3,
        eligibility_rules=eligibility_rules,
        rewetting_capacity_columns=rewetting_capacity_columns,
    )
    shape = system["shape"]
    n_ed, n_category, n_use = shape
    ed_lookup = {
        str(value): index
        for index, value in enumerate(reference_sc3["CSOED"].astype(str).tolist())
    }
    use_lookup = {use: index for index, use in enumerate(SC3_USES)}
    reference = _aggregate_ed_use(_reference_cell_allocation(reference_sc3))

    def vidx(ed: int, category: int, use: int) -> int:
        return (ed * n_category + category) * n_use + use

    rows: list[dict[str, object]] = []
    for raw_ed, raw_use in queries:
        ed_key = str(raw_ed)
        use = str(raw_use).strip().upper()
        if ed_key not in ed_lookup:
            raise ValueError(f"unknown CSOED in exact-bound query: {ed_key}")
        if use not in use_lookup:
            raise ValueError(f"unsupported use in exact-bound query: {use}")
        ed_index = ed_lookup[ed_key]
        use_index = use_lookup[use]

        objective = np.zeros(n_ed * n_category * n_use, dtype=float)
        for category in range(n_category):
            objective[vidx(ed_index, category, use_index)] = 1.0

        low = system["linprog"](
            objective,
            A_ub=system["A_ub"],
            b_ub=system["b_ub"],
            A_eq=system["A_eq"],
            b_eq=system["b_eq"],
            bounds=system["bounds"],
            method=LP_METHOD,
        )
        high = system["linprog"](
            -objective,
            A_ub=system["A_ub"],
            b_ub=system["b_ub"],
            A_eq=system["A_eq"],
            b_eq=system["b_eq"],
            bounds=system["bounds"],
            method=LP_METHOD,
        )
        if not low.success or not high.success:
            message = low.message if not low.success else high.message
            raise RuntimeError(f"exact SC3 feasible-bound LP failed: {message}")

        minimum = float(objective @ low.x)
        maximum = float(objective @ high.x)
        reference_ha = float(reference[ed_index, use_index])
        if reference_ha < minimum - 1e-6 or reference_ha > maximum + 1e-6:
            raise AssertionError("reference allocation lies outside exact feasible bounds")
        rows.append(
            {
                "CSOED": ed_key,
                "USE": use,
                "REFERENCE_HA": reference_ha,
                "EXACT_MIN_HA": max(minimum, 0.0),
                "EXACT_MAX_HA": max(maximum, 0.0),
                "EXACT_RANGE_HA": max(maximum - minimum, 0.0),
                "FIXED_NATIONAL_REALISED_HA": float(system["realised"][use]),
                "SC3_FEASIBLE_GEOGRAPHY_VERSION": FLEX_VERSION,
                "INTERPRETATION": (
                    "EXACT_SPATIAL_BOUND_GIVEN_FIXED_PER_USE_NATIONAL_REALISED_VECTOR"
                ),
            }
        )
    return pd.DataFrame(rows)
