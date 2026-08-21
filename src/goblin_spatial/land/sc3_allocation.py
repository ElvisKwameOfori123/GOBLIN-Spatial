"""SC3 v2.7 constrained allocation of explicit national land-use targets.

SC3 consumes completed mature SC2 opportunity/eligibility output. National
targets are supplied by the caller, normally from the editable scenario control
row; this module contains no pathway-specific target table.

Stage A jointly allocates the five mineral/bioeconomy uses with the mature
lexicographic LP and nested shared physical pools. Stage 1 minimises total unmet
hectares. Stage 2 holds that minimum unmet total fixed and maximises the
target-normalised SC2 opportunity ranking.

Stage B allocates rewetting only after Stage A, within both the post-Stage-A
Available residual and an externally anchored drained-organic-grassland stock
spatialised by ``ALL_GRASSLAND x IFS_PEAT_CUTOVER_UAA_SHARE``.

The frozen SC1 release is never changed and no infeasible hectares are forced.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


STAGE_A_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
)
REWETTING_USE = "REWETTING"
SC3_USES = (*STAGE_A_USES, REWETTING_USE)

TILLAGE_STRICT = False
WILLOW_WIDE = False
REQUIRE_FOREST_YC = True
TARGET_NORMALISE_STAGE2_SCORE = True
NATIONAL_DRAINED_ORGANIC_GRASSLAND_HA = 141_000.0
HA_TOL = 1e-6
ED_CLOSURE_TOL = 1e-7
LP_METHOD = "highs"

DEFAULT_CAPACITY_COLUMNS = {
    "AD_GRASS": "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA",
    "BIOREFINERY_GRASS": "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA",
    "WILLOW": "RELEASED_WILLOW_ELIGIBLE_HA",
    "ADDITIONAL_TILLAGE": "RELEASED_TILLAGE_ELIGIBLE_HA",
    "FOREST": "RELEASED_FOREST_ELIGIBLE_HA",
}
DEFAULT_SCORE_COLUMNS = {
    "AD_GRASS": "AD_GRASS_OPPORTUNITY_SCORE",
    "BIOREFINERY_GRASS": "AD_GRASS_OPPORTUNITY_SCORE",
    "WILLOW": "WILLOW_OPPORTUNITY_SCORE",
    "ADDITIONAL_TILLAGE": "GOBLIN_SOIL_PRODUCTIVITY_SCORE",
    "FOREST": "FORESTRY_OPPORTUNITY_SCORE",
    "REWETTING": "IFS_PEAT_CUTOVER_UAA_SHARE",
}


def _scipy():
    """Lazy-load scipy so the verified historical baseline has no new dependency."""

    try:
        from scipy.optimize import linprog
        from scipy.sparse import coo_matrix, vstack
    except ImportError as exc:  # pragma: no cover - import guard only
        raise ImportError(
            "SC3 v2.7 allocation requires scipy. Install with: "
            "pip install 'goblin-spatial[scenario]'"
        ) from exc
    return linprog, coo_matrix, vstack


def _validate_targets(targets: Mapping[str, float]) -> dict[str, float]:
    supplied = {
        str(key).strip().upper(): float(value)
        for key, value in dict(targets).items()
    }
    missing = sorted(set(SC3_USES) - set(supplied))
    extra = sorted(set(supplied) - set(SC3_USES))
    if missing or extra:
        raise ValueError(
            "SC3 targets must contain exactly the six supported land uses; "
            f"missing={missing}, extra={extra}"
        )
    if any((not np.isfinite(value)) or value < 0 for value in supplied.values()):
        raise ValueError("SC3 national targets must be finite and non-negative")
    return supplied


def _resolve_columns(
    supplied: Mapping[str, str] | None,
    defaults: Mapping[str, str],
    *,
    required_uses: Sequence[str],
    label: str,
) -> dict[str, str]:
    resolved = dict(defaults)
    if supplied is not None:
        for key, value in dict(supplied).items():
            use = str(key).strip().upper()
            if use in required_uses:
                resolved[use] = str(value).strip()
    missing = [use for use in required_uses if not resolved.get(use)]
    if missing:
        raise ValueError(f"{label} missing mappings for {missing}")
    return resolved


def _values(
    frame: pd.DataFrame,
    column: str,
    *,
    bounded_score: bool = False,
) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"SC3 input missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    if bounded_score:
        if ((values < -1e-12) | (values > 1.0 + 1e-12)).any():
            raise ValueError(f"{column} must lie in [0, 1]")
        return np.clip(values, 0.0, 1.0)
    if (values < -1e-10).any():
        raise ValueError(f"{column} must be non-negative")
    return np.maximum(values, 0.0)


def _physical_capacities(
    frame: pd.DataFrame,
    targets: Mapping[str, float],
    *,
    release: np.ndarray,
    capacity_columns: Mapping[str, str],
    drained_organic_grassland_ha: float,
    require_forest_yc: bool,
) -> tuple[dict[str, np.ndarray], dict[str, float | np.ndarray]]:
    caps = {
        use: np.minimum(release, _values(frame, capacity_columns[use]))
        for use in STAGE_A_USES
    }

    # Mature forest rule: physical eligibility is additionally conditional on
    # finite positive forest Yield Class context.
    forest_pre_yc = caps["FOREST"].copy()
    if require_forest_yc and float(targets["FOREST"]) > HA_TOL:
        if "FOREST_YC_WEIGHTED_MEAN" not in frame.columns:
            raise ValueError(
                "principal SC3 forest target requires FOREST_YC_WEIGHTED_MEAN"
            )
        yc = pd.to_numeric(
            frame["FOREST_YC_WEIGHTED_MEAN"], errors="coerce"
        ).to_numpy(float)
        has_yc = np.isfinite(yc) & (yc > 0)
        caps["FOREST"] = np.where(has_yc, caps["FOREST"], 0.0)
    forest_removed_mask = (forest_pre_yc > HA_TOL) & (
        caps["FOREST"] < forest_pre_yc - HA_TOL
    )

    # Mature rewetting rule: RELEASED_ORGANIC_WEIGHT_HA remains an unscaled
    # diagnostic. Principal capacity uses an external drained-organic-grassland
    # stock, spatialised by ALL_GRASSLAND x IFS peat/cutover share, then
    # intersected with the policy-specific released-land geography.
    grass = _values(frame, "ALL_GRASSLAND")
    organic_share = _values(
        frame,
        "IFS_PEAT_CUTOVER_UAA_SHARE",
        bounded_score=True,
    )
    organic_weight = grass * organic_share
    total_weight = float(organic_weight.sum())
    anchor = float(drained_organic_grassland_ha)
    if not np.isfinite(anchor) or anchor < 0:
        raise ValueError(
            "drained_organic_grassland_ha must be finite and non-negative"
        )
    if anchor > HA_TOL and total_weight <= HA_TOL:
        raise AssertionError(
            "cannot spatialise drained-organic-grassland stock from zero "
            "ALL_GRASSLAND x IFS_PEAT_CUTOVER_UAA_SHARE"
        )
    stock = (
        anchor * organic_weight / total_weight
        if anchor > HA_TOL
        else np.zeros(len(frame), dtype=float)
    )
    if (stock - grass > HA_TOL).any():
        raise AssertionError(
            "anchored ED drained-organic-grassland stock exceeds ALL_GRASSLAND"
        )
    if abs(float(stock.sum()) - anchor) > HA_TOL:
        raise AssertionError(
            "drained-organic-grassland stock does not close nationally"
        )

    caps[REWETTING_USE] = np.minimum(release, stock)
    raw_organic = (
        float(_values(frame, "RELEASED_ORGANIC_WEIGHT_HA").sum())
        if "RELEASED_ORGANIC_WEIGHT_HA" in frame.columns
        else np.nan
    )
    diag: dict[str, float | np.ndarray] = {
        "REWETTING_STOCK_BY_ED_HA": stock,
        "REWETTING_PRE_STAGE_A_CAPACITY_HA": caps[REWETTING_USE].copy(),
        "REWETTING_NATIONAL_STOCK_ANCHOR_HA": anchor,
        "REWETTING_RAW_UNSCALED_SC2_HA": raw_organic,
        "FOREST_ELIGIBLE_BEFORE_YC_HA": float(forest_pre_yc.sum()),
        "FOREST_ELIGIBLE_AFTER_YC_HA": float(caps["FOREST"].sum()),
        "FOREST_YC_REMOVED_HA": float(
            (forest_pre_yc - caps["FOREST"]).sum()
        ),
        "FOREST_YC_REMOVED_EDS": int(forest_removed_mask.sum()),
    }
    return caps, diag


def _shared_pools(
    frame: pd.DataFrame,
    release: np.ndarray,
    *,
    tillage_strict: bool,
    willow_wide: bool,
) -> dict[str, np.ndarray]:
    if willow_wide:
        lower_col = (
            "RELEASED_TILLAGE_STRICT_ELIGIBLE_HA"
            if tillage_strict
            else "RELEASED_TILLAGE_ELIGIBLE_HA"
        )
    else:
        lower_col = "RELEASED_WILLOW_ELIGIBLE_HA"

    pools = {
        "POOL_TILLAGE_WILLOW": np.minimum(
            release,
            _values(frame, lower_col),
        ),
        "POOL_AD_BIOREFINERY": np.minimum(
            release,
            _values(frame, "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA"),
        ),
        "POOL_FOREST": np.minimum(
            release,
            _values(frame, "RELEASED_FOREST_ELIGIBLE_HA"),
        ),
    }
    if (
        pools["POOL_AD_BIOREFINERY"] - pools["POOL_FOREST"] > HA_TOL
    ).any():
        raise AssertionError(
            "SC2 AD/biorefinery pool exceeds forest mineral pool"
        )
    if (
        not willow_wide
        and (
            pools["POOL_TILLAGE_WILLOW"]
            - pools["POOL_AD_BIOREFINERY"]
            > HA_TOL
        ).any()
    ):
        raise AssertionError(
            "SC2 tillage/willow pool exceeds AD/biorefinery pool"
        )
    if (pools["POOL_FOREST"] - release > HA_TOL).any():
        raise AssertionError("SC2 forest pool exceeds released-land budget")
    return pools


def _joint_stage_a_allocate(
    release: np.ndarray,
    caps: Mapping[str, np.ndarray],
    pools: Mapping[str, np.ndarray],
    scores: Mapping[str, np.ndarray],
    targets: Mapping[str, float],
    *,
    target_normalise_score: bool,
    willow_wide: bool,
) -> tuple[dict[str, np.ndarray], dict[str, float], dict[str, object]]:
    """Mature lexicographic LP for the five Stage-A uses."""

    linprog, coo_matrix, vstack = _scipy()
    uses = STAGE_A_USES
    n_ed = len(release)
    n_use = len(uses)
    n_alloc = n_ed * n_use
    unmet_offset = n_alloc
    n_var = n_alloc + n_use
    use_index = {use: i for i, use in enumerate(uses)}

    def vidx(e: int, u: int) -> int:
        return e * n_use + u

    bounds = []
    for e in range(n_ed):
        for use in uses:
            upper = float(max(caps[use][e], 0.0))
            if float(targets[use]) <= HA_TOL:
                upper = 0.0
            bounds.append((0.0, upper))
    for use in uses:
        bounds.append((0.0, float(max(targets[use], 0.0))))

    # National target identities: allocation + unmet = explicit target.
    rr: list[int] = []
    cc: list[int] = []
    dd: list[float] = []
    beq: list[float] = []
    for u, use in enumerate(uses):
        for e in range(n_ed):
            rr.append(u)
            cc.append(vidx(e, u))
            dd.append(1.0)
        rr.append(u)
        cc.append(unmet_offset + u)
        dd.append(1.0)
        beq.append(float(targets[use]))
    aeq = coo_matrix((dd, (rr, cc)), shape=(n_use, n_var)).tocsr()
    beq_array = np.asarray(beq, float)

    # ED released-land budget and mature nested mineral pools.
    rr = []
    cc = []
    dd = []
    bub: list[float] = []
    row = 0
    for e in range(n_ed):
        for use in uses:
            rr.append(row)
            cc.append(vidx(e, use_index[use]))
            dd.append(1.0)
        bub.append(float(release[e]))
        row += 1

        lower_uses = ["ADDITIONAL_TILLAGE"]
        if not willow_wide:
            lower_uses.append("WILLOW")
        for use in lower_uses:
            rr.append(row)
            cc.append(vidx(e, use_index[use]))
            dd.append(1.0)
        bub.append(float(pools["POOL_TILLAGE_WILLOW"][e]))
        row += 1

        for use in (
            "AD_GRASS",
            "BIOREFINERY_GRASS",
            "WILLOW",
            "ADDITIONAL_TILLAGE",
        ):
            rr.append(row)
            cc.append(vidx(e, use_index[use]))
            dd.append(1.0)
        bub.append(float(pools["POOL_AD_BIOREFINERY"][e]))
        row += 1

        for use in uses:
            rr.append(row)
            cc.append(vidx(e, use_index[use]))
            dd.append(1.0)
        bub.append(float(pools["POOL_FOREST"][e]))
        row += 1

    aub = coo_matrix((dd, (rr, cc)), shape=(row, n_var)).tocsr()
    bub_array = np.asarray(bub, float)

    # Stage 1: minimise total unmet hectares.
    objective_1 = np.zeros(n_var, float)
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
        raise RuntimeError(
            f"SC3 Stage-A feasibility LP failed: {stage_1.message}"
        )
    min_unmet = float(stage_1.x[unmet_offset:].sum())

    # Stage 2: preserve minimum unmet and maximise spatial opportunity fit.
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
    aeq_2 = vstack([aeq, extra], format="csr")
    beq_2 = np.concatenate([beq_array, [min_unmet]])

    objective_2 = np.zeros(n_var, float)
    for e in range(n_ed):
        for use in uses:
            coefficient = float(scores[use][e])
            if target_normalise_score:
                coefficient /= max(float(targets[use]), 1.0)
            objective_2[vidx(e, use_index[use])] = -coefficient

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
            f"SC3 Stage-A opportunity LP failed: {stage_2.message}"
        )

    allocation = {
        use: np.asarray(
            [stage_2.x[vidx(e, use_index[use])] for e in range(n_ed)],
            float,
        )
        for use in uses
    }
    unmet = {
        use: float(max(stage_2.x[unmet_offset + use_index[use]], 0.0))
        for use in uses
    }
    return allocation, unmet, {
        "STAGE_A_MIN_TOTAL_UNMET_HA": min_unmet,
        "STAGE_A_OPPORTUNITY_OBJECTIVE": float(-stage_2.fun),
        "STAGE_A_STAGE1_MESSAGE": stage_1.message,
        "STAGE_A_STAGE2_MESSAGE": stage_2.message,
        "STAGE_A_N_VARIABLES": int(n_var),
        "STAGE_A_N_EQUALITY_CONSTRAINTS": int(aeq_2.shape[0]),
        "STAGE_A_N_INEQUALITY_CONSTRAINTS": int(aub.shape[0]),
    }


def _allocate_rewetting(
    capacity: np.ndarray,
    score: np.ndarray,
    target: float,
) -> tuple[np.ndarray, float, dict[str, object]]:
    """Allocate rewetting after Stage A within post-Stage-A organic capacity."""

    linprog, _, _ = _scipy()
    capacity = np.maximum(np.asarray(capacity, float), 0.0)
    score = np.clip(np.asarray(score, float), 0.0, 1.0)
    target = max(float(target), 0.0)
    feasible_target = min(target, float(capacity.sum()))
    unmet = max(target - feasible_target, 0.0)
    if feasible_target <= HA_TOL:
        return np.zeros_like(capacity), unmet, {
            "REWETTING_STAGE_TARGET_HA": target,
            "REWETTING_STAGE_CAPACITY_HA": float(capacity.sum()),
            "REWETTING_STAGE_ALLOCATED_HA": 0.0,
            "REWETTING_STAGE_UNMET_HA": unmet,
            "REWETTING_STAGE_STATUS": (
                "NO_TARGET"
                if target <= HA_TOL
                else "NO_FEASIBLE_ALLOCATION"
            ),
        }

    solution = linprog(
        -score,
        A_eq=np.ones((1, len(capacity)), dtype=float),
        b_eq=np.asarray([feasible_target], dtype=float),
        bounds=[(0.0, float(cap)) for cap in capacity],
        method=LP_METHOD,
    )
    if not solution.success:
        raise RuntimeError(
            f"SC3 sequential rewetting LP failed: {solution.message}"
        )
    allocation = np.maximum(np.asarray(solution.x, float), 0.0)
    return allocation, unmet, {
        "REWETTING_STAGE_TARGET_HA": target,
        "REWETTING_STAGE_CAPACITY_HA": float(capacity.sum()),
        "REWETTING_STAGE_ALLOCATED_HA": float(allocation.sum()),
        "REWETTING_STAGE_UNMET_HA": unmet,
        "REWETTING_STAGE_OBJECTIVE": float(-solution.fun),
        "REWETTING_STAGE_STATUS": "OPTIMAL",
        "REWETTING_STAGE_MESSAGE": solution.message,
    }


def allocate_sc3_targets(
    frame: pd.DataFrame,
    targets: Mapping[str, float],
    *,
    capacity_columns: Mapping[str, str] | None = None,
    score_columns: Mapping[str, str] | None = None,
    release_column: str = "SC2_POTENTIAL_RELEASE_HA",
    stage_a_priority: Sequence[str] | None = None,
    drained_organic_grassland_ha: float = NATIONAL_DRAINED_ORGANIC_GRASSLAND_HA,
    tillage_strict: bool = TILLAGE_STRICT,
    willow_wide: bool = WILLOW_WIDE,
    require_forest_yc: bool = REQUIRE_FOREST_YC,
    target_normalise_score: bool = TARGET_NORMALISE_STAGE2_SCORE,
) -> pd.DataFrame:
    """Allocate explicit targets using mature SC3 v2.7 mathematics.

    ``stage_a_priority`` is accepted only to make the scientific change
    explicit: SC3 v2.7 has no sequential Stage-A priority. Supplying one is
    rejected rather than silently reverting to the earlier allocator.
    """

    if stage_a_priority is not None:
        raise ValueError(
            "SC3 v2.7 Stage A is a joint LP; sequential stage_a_priority "
            "is not supported"
        )
    if "CSOED" not in frame.columns:
        raise ValueError("SC3 allocation requires CSOED")
    if frame["CSOED"].duplicated().any():
        raise ValueError("SC3 endpoint allocation requires one row per ED")

    target_map = _validate_targets(targets)
    capacity_map = _resolve_columns(
        capacity_columns,
        DEFAULT_CAPACITY_COLUMNS,
        required_uses=STAGE_A_USES,
        label="capacity_columns",
    )
    score_map = _resolve_columns(
        score_columns,
        DEFAULT_SCORE_COLUMNS,
        required_uses=SC3_USES,
        label="score_columns",
    )

    out = frame.copy()
    release = _values(out, release_column)
    if "GOBLIN_RELEASED_GRASSLAND_HA" in out.columns:
        goblin_release = _values(out, "GOBLIN_RELEASED_GRASSLAND_HA")
        if not np.allclose(release, goblin_release, atol=ED_CLOSURE_TOL):
            raise AssertionError(
                "SC3 release column disagrees with frozen SC1 GOBLIN release"
            )

    # Apply the mature strict/wide sensitivity switches only when caller has
    # not explicitly overridden the individual capacity columns.
    if capacity_columns is None:
        if tillage_strict:
            capacity_map["ADDITIONAL_TILLAGE"] = (
                "RELEASED_TILLAGE_STRICT_ELIGIBLE_HA"
            )
        if willow_wide:
            capacity_map["WILLOW"] = "RELEASED_WILLOW_WIDE_ELIGIBLE_HA"

    caps, cap_diag = _physical_capacities(
        out,
        target_map,
        release=release,
        capacity_columns=capacity_map,
        drained_organic_grassland_ha=drained_organic_grassland_ha,
        require_forest_yc=require_forest_yc,
    )
    scores = {
        use: _values(out, score_map[use], bounded_score=True)
        for use in SC3_USES
    }
    pools = _shared_pools(
        out,
        release,
        tillage_strict=tillage_strict,
        willow_wide=willow_wide,
    )

    allocation, unmet, stage_a_solver = _joint_stage_a_allocate(
        release,
        caps,
        pools,
        scores,
        target_map,
        target_normalise_score=target_normalise_score,
        willow_wide=willow_wide,
    )

    stage_a_allocated = np.zeros(len(out), dtype=float)
    for use in STAGE_A_USES:
        stage_a_allocated += allocation[use]
    available_before_rewetting = np.maximum(
        release - stage_a_allocated,
        0.0,
    )

    # Tighten the anchored organic capacity to the actual post-Stage-A
    # Available residual. This is the v2.7 physical exclusivity correction.
    pre_rewet_capacity = np.asarray(
        cap_diag["REWETTING_PRE_STAGE_A_CAPACITY_HA"],
        float,
    )
    post_rewet_capacity = np.minimum(
        pre_rewet_capacity,
        available_before_rewetting,
    )
    rewetting, rewet_unmet, rewet_solver = _allocate_rewetting(
        post_rewet_capacity,
        scores[REWETTING_USE],
        target_map[REWETTING_USE],
    )
    caps[REWETTING_USE] = post_rewet_capacity
    allocation[REWETTING_USE] = rewetting
    unmet[REWETTING_USE] = float(rewet_unmet)

    residual = np.maximum(
        available_before_rewetting - rewetting,
        0.0,
    )

    for use in SC3_USES:
        realised = allocation[use]
        target = float(target_map[use])
        out[f"SC3_ELIGIBLE_{use}_HA"] = caps[use]
        out[f"SC3_{use}_OPPORTUNITY_SCORE"] = scores[use]
        out[f"SC3_REALIZED_{use}_HA"] = realised
        out[f"SC3_NATIONAL_TARGET_{use}_HA"] = target
        out[f"SC3_NATIONAL_REALIZED_{use}_HA"] = float(realised.sum())
        out[f"SC3_NATIONAL_UNMET_{use}_HA"] = float(unmet[use])
        if (realised - caps[use] > HA_TOL).any():
            raise AssertionError(
                f"{use}: allocation exceeds physical eligibility"
            )
        if abs(float(realised.sum()) + float(unmet[use]) - target) > HA_TOL:
            raise AssertionError(f"{use}: national target accounting failed")

    out["SC3_STAGE_A_REALIZED_HA"] = stage_a_allocated
    out["SC3_STAGE_A_AVAILABLE_HA"] = available_before_rewetting
    out["SC3_REWETTING_PRE_STAGE_A_CAPACITY_HA"] = pre_rewet_capacity
    out["SC3_REWETTING_POST_STAGE_A_CAPACITY_HA"] = post_rewet_capacity
    out["SC3_DRAINED_ORGANIC_GRASSLAND_STOCK_HA"] = np.asarray(
        cap_diag["REWETTING_STOCK_BY_ED_HA"],
        float,
    )
    out["SC3_RESIDUAL_AVAILABLE_LAND_HA"] = residual
    out["SC3_REALISED_CONVERSION_HA"] = stage_a_allocated + rewetting

    # Preserve both source-style parent Available accounting and strict physical
    # exclusivity after the rewetting overlay.
    out["SC3_PARENT_LAND_ACCOUNTING_CLOSURE_HA"] = (
        stage_a_allocated + available_before_rewetting - release
    )
    out["SC3_STRICT_EXCLUSIVE_LAND_ACCOUNTING_CLOSURE_HA"] = (
        out["SC3_REALISED_CONVERSION_HA"].to_numpy(float)
        + residual
        - release
    )
    out["SC3_ACCOUNTING_CLOSURE_HA"] = out[
        "SC3_STRICT_EXCLUSIVE_LAND_ACCOUNTING_CLOSURE_HA"
    ]
    if (
        float(
            np.max(
                np.abs(out["SC3_PARENT_LAND_ACCOUNTING_CLOSURE_HA"])
            )
        )
        > ED_CLOSURE_TOL
    ):
        raise AssertionError("SC3 parent released-land accounting failed")
    if (
        float(np.max(np.abs(out["SC3_ACCOUNTING_CLOSURE_HA"])))
        > ED_CLOSURE_TOL
    ):
        raise AssertionError("SC3 strict-exclusive land accounting failed")

    # Realised shared-pool validation.
    lower_used = allocation["ADDITIONAL_TILLAGE"].copy()
    if not willow_wide:
        lower_used += allocation["WILLOW"]
    ad_pool_used = (
        allocation["AD_GRASS"]
        + allocation["BIOREFINERY_GRASS"]
        + allocation["WILLOW"]
        + allocation["ADDITIONAL_TILLAGE"]
    )
    forest_pool_used = sum(allocation[use] for use in STAGE_A_USES)
    if (lower_used - pools["POOL_TILLAGE_WILLOW"] > HA_TOL).any():
        raise AssertionError(
            "SC3 exceeded tillage/willow shared physical pool"
        )
    if (ad_pool_used - pools["POOL_AD_BIOREFINERY"] > HA_TOL).any():
        raise AssertionError(
            "SC3 exceeded AD/biorefinery shared physical pool"
        )
    if (forest_pool_used - pools["POOL_FOREST"] > HA_TOL).any():
        raise AssertionError(
            "SC3 exceeded forest mineral shared physical pool"
        )

    out["SC3_POOL_TILLAGE_WILLOW_CAPACITY_HA"] = pools[
        "POOL_TILLAGE_WILLOW"
    ]
    out["SC3_POOL_TILLAGE_WILLOW_USED_HA"] = lower_used
    out["SC3_POOL_AD_BIOREFINERY_CAPACITY_HA"] = pools[
        "POOL_AD_BIOREFINERY"
    ]
    out["SC3_POOL_AD_BIOREFINERY_USED_HA"] = ad_pool_used
    out["SC3_POOL_FOREST_CAPACITY_HA"] = pools["POOL_FOREST"]
    out["SC3_POOL_FOREST_USED_HA"] = forest_pool_used

    out["SC3_NATIONAL_STAGE_A_AVAILABLE_HA"] = float(
        available_before_rewetting.sum()
    )
    out["SC3_NATIONAL_RESIDUAL_AVAILABLE_LAND_HA"] = float(
        residual.sum()
    )
    out["SC3_TOTAL_UNMET_RELEASED_LAND_TARGET_HA"] = float(
        sum(unmet[use] for use in STAGE_A_USES)
    )
    out["SC3_TOTAL_UNMET_REWETTING_LAND_STATE_HA"] = float(
        unmet[REWETTING_USE]
    )
    out["SC3_TOTAL_UNMET_TARGET_HA"] = float(sum(unmet.values()))
    out["SC3_REWETTING_NATIONAL_STOCK_ANCHOR_HA"] = float(
        cap_diag["REWETTING_NATIONAL_STOCK_ANCHOR_HA"]
    )
    out["SC3_REWETTING_RAW_UNSCALED_SC2_TOTAL_HA"] = float(
        cap_diag["REWETTING_RAW_UNSCALED_SC2_HA"]
    )
    out["SC3_FOREST_ELIGIBLE_BEFORE_YC_HA"] = float(
        cap_diag["FOREST_ELIGIBLE_BEFORE_YC_HA"]
    )
    out["SC3_FOREST_ELIGIBLE_AFTER_YC_HA"] = float(
        cap_diag["FOREST_ELIGIBLE_AFTER_YC_HA"]
    )
    out["SC3_FOREST_YC_REMOVED_HA"] = float(
        cap_diag["FOREST_YC_REMOVED_HA"]
    )
    out["SC3_FOREST_YC_REMOVED_EDS"] = int(
        cap_diag["FOREST_YC_REMOVED_EDS"]
    )

    for key, value in stage_a_solver.items():
        out[f"SC3_SOLVER_{key}"] = value
    for key, value in rewet_solver.items():
        out[f"SC3_SOLVER_{key}"] = value

    out["SC3_ALLOCATION_METHOD"] = (
        "STAGE_A_JOINT_MINERAL_LP_THEN_STAGE_B_REWETTING_WITHIN_AVAILABLE"
    )
    out["SC3_STAGE2_SCORE_NORMALISATION"] = (
        "TARGET_NORMALISED" if target_normalise_score else "RAW_SCORE"
    )
    out["SC3_TILLAGE_ELIGIBILITY"] = (
        "CLASSES_1_2_MINERAL"
        if tillage_strict
        else "CLASSES_1_3_MINERAL"
    )
    out["SC3_WILLOW_ELIGIBILITY"] = (
        "CLASSES_1_4_MINERAL"
        if willow_wide
        else "CLASSES_1_3_MINERAL"
    )
    out["SC3_FOREST_REQUIRES_YC"] = bool(require_forest_yc)
    out["SC3_REWETTING_CAPACITY_BASIS"] = (
        "DRAINED_ORGANIC_STOCK_SCALED_BY_"
        "ALL_GRASSLAND_X_IFS_PEAT_CUTOVER_UAA_SHARE"
    )
    out["SC3_ALLOCATION_VERSION"] = "2.7"
    return out


def summarise_sc3_allocation(
    frame: pd.DataFrame,
    *,
    release_column: str = "SC2_POTENTIAL_RELEASE_HA",
) -> pd.DataFrame:
    """Return one national reconciliation row for mature SC3 v2.7 output."""

    required = {
        release_column,
        "SC3_STAGE_A_AVAILABLE_HA",
        "SC3_RESIDUAL_AVAILABLE_LAND_HA",
        "SC3_REALISED_CONVERSION_HA",
        "SC3_ACCOUNTING_CLOSURE_HA",
    }
    for use in SC3_USES:
        required.update(
            {
                f"SC3_REALIZED_{use}_HA",
                f"SC3_NATIONAL_TARGET_{use}_HA",
                f"SC3_NATIONAL_UNMET_{use}_HA",
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"SC3 summary missing columns: {missing}")

    row: dict[str, float | str] = {
        "POTENTIAL_RELEASE_HA": float(
            pd.to_numeric(frame[release_column], errors="raise").sum()
        ),
        "STAGE_A_AVAILABLE_HA": float(
            pd.to_numeric(
                frame["SC3_STAGE_A_AVAILABLE_HA"],
                errors="raise",
            ).sum()
        ),
        "REALISED_CONVERSION_HA": float(
            pd.to_numeric(
                frame["SC3_REALISED_CONVERSION_HA"],
                errors="raise",
            ).sum()
        ),
        "RESIDUAL_AVAILABLE_LAND_HA": float(
            pd.to_numeric(
                frame["SC3_RESIDUAL_AVAILABLE_LAND_HA"],
                errors="raise",
            ).sum()
        ),
        "MAX_ABS_ED_ACCOUNTING_CLOSURE_HA": float(
            pd.to_numeric(
                frame["SC3_ACCOUNTING_CLOSURE_HA"],
                errors="raise",
            ).abs().max()
        ),
    }
    total_unmet = 0.0
    for use in SC3_USES:
        target = float(
            pd.to_numeric(
                frame[f"SC3_NATIONAL_TARGET_{use}_HA"],
                errors="raise",
            ).iloc[0]
        )
        realised = float(
            pd.to_numeric(
                frame[f"SC3_REALIZED_{use}_HA"],
                errors="raise",
            ).sum()
        )
        unmet = float(
            pd.to_numeric(
                frame[f"SC3_NATIONAL_UNMET_{use}_HA"],
                errors="raise",
            ).iloc[0]
        )
        row[f"TARGET_{use}_HA"] = target
        row[f"REALISED_{use}_HA"] = realised
        row[f"UNMET_{use}_HA"] = unmet
        total_unmet += unmet
    row["TOTAL_UNMET_TARGET_HA"] = total_unmet
    row["ACCOUNTING_CLOSURE_HA"] = (
        float(row["REALISED_CONVERSION_HA"])
        + float(row["RESIDUAL_AVAILABLE_LAND_HA"])
        - float(row["POTENTIAL_RELEASE_HA"])
    )
    return pd.DataFrame([row])
