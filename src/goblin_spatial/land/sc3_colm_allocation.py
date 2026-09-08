"""SC3 joint allocation on finite Colm physical released-land resource cells.

SC3 consumes a frozen SC2 Colm-direct resource partition and explicit national
2050 land-use targets. The five Stage-A uses compete simultaneously for the same
seven ED x soil resource cells, so one released hectare cannot satisfy multiple
future uses.

The optimiser is lexicographic when explicit opportunity scores are supplied:
Stage 1 minimises total unmet national target; Stage 2 preserves that minimum
shortfall and maximises evidence-backed spatial opportunity fit. When no
opportunity score mapping is supplied, the Stage-1 feasibility solution is used
without inventing a ranking.

Rewetting remains scientifically separate. Mapped peat alone is not accepted as
rewetting capacity. A positive rewetting target requires explicit validated
released-land capacity columns by Colm resource category.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from goblin_spatial.land.sc2_colm_direct import (
    COLM_PHYSICAL_CATEGORIES,
    COLM_RELEASED_AREA_COLUMNS,
    COLM_STAGE_A_USES,
    validate_colm_eligibility_rules,
)

STAGE_A_USES = COLM_STAGE_A_USES
REWETTING_USE = "REWETTING"
SC3_USES = (*STAGE_A_USES, REWETTING_USE)
HA_TOL = 1e-7
LP_METHOD = "highs"
SC3_COLM_VERSION = "1.0"


def _scipy():
    try:
        from scipy.optimize import linprog
        from scipy.sparse import coo_matrix, vstack
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Colm-direct SC3 requires scipy. Install with: "
            "pip install 'goblin-spatial[scenario]'"
        ) from exc
    return linprog, coo_matrix, vstack


def _numeric(frame: pd.DataFrame, column: str, *, bounded: bool = False) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"Colm-direct SC3 input missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    if bounded:
        if ((values < -1e-12) | (values > 1.0 + 1e-12)).any():
            raise ValueError(f"{column} must lie in [0,1]")
        return np.clip(values, 0.0, 1.0)
    if (values < -1e-10).any():
        raise ValueError(f"{column} must be non-negative")
    return np.maximum(values, 0.0)


def _validate_targets(targets: Mapping[str, float]) -> dict[str, float]:
    supplied = {str(key).strip().upper(): float(value) for key, value in targets.items()}
    missing = sorted(set(SC3_USES) - set(supplied))
    extra = sorted(set(supplied) - set(SC3_USES))
    if missing or extra:
        raise ValueError(
            "Colm-direct SC3 targets must contain exactly the six supported uses; "
            f"missing={missing}, extra={extra}"
        )
    if any((not np.isfinite(value)) or value < 0 for value in supplied.values()):
        raise ValueError("SC3 national targets must be finite and non-negative")
    return supplied


def _resource_matrix(frame: pd.DataFrame) -> np.ndarray:
    missing = sorted(set(COLM_RELEASED_AREA_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"SC3 missing Colm released-resource columns: {missing}")
    resource = (
        frame[list(COLM_RELEASED_AREA_COLUMNS)]
        .apply(pd.to_numeric, errors="raise")
        .to_numpy(dtype=float)
    )
    if (~np.isfinite(resource)).any() or (resource < -1e-10).any():
        raise ValueError("SC3 Colm released-resource cells must be finite and non-negative")
    resource = np.maximum(resource, 0.0)
    if "GOBLIN_RELEASED_GRASSLAND_HA" in frame.columns:
        release = _numeric(frame, "GOBLIN_RELEASED_GRASSLAND_HA")
        if not np.allclose(resource.sum(axis=1), release, atol=1e-7):
            raise AssertionError("SC3 Colm resource cells do not close to frozen SC1 release")
    return resource


def _opportunity_scores(
    frame: pd.DataFrame,
    mapping: Mapping[str, str] | None,
) -> tuple[dict[str, np.ndarray], bool]:
    if mapping is None:
        return {
            use: np.zeros(len(frame), dtype=float) for use in STAGE_A_USES
        }, False
    supplied = {str(key).strip().upper(): str(value).strip() for key, value in mapping.items()}
    missing = sorted(set(STAGE_A_USES) - set(supplied))
    extra = sorted(set(supplied) - set(STAGE_A_USES))
    if missing or extra:
        raise ValueError(
            "opportunity score mapping must cover every Stage-A use exactly; "
            f"missing={missing}, extra={extra}"
        )
    return {
        use: _numeric(frame, supplied[use], bounded=True) for use in STAGE_A_USES
    }, True


def _joint_stage_a(
    resource: np.ndarray,
    targets: Mapping[str, float],
    rules: Mapping[str, Mapping[str, float]],
    scores: Mapping[str, np.ndarray],
    *,
    apply_ranking: bool,
) -> tuple[np.ndarray, dict[str, float], dict[str, object]]:
    """Jointly allocate Stage-A uses over ED x Colm-soil cells."""

    linprog, coo_matrix, vstack = _scipy()
    validated = validate_colm_eligibility_rules(rules, allowed_uses=STAGE_A_USES)
    if set(validated) != set(STAGE_A_USES):
        missing = sorted(set(STAGE_A_USES) - set(validated))
        extra = sorted(set(validated) - set(STAGE_A_USES))
        raise ValueError(
            "SC3 requires one explicit eligibility rule for every Stage-A use; "
            f"missing={missing}, extra={extra}"
        )

    n_ed, n_category = resource.shape
    n_use = len(STAGE_A_USES)
    n_alloc = n_ed * n_category * n_use
    unmet_offset = n_alloc
    n_var = n_alloc + n_use
    use_index = {use: index for index, use in enumerate(STAGE_A_USES)}

    def vidx(ed: int, category: int, use: int) -> int:
        return (ed * n_category + category) * n_use + use

    bounds: list[tuple[float, float]] = []
    for ed in range(n_ed):
        for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
            cell = float(resource[ed, category_index])
            for use in STAGE_A_USES:
                coefficient = float(validated[use][category])
                upper = cell * coefficient
                if float(targets[use]) <= HA_TOL:
                    upper = 0.0
                bounds.append((0.0, max(upper, 0.0)))
    for use in STAGE_A_USES:
        bounds.append((0.0, max(float(targets[use]), 0.0)))

    # National target identities: allocation + unmet = target.
    rr: list[int] = []
    cc: list[int] = []
    dd: list[float] = []
    beq: list[float] = []
    for use_pos, use in enumerate(STAGE_A_USES):
        for ed in range(n_ed):
            for category in range(n_category):
                rr.append(use_pos)
                cc.append(vidx(ed, category, use_pos))
                dd.append(1.0)
        rr.append(use_pos)
        cc.append(unmet_offset + use_pos)
        dd.append(1.0)
        beq.append(float(targets[use]))
    aeq = coo_matrix((dd, (rr, cc)), shape=(n_use, n_var)).tocsr()
    beq_array = np.asarray(beq, dtype=float)

    # Shared physical resource: all competing uses draw from the same soil cell.
    rr = []
    cc = []
    dd = []
    bub: list[float] = []
    row = 0
    for ed in range(n_ed):
        for category in range(n_category):
            for use_pos in range(n_use):
                rr.append(row)
                cc.append(vidx(ed, category, use_pos))
                dd.append(1.0)
            bub.append(float(resource[ed, category]))
            row += 1
    aub = coo_matrix((dd, (rr, cc)), shape=(row, n_var)).tocsr()
    bub_array = np.asarray(bub, dtype=float)

    objective_1 = np.zeros(n_var, dtype=float)
    objective_1[unmet_offset:] = 1.0
    stage_1 = linprog(
        objective_1,
        A_ub=aub,
        b_ub=bub_array,
        A_eq=aeq,
        b_eq=beq_array,
        bounds=bounds,
        method=LP_METHOD,
    )
    if not stage_1.success:
        raise RuntimeError(f"SC3 Colm Stage-A feasibility LP failed: {stage_1.message}")
    min_unmet = float(stage_1.x[unmet_offset:].sum())

    solution = stage_1
    if apply_ranking:
        # Preserve minimum total unmet and maximise explicit opportunity fit.
        extra = coo_matrix(
            (
                np.ones(n_use),
                (
                    np.zeros(n_use, dtype=int),
                    np.arange(unmet_offset, unmet_offset + n_use),
                ),
            ),
            shape=(1, n_var),
        ).tocsr()
        aeq_2 = vstack([aeq, extra]).tocsr()
        beq_2 = np.concatenate([beq_array, np.array([min_unmet])])
        objective_2 = np.zeros(n_var, dtype=float)
        for ed in range(n_ed):
            for category in range(n_category):
                for use_pos, use in enumerate(STAGE_A_USES):
                    target = float(targets[use])
                    normaliser = target if target > HA_TOL else 1.0
                    objective_2[vidx(ed, category, use_pos)] = (
                        -float(scores[use][ed]) / normaliser
                    )
        stage_2 = linprog(
            objective_2,
            A_ub=aub,
            b_ub=bub_array,
            A_eq=aeq_2,
            b_eq=beq_2,
            bounds=bounds,
            method=LP_METHOD,
        )
        if not stage_2.success:
            raise RuntimeError(
                f"SC3 Colm Stage-A opportunity LP failed: {stage_2.message}"
            )
        solution = stage_2

    alloc = solution.x[:n_alloc].reshape(n_ed, n_category, n_use)
    unmet = {
        use: float(solution.x[unmet_offset + use_index[use]])
        for use in STAGE_A_USES
    }
    if (alloc.sum(axis=2) - resource > 1e-6).any():
        raise AssertionError("SC3 Stage-A allocation exceeded a Colm resource cell")
    for use_pos, use in enumerate(STAGE_A_USES):
        realised = float(alloc[:, :, use_pos].sum())
        if abs(realised + unmet[use] - float(targets[use])) > 1e-5:
            raise AssertionError(f"SC3 national target identity failed for {use}")

    diagnostics: dict[str, object] = {
        "MIN_STAGE_A_UNMET_HA": min_unmet,
        "OPPORTUNITY_RANKING_APPLIED": bool(apply_ranking),
        "LP_METHOD": LP_METHOD,
    }
    return alloc, unmet, diagnostics


def _allocate_rewetting(
    frame: pd.DataFrame,
    residual_resource: np.ndarray,
    target: float,
    *,
    capacity_columns: Mapping[str, str] | None,
    opportunity_column: str | None,
) -> tuple[np.ndarray, float, dict[str, object]]:
    """Allocate rewetting only from explicitly validated residual capacities."""

    n_ed, n_category = residual_resource.shape
    allocation = np.zeros_like(residual_resource)
    target = float(target)
    if target <= HA_TOL:
        return allocation, 0.0, {
            "REWETTING_CAPACITY_STATUS": "ZERO_TARGET",
            "REWETTING_AVAILABLE_CAPACITY_HA": 0.0,
        }
    if capacity_columns is None:
        raise ValueError(
            "positive REWETTING target requires explicit validated rewetting capacity "
            "columns by Colm category; mapped peat alone is not accepted"
        )

    mapping = {str(key).strip().upper(): str(value).strip() for key, value in capacity_columns.items()}
    extra = sorted(set(mapping) - set(COLM_PHYSICAL_CATEGORIES))
    if extra:
        raise ValueError(f"unknown Colm categories in rewetting capacity mapping: {extra}")
    if not mapping:
        raise ValueError("rewetting capacity mapping cannot be empty")

    capacity = np.zeros_like(residual_resource)
    for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
        if category not in mapping:
            continue
        raw = _numeric(frame, mapping[category])
        capacity[:, category_index] = np.minimum(
            np.maximum(raw, 0.0),
            residual_resource[:, category_index],
        )

    available = float(capacity.sum())
    realised_target = min(target, available)
    if realised_target <= HA_TOL:
        return allocation, target, {
            "REWETTING_CAPACITY_STATUS": "VALIDATED_CAPACITY_ZERO",
            "REWETTING_AVAILABLE_CAPACITY_HA": available,
        }

    if opportunity_column is None:
        weights = capacity.copy()
    else:
        score = _numeric(frame, opportunity_column, bounded=True)
        weights = capacity * score[:, None]
        if float(weights.sum()) <= HA_TOL:
            weights = capacity.copy()

    remaining_capacity = capacity.copy()
    remaining = realised_target
    for _ in range(20000):
        if remaining <= HA_TOL:
            break
        active = (remaining_capacity > HA_TOL) & (weights > HA_TOL)
        if not active.any():
            active = remaining_capacity > HA_TOL
            local_weights = np.where(active, remaining_capacity, 0.0)
        else:
            local_weights = np.where(active, weights, 0.0)
        total_weight = float(local_weights.sum())
        if total_weight <= HA_TOL:
            break
        proposal = remaining * local_weights / total_weight
        take = np.minimum(proposal, remaining_capacity)
        moved = float(take.sum())
        if moved <= 1e-12:
            break
        allocation += take
        remaining_capacity = np.maximum(remaining_capacity - take, 0.0)
        remaining = max(remaining - moved, 0.0)
    if remaining > 1e-5:
        raise AssertionError("rewetting allocation failed to place available validated capacity")

    unmet = target - float(allocation.sum())
    return allocation, max(unmet, 0.0), {
        "REWETTING_CAPACITY_STATUS": "VALIDATED_EXPLICIT_CAPACITY",
        "REWETTING_AVAILABLE_CAPACITY_HA": available,
    }


def allocate_colm_sc3_targets(
    frame: pd.DataFrame,
    targets: Mapping[str, float],
    *,
    eligibility_rules: Mapping[str, Mapping[str, float]],
    opportunity_columns: Mapping[str, str] | None = None,
    rewetting_capacity_columns: Mapping[str, str] | None = None,
    rewetting_opportunity_column: str | None = None,
) -> pd.DataFrame:
    """Allocate explicit national targets over frozen Colm physical resources."""

    if "CSOED" not in frame.columns:
        raise ValueError("SC3 requires CSOED")
    if frame["CSOED"].duplicated().any():
        raise ValueError("SC3 requires one row per ED")

    target = _validate_targets(targets)
    resource = _resource_matrix(frame)
    scores, ranking = _opportunity_scores(frame, opportunity_columns)
    stage_a, unmet, diagnostics = _joint_stage_a(
        resource,
        target,
        eligibility_rules,
        scores,
        apply_ranking=ranking,
    )

    residual = np.maximum(resource - stage_a.sum(axis=2), 0.0)
    rewetting, rewetting_unmet, rewetting_diag = _allocate_rewetting(
        frame,
        residual,
        target[REWETTING_USE],
        capacity_columns=rewetting_capacity_columns,
        opportunity_column=rewetting_opportunity_column,
    )
    residual = np.maximum(residual - rewetting, 0.0)
    unmet[REWETTING_USE] = float(rewetting_unmet)

    out = frame.copy()
    for use_pos, use in enumerate(STAGE_A_USES):
        out[f"SC3_{use}_ALLOCATED_HA"] = stage_a[:, :, use_pos].sum(axis=1)
        for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
            out[f"SC3_{use}_{category}_HA"] = stage_a[:, category_index, use_pos]
    out["SC3_REWETTING_ALLOCATED_HA"] = rewetting.sum(axis=1)
    for category_index, category in enumerate(COLM_PHYSICAL_CATEGORIES):
        out[f"SC3_REWETTING_{category}_HA"] = rewetting[:, category_index]
        out[f"SC3_RESIDUAL_{category}_HA"] = residual[:, category_index]

    allocated_columns = [f"SC3_{use}_ALLOCATED_HA" for use in SC3_USES]
    out["SC3_TOTAL_ALLOCATED_HA"] = out[allocated_columns].sum(axis=1)
    out["SC3_RESIDUAL_RELEASED_HA"] = residual.sum(axis=1)
    release = _numeric(out, "GOBLIN_RELEASED_GRASSLAND_HA")
    if not np.allclose(
        out["SC3_TOTAL_ALLOCATED_HA"].to_numpy(float)
        + out["SC3_RESIDUAL_RELEASED_HA"].to_numpy(float),
        release,
        atol=1e-6,
    ):
        raise AssertionError("SC3 allocated + residual land does not close to frozen release")

    for use in SC3_USES:
        realised = float(pd.to_numeric(out[f"SC3_{use}_ALLOCATED_HA"], errors="raise").sum())
        if abs(realised + float(unmet[use]) - float(target[use])) > 1e-5:
            raise AssertionError(f"SC3 realised + unmet does not close for {use}")
        out[f"SC3_{use}_NATIONAL_TARGET_HA"] = float(target[use])
        out[f"SC3_{use}_NATIONAL_REALISED_HA"] = realised
        out[f"SC3_{use}_NATIONAL_UNMET_HA"] = float(unmet[use])

    out["SC3_COLM_VERSION"] = SC3_COLM_VERSION
    out["SC3_ALLOCATION_ARCHITECTURE"] = "ED_X_COLM_SOIL_SHARED_RESOURCE_LP"
    out["SC3_G1_G2_G3_USED"] = False
    out["SC3_OPPORTUNITY_RANKING_APPLIED"] = bool(
        diagnostics["OPPORTUNITY_RANKING_APPLIED"]
    )
    out["SC3_STAGE_A_MIN_UNMET_HA"] = float(diagnostics["MIN_STAGE_A_UNMET_HA"])
    out["SC3_REWETTING_CAPACITY_STATUS"] = str(
        rewetting_diag["REWETTING_CAPACITY_STATUS"]
    )
    out["SC3_REWETTING_AVAILABLE_CAPACITY_HA"] = float(
        rewetting_diag["REWETTING_AVAILABLE_CAPACITY_HA"]
    )
    return out


def summarise_colm_sc3_allocation(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one-row national realised/unmet/residual SC3 summary."""

    row: dict[str, float | str | bool] = {}
    for use in SC3_USES:
        allocated = f"SC3_{use}_ALLOCATED_HA"
        if allocated not in frame.columns:
            raise ValueError(f"SC3 summary missing {allocated}")
        row[f"{use}_REALISED_HA"] = float(
            pd.to_numeric(frame[allocated], errors="raise").sum()
        )
        target_column = f"SC3_{use}_NATIONAL_TARGET_HA"
        unmet_column = f"SC3_{use}_NATIONAL_UNMET_HA"
        row[f"{use}_TARGET_HA"] = float(pd.to_numeric(frame[target_column], errors="raise").iloc[0])
        row[f"{use}_UNMET_HA"] = float(pd.to_numeric(frame[unmet_column], errors="raise").iloc[0])
    row["TOTAL_RELEASED_HA"] = float(_numeric(frame, "GOBLIN_RELEASED_GRASSLAND_HA").sum())
    row["TOTAL_ALLOCATED_HA"] = float(_numeric(frame, "SC3_TOTAL_ALLOCATED_HA").sum())
    row["RESIDUAL_RELEASED_HA"] = float(_numeric(frame, "SC3_RESIDUAL_RELEASED_HA").sum())
    row["SC3_COLM_VERSION"] = str(frame["SC3_COLM_VERSION"].iloc[0])
    row["OPPORTUNITY_RANKING_APPLIED"] = bool(frame["SC3_OPPORTUNITY_RANKING_APPLIED"].iloc[0])
    row["REWETTING_CAPACITY_STATUS"] = str(frame["SC3_REWETTING_CAPACITY_STATUS"].iloc[0])
    return pd.DataFrame([row])
