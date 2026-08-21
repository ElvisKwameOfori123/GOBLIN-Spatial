"""Cross-run SC1 transition-foresight diagnostics.

The principal scenario engine deliberately separates a single physical run from
comparative foresight analysis.  This module compares completed SC1 ED outputs
across national pathways and/or spatial allocation rules without changing any
underlying livestock state.

The main questions are:

* Which EDs are protected relative to PRORATA?
* Which EDs absorb displaced adjustment under the same national endpoint?
* Which EDs are pathway-sensitive?
* Which EDs are allocation-sensitive?
* Which EDs remain exposed across every supplied plausible run?

No threshold for "high" or "robust" exposure is invented here.  Continuous
lower-bound/range diagnostics are always reported.  Optional classifications are
created only when the caller supplies explicit thresholds.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


DEFAULT_SCENARIO_COLUMN = "PATHWAY_NAME"
DEFAULT_RULE_COLUMN = "PATHWAY_ALLOCATION_RULE"


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"SC1 comparison missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def _require_run_identity(
    frame: pd.DataFrame,
    *,
    scenario_column: str,
    rule_column: str,
) -> None:
    required = {"CSOED", scenario_column, rule_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"SC1 comparison missing columns: {missing}")
    if frame[["CSOED", scenario_column, rule_column]].duplicated().any():
        raise ValueError("SC1 comparison requires one row per ED x scenario x allocation rule")


def add_sc1_comparison_intensity(frame: pd.DataFrame) -> pd.DataFrame:
    """Add relative cattle and SO exposure measures suitable for cross-run comparison."""

    out = frame.copy()
    if "TOTAL_CATTLE_REDUCTION_HEAD" not in out.columns:
        if "CUMULATIVE_REDUCTION_TOTAL_CATTLE" not in out.columns:
            raise ValueError("SC1 comparison requires a total-cattle reduction column")
        reduction = _numeric(out, "CUMULATIVE_REDUCTION_TOTAL_CATTLE")
        if (reduction < -1e-9).any():
            raise ValueError("total-cattle reduction cannot be negative")
        out["TOTAL_CATTLE_REDUCTION_HEAD"] = np.maximum(reduction, 0.0)

    if "BASE_TOTAL_CATTLE" not in out.columns:
        raise ValueError("SC1 comparison requires BASE_TOTAL_CATTLE")
    base_cattle = _numeric(out, "BASE_TOTAL_CATTLE")
    reduction = _numeric(out, "TOTAL_CATTLE_REDUCTION_HEAD")
    if (base_cattle < -1e-9).any() or (reduction < -1e-9).any():
        raise ValueError("cattle comparison values cannot be negative")
    out["TOTAL_CATTLE_REDUCTION_PCT_OF_BASE"] = np.divide(
        100.0 * np.maximum(reduction, 0.0),
        np.maximum(base_cattle, 0.0),
        out=np.zeros(len(out), dtype=float),
        where=base_cattle > 0,
    )

    if "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" not in out.columns:
        if "SO_LIVESTOCK_EXPOSURE_2020_EUR" in out.columns:
            exposure = _numeric(out, "SO_LIVESTOCK_EXPOSURE_2020_EUR")
            out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"] = np.maximum(exposure, 0.0)

    if (
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" in out.columns
        and "BASE_SO_LIVESTOCK_2020_EUR" in out.columns
    ):
        loss = _numeric(out, "SO_LIVESTOCK_GROSS_LOSS_2020_EUR")
        base_so = _numeric(out, "BASE_SO_LIVESTOCK_2020_EUR")
        if (loss < -1e-9).any() or (base_so < -1e-9).any():
            raise ValueError("SO comparison values cannot be negative")
        out["SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE"] = np.divide(
            100.0 * np.maximum(loss, 0.0),
            np.maximum(base_so, 0.0),
            out=np.zeros(len(out), dtype=float),
            where=base_so > 0,
        )

    return out


def compare_sc1_to_prorata(
    frame: pd.DataFrame,
    *,
    scenario_column: str = DEFAULT_SCENARIO_COLUMN,
    rule_column: str = DEFAULT_RULE_COLUMN,
    prorata_label: str = "PRORATA",
) -> pd.DataFrame:
    """Measure protection benefit and displaced burden relative to PRORATA.

    Comparisons are always made within the same national scenario.  Positive
    ``PROTECTION_RELIEF_*`` means the alternative rule exposes an ED less than
    PRORATA.  Positive ``DISPLACED_BURDEN_*`` means it exposes the ED more.  The
    national sum of signed differences should be approximately zero for physical
    quantities when the compared runs close to the same national endpoint.
    """

    out = add_sc1_comparison_intensity(frame)
    _require_run_identity(
        out,
        scenario_column=scenario_column,
        rule_column=rule_column,
    )

    reference = out.loc[
        out[rule_column].astype(str).str.upper().eq(str(prorata_label).upper())
    ].copy()
    if reference.empty:
        raise ValueError(f"SC1 comparison requires a {prorata_label} reference run")
    if reference[["CSOED", scenario_column]].duplicated().any():
        raise ValueError("multiple PRORATA reference rows for the same ED and scenario")

    metrics = [
        column
        for column in (
            "TOTAL_CATTLE_REDUCTION_HEAD",
            "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
            "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
            "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
            "GOBLIN_RELEASED_GRASSLAND_HA",
        )
        if column in out.columns
    ]
    ref_cols = ["CSOED", scenario_column, *metrics]
    reference = reference[ref_cols].rename(
        columns={column: f"PRORATA_{column}" for column in metrics}
    )
    out = out.merge(
        reference,
        on=["CSOED", scenario_column],
        how="left",
        validate="many_to_one",
    )
    if out[[f"PRORATA_{column}" for column in metrics]].isna().any().any():
        raise ValueError("a scenario/rule run has no matching PRORATA ED reference")

    for column in metrics:
        current = pd.to_numeric(out[column], errors="raise").to_numpy(dtype=float)
        ref = pd.to_numeric(out[f"PRORATA_{column}"], errors="raise").to_numpy(dtype=float)
        signed = current - ref
        out[f"SIGNED_DIFFERENCE_FROM_PRORATA_{column}"] = signed
        out[f"PROTECTION_RELIEF_{column}"] = np.maximum(-signed, 0.0)
        out[f"DISPLACED_BURDEN_{column}"] = np.maximum(signed, 0.0)

    return out


def _range_by_groups(
    frame: pd.DataFrame,
    *,
    group_columns: Sequence[str],
    value_column: str,
) -> pd.Series:
    grouped = frame.groupby(list(group_columns), sort=False)[value_column]
    ranges = grouped.max() - grouped.min()
    if len(group_columns) == 1:
        return ranges
    return ranges.groupby(level=0).max()


def build_sc1_robust_exposure(
    frame: pd.DataFrame,
    *,
    scenario_column: str = DEFAULT_SCENARIO_COLUMN,
    rule_column: str = DEFAULT_RULE_COLUMN,
    cattle_reduction_pct_threshold: float | None = None,
    so_loss_pct_threshold: float | None = None,
) -> pd.DataFrame:
    """Summarise robust, pathway-sensitive and allocation-sensitive ED exposure.

    ``ROBUST_MIN_*`` is the conservative lower bound observed across every
    supplied scenario/rule combination.  ``PATHWAY_SENSITIVITY_*`` measures the
    maximum between-pathway range observed while holding an allocation rule
    fixed.  ``ALLOCATION_SENSITIVITY_*`` measures the maximum between-rule range
    observed while holding a national pathway fixed.

    Optional boolean classifications are added only when explicit thresholds are
    supplied by the caller.
    """

    out = add_sc1_comparison_intensity(frame)
    _require_run_identity(
        out,
        scenario_column=scenario_column,
        rule_column=rule_column,
    )

    expected_runs = out[[scenario_column, rule_column]].drop_duplicates()
    run_count = len(expected_runs)
    counts = out.groupby("CSOED", sort=False).size()
    if (counts != run_count).any():
        raise ValueError(
            "robust-exposure comparison requires the same scenario/rule run set for every ED"
        )

    metrics = ["TOTAL_CATTLE_REDUCTION_PCT_OF_BASE"]
    if "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE" in out.columns:
        metrics.append("SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE")

    rows = []
    for ed, block in out.groupby("CSOED", sort=False):
        row: dict[str, object] = {
            "CSOED": ed,
            "RUN_COUNT": int(len(block)),
            "SCENARIO_COUNT": int(block[scenario_column].nunique()),
            "ALLOCATION_RULE_COUNT": int(block[rule_column].nunique()),
        }
        for column in metrics:
            values = pd.to_numeric(block[column], errors="raise").to_numpy(dtype=float)
            label = (
                "CATTLE_REDUCTION_PCT"
                if column == "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE"
                else "SO_LOSS_PCT"
            )
            row[f"ROBUST_MIN_{label}"] = float(values.min())
            row[f"MEAN_{label}"] = float(values.mean())
            row[f"MAX_{label}"] = float(values.max())
            row[f"TOTAL_RANGE_{label}"] = float(values.max() - values.min())
        rows.append(row)
    summary = pd.DataFrame(rows)

    for column in metrics:
        label = (
            "CATTLE_REDUCTION_PCT"
            if column == "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE"
            else "SO_LOSS_PCT"
        )
        pathway_ranges = (
            out.groupby(["CSOED", rule_column], sort=False)[column].max()
            - out.groupby(["CSOED", rule_column], sort=False)[column].min()
        ).groupby(level=0).max()
        allocation_ranges = (
            out.groupby(["CSOED", scenario_column], sort=False)[column].max()
            - out.groupby(["CSOED", scenario_column], sort=False)[column].min()
        ).groupby(level=0).max()
        summary[f"PATHWAY_SENSITIVITY_{label}"] = summary["CSOED"].map(pathway_ranges).fillna(0.0)
        summary[f"ALLOCATION_SENSITIVITY_{label}"] = summary["CSOED"].map(allocation_ranges).fillna(0.0)

    if cattle_reduction_pct_threshold is not None:
        threshold = float(cattle_reduction_pct_threshold)
        if not np.isfinite(threshold) or threshold < 0:
            raise ValueError("cattle_reduction_pct_threshold must be finite and non-negative")
        summary["ROBUSTLY_EXPOSED_CATTLE"] = (
            summary["ROBUST_MIN_CATTLE_REDUCTION_PCT"] >= threshold
        )

    if so_loss_pct_threshold is not None:
        if "ROBUST_MIN_SO_LOSS_PCT" not in summary.columns:
            raise ValueError("SO threshold supplied but SO exposure is unavailable")
        threshold = float(so_loss_pct_threshold)
        if not np.isfinite(threshold) or threshold < 0:
            raise ValueError("so_loss_pct_threshold must be finite and non-negative")
        summary["ROBUSTLY_EXPOSED_SO"] = summary["ROBUST_MIN_SO_LOSS_PCT"] >= threshold

    return summary.sort_values("CSOED", kind="stable").reset_index(drop=True)


def summarise_sc1_redistribution(
    compared: pd.DataFrame,
    *,
    scenario_column: str = DEFAULT_SCENARIO_COLUMN,
    rule_column: str = DEFAULT_RULE_COLUMN,
) -> pd.DataFrame:
    """Return compact national protection/displacement totals by scenario and rule."""

    required = {scenario_column, rule_column}
    missing = sorted(required - set(compared.columns))
    if missing:
        raise ValueError(f"redistribution summary missing columns: {missing}")

    metric_suffixes = []
    for column in compared.columns:
        prefix = "PROTECTION_RELIEF_"
        if column.startswith(prefix):
            suffix = column[len(prefix):]
            if f"DISPLACED_BURDEN_{suffix}" in compared.columns:
                metric_suffixes.append(suffix)
    if not metric_suffixes:
        raise ValueError("redistribution summary requires compare_sc1_to_prorata output")

    rows: list[dict[str, object]] = []
    for keys, block in compared.groupby([scenario_column, rule_column], sort=True):
        scenario, rule = keys
        row: dict[str, object] = {
            scenario_column: scenario,
            rule_column: rule,
            "ED_COUNT": int(block["CSOED"].nunique()),
        }
        for suffix in metric_suffixes:
            relief = pd.to_numeric(
                block[f"PROTECTION_RELIEF_{suffix}"], errors="raise"
            ).to_numpy(dtype=float)
            burden = pd.to_numeric(
                block[f"DISPLACED_BURDEN_{suffix}"], errors="raise"
            ).to_numpy(dtype=float)
            signed = pd.to_numeric(
                block[f"SIGNED_DIFFERENCE_FROM_PRORATA_{suffix}"], errors="raise"
            ).to_numpy(dtype=float)
            row[f"TOTAL_PROTECTION_RELIEF_{suffix}"] = float(relief.sum())
            row[f"TOTAL_DISPLACED_BURDEN_{suffix}"] = float(burden.sum())
            row[f"NET_DIFFERENCE_FROM_PRORATA_{suffix}"] = float(signed.sum())
            row[f"EDS_PROTECTED_{suffix}"] = int((relief > 1e-12).sum())
            row[f"EDS_WITH_DISPLACED_BURDEN_{suffix}"] = int((burden > 1e-12).sum())
        rows.append(row)
    return pd.DataFrame(rows)
