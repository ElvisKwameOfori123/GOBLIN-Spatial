#!/usr/bin/env python
"""Build the compact supplementary validation summary used in Paper 1.

This script does not introduce a new validation model. It selects headline
metrics already produced by the historical release and restricts temporal
stability to transitions ending in 2020, before the fixed post-2020 spatial
shares can mechanically inflate continuity.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_VALIDATION = ROOT / "data/processed/validation/historical"
STABILITY_PATH = HISTORICAL_VALIDATION / "temporal_rank_stability.csv"
HOLDOUT_PATH = ROOT / "data/inputs/baseline/census_reconciliation/temporal_holdout_2010_2020.csv"
OUTPUT_PATH = HISTORICAL_VALIDATION / "paper1_validation_summary.csv"

SIGNATURES = (
    "SIG_DAIRY_SHARE_ADULT_COWS",
    "SIG_FOLLOWERS_PER_ADULT_COW",
    "SIG_DXD_SHARE_ORIGIN_FOLLOWERS",
    "SIG_DXB_SHARE_ORIGIN_FOLLOWERS",
    "SIG_BXB_SHARE_ORIGIN_FOLLOWERS",
)


def main() -> None:
    stability = pd.read_csv(STABILITY_PATH)
    pre2021 = stability.loc[(pd.to_numeric(stability["YEAR_TO"], errors="raise") <= 2020) & stability["INDICATOR"].isin(SIGNATURES)].copy()
    summary = pre2021.groupby("INDICATOR", as_index=False).agg(
        N_TRANSITIONS=("SPEARMAN_RHO", "size"),
        MIN_SPEARMAN_RHO=("SPEARMAN_RHO", "min"),
        MEDIAN_SPEARMAN_RHO=("SPEARMAN_RHO", "median"),
        MAX_SPEARMAN_RHO=("SPEARMAN_RHO", "max"),
    )
    rows = [{
        "VALIDATION_TEST": "ADJACENT_YEAR_SIGNATURE_STABILITY_2015_2020",
        "SCOPE": r["INDICATOR"],
        "N": int(r["N_TRANSITIONS"]),
        "SPEARMAN_RHO_MIN": float(r["MIN_SPEARMAN_RHO"]),
        "SPEARMAN_RHO_MEDIAN": float(r["MEDIAN_SPEARMAN_RHO"]),
        "SPEARMAN_RHO_MAX": float(r["MAX_SPEARMAN_RHO"]),
    } for r in summary.to_dict("records")]

    holdout = pd.read_csv(HOLDOUT_PATH)
    dairy = holdout.loc[holdout["VARIABLE"] == "DAIRY_COW"]
    if len(dairy) != 1:
        raise AssertionError("expected exactly one DAIRY_COW temporal holdout row")
    d = dairy.iloc[0]
    rows.append({
        "VALIDATION_TEST": "CENSUS_CARRY_FORWARD_2010_2020",
        "SCOPE": "DAIRY_COW",
        "N": int(d["EDS_SCORED"]),
        "SPEARMAN_RHO_MIN": float(d["ED_SPEARMAN"]),
        "SPEARMAN_RHO_MEDIAN": float(d["UNIT_SPEARMAN"]),
        "SPEARMAN_RHO_MAX": float(d["UNIT_SPEARMAN"]),
        "ED_DISPLACED_PCT": float(d["ED_DISPLACED_PCT"]),
        "WFD_DISPLACED_PCT": float(d["UNIT_DISPLACED_PCT"]),
    })
    out = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False)
    print(f"Paper 1 validation summary written to: {OUTPUT_PATH}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
