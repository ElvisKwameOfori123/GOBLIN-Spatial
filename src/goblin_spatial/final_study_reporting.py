"""Final question-driven scientific reporting for the GOBLIN-Spatial study.

This module is deliberately downstream of SC1, SC2 and SC3.  It treats them as
three analytical views of one internally consistent national pathway:

    transition incidence -> exposure/vulnerability -> opportunity -> feasible response

No livestock, released-land, opportunity or SC3 allocation mathematics are
changed here.  The module consumes canonical completed-run outputs through the
validated base study reporter, adds interpretation-focused derived tables, then
rewrites the final workbook/database/figure package around the scientific
questions of the study.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from goblin_spatial.scenario.comparison import add_sc1_comparison_intensity
from goblin_spatial.study_reporting import (
    PRINCIPAL_RULES,
    PRINCIPAL_SCENARIOS,
    RULE_LABELS,
    SC3_USES,
    USE_LABELS,
    _format_sheet,
    _save_figure,
    _setup_matplotlib,
    export_study_results as _base_export_study_results,
)


FINAL_STUDY_REPORTING_VERSION = "2.0"
ID_COLS = ["STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY"]
ED_ID_COLS = [*ID_COLS, "CSOED"]

ELIGIBILITY_BY_USE = {
    "AD_GRASS": "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA",
    "BIOREFINERY_GRASS": "RELEASED_AD_BIOREFINERY_GRASS_ELIGIBLE_HA",
    "WILLOW": "RELEASED_WILLOW_ELIGIBLE_HA",
    "ADDITIONAL_TILLAGE": "RELEASED_TILLAGE_ELIGIBLE_HA",
    "FOREST": "RELEASED_FOREST_ELIGIBLE_HA",
    "REWETTING": "RELEASED_REWETTING_ELIGIBLE_WEIGHT_HA",
}

SC3_SCORE_BY_USE = {
    "AD_GRASS": "SC3_AD_GRASS_OPPORTUNITY_SCORE",
    "BIOREFINERY_GRASS": "SC3_BIOREFINERY_GRASS_OPPORTUNITY_SCORE",
    "WILLOW": "SC3_WILLOW_OPPORTUNITY_SCORE",
    "ADDITIONAL_TILLAGE": "SC3_ADDITIONAL_TILLAGE_OPPORTUNITY_SCORE",
    "FOREST": "SC3_FOREST_OPPORTUNITY_SCORE",
    "REWETTING": "SC3_REWETTING_OPPORTUNITY_SCORE",
}


def _numeric(frame: pd.DataFrame, column: str, *, default: float | None = None) -> pd.Series:
    if column not in frame.columns:
        if default is None:
            raise ValueError(f"final study reporting missing column: {column}")
        return pd.Series(float(default), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _safe_ratio(numerator, denominator, *, scale: float = 1.0) -> np.ndarray:
    n = np.asarray(numerator, dtype=float)
    d = np.asarray(denominator, dtype=float)
    return np.divide(scale * n, d, out=np.zeros_like(n, dtype=float), where=np.isfinite(d) & (d > 0))


def _run_order(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    s_order = {s: i for i, s in enumerate(PRINCIPAL_SCENARIOS)}
    r_order = {r: i for i, r in enumerate(PRINCIPAL_RULES)}
    out["_SCENARIO_ORDER"] = out["STUDY_SCENARIO_ID"].map(s_order).fillna(999)
    out["_RULE_ORDER"] = out["STUDY_ALLOCATION_POLICY"].map(r_order).fillna(999)
    out = out.sort_values(["_SCENARIO_ORDER", "_RULE_ORDER"], kind="stable")
    return out.drop(columns=["_SCENARIO_ORDER", "_RULE_ORDER"])


def _read_sqlite(path: Path) -> dict[str, pd.DataFrame]:
    with sqlite3.connect(path) as con:
        names = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {name: pd.read_sql_query(f'SELECT * FROM "{name}"', con) for name in names}


def _write_derived_sqlite(path: Path, tables: dict[str, pd.DataFrame], figure_data: pd.DataFrame) -> None:
    with sqlite3.connect(path) as con:
        for name, frame in tables.items():
            frame.to_sql(name, con, if_exists="replace", index=False)
        figure_data.to_sql("figure_data", con, if_exists="replace", index=False)
        pd.DataFrame([{
            "reporting_version": FINAL_STUDY_REPORTING_VERSION,
            "interpretation": "Question-driven integrated SC1-SC2-SC3 final results package",
        }]).to_sql("final_report_metadata", con, if_exists="replace", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS idx_transition_conditions_run_ed ON transition_conditions (STUDY_SCENARIO_ID, STUDY_ALLOCATION_POLICY, CSOED)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_map_data_run_ed ON map_data (STUDY_SCENARIO_ID, STUDY_ALLOCATION_POLICY, CSOED)")
        con.commit()


def _gini(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    x = np.maximum(x, 0.0)
    if len(x) == 0 or float(x.sum()) <= 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return float((2.0 * np.dot(np.arange(1, n + 1), x) / (n * x.sum())) - (n + 1.0) / n)


def _top_share(values: np.ndarray, share_of_units: float) -> float:
    x = np.maximum(np.asarray(values, dtype=float), 0.0)
    total = float(np.nansum(x))
    if total <= 0:
        return 0.0
    n = max(1, int(np.ceil(len(x) * float(share_of_units))))
    return 100.0 * float(np.sort(np.nan_to_num(x, nan=0.0))[::-1][:n].sum()) / total


def _units_for_share(values: np.ndarray, target_share: float) -> int:
    x = np.sort(np.maximum(np.nan_to_num(np.asarray(values, dtype=float), nan=0.0), 0.0))[::-1]
    total = float(x.sum())
    if total <= 0:
        return 0
    return int(np.searchsorted(np.cumsum(x), target_share * total, side="left") + 1)


def _ge2_decomposition(values: np.ndarray, groups: pd.Series) -> tuple[float, float, float, float, float]:
    x = np.maximum(np.nan_to_num(np.asarray(values, dtype=float), nan=0.0), 0.0)
    n = len(x)
    mu = float(x.mean()) if n else 0.0
    if n == 0 or mu <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    total = 0.5 * float(np.mean((x / mu) ** 2 - 1.0))
    within = 0.0
    between_sum = 0.0
    g = groups.astype("string").fillna("<NA>").to_numpy()
    for label in pd.unique(g):
        mask = g == label
        xg = x[mask]
        ng = len(xg)
        if ng == 0:
            continue
        mug = float(xg.mean())
        pg = ng / n
        ratio = mug / mu if mu > 0 else 0.0
        if mug > 0:
            ge_g = 0.5 * float(np.mean((xg / mug) ** 2 - 1.0))
            within += pg * (ratio ** 2) * ge_g
        between_sum += pg * (ratio ** 2)
    between = 0.5 * (between_sum - 1.0)
    total = max(total, 0.0)
    within = max(within, 0.0)
    between = max(between, 0.0)
    within_share = 100.0 * within / total if total > 0 else 0.0
    between_share = 100.0 * between / total if total > 0 else 0.0
    return total, within, between, within_share, between_share


def build_distribution_summary(sc1_ed: pd.DataFrame) -> pd.DataFrame:
    sc1 = add_sc1_comparison_intensity(sc1_ed)
    rows: list[dict[str, object]] = []
    metrics = [("TOTAL_CATTLE_REDUCTION_HEAD", "CATTLE_REDUCTION")]
    if "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" in sc1.columns:
        metrics.append(("SO_LIVESTOCK_GROSS_LOSS_2020_EUR", "SO_GROSS_LOSS"))
    if "GOBLIN_RELEASED_GRASSLAND_HA" in sc1.columns:
        metrics.append(("GOBLIN_RELEASED_GRASSLAND_HA", "RELEASED_LAND"))
    for (scenario, rule), block in sc1.groupby(ID_COLS, sort=False):
        for column, label in metrics:
            values = np.maximum(_numeric(block, column, default=0.0).fillna(0.0).to_numpy(float), 0.0)
            groups = block["County"] if "County" in block.columns else pd.Series("<NA>", index=block.index)
            ge_total, ge_within, ge_between, within_share, between_share = _ge2_decomposition(values, groups)
            rows.append({
                "STUDY_SCENARIO_ID": scenario,
                "STUDY_ALLOCATION_POLICY": rule,
                "METRIC": label,
                "TOTAL": float(values.sum()),
                "MEAN_PER_ED": float(values.mean()) if len(values) else 0.0,
                "GINI": _gini(values),
                "TOP_10PCT_ED_SHARE_PCT": _top_share(values, 0.10),
                "TOP_20PCT_ED_SHARE_PCT": _top_share(values, 0.20),
                "EDS_FOR_50PCT": _units_for_share(values, 0.50),
                "EDS_FOR_80PCT": _units_for_share(values, 0.80),
                "GE2_TOTAL": ge_total,
                "GE2_WITHIN_COUNTY": ge_within,
                "GE2_BETWEEN_COUNTY": ge_between,
                "GE2_WITHIN_COUNTY_SHARE_PCT": within_share,
                "GE2_BETWEEN_COUNTY_SHARE_PCT": between_share,
                "GE2_CLOSURE": ge_total - ge_within - ge_between,
            })
    return _run_order(pd.DataFrame(rows))


def build_lorenz_data(sc1_ed: pd.DataFrame) -> pd.DataFrame:
    sc1 = add_sc1_comparison_intensity(sc1_ed)
    rows: list[dict[str, object]] = []
    metrics = [("TOTAL_CATTLE_REDUCTION_HEAD", "Cattle reduction")]
    if "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" in sc1.columns:
        metrics.append(("SO_LIVESTOCK_GROSS_LOSS_2020_EUR", "Standard Output gross loss"))
    for (scenario, rule), block in sc1.groupby(ID_COLS, sort=False):
        for column, label in metrics:
            x = np.sort(np.maximum(_numeric(block, column, default=0.0).fillna(0.0).to_numpy(float), 0.0))
            if len(x) == 0:
                continue
            total = float(x.sum())
            cum = np.cumsum(x) / total if total > 0 else np.zeros(len(x))
            idx = np.unique(np.linspace(0, len(x) - 1, 101).round().astype(int))
            rows.append({
                "STUDY_SCENARIO_ID": scenario,
                "STUDY_ALLOCATION_POLICY": rule,
                "METRIC": label,
                "CUMULATIVE_ED_SHARE_PCT": 0.0,
                "CUMULATIVE_EXPOSURE_SHARE_PCT": 0.0,
            })
            for i in idx:
                rows.append({
                    "STUDY_SCENARIO_ID": scenario,
                    "STUDY_ALLOCATION_POLICY": rule,
                    "METRIC": label,
                    "CUMULATIVE_ED_SHARE_PCT": 100.0 * (i + 1) / len(x),
                    "CUMULATIVE_EXPOSURE_SHARE_PCT": 100.0 * float(cum[i]),
                })
    return pd.DataFrame(rows).sort_values([
        "METRIC", "STUDY_SCENARIO_ID", "STUDY_ALLOCATION_POLICY", "CUMULATIVE_ED_SHARE_PCT"
    ], kind="stable").reset_index(drop=True)


def build_exposure_persistence(sc1_ed: pd.DataFrame) -> pd.DataFrame:
    sc1 = add_sc1_comparison_intensity(sc1_ed).copy()
    metrics = [("TOTAL_CATTLE_REDUCTION_PCT_OF_BASE", "CATTLE")]
    if "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE" in sc1.columns:
        metrics.append(("SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", "SO"))
    for column, label in metrics:
        flag = pd.Series(False, index=sc1.index)
        for _, block in sc1.groupby(ID_COLS, sort=False):
            values = _numeric(block, column, default=0.0).fillna(0.0)
            positive = values[values > 0]
            if positive.empty:
                continue
            threshold = float(positive.quantile(0.90))
            flag.loc[block.index] = values.ge(threshold) & values.gt(0)
        sc1[f"TOP_DECILE_{label}_FLAG"] = flag
    base = sc1.groupby("CSOED", sort=False).agg(
        County=("County", "first") if "County" in sc1.columns else ("CSOED", "first"),
        RUN_COUNT=("CSOED", "size"),
    ).reset_index()
    for _, label in metrics:
        counts = sc1.groupby("CSOED", sort=False)[f"TOP_DECILE_{label}_FLAG"].sum().astype(int)
        base[f"TOP_DECILE_{label}_FREQUENCY"] = base["CSOED"].map(counts).fillna(0).astype(int)
        base[f"TOP_DECILE_{label}_SHARE_OF_RUNS_PCT"] = _safe_ratio(
            base[f"TOP_DECILE_{label}_FREQUENCY"], base["RUN_COUNT"], scale=100.0
        )
    return base.sort_values("CSOED", kind="stable").reset_index(drop=True)


def build_land_release_summary(sc1_ed: pd.DataFrame) -> pd.DataFrame:
    cols = {
        "GROSS_RELEASE_HA": "GOBLIN_RELEASED_GRASSLAND_HA",
        "DAIRY_RELEASE_HA": "GOBLIN_RELEASED_DAIRY_LAND_HA",
        "BEEF_RELEASE_HA": "GOBLIN_RELEASED_BEEF_LAND_HA",
        "SHEEP_RELEASE_HA": "GOBLIN_RELEASED_SHEEP_LAND_HA",
        "G1_RELEASE_HA": "GOBLIN_RELEASED_G1_HA",
        "G2_RELEASE_HA": "GOBLIN_RELEASED_G2_HA",
        "G3_RELEASE_HA": "GOBLIN_RELEASED_G3_HA",
    }
    rows: list[dict[str, object]] = []
    for (scenario, rule), block in sc1_ed.groupby(ID_COLS, sort=False):
        row: dict[str, object] = {"STUDY_SCENARIO_ID": scenario, "STUDY_ALLOCATION_POLICY": rule}
        for out_col, source in cols.items():
            row[out_col] = float(_numeric(block, source, default=np.nan).sum(min_count=1))
        gross = float(row.get("GROSS_RELEASE_HA", np.nan))
        for group in ("G1", "G2", "G3"):
            value = float(row.get(f"{group}_RELEASE_HA", np.nan))
            row[f"{group}_RELEASE_SHARE_PCT"] = 100.0 * value / gross if np.isfinite(gross) and gross > 0 and np.isfinite(value) else np.nan
        rows.append(row)
    return _run_order(pd.DataFrame(rows))


def build_opportunity_summary(sc2_ed: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (scenario, rule), block in sc2_ed.groupby(ID_COLS, sort=False):
        release = float(_numeric(block, "SC2_POTENTIAL_RELEASE_HA", default=0.0).fillna(0.0).sum())
        row: dict[str, object] = {
            "STUDY_SCENARIO_ID": scenario,
            "STUDY_ALLOCATION_POLICY": rule,
            "POTENTIAL_RELEASE_HA": release,
        }
        for use, source in ELIGIBILITY_BY_USE.items():
            eligible = float(_numeric(block, source, default=np.nan).sum(min_count=1))
            row[f"{use}_ELIGIBLE_HA"] = eligible
            row[f"{use}_ELIGIBILITY_COVERAGE_PCT"] = 100.0 * eligible / release if release > 0 and np.isfinite(eligible) else np.nan
        for score in (
            "FORESTRY_OPPORTUNITY_SCORE",
            "REWETTING_OPPORTUNITY_SCORE",
            "AD_GRASS_OPPORTUNITY_SCORE",
            "WILLOW_OPPORTUNITY_SCORE",
            "ENERGY_GRASS_OPPORTUNITY_SCORE",
            "NATURE_OPPORTUNITY_SCORE",
        ):
            if score in block.columns:
                values = _numeric(block, score).to_numpy(float)
                weights = _numeric(block, "SC2_POTENTIAL_RELEASE_HA", default=0.0).fillna(0.0).to_numpy(float)
                valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
                row[f"RELEASE_WEIGHTED_{score}"] = float(np.average(values[valid], weights=weights[valid])) if valid.any() else np.nan
        if "SOIL_REPRESENTATION_DIVERGENCE" in block.columns:
            row["MEAN_SOIL_REPRESENTATION_DIVERGENCE"] = float(_numeric(block, "SOIL_REPRESENTATION_DIVERGENCE").mean())
        rows.append(row)
    return _run_order(pd.DataFrame(rows))


def build_transition_conditions(
    sc1_ed: pd.DataFrame,
    sc2_ed: pd.DataFrame,
    sc3_ed: pd.DataFrame,
    persistence: pd.DataFrame,
    robust: pd.DataFrame,
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    base = add_sc1_comparison_intensity(sc1_ed).copy()
    sc2_keep = [*ED_ID_COLS]
    for column in (
        "SC2_POTENTIAL_RELEASE_HA",
        "SOIL_REPRESENTATION_DIVERGENCE",
        "FORESTRY_OPPORTUNITY_SCORE",
        "REWETTING_OPPORTUNITY_SCORE",
        "AD_GRASS_OPPORTUNITY_SCORE",
        "WILLOW_OPPORTUNITY_SCORE",
        "ENERGY_GRASS_OPPORTUNITY_SCORE",
        "NATURE_OPPORTUNITY_SCORE",
        *ELIGIBILITY_BY_USE.values(),
    ):
        if column in sc2_ed.columns and column not in sc2_keep:
            sc2_keep.append(column)
    base = base.merge(sc2_ed[sc2_keep], on=ED_ID_COLS, how="left", validate="one_to_one")
    sc3_keep = [*ED_ID_COLS]
    for use in SC3_USES:
        for column in (
            f"SC3_ELIGIBLE_{use}_HA",
            f"SC3_REALIZED_{use}_HA",
            f"SC3_NATIONAL_TARGET_{use}_HA",
            f"SC3_NATIONAL_UNMET_{use}_HA",
            SC3_SCORE_BY_USE[use],
        ):
            if column in sc3_ed.columns and column not in sc3_keep:
                sc3_keep.append(column)
    for column in (
        "SC3_STAGE_A_REALIZED_HA",
        "SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA",
        "SC3_REWETTING_FROM_RELEASED_LAND_HA",
        "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA",
        "SC3_REWETTING_PRE_STAGE_A_CAPACITY_HA",
        "SC3_REWETTING_POST_STAGE_A_CAPACITY_HA",
        "SC3_POOL_TILLAGE_WILLOW_CAPACITY_HA",
        "SC3_POOL_TILLAGE_WILLOW_USED_HA",
        "SC3_POOL_AD_BIOREFINERY_CAPACITY_HA",
        "SC3_POOL_AD_BIOREFINERY_USED_HA",
        "SC3_POOL_FOREST_CAPACITY_HA",
        "SC3_POOL_FOREST_USED_HA",
    ):
        if column in sc3_ed.columns and column not in sc3_keep:
            sc3_keep.append(column)
    base = base.merge(sc3_ed[sc3_keep], on=ED_ID_COLS, how="left", validate="one_to_one")
    release = _numeric(base, "GOBLIN_RELEASED_GRASSLAND_HA", default=0.0).fillna(0.0)
    if "ALL_GRASSLAND" in base.columns:
        base["RELEASED_LAND_PCT_OF_BASE_GRASSLAND"] = _safe_ratio(release, _numeric(base, "ALL_GRASSLAND", default=0.0), scale=100.0)
    realised_cols = [f"SC3_REALIZED_{use}_HA" for use in SC3_USES if f"SC3_REALIZED_{use}_HA" in base.columns]
    if realised_cols:
        base["TOTAL_REALISED_ALTERNATIVE_USE_HA"] = base[realised_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
        base["ALTERNATIVE_USE_UPTAKE_PCT_OF_RELEASE"] = _safe_ratio(base["TOTAL_REALISED_ALTERNATIVE_USE_HA"], release, scale=100.0)
    for use in SC3_USES:
        realised_col = f"SC3_REALIZED_{use}_HA"
        eligible_col = f"SC3_ELIGIBLE_{use}_HA"
        if eligible_col in base.columns:
            base[f"{use}_ELIGIBILITY_COVERAGE_PCT"] = _safe_ratio(_numeric(base, eligible_col, default=0.0), release, scale=100.0)
        if realised_col in base.columns and eligible_col in base.columns:
            base[f"{use}_OPPORTUNITY_MOBILISATION_PCT"] = _safe_ratio(_numeric(base, realised_col, default=0.0), _numeric(base, eligible_col, default=0.0), scale=100.0)
            base[f"{use}_UNUSED_ELIGIBLE_HA"] = np.maximum(
                _numeric(base, eligible_col, default=0.0).fillna(0.0) - _numeric(base, realised_col, default=0.0).fillna(0.0), 0.0
            )
    if "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA" in base.columns:
        base["FINAL_UNALLOCATED_PCT_OF_RELEASE"] = _safe_ratio(_numeric(base, "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA", default=0.0), release, scale=100.0)
    pcols = [c for c in persistence.columns if c != "County"]
    base = base.merge(persistence[pcols], on="CSOED", how="left", validate="many_to_one")
    base = base.merge(robust, on="CSOED", how="left", validate="many_to_one", suffixes=("", "_ROBUST"))
    comp_cols = [*ED_ID_COLS]
    for c in comparison.columns:
        if c.startswith("PROTECTION_RELIEF_") or c.startswith("DISPLACED_BURDEN_") or c.startswith("SIGNED_DIFFERENCE_FROM_PRORATA_"):
            comp_cols.append(c)
    comp_cols = list(dict.fromkeys(c for c in comp_cols if c in comparison.columns))
    if len(comp_cols) > len(ED_ID_COLS):
        base = base.merge(comparison[comp_cols], on=ED_ID_COLS, how="left", validate="one_to_one")
    return _run_order(base)


def build_opportunity_mobilisation(sc3_ed: pd.DataFrame, sc3_national: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (scenario, rule), block in sc3_ed.groupby(ID_COLS, sort=False):
        nblock = sc3_national.loc[
            sc3_national["STUDY_SCENARIO_ID"].astype(str).eq(str(scenario))
            & sc3_national["STUDY_ALLOCATION_POLICY"].astype(str).eq(str(rule))
        ]
        nrow = nblock.iloc[0] if len(nblock) else pd.Series(dtype=object)
        for use in SC3_USES:
            eligible_col = f"SC3_ELIGIBLE_{use}_HA"
            realised_col = f"SC3_REALIZED_{use}_HA"
            score_col = SC3_SCORE_BY_USE[use]
            eligible = float(_numeric(block, eligible_col, default=np.nan).sum(min_count=1))
            realised = float(_numeric(block, realised_col, default=np.nan).sum(min_count=1))
            target = float(nrow.get(f"TARGET_{use}_HA", np.nan))
            unmet = float(nrow.get(f"UNMET_{use}_HA", np.nan))
            siting_quality = np.nan
            if realised_col in block.columns and score_col in block.columns:
                w = _numeric(block, realised_col, default=0.0).fillna(0.0).to_numpy(float)
                s = _numeric(block, score_col).to_numpy(float)
                valid = np.isfinite(w) & np.isfinite(s) & (w > 0)
                if valid.any():
                    siting_quality = float(np.average(s[valid], weights=w[valid]))
            rows.append({
                "STUDY_SCENARIO_ID": scenario,
                "STUDY_ALLOCATION_POLICY": rule,
                "LAND_USE": use,
                "LAND_USE_LABEL": USE_LABELS[use],
                "ELIGIBLE_HA": eligible,
                "TARGET_HA": target,
                "REALISED_HA": realised,
                "UNMET_HA": unmet,
                "TARGET_REALISATION_PCT": 100.0 * realised / target if np.isfinite(target) and target > 0 else np.nan,
                "OPPORTUNITY_MOBILISATION_PCT": 100.0 * realised / eligible if np.isfinite(eligible) and eligible > 0 else np.nan,
                "UNUSED_ELIGIBLE_HA": max(eligible - realised, 0.0) if np.isfinite(eligible) and np.isfinite(realised) else np.nan,
                "REALISED_WEIGHTED_OPPORTUNITY_SCORE": siting_quality,
                "NOTE": "Eligible hectares are use-specific and overlapping across uses; do not sum them across land uses.",
            })
    return _run_order(pd.DataFrame(rows))


def build_shared_pool_summary(sc3_ed: pd.DataFrame) -> pd.DataFrame:
    mappings = {
        "TILLAGE_WILLOW": ("SC3_POOL_TILLAGE_WILLOW_CAPACITY_HA", "SC3_POOL_TILLAGE_WILLOW_USED_HA"),
        "AD_BIOREFINERY": ("SC3_POOL_AD_BIOREFINERY_CAPACITY_HA", "SC3_POOL_AD_BIOREFINERY_USED_HA"),
        "FOREST_MINERAL": ("SC3_POOL_FOREST_CAPACITY_HA", "SC3_POOL_FOREST_USED_HA"),
    }
    rows: list[dict[str, object]] = []
    for (scenario, rule), block in sc3_ed.groupby(ID_COLS, sort=False):
        for label, (cap_col, used_col) in mappings.items():
            if cap_col not in block.columns or used_col not in block.columns:
                continue
            capacity = float(_numeric(block, cap_col).sum())
            used = float(_numeric(block, used_col).sum())
            rows.append({
                "STUDY_SCENARIO_ID": scenario,
                "STUDY_ALLOCATION_POLICY": rule,
                "SHARED_POOL": label,
                "CAPACITY_HA": capacity,
                "USED_HA": used,
                "UNUSED_HA": max(capacity - used, 0.0),
                "UTILISATION_PCT": 100.0 * used / capacity if capacity > 0 else np.nan,
            })
    if not rows:
        return pd.DataFrame(columns=[*ID_COLS, "SHARED_POOL", "CAPACITY_HA", "USED_HA", "UNUSED_HA", "UTILISATION_PCT"])
    return _run_order(pd.DataFrame(rows))


def build_rewetting_summary(sc3_ed: pd.DataFrame, sc3_national: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (scenario, rule), block in sc3_ed.groupby(ID_COLS, sort=False):
        nblock = sc3_national.loc[
            sc3_national["STUDY_SCENARIO_ID"].astype(str).eq(str(scenario))
            & sc3_national["STUDY_ALLOCATION_POLICY"].astype(str).eq(str(rule))
        ]
        nrow = nblock.iloc[0] if len(nblock) else pd.Series(dtype=object)
        rows.append({
            "STUDY_SCENARIO_ID": scenario,
            "STUDY_ALLOCATION_POLICY": rule,
            "TARGET_HA": float(nrow.get("TARGET_REWETTING_HA", np.nan)),
            "PRE_STAGE_A_CAPACITY_HA": float(_numeric(block, "SC3_REWETTING_PRE_STAGE_A_CAPACITY_HA", default=np.nan).sum(min_count=1)),
            "POST_STAGE_A_CAPACITY_HA": float(_numeric(block, "SC3_REWETTING_POST_STAGE_A_CAPACITY_HA", default=np.nan).sum(min_count=1)),
            "REALISED_HA": float(_numeric(block, "SC3_REALIZED_REWETTING_HA", default=np.nan).sum(min_count=1)),
            "UNMET_HA": float(nrow.get("UNMET_REWETTING_HA", np.nan)),
        })
    return _run_order(pd.DataFrame(rows))


def build_headline_results(
    national: pd.DataFrame,
    distribution: pd.DataFrame,
    land_release: pd.DataFrame,
    accounting: pd.DataFrame,
    sc3_national: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, n in national.iterrows():
        scenario = str(n["SCENARIO_ID"] if "SCENARIO_ID" in n else n["STUDY_SCENARIO_ID"])
        rule = str(n["ALLOCATION_POLICY"] if "ALLOCATION_POLICY" in n else n["STUDY_ALLOCATION_POLICY"])
        d = distribution.loc[
            distribution["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            & distribution["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ]
        a = accounting.loc[
            accounting["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            & accounting["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ]
        s3 = sc3_national.loc[
            sc3_national["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            & sc3_national["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ]
        lr = land_release.loc[
            land_release["STUDY_SCENARIO_ID"].astype(str).eq(scenario)
            & land_release["STUDY_ALLOCATION_POLICY"].astype(str).eq(rule)
        ]
        cattle = d.loc[d["METRIC"].eq("CATTLE_REDUCTION")]
        so = d.loc[d["METRIC"].eq("SO_GROSS_LOSS")]
        arow = a.iloc[0] if len(a) else pd.Series(dtype=object)
        srow = s3.iloc[0] if len(s3) else pd.Series(dtype=object)
        lrrow = lr.iloc[0] if len(lr) else pd.Series(dtype=object)
        base_total = float(n.get("BASE_TOTAL_CATTLE", np.nan))
        scenario_total = float(n.get("SCENARIO_TOTAL_CATTLE", np.nan))
        rows.append({
            "STUDY_SCENARIO_ID": scenario,
            "STUDY_ALLOCATION_POLICY": rule,
            "ALLOCATION_POLICY_LABEL": RULE_LABELS.get(rule, rule),
            "SCENARIO_TOTAL_CATTLE": scenario_total,
            "TOTAL_CATTLE_REDUCTION_HEAD": base_total - scenario_total if np.isfinite(base_total) and np.isfinite(scenario_total) else np.nan,
            "GROSS_SO_EXPOSURE_EUR": float(n.get("GROSS_SO_LIVESTOCK_LOSS_2020_EUR", np.nan)),
            "CATTLE_REDUCTION_GINI": float(cattle.iloc[0]["GINI"]) if len(cattle) else np.nan,
            "SO_LOSS_GINI": float(so.iloc[0]["GINI"]) if len(so) else np.nan,
            "SO_TOP10_ED_SHARE_PCT": float(so.iloc[0]["TOP_10PCT_ED_SHARE_PCT"]) if len(so) else np.nan,
            "SO_EDS_FOR_50PCT": int(so.iloc[0]["EDS_FOR_50PCT"]) if len(so) else np.nan,
            "SO_WITHIN_COUNTY_VARIATION_SHARE_PCT": float(so.iloc[0]["GE2_WITHIN_COUNTY_SHARE_PCT"]) if len(so) else np.nan,
            "SO_BETWEEN_COUNTY_VARIATION_SHARE_PCT": float(so.iloc[0]["GE2_BETWEEN_COUNTY_SHARE_PCT"]) if len(so) else np.nan,
            "GROSS_RELEASE_HA": float(lrrow.get("GROSS_RELEASE_HA", n.get("RUN_GROSS_RELEASE_HA", np.nan))),
            "G1_RELEASE_SHARE_PCT": float(lrrow.get("G1_RELEASE_SHARE_PCT", np.nan)),
            "G2_RELEASE_SHARE_PCT": float(lrrow.get("G2_RELEASE_SHARE_PCT", np.nan)),
            "G3_RELEASE_SHARE_PCT": float(lrrow.get("G3_RELEASE_SHARE_PCT", np.nan)),
            "STAGE_A_TARGET_HA": float(arow.get("STAGE_A_TARGET_HA", np.nan)),
            "STAGE_A_REALIZED_HA": float(arow.get("STAGE_A_REALIZED_HA", np.nan)),
            "STAGE_A_UNMET_HA": float(arow.get("STAGE_A_UNMET_HA", np.nan)),
            "REWETTING_REALIZED_HA": float(arow.get("REWETTING_REALIZED_HA", np.nan)),
            "TOTAL_UNMET_TARGET_HA": float(srow.get("TOTAL_UNMET_TARGET_HA", np.nan)),
            "FINAL_UNALLOCATED_RELEASED_LAND_HA": float(arow.get("SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA", np.nan)),
        })
    return _run_order(pd.DataFrame(rows))


def build_map_data(conditions: pd.DataFrame) -> pd.DataFrame:
    wanted = [
        *ED_ID_COLS,
        "County",
        "TOTAL_CATTLE_REDUCTION_HEAD",
        "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
        "GOBLIN_RELEASED_GRASSLAND_HA",
        "RELEASED_LAND_PCT_OF_BASE_GRASSLAND",
        "ECONOMIC_VULNERABILITY_SCORE",
        "SOCIAL_VULNERABILITY_SCORE",
        "TOP_DECILE_CATTLE_FREQUENCY",
        "TOP_DECILE_SO_FREQUENCY",
        "ROBUST_MIN_CATTLE_REDUCTION_PCT",
        "ROBUST_MIN_SO_LOSS_PCT",
        "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT",
        "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT",
        "FOREST_ELIGIBILITY_COVERAGE_PCT",
        "AD_GRASS_ELIGIBILITY_COVERAGE_PCT",
        "WILLOW_ELIGIBILITY_COVERAGE_PCT",
        "ALTERNATIVE_USE_UPTAKE_PCT_OF_RELEASE",
        "FINAL_UNALLOCATED_PCT_OF_RELEASE",
    ]
    for c in conditions.columns:
        if c.startswith("PROTECTION_RELIEF_") or c.startswith("DISPLACED_BURDEN_"):
            wanted.append(c)
    wanted = list(dict.fromkeys(c for c in wanted if c in conditions.columns))
    return conditions[wanted].copy()


def build_final_figure_data(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    def add(fig: str, scenario: str, rule: str, component: str, value: float, unit: str, **extra: object) -> None:
        row: dict[str, object] = {
            "FIGURE_ID": fig,
            "SCENARIO_ID": scenario,
            "ALLOCATION_POLICY": rule,
            "COMPONENT": component,
            "VALUE": float(value) if pd.notna(value) else np.nan,
            "UNIT": unit,
        }
        row.update(extra)
        rows.append(row)
    for _, r in tables["headline_results"].iterrows():
        add("F02_SO_EXPOSURE", str(r["STUDY_SCENARIO_ID"]), str(r["STUDY_ALLOCATION_POLICY"]), "Gross SO loss", float(r["GROSS_SO_EXPOSURE_EUR"]) / 1e6, "EUR million")
    for _, r in tables["national_results"].iterrows():
        s = str(r.get("SCENARIO_ID", r.get("STUDY_SCENARIO_ID", "")))
        rule = str(r.get("ALLOCATION_POLICY", r.get("STUDY_ALLOCATION_POLICY", "")))
        if rule != "PRORATA":
            continue
        dairy = float(r.get("SCENARIO_DAIRY_COW", r.get("SCENARIO_DAIRY_COWS", 0.0))) / 1000.0
        suckler = float(r.get("SCENARIO_SUCKLER_COW", r.get("SCENARIO_SUCKLER_COWS", 0.0))) / 1000.0
        total = float(r.get("SCENARIO_TOTAL_CATTLE", 0.0)) / 1000.0
        add("F01_LIVESTOCK_ENDPOINT", s, rule, "Dairy cows", dairy, "thousand head")
        add("F01_LIVESTOCK_ENDPOINT", s, rule, "Suckler cows", suckler, "thousand head")
        add("F01_LIVESTOCK_ENDPOINT", s, rule, "Follower/other cattle", max(total - dairy - suckler, 0.0), "thousand head")
    redistribution = tables["redistribution"]
    suffix = "SO_LIVESTOCK_GROSS_LOSS_2020_EUR"
    for _, r in redistribution.iterrows():
        s, rule = str(r["PATHWAY_NAME"]), str(r["PATHWAY_ALLOCATION_RULE"])
        if rule == "PRORATA":
            continue
        relief = float(r.get(f"TOTAL_PROTECTION_RELIEF_{suffix}", np.nan)) / 1e6
        burden = float(r.get(f"TOTAL_DISPLACED_BURDEN_{suffix}", np.nan)) / 1e6
        add("F05_REDISTRIBUTION", s, rule, "Protection relief", -relief, "EUR million")
        add("F05_REDISTRIBUTION", s, rule, "Displaced burden", burden, "EUR million")
    for _, r in tables["persistence_histogram"].iterrows():
        add("F07_PERSISTENCE", "ALL", "ALL", str(r["METRIC"]), float(r["ED_COUNT"]), "ED count", FREQUENCY=int(r["FREQUENCY"]))
    for _, r in tables["distribution_summary"].iterrows():
        if str(r["METRIC"]) != "SO_GROSS_LOSS":
            continue
        add("F08_WITHIN_BETWEEN", str(r["STUDY_SCENARIO_ID"]), str(r["STUDY_ALLOCATION_POLICY"]), "Within county", float(r["GE2_WITHIN_COUNTY_SHARE_PCT"]), "%")
        add("F08_WITHIN_BETWEEN", str(r["STUDY_SCENARIO_ID"]), str(r["STUDY_ALLOCATION_POLICY"]), "Between county", float(r["GE2_BETWEEN_COUNTY_SHARE_PCT"]), "%")
    for _, r in tables["land_release_summary"].iterrows():
        s, rule = str(r["STUDY_SCENARIO_ID"]), str(r["STUDY_ALLOCATION_POLICY"])
        if rule != "PRORATA":
            continue
        for component in ("DAIRY", "BEEF", "SHEEP"):
            add("F09_RELEASE_SYSTEM", s, rule, component.title(), float(r.get(f"{component}_RELEASE_HA", np.nan)) / 1000.0, "kha")
        for component in ("G1", "G2", "G3"):
            add("F10_RELEASE_SOIL", s, rule, component, float(r.get(f"{component}_RELEASE_HA", np.nan)) / 1000.0, "kha")
    for _, r in tables["opportunity_mobilisation"].iterrows():
        if str(r["STUDY_ALLOCATION_POLICY"]) != "PRORATA":
            continue
        s, label = str(r["STUDY_SCENARIO_ID"]), str(r["LAND_USE_LABEL"])
        add("F12_TARGET_REALISED", s, "PRORATA", f"{label} realised", float(r["REALISED_HA"]) / 1000.0, "kha", LAND_USE=label, SERIES="Realised")
        add("F12_TARGET_REALISED", s, "PRORATA", f"{label} unmet", float(r["UNMET_HA"]) / 1000.0, "kha", LAND_USE=label, SERIES="Unmet")
        if pd.notna(r["OPPORTUNITY_MOBILISATION_PCT"]):
            add("F14_MOBILISATION", s, "PRORATA", label, float(r["OPPORTUNITY_MOBILISATION_PCT"]), "%")
    for _, r in tables["land_accounting"].iterrows():
        s, rule = str(r["STUDY_SCENARIO_ID"]), str(r["STUDY_ALLOCATION_POLICY"])
        if rule != "PRORATA":
            continue
        add("F13_LAND_ACCOUNTING", s, rule, "Stage A realised", float(r["STAGE_A_REALIZED_HA"]) / 1000.0, "kha")
        add("F13_LAND_ACCOUNTING", s, rule, "Rewetting realised", float(r["REWETTING_REALIZED_HA"]) / 1000.0, "kha")
        add("F13_LAND_ACCOUNTING", s, rule, "Final unallocated", float(r["SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"]) / 1000.0, "kha")
    cond = tables["transition_conditions"]
    if "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE" in cond.columns and "FOREST_ELIGIBILITY_COVERAGE_PCT" in cond.columns:
        subset = cond.loc[
            cond["STUDY_SCENARIO_ID"].astype(str).eq("ALL_GAS_NZ")
            & cond["STUDY_ALLOCATION_POLICY"].astype(str).eq("PRORATA")
        ]
        for _, r in subset.iterrows():
            rows.append({
                "FIGURE_ID": "F11_EXPOSURE_OPPORTUNITY",
                "SCENARIO_ID": "ALL_GAS_NZ",
                "ALLOCATION_POLICY": "PRORATA",
                "COMPONENT": "ED",
                "VALUE": float(r.get("FOREST_ELIGIBILITY_COVERAGE_PCT", np.nan)),
                "UNIT": "% released land forest-eligible",
                "CSOED": r.get("CSOED"),
                "X_VALUE": float(r.get("SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", np.nan)),
                "X_UNIT": "% baseline Standard Output exposed",
            })
    return pd.DataFrame(rows)


def _label(scenario: str, rule: str) -> str:
    short = {
        "PRORATA": "PR",
        "DAIRY_PROTECTION": "DP",
        "ECONOMIC_CAPACITY_PROTECTION": "EP",
        "SOCIAL_VULNERABILITY_PROTECTION": "SP",
    }.get(rule, rule)
    return f"{scenario}\n{short}"


def generate_final_figures(tables: dict[str, pd.DataFrame], output_dir: Path) -> list[Path]:
    plt = _setup_matplotlib()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    f1 = tables["figure_data"].loc[lambda x: x["FIGURE_ID"].eq("F01_LIVESTOCK_ENDPOINT")]
    if not f1.empty:
        pivot = f1.pivot(index="SCENARIO_ID", columns="COMPONENT", values="VALUE").reindex(PRINCIPAL_SCENARIOS)
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        bottom = np.zeros(len(pivot))
        for component in ("Dairy cows", "Suckler cows", "Follower/other cattle"):
            vals = pivot.get(component, pd.Series(0.0, index=pivot.index)).fillna(0.0).to_numpy(float)
            ax.bar(pivot.index, vals, bottom=bottom, label=component)
            bottom += vals
        ax.set_ylabel("Cattle (thousand head)")
        ax.set_title("National cattle composition at the pathway endpoint")
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig01_livestock_endpoint")
        plt.close(fig)
    f2 = tables["figure_data"].loc[lambda x: x["FIGURE_ID"].eq("F02_SO_EXPOSURE")]
    if not f2.empty:
        order = [(s, r) for s in PRINCIPAL_SCENARIOS for r in PRINCIPAL_RULES]
        lookup = {(str(r.SCENARIO_ID), str(r.ALLOCATION_POLICY)): float(r.VALUE) for r in f2.itertuples()}
        labels = [_label(s, r) for s, r in order if (s, r) in lookup]
        vals = [lookup[(s, r)] for s, r in order if (s, r) in lookup]
        fig, ax = plt.subplots(figsize=(10.8, 5.1))
        ax.bar(labels, vals)
        ax.set_ylabel("Gross Standard Output exposure (EUR million)")
        ax.set_title("Production-value exposure across pathways and incidence rules")
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig02_standard_output_exposure")
        plt.close(fig)
    order = [(s, r) for s in PRINCIPAL_SCENARIOS for r in PRINCIPAL_RULES]
    national = tables["sc3_national"]
    accounting = tables["land_accounting"]
    if not national.empty:
        merged = national.merge(accounting[[*ID_COLS, "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"]], on=ID_COLS, how="left")
        fig, ax = plt.subplots(figsize=(11.7, 6.0))
        bottoms = np.zeros(len(order))
        labels = [_label(s, r) for s, r in order]
        for use in [*SC3_USES, "FINAL_RESIDUAL"]:
            vals = []
            for s, rule in order:
                hit = merged.loc[(merged["STUDY_SCENARIO_ID"] == s) & (merged["STUDY_ALLOCATION_POLICY"] == rule)]
                if hit.empty:
                    vals.append(0.0)
                elif use == "FINAL_RESIDUAL":
                    vals.append(float(hit.iloc[0]["SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"]) / 1000.0)
                else:
                    vals.append(float(hit.iloc[0].get(f"REALISED_{use}_HA", 0.0)) / 1000.0)
            arr = np.asarray(vals, float)
            ax.bar(labels, arr, bottom=bottoms, label=USE_LABELS.get(use, "Final unallocated land"))
            bottoms += arr
        ax.set_ylabel("Released-land allocation (kha)")
        ax.set_title("Feasible spatial use of released livestock land")
        ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.16))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig03_released_land_allocation")
        plt.close(fig)
    lorenz = tables["lorenz_data"]
    block = lorenz.loc[lorenz["METRIC"].eq("Standard Output gross loss") & lorenz["STUDY_ALLOCATION_POLICY"].eq("PRORATA")]
    if not block.empty:
        fig, ax = plt.subplots(figsize=(6.8, 6.0))
        ax.plot([0, 100], [0, 100], linestyle="--", linewidth=1, label="Equal distribution")
        for s in PRINCIPAL_SCENARIOS:
            b = block.loc[block["STUDY_SCENARIO_ID"].eq(s)].sort_values("CUMULATIVE_ED_SHARE_PCT")
            if not b.empty:
                ax.plot(b["CUMULATIVE_ED_SHARE_PCT"], b["CUMULATIVE_EXPOSURE_SHARE_PCT"], label=s)
        ax.set_xlabel("Cumulative share of EDs (%)")
        ax.set_ylabel("Cumulative share of SO exposure (%)")
        ax.set_title("Spatial concentration of production-value exposure")
        ax.legend()
        ax.grid(alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig04_transition_concentration")
        plt.close(fig)
    f5 = tables["figure_data"].loc[lambda x: x["FIGURE_ID"].eq("F05_REDISTRIBUTION")]
    if not f5.empty:
        pivot = f5.pivot_table(index=["SCENARIO_ID", "ALLOCATION_POLICY"], columns="COMPONENT", values="VALUE", aggfunc="sum")
        labels = [_label(str(s), str(r)) for s, r in pivot.index]
        x = np.arange(len(pivot))
        fig, ax = plt.subplots(figsize=(10.7, 5.3))
        relief = pivot.get("Protection relief", pd.Series(0.0, index=pivot.index)).to_numpy(float)
        burden = pivot.get("Displaced burden", pd.Series(0.0, index=pivot.index)).to_numpy(float)
        ax.bar(x, relief, label="Protection relief")
        ax.bar(x, burden, label="Displaced burden")
        ax.axhline(0.0, linewidth=1)
        ax.set_xticks(x, labels)
        ax.set_ylabel("Change in Standard Output exposure (EUR million)")
        ax.set_title("Protection redistributes rather than removes transition exposure")
        ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.14))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig05_protection_redistribution")
        plt.close(fig)
    robust = tables["robust_exposure"]
    xcol, ycol = "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT", "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT"
    if xcol in robust.columns and ycol in robust.columns and not robust.empty:
        fig, ax = plt.subplots(figsize=(7.2, 6.0))
        ax.scatter(_numeric(robust, xcol), _numeric(robust, ycol), s=14, alpha=0.55)
        ax.set_xlabel("Pathway sensitivity (percentage points)")
        ax.set_ylabel("Allocation-rule sensitivity (percentage points)")
        ax.set_title("ED sensitivity to pathway ambition and incidence rule")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig06_pathway_allocation_sensitivity")
        plt.close(fig)
    hist = tables["persistence_histogram"]
    if not hist.empty:
        pivot = hist.pivot(index="FREQUENCY", columns="METRIC", values="ED_COUNT").fillna(0.0).reindex(range(13), fill_value=0.0)
        fig, ax = plt.subplots(figsize=(8.6, 5.2))
        x = np.arange(len(pivot))
        width = 0.38
        for j, metric in enumerate(list(pivot.columns)[:2]):
            ax.bar(x + (j - 0.5) * width, pivot[metric].to_numpy(float), width, label=metric)
        ax.set_xticks(x, [str(i) for i in pivot.index])
        ax.set_xlabel("Number of scenario-rule combinations in top exposure decile")
        ax.set_ylabel("ED count")
        ax.set_title("Persistence of high transition exposure across modeled futures")
        ax.legend()
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig07_persistent_exposure")
        plt.close(fig)
    dist = tables["distribution_summary"]
    db = dist.loc[dist["METRIC"].eq("SO_GROSS_LOSS")]
    if not db.empty:
        db = _run_order(db)
        labels = [_label(str(r.STUDY_SCENARIO_ID), str(r.STUDY_ALLOCATION_POLICY)) for r in db.itertuples()]
        within = db["GE2_WITHIN_COUNTY_SHARE_PCT"].to_numpy(float)
        between = db["GE2_BETWEEN_COUNTY_SHARE_PCT"].to_numpy(float)
        fig, ax = plt.subplots(figsize=(10.8, 5.4))
        ax.bar(labels, within, label="Within county")
        ax.bar(labels, between, bottom=within, label="Between county")
        ax.set_ylim(0, 100)
        ax.set_ylabel("Share of GE(2) variation (%)")
        ax.set_title("Where spatial inequality in production-value exposure occurs")
        ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.14))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig08_within_between_heterogeneity")
        plt.close(fig)
    release = tables["land_release_summary"].loc[lambda x: x["STUDY_ALLOCATION_POLICY"].eq("PRORATA")].set_index("STUDY_SCENARIO_ID").reindex(PRINCIPAL_SCENARIOS)
    if not release.empty and any(f"{s}_RELEASE_HA" in release.columns for s in ("DAIRY", "BEEF", "SHEEP")):
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        bottom = np.zeros(len(release))
        for system in ("DAIRY", "BEEF", "SHEEP"):
            vals = _numeric(release, f"{system}_RELEASE_HA", default=0.0).fillna(0.0).to_numpy(float) / 1000.0
            ax.bar(release.index, vals, bottom=bottom, label=system.title())
            bottom += vals
        ax.set_ylabel("Released grassland (kha)")
        ax.set_title("Livestock-system origin of released land")
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig09_released_land_systems")
        plt.close(fig)
    if not release.empty and any(f"G{i}_RELEASE_HA" in release.columns for i in (1, 2, 3)):
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        bottom = np.zeros(len(release))
        for group in ("G1", "G2", "G3"):
            vals = _numeric(release, f"{group}_RELEASE_HA", default=0.0).fillna(0.0).to_numpy(float) / 1000.0
            ax.bar(release.index, vals, bottom=bottom, label=group)
            bottom += vals
        ax.set_ylabel("Released grassland (kha)")
        ax.set_title("Agricultural-capability composition of released land")
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig10_released_land_soil")
        plt.close(fig)
    cond = tables["transition_conditions"]
    needed = {"SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", "FOREST_ELIGIBILITY_COVERAGE_PCT"}
    if needed.issubset(cond.columns):
        b = cond.loc[cond["STUDY_SCENARIO_ID"].eq("ALL_GAS_NZ") & cond["STUDY_ALLOCATION_POLICY"].eq("PRORATA")].dropna(subset=list(needed))
        if not b.empty:
            fig, ax = plt.subplots(figsize=(7.2, 6.0))
            ax.scatter(b["SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"], b["FOREST_ELIGIBILITY_COVERAGE_PCT"], s=14, alpha=0.55)
            ax.set_xlabel("Gross Standard Output exposure (% of baseline)")
            ax.set_ylabel("Forest-eligible share of released land (%)")
            ax.set_title("Transition exposure and released-land opportunity")
            ax.grid(alpha=0.2)
            fig.tight_layout()
            outputs += _save_figure(fig, output_dir / "fig11_exposure_forest_opportunity")
            plt.close(fig)
    mob = tables["opportunity_mobilisation"].loc[lambda x: x["STUDY_ALLOCATION_POLICY"].eq("PRORATA")].copy()
    if not mob.empty:
        mob["LABEL"] = mob["STUDY_SCENARIO_ID"].astype(str) + "\n" + mob["LAND_USE_LABEL"].astype(str)
        realised = mob["REALISED_HA"].fillna(0.0).to_numpy(float) / 1000.0
        unmet = mob["UNMET_HA"].fillna(0.0).to_numpy(float) / 1000.0
        fig, ax = plt.subplots(figsize=(13.0, 6.0))
        ax.bar(mob["LABEL"], realised, label="Realised")
        ax.bar(mob["LABEL"], unmet, bottom=realised, label="Unmet")
        ax.set_ylabel("Pathway target (kha)")
        ax.set_title("Spatial delivery of pathway land-use targets")
        ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.20))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig12_target_realised_unmet")
        plt.close(fig)
    acc = tables["land_accounting"].loc[lambda x: x["STUDY_ALLOCATION_POLICY"].eq("PRORATA")].set_index("STUDY_SCENARIO_ID").reindex(PRINCIPAL_SCENARIOS)
    if not acc.empty:
        fig, ax = plt.subplots(figsize=(8.4, 5.2))
        bottom = np.zeros(len(acc))
        for col, label in (
            ("STAGE_A_REALIZED_HA", "Stage A realised"),
            ("REWETTING_REALIZED_HA", "Rewetting realised"),
            ("SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA", "Final unallocated"),
        ):
            vals = _numeric(acc, col, default=0.0).fillna(0.0).to_numpy(float) / 1000.0
            ax.bar(acc.index, vals, bottom=bottom, label=label)
            bottom += vals
        ax.set_ylabel("Gross released land (kha)")
        ax.set_title("Strict spatial accounting of released livestock land")
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.13))
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig13_land_accounting")
        plt.close(fig)
    if not mob.empty and mob["OPPORTUNITY_MOBILISATION_PCT"].notna().any():
        fig, ax = plt.subplots(figsize=(13.0, 5.6))
        ax.bar(mob["LABEL"], mob["OPPORTUNITY_MOBILISATION_PCT"].fillna(0.0).to_numpy(float))
        ax.set_ylabel("Realised / eligible land (%)")
        ax.set_title("Pathway mobilisation of use-specific spatial opportunity")
        ax.grid(axis="y", alpha=0.2)
        fig.tight_layout()
        outputs += _save_figure(fig, output_dir / "fig14_opportunity_mobilisation")
        plt.close(fig)
    return outputs


def _read_me(study_root: Path) -> pd.DataFrame:
    return pd.DataFrame([
        ("Purpose", "Question-driven final GOBLIN-Spatial results package. SC1, SC2 and SC3 are reported as linked views of the same national pathway, not independent scenarios."),
        ("Core chain", "National pathway -> transition incidence -> Standard Output exposure/vulnerability -> released land -> natural-capital opportunity -> feasible response -> residual constraint."),
        ("Canonical source", "All reporting is downstream of completed canonical run CSVs. No SC1/SC2/SC3 scientific mathematics are changed."),
        ("Standard Output", "Fixed-2020 livestock production-value exposure only. It is not farm income, profit, welfare loss or compensation."),
        ("Persistence", "Top-decile frequency is a count across the 12 modeled pathway/rule combinations, not a probability or confidence interval."),
        ("Opportunity", "Use-specific physical eligibility and opportunity are not adoption forecasts. Eligible hectares overlap across alternative uses and must not be summed."),
        ("Mobilisation", "Realised/eligible land is pathway mobilisation of modeled spatial opportunity, not observed farmer adoption."),
        ("Land accounting", "Parent GOBLIN Available target, post-Stage-A unallocated release and final post-rewetting residual remain distinct."),
        ("Maps", "Map-ready variables are exported, but cartographic outputs remain a separate downstream stage after numerical results are inspected and frozen."),
        ("Study root", str(study_root)),
        ("Final reporting version", FINAL_STUDY_REPORTING_VERSION),
    ], columns=["ITEM", "VALUE"])


def _data_dictionary() -> pd.DataFrame:
    return pd.DataFrame([
        ("TOTAL_CATTLE_REDUCTION_PCT_OF_BASE", "%", "Physical cattle reduction relative to each ED baseline."),
        ("SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE", "%", "Gross livestock Standard Output production-value exposure relative to baseline SO."),
        ("TOP_DECILE_SO_FREQUENCY", "runs", "Number of supplied pathway/rule combinations in which the ED lies in the positive top decile of SO exposure."),
        ("GE2_WITHIN_COUNTY_SHARE_PCT", "%", "Share of GE(2) spatial variation attributable to differences among EDs within counties."),
        ("GE2_BETWEEN_COUNTY_SHARE_PCT", "%", "Share of GE(2) spatial variation attributable to differences between county means."),
        ("*_ELIGIBILITY_COVERAGE_PCT", "%", "Use-specific physically eligible hectares divided by the ED released-land budget. Use-specific eligibilities overlap."),
        ("*_OPPORTUNITY_MOBILISATION_PCT", "%", "Realised use-specific hectares divided by use-specific eligible hectares. Not an adoption rate."),
        ("ALTERNATIVE_USE_UPTAKE_PCT_OF_RELEASE", "%", "Total realised SC3 alternative-use hectares divided by released livestock land."),
        ("FINAL_UNALLOCATED_PCT_OF_RELEASE", "%", "Final unallocated released land after Stage A and rewetting divided by released land."),
        ("ROBUST_MIN_*", "varies", "Minimum ED exposure observed across the complete supplied scenario/rule set."),
        ("PATHWAY_SENSITIVITY_*", "percentage points", "Maximum between-pathway range while holding allocation rule fixed."),
        ("ALLOCATION_SENSITIVITY_*", "percentage points", "Maximum between-rule range while holding pathway fixed."),
    ], columns=["VARIABLE", "UNIT", "INTERPRETATION"])


def _write_workbook(path: Path, tables: dict[str, pd.DataFrame], figure_paths: list[Path], study_root: Path) -> None:
    sheets = [
        ("00_Read_Me", _read_me(study_root)),
        ("01_Scenario_Design", tables["run_registry"]),
        ("02_Headline_Results", tables["headline_results"]),
        ("03_National_Pathways", tables["national_results"]),
        ("04_SC1_Livestock", tables["livestock"]),
        ("05_SC1_Distribution", tables["distribution_summary"]),
        ("06_SC1_Protection", tables["redistribution"]),
        ("07_SC1_Persistence", tables["persistence"]),
        ("08_SC1_Robustness", tables["robust_exposure"]),
        ("09_SC1_Land_Release", tables["land_release_summary"]),
        ("10_SC2_Opportunity", tables["opportunity_summary"]),
        ("11_Transition_Conditions", tables["transition_conditions"]),
        ("12_Opportunity_Mobilisation", tables["opportunity_mobilisation"]),
        ("13_SC3_Target_Realised", tables["sc3_national"]),
        ("14_SC3_Shared_Pools", tables["shared_pool_summary"]),
        ("15_SC3_Rewetting", tables["rewetting_summary"]),
        ("16_SC3_Land_Accounting", tables["land_accounting"]),
        ("17_County_Results", tables["county"]),
        ("18_Map_Data", tables["map_data"]),
        ("19_Figure_Data", tables["figure_data"]),
        ("20_Validation", tables["validation"]),
        ("21_Reconciliation", tables["reconciliation"]),
        ("22_Data_Dictionary", _data_dictionary()),
        ("90_ED_SC1_Full", tables["sc1_ed"]),
        ("91_ED_SC2_Full", tables["sc2_ed"]),
        ("92_ED_SC3_Full", tables["sc3_ed"]),
    ]
    with pd.ExcelWriter(path, engine="xlsxwriter", engine_kwargs={"options": {"strings_to_urls": False}}) as writer:
        for name, frame in sheets:
            frame.to_excel(writer, sheet_name=name, index=False)
            _format_sheet(writer, name, frame)
        if figure_paths:
            ws = writer.book.add_worksheet("23_Figures")
            writer.sheets["23_Figures"] = ws
            ws.hide_gridlines(2)
            ws.set_column("A:A", 3)
            ws.set_column("B:N", 14)
            row = 1
            for png in [p for p in figure_paths if p.suffix.lower() == ".png"]:
                ws.write(row, 1, png.stem.replace("_", " ").title())
                ws.insert_image(row + 1, 1, str(png), {"x_scale": 0.70, "y_scale": 0.70})
                row += 27


def _persistence_histogram(persistence: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, column in (("Cattle reduction", "TOP_DECILE_CATTLE_FREQUENCY"), ("SO exposure", "TOP_DECILE_SO_FREQUENCY")):
        if column not in persistence.columns:
            continue
        counts = persistence[column].value_counts().reindex(range(int(persistence["RUN_COUNT"].max()) + 1), fill_value=0)
        for frequency, count in counts.items():
            rows.append({"METRIC": label, "FREQUENCY": int(frequency), "ED_COUNT": int(count)})
    return pd.DataFrame(rows)


def export_study_results(
    study_root: str | Path,
    *,
    output_dir: str | Path | None = None,
    require_complete_matrix: bool = True,
    generate_figures: bool = True,
) -> dict[str, Path]:
    """Build the final question-driven workbook, SQLite database and graph suite."""
    root = Path(study_root).resolve()
    out = Path(output_dir).resolve() if output_dir is not None else (root / "final_results").resolve()
    out.mkdir(parents=True, exist_ok=True)
    base_outputs = _base_export_study_results(
        root,
        output_dir=out,
        require_complete_matrix=require_complete_matrix,
        generate_figures=False,
    )
    tables = _read_sqlite(base_outputs["sqlite"])
    tables["distribution_summary"] = build_distribution_summary(tables["sc1_ed"])
    tables["lorenz_data"] = build_lorenz_data(tables["sc1_ed"])
    tables["persistence"] = build_exposure_persistence(tables["sc1_ed"])
    tables["persistence_histogram"] = _persistence_histogram(tables["persistence"])
    tables["land_release_summary"] = build_land_release_summary(tables["sc1_ed"])
    tables["opportunity_summary"] = build_opportunity_summary(tables["sc2_ed"])
    tables["transition_conditions"] = build_transition_conditions(
        tables["sc1_ed"], tables["sc2_ed"], tables["sc3_ed"], tables["persistence"], tables["robust_exposure"], tables["sc1_comparison"]
    )
    tables["opportunity_mobilisation"] = build_opportunity_mobilisation(tables["sc3_ed"], tables["sc3_national"])
    tables["shared_pool_summary"] = build_shared_pool_summary(tables["sc3_ed"])
    tables["rewetting_summary"] = build_rewetting_summary(tables["sc3_ed"], tables["sc3_national"])
    tables["headline_results"] = build_headline_results(
        tables["national_results"], tables["distribution_summary"], tables["land_release_summary"], tables["land_accounting"], tables["sc3_national"]
    )
    tables["map_data"] = build_map_data(tables["transition_conditions"])
    tables["figure_data"] = build_final_figure_data(tables)
    figure_dir = out / "figures"
    figure_paths: list[Path] = []
    if generate_figures:
        figure_paths = generate_final_figures(tables, figure_dir)
    _write_derived_sqlite(base_outputs["sqlite"], {
        "distribution_summary": tables["distribution_summary"],
        "lorenz_data": tables["lorenz_data"],
        "persistence": tables["persistence"],
        "persistence_histogram": tables["persistence_histogram"],
        "land_release_summary": tables["land_release_summary"],
        "opportunity_summary": tables["opportunity_summary"],
        "transition_conditions": tables["transition_conditions"],
        "opportunity_mobilisation": tables["opportunity_mobilisation"],
        "shared_pool_summary": tables["shared_pool_summary"],
        "rewetting_summary": tables["rewetting_summary"],
        "headline_results": tables["headline_results"],
        "map_data": tables["map_data"],
    }, tables["figure_data"])
    workbook = out / "GOBLIN_Spatial_Final_Results_Master.xlsx"
    _write_workbook(workbook, tables, figure_paths, root)
    figure_csv = out / "GOBLIN_Spatial_Figure_Data.csv"
    tables["figure_data"].to_csv(figure_csv, index=False)
    map_csv = out / "GOBLIN_Spatial_Map_Data.csv"
    tables["map_data"].to_csv(map_csv, index=False)
    transition_csv = out / "GOBLIN_Spatial_Transition_Conditions.csv"
    tables["transition_conditions"].to_csv(transition_csv, index=False)
    outputs = {
        "workbook": workbook,
        "sqlite": base_outputs["sqlite"],
        "figure_data_csv": figure_csv,
        "map_data_csv": map_csv,
        "transition_conditions_csv": transition_csv,
        "figure_directory": figure_dir,
    }
    for label, path in outputs.items():
        if label != "figure_directory" and not path.exists():
            raise AssertionError(f"final reporting output was not created: {path}")
    return outputs
