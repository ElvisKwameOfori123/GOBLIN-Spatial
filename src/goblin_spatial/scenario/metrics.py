"""SC1 transition, exposure and distributional diagnostics.

These metrics are reporting outputs only.  They never feed back into cattle
allocation, cohort propagation or released-land spatialisation.

Standard Output (SO) remains a fixed-2020 production-value exposure measure,
not profit, income or welfare.  Some EDs can in principle gain SO when endpoint
composition shifts even while national cattle numbers contract.  Distributional
loss metrics therefore use the positive part of baseline-minus-scenario SO and
report gains separately rather than forcing signed values into a Gini formula.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise KeyError(column)
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def gini(values: np.ndarray | pd.Series) -> float:
    """Return the standard Gini coefficient for finite non-negative values."""

    x = np.asarray(values, dtype=float)
    if x.ndim != 1:
        raise ValueError("gini requires a one-dimensional vector")
    if (~np.isfinite(x)).any() or (x < -1e-12).any():
        raise ValueError("gini requires finite non-negative values")
    x = np.maximum(x, 0.0)
    n = len(x)
    total = float(x.sum())
    if n == 0 or total <= 1e-15:
        return 0.0
    ordered = np.sort(x)
    ranks = np.arange(1, n + 1, dtype=float)
    value = float(np.sum((2.0 * ranks - n - 1.0) * ordered) / (n * total))
    return float(np.clip(value, 0.0, 1.0))


def _top_share(values: np.ndarray, fraction: float) -> float:
    x = np.maximum(np.asarray(values, dtype=float), 0.0)
    if not 0.0 < float(fraction) <= 1.0:
        raise ValueError("fraction must lie in (0, 1]")
    total = float(x.sum())
    if len(x) == 0 or total <= 1e-15:
        return 0.0
    count = max(1, int(math.ceil(len(x) * float(fraction))))
    return float(np.sort(x)[-count:].sum() / total)


def _units_to_reach_share(values: np.ndarray, share: float) -> int:
    x = np.maximum(np.asarray(values, dtype=float), 0.0)
    if not 0.0 < float(share) <= 1.0:
        raise ValueError("share must lie in (0, 1]")
    total = float(x.sum())
    if len(x) == 0 or total <= 1e-15:
        return 0
    ordered = np.sort(x)[::-1]
    threshold = total * float(share)
    return int(np.searchsorted(np.cumsum(ordered), threshold, side="left") + 1)


def add_sc1_ed_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach transparent ED-level SC1 exposure/intensity reporting columns."""

    out = frame.copy()

    if "SO_LIVESTOCK_EXPOSURE_2020_EUR" in out.columns:
        exposure = _numeric(out, "SO_LIVESTOCK_EXPOSURE_2020_EUR")
        out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"] = np.maximum(exposure, 0.0)
        out["SO_LIVESTOCK_GAIN_2020_EUR"] = np.maximum(-exposure, 0.0)

    if "CUMULATIVE_REDUCTION_TOTAL_CATTLE" in out.columns:
        cattle_reduction = _numeric(out, "CUMULATIVE_REDUCTION_TOTAL_CATTLE")
        if (cattle_reduction < -1e-9).any():
            raise ValueError("SC1 total-cattle reduction cannot be negative")
        out["TOTAL_CATTLE_REDUCTION_HEAD"] = np.maximum(cattle_reduction, 0.0)

    if "AGRICULTURAL_HOLDINGS" in out.columns:
        holdings = pd.to_numeric(out["AGRICULTURAL_HOLDINGS"], errors="coerce").to_numpy(dtype=float)
        valid_holdings = np.isfinite(holdings) & (holdings > 0)
        if "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" in out.columns:
            gross_loss = out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"].to_numpy(dtype=float)
            out["SO_LIVESTOCK_GROSS_LOSS_PER_HOLDING_2020_EUR"] = np.divide(
                gross_loss,
                holdings,
                out=np.full(len(out), np.nan, dtype=float),
                where=valid_holdings,
            )
        if "TOTAL_CATTLE_REDUCTION_HEAD" in out.columns:
            cattle = out["TOTAL_CATTLE_REDUCTION_HEAD"].to_numpy(dtype=float)
            out["TOTAL_CATTLE_REDUCTION_PER_HOLDING"] = np.divide(
                cattle,
                holdings,
                out=np.full(len(out), np.nan, dtype=float),
                where=valid_holdings,
            )

    if "GOBLIN_RELEASED_GRASSLAND_HA" in out.columns:
        released = _numeric(out, "GOBLIN_RELEASED_GRASSLAND_HA")
        if (released < -1e-9).any():
            raise ValueError("SC1 released grassland cannot be negative")
        released = np.maximum(released, 0.0)
        if "ALL_GRASSLAND" in out.columns:
            grass = _numeric(out, "ALL_GRASSLAND")
            if (grass < -1e-9).any():
                raise ValueError("ALL_GRASSLAND cannot be negative")
            out["GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE"] = np.divide(
                100.0 * released,
                grass,
                out=np.zeros(len(out), dtype=float),
                where=grass > 0,
            )

    share_columns = {
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR": "SO_GROSS_LOSS_SHARE_NATIONAL",
        "TOTAL_CATTLE_REDUCTION_HEAD": "TOTAL_CATTLE_REDUCTION_SHARE_NATIONAL",
        "GOBLIN_RELEASED_GRASSLAND_HA": "RELEASED_GRASSLAND_SHARE_NATIONAL",
    }
    for source, destination in share_columns.items():
        if source not in out.columns:
            continue
        values = pd.to_numeric(out[source], errors="raise").to_numpy(dtype=float)
        values = np.maximum(values, 0.0)
        total = float(values.sum())
        out[destination] = values / total if total > 1e-15 else np.zeros(len(out))

    return out


