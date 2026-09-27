"""Diagnostics for the final cattle genetics disaggregation.

This script does not alter the model. It runs the frozen CSO cattle panel
through the existing GOBLIN genetics allocator and writes transparent checks
on exact closure, support/receiver use, concentration and biologically
interpretable ED ratios for 2020.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle import add_cattle_cohorts, build_cattle_panel
from goblin_spatial.cattle.cohorts import (
    CONTAINERS,
    FINAL_21_COHORTS,
    GENETICS,
    _build_biological_controls,
    _build_ed_genetic_support,
    _load_goblin,
)
from goblin_spatial.config import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUTPUT_DIR = ROOT / "data/processed/validation/historical"


def _sum_columns(mapping_key: str) -> list[str]:
    if mapping_key == "dairy_origin":
        return [
            mapping[genetic]
            for mapping in CONTAINERS.values()
            for genetic in ("DxD", "DxB")
        ]
    if mapping_key == "bxb":
        return [mapping["BxB"] for mapping in CONTAINERS.values()]
    raise ValueError(mapping_key)


def _top_share(values: pd.Series, fraction: float) -> float:
    values = pd.to_numeric(values, errors="raise").astype(float)
    total = float(values.sum())
    if total <= 0:
        return 0.0
    n = max(1, int(np.ceil(len(values) * fraction)))
    return float(values.nlargest(n).sum() / total)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="raise").astype(float)
    denominator = pd.to_numeric(denominator, errors="raise").astype(float)
    out = pd.Series(np.nan, index=numerator.index, dtype=float)
    positive = denominator > 0
    out.loc[positive] = numerator.loc[positive] / denominator.loc[positive]
    return out


def run() -> None:
    config = load_config(CONFIG)
    panel = build_cattle_panel(config)
    cattle = add_cattle_cohorts(panel, config)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Hard accounting checks.
    if not (
        cattle[FINAL_21_COHORTS].sum(axis=1).astype(np.int64)
        == cattle["TOTAL_CATTLE"].astype(np.int64)
    ).all():
        raise AssertionError("21-cohort cattle total does not close to TOTAL_CATTLE")

    for container, mapping in CONTAINERS.items():
        columns = [mapping[g] for g in GENETICS]
        if not (
            cattle[columns].sum(axis=1).astype(np.int64)
            == cattle[container].astype(np.int64)
        ).all():
            raise AssertionError(f"{container}: genetic rows do not close")

    goblin = _load_goblin(config.files["goblin_cohorts"])
    targets, _ = _build_biological_controls(cattle, goblin)
    dairy_support, bxb_support, _, _ = _build_ed_genetic_support(cattle, targets)

    national_rows: list[dict] = []
    for year in sorted(cattle["YEAR"].unique()):
        year_frame = cattle.loc[cattle["YEAR"] == year]
        for container, mapping in CONTAINERS.items():
            target = targets[(int(year), container)]
            observed = np.array(
                [int(year_frame[mapping[g]].sum()) for g in GENETICS], dtype=np.int64
            )
            if not np.array_equal(observed, target):
                raise AssertionError(
                    f"{year} {container}: genetic national margin does not close"
                )
            for j, genetic in enumerate(GENETICS):
                national_rows.append(
                    {
                        "YEAR": int(year),
                        "CONTAINER": container,
                        "GENETIC": genetic,
                        "OBSERVED": int(observed[j]),
                        "TARGET": int(target[j]),
                        "DIFF": int(observed[j] - target[j]),
                    }
                )

    national = pd.DataFrame(national_rows)
    national.to_csv(OUTPUT_DIR / "cattle_genetics_national_margins.csv", index=False)

    y2020 = cattle.loc[cattle["YEAR"] == 2020].copy()
    dairy_cols = _sum_columns("dairy_origin")
    bxb_cols = _sum_columns("bxb")
    y2020["DAIRY_ORIGIN_YOUNG"] = y2020[dairy_cols].sum(axis=1)
    y2020["BXB_YOUNG"] = y2020[bxb_cols].sum(axis=1)
    y2020["IS_DAIRY_SUPPORT"] = y2020["CSOED"].isin(dairy_support)
    y2020["IS_BXB_SUPPORT"] = y2020["CSOED"].isin(bxb_support)
    y2020["NO_ADULT_RECEIVER"] = (
        y2020["DAIRY_COW"].eq(0)
        & y2020["OTHER_COW"].eq(0)
        & y2020["OTHER_CATTLE"].gt(0)
    )
    y2020["ZERO_DAIRY_WITH_DAIRY_ORIGIN"] = (
        y2020["DAIRY_COW"].eq(0) & y2020["DAIRY_ORIGIN_YOUNG"].gt(0)
    )
    y2020["ZERO_SUCKLER_WITH_BXB"] = (
        y2020["OTHER_COW"].eq(0) & y2020["BXB_YOUNG"].gt(0)
    )

    bxb_calves = (
        y2020["BxB_calves_m"].astype(float)
        + y2020["BxB_calves_f"].astype(float)
    )
    y2020["BXB_CALVES_PER_SUCKLER_COW"] = _safe_ratio(
        bxb_calves, y2020["OTHER_COW"]
    )
    dairy_calves = (
        y2020["DxD_calves_m"].astype(float)
        + y2020["DxD_calves_f"].astype(float)
        + y2020["DxB_calves_m"].astype(float)
        + y2020["DxB_calves_f"].astype(float)
    )
    y2020["DAIRY_ORIGIN_CALVES_PER_DAIRY_COW"] = _safe_ratio(
        dairy_calves, y2020["DAIRY_COW"]
    )

    ed_columns = [
        "CSOED",
        "County",
        "ED",
        "DAIRY_COW",
        "OTHER_COW",
        "OTHER_CATTLE",
        "DAIRY_ORIGIN_YOUNG",
        "BXB_YOUNG",
        "IS_DAIRY_SUPPORT",
        "IS_BXB_SUPPORT",
        "NO_ADULT_RECEIVER",
        "ZERO_DAIRY_WITH_DAIRY_ORIGIN",
        "ZERO_SUCKLER_WITH_BXB",
        "BXB_CALVES_PER_SUCKLER_COW",
        "DAIRY_ORIGIN_CALVES_PER_DAIRY_COW",
    ]
    y2020[ed_columns].to_csv(
        OUTPUT_DIR / "cattle_genetics_ed_2020.csv", index=False
    )

    suckler_ratio = y2020.loc[
        y2020["OTHER_COW"] > 0, "BXB_CALVES_PER_SUCKLER_COW"
    ].dropna()
    dairy_ratio = y2020.loc[
        y2020["DAIRY_COW"] > 0, "DAIRY_ORIGIN_CALVES_PER_DAIRY_COW"
    ].dropna()

    total_dairy_origin = float(y2020["DAIRY_ORIGIN_YOUNG"].sum())
    total_bxb = float(y2020["BXB_YOUNG"].sum())
    no_adult = y2020["NO_ADULT_RECEIVER"]

    summary = pd.DataFrame(
        [
            {"METRIC": "ed_count_2020", "VALUE": len(y2020)},
            {"METRIC": "dairy_support_ed_count", "VALUE": len(dairy_support)},
            {"METRIC": "bxb_support_ed_count", "VALUE": len(bxb_support)},
            {
                "METRIC": "no_adult_receiver_ed_count",
                "VALUE": int(no_adult.sum()),
            },
            {
                "METRIC": "zero_dairy_ed_with_dairy_origin_count",
                "VALUE": int(y2020["ZERO_DAIRY_WITH_DAIRY_ORIGIN"].sum()),
            },
            {
                "METRIC": "zero_suckler_ed_with_bxb_count",
                "VALUE": int(y2020["ZERO_SUCKLER_WITH_BXB"].sum()),
            },
            {
                "METRIC": "dairy_origin_share_in_zero_dairy_eds",
                "VALUE": (
                    float(
                        y2020.loc[
                            y2020["DAIRY_COW"].eq(0), "DAIRY_ORIGIN_YOUNG"
                        ].sum()
                    )
                    / total_dairy_origin
                    if total_dairy_origin > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "bxb_share_in_zero_suckler_eds",
                "VALUE": (
                    float(y2020.loc[y2020["OTHER_COW"].eq(0), "BXB_YOUNG"].sum())
                    / total_bxb
                    if total_bxb > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "dairy_origin_share_in_no_adult_receivers",
                "VALUE": (
                    float(y2020.loc[no_adult, "DAIRY_ORIGIN_YOUNG"].sum())
                    / total_dairy_origin
                    if total_dairy_origin > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "bxb_share_in_no_adult_receivers",
                "VALUE": (
                    float(y2020.loc[no_adult, "BXB_YOUNG"].sum())
                    / total_bxb
                    if total_bxb > 0
                    else 0.0
                ),
            },
            {
                "METRIC": "bxb_calves_per_suckler_median",
                "VALUE": float(suckler_ratio.median()),
            },
            {
                "METRIC": "bxb_calves_per_suckler_p95",
                "VALUE": float(suckler_ratio.quantile(0.95)),
            },
            {
                "METRIC": "bxb_calves_per_suckler_p99",
                "VALUE": float(suckler_ratio.quantile(0.99)),
            },
            {
                "METRIC": "bxb_calves_per_suckler_max",
                "VALUE": float(suckler_ratio.max()),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_median",
                "VALUE": float(dairy_ratio.median()),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_p95",
                "VALUE": float(dairy_ratio.quantile(0.95)),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_p99",
                "VALUE": float(dairy_ratio.quantile(0.99)),
            },
            {
                "METRIC": "dairy_origin_calves_per_dairy_max",
                "VALUE": float(dairy_ratio.max()),
            },
            {
                "METRIC": "dairy_origin_top_1pct_share",
                "VALUE": _top_share(y2020["DAIRY_ORIGIN_YOUNG"], 0.01),
            },
            {
                "METRIC": "dairy_origin_top_5pct_share",
                "VALUE": _top_share(y2020["DAIRY_ORIGIN_YOUNG"], 0.05),
            },
            {
                "METRIC": "bxb_top_1pct_share",
                "VALUE": _top_share(y2020["BXB_YOUNG"], 0.01),
            },
            {
                "METRIC": "bxb_top_5pct_share",
                "VALUE": _top_share(y2020["BXB_YOUNG"], 0.05),
            },
        ]
    )
    summary.to_csv(OUTPUT_DIR / "cattle_genetics_summary.csv", index=False)

    # The 51 no-adult EDs are known rearing/finishing locations. They may carry
    # both origins, but genetics must never create cattle outside OTHER_CATTLE.
    if int(no_adult.sum()) != 51:
        raise AssertionError("2020 no-adult receiver count changed unexpectedly")
    if (
        y2020.loc[no_adult, "DAIRY_ORIGIN_YOUNG"] > y2020.loc[no_adult, "OTHER_CATTLE"]
    ).any():
        raise AssertionError("receiver dairy-origin allocation exceeds OTHER_CATTLE")
    if (
        y2020.loc[no_adult, "BXB_YOUNG"] > y2020.loc[no_adult, "OTHER_CATTLE"]
    ).any():
        raise AssertionError("receiver BxB allocation exceeds OTHER_CATTLE")

    print("Cattle genetics diagnostics")
    print(summary.to_string(index=False))
    print("National genetic margin max absolute difference:", int(national["DIFF"].abs().max()))
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_summary.csv")
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_ed_2020.csv")
    print("Wrote:", OUTPUT_DIR / "cattle_genetics_national_margins.csv")


if __name__ == "__main__":
    run()