def build_sc1_national_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one-row national SC1 transition/exposure/distribution summary."""

    out = add_sc1_ed_metrics(frame)
    row: dict[str, float | int | str] = {}

    for source, destination in (
        ("PATHWAY_NAME", "SCENARIO_ID"),
        ("SCENARIO_NAME", "SCENARIO_ID"),
    ):
        if source in out.columns:
            row[destination] = str(out[source].iloc[0])
            break
    if "PATHWAY_BASELINE_YEAR" in out.columns:
        row["RUN_START_YEAR"] = int(pd.to_numeric(out["PATHWAY_BASELINE_YEAR"], errors="raise").iloc[0])
    elif "SCENARIO_BASELINE_YEAR" in out.columns:
        row["RUN_START_YEAR"] = int(pd.to_numeric(out["SCENARIO_BASELINE_YEAR"], errors="raise").iloc[0])
    if "MILESTONE_YEAR" in out.columns:
        row["TARGET_YEAR"] = int(pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").iloc[0])
    row["ED_COUNT"] = int(out["CSOED"].nunique()) if "CSOED" in out.columns else int(len(out))

    sum_columns = {
        "BASE_DAIRY_COW": "BASE_DAIRY_COWS",
        "SCENARIO_DAIRY_COW": "SCENARIO_DAIRY_COWS",
        "BASE_OTHER_COW": "BASE_SUCKLER_COWS",
        "SCENARIO_OTHER_COW": "SCENARIO_SUCKLER_COWS",
        "BASE_TOTAL_CATTLE": "BASE_TOTAL_CATTLE",
        "SCENARIO_TOTAL_CATTLE": "SCENARIO_TOTAL_CATTLE",
        "CUMULATIVE_REDUCTION_TOTAL_CATTLE": "TOTAL_CATTLE_REDUCTION_HEAD",
        "BASE_SO_LIVESTOCK_2020_EUR": "BASE_SO_LIVESTOCK_2020_EUR",
        "SCENARIO_SO_LIVESTOCK_2020_EUR": "SCENARIO_SO_LIVESTOCK_2020_EUR",
        "SO_LIVESTOCK_EXPOSURE_2020_EUR": "NET_SO_LIVESTOCK_EXPOSURE_2020_EUR",
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR": "GROSS_SO_LIVESTOCK_LOSS_2020_EUR",
        "SO_LIVESTOCK_GAIN_2020_EUR": "GROSS_SO_LIVESTOCK_GAIN_2020_EUR",
        "GOBLIN_RELEASED_GRASSLAND_HA": "GOBLIN_RELEASED_GRASSLAND_HA",
    }
    for column, name in sum_columns.items():
        if column in out.columns:
            row[name] = float(pd.to_numeric(out[column], errors="raise").sum())

    if "BASE_SO_LIVESTOCK_2020_EUR" in out.columns:
        base_so = np.maximum(_numeric(out, "BASE_SO_LIVESTOCK_2020_EUR"), 0.0)
        scenario_so = np.maximum(_numeric(out, "SCENARIO_SO_LIVESTOCK_2020_EUR"), 0.0)
        row["GINI_BASE_SO_LIVESTOCK"] = gini(base_so)
        row["GINI_SCENARIO_SO_LIVESTOCK"] = gini(scenario_so)
        row["DELTA_GINI_SO_LIVESTOCK"] = row["GINI_SCENARIO_SO_LIVESTOCK"] - row["GINI_BASE_SO_LIVESTOCK"]

    diagnostic_vectors = {
        "SO_LOSS": "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "TOTAL_CATTLE_REDUCTION": "TOTAL_CATTLE_REDUCTION_HEAD",
        "ADULT_CATTLE_REDUCTION": "REDUCTION_ADULT_COWS",
        "RELEASED_GRASSLAND": "GOBLIN_RELEASED_GRASSLAND_HA",
    }
    for label, column in diagnostic_vectors.items():
        if column not in out.columns:
            continue
        values = _numeric(out, column)
        if (values < -1e-9).any():
            raise ValueError(f"{column} cannot be negative for SC1 distribution metrics")
        values = np.maximum(values, 0.0)
        row[f"GINI_{label}"] = gini(values)
        row[f"TOP_10PCT_ED_SHARE_{label}"] = _top_share(values, 0.10)
        row[f"TOP_20PCT_ED_SHARE_{label}"] = _top_share(values, 0.20)
        row[f"EDS_FOR_50PCT_{label}"] = _units_to_reach_share(values, 0.50)
        row[f"EDS_FOR_80PCT_{label}"] = _units_to_reach_share(values, 0.80)
        row[f"EDS_WITH_POSITIVE_{label}"] = int((values > 1e-12).sum())

    if "SO_LIVESTOCK_EXPOSURE_2020_EUR" in out.columns:
        exposure = _numeric(out, "SO_LIVESTOCK_EXPOSURE_2020_EUR")
        row["EDS_WITH_SO_LOSS"] = int((exposure > 1e-9).sum())
        row["EDS_WITH_SO_GAIN"] = int((exposure < -1e-9).sum())
        row["EDS_WITH_NO_MATERIAL_SO_CHANGE"] = int((np.abs(exposure) <= 1e-9).sum())

    return pd.DataFrame([row])


def build_sc1_county_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate SC1 physical and SO exposure incidence to county level."""

    if "County" not in frame.columns:
        raise ValueError("SC1 county summary requires County")
    out = add_sc1_ed_metrics(frame)
    value_columns = [
        column
        for column in (
            "BASE_DAIRY_COW",
            "SCENARIO_DAIRY_COW",
            "BASE_OTHER_COW",
            "SCENARIO_OTHER_COW",
            "BASE_TOTAL_CATTLE",
            "SCENARIO_TOTAL_CATTLE",
            "TOTAL_CATTLE_REDUCTION_HEAD",
            "BASE_SO_LIVESTOCK_2020_EUR",
            "SCENARIO_SO_LIVESTOCK_2020_EUR",
            "SO_LIVESTOCK_EXPOSURE_2020_EUR",
            "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
            "SO_LIVESTOCK_GAIN_2020_EUR",
            "GOBLIN_RELEASED_GRASSLAND_HA",
            "AGRICULTURAL_HOLDINGS",
            "ALL_GRASSLAND",
        )
        if column in out.columns
    ]
    summary = out.groupby("County", as_index=False)[value_columns].sum(numeric_only=True)
    summary["ED_COUNT"] = out.groupby("County")["CSOED"].nunique().reindex(summary["County"]).to_numpy()

    for source, destination in (
        ("SO_LIVESTOCK_GROSS_LOSS_2020_EUR", "COUNTY_SHARE_NATIONAL_SO_GROSS_LOSS"),
        ("TOTAL_CATTLE_REDUCTION_HEAD", "COUNTY_SHARE_NATIONAL_CATTLE_REDUCTION"),
        ("GOBLIN_RELEASED_GRASSLAND_HA", "COUNTY_SHARE_NATIONAL_RELEASED_GRASSLAND"),
    ):
        if source not in summary.columns:
            continue
        total = float(summary[source].sum())
        summary[destination] = summary[source] / total if total > 1e-15 else 0.0

    return summary.sort_values("County", kind="stable").reset_index(drop=True)
