#!/usr/bin/env python
"""Build the compact validation summary used in Paper 1.

This does not introduce a new reconstruction or validation model. It selects
headline metrics from diagnostics already produced by the historical release:

1. adjacent-year ED signature stability, restricted to transitions ending in
   2020 so that post-2020 fixed spatial shares do not inflate the summary; and
2. the Stage 00 2010->2020 census carry-forward holdout at ED and WFD scale.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_VALIDATION = ROOT / "data/processed/validation/historical"
STABILITY_PATH = HISTORICAL_VALIDATION / "temporal_rank_stability.csv"
HOLDOUT_PATH = (
    ROOT
    / "data/inputs/baseline/census_reconciliation/temporal_holdout_2010_2020.csv"
)
OUTPUT_PATH = HISTORICAL_VALIDATION / "paper1_validation_summary.csv"

SIGNATURES = (
    "SIG_DAIRY_SHARE_ADULT_COWS",
    "SIG_FOLLOWERS_PER_ADULT_COW",
    "SIG_DXD_SHARE_ORIGIN_FOLLOWERS",
    "SIG_DXB_SHARE_ORIGIN_FOLLOWERS",
    "SIG_BXB_SHARE_ORIGIN_FOLLOWERS",
)


def main() -> None:
    if not STABILITY_PATH.exists():
        raise FileNotFoundError(
            f"{STABILITY_PATH} not found. Run scripts/run_historical_validation.py first."
        )
    if not HOLDOUT_PATH.exists():
        raise FileNotFoundError(
            f"{HOLDOUT_PATH} not found. Run scripts/prepare_census_inputs.py first."
        )

    stability = pd.read_csv(STABILITY_PATH)
    required_stability = {"YEAR_TO", "INDICATOR", "SPEARMAN_RHO"}
    missing = sorted(required_stability - set(stability.columns))
    if missing:
        raise ValueError(f"temporal stability output missing columns: {missing}")

    # Only transitions 2015->2016 through 2019->2020 are used in the Paper 1
    # headline. Post-2020 spatial shares are fixed by design.
    pre2021 = stability.loc[
        (pd.to_numeric(stability["YEAR_TO"], errors="raise") <= 2020)
        & stability["INDICATOR"].isin(SIGNATURES)
    ].copy()

    stability_summary = (
        pre2021.groupby("INDICATOR", as_index=False)
        .agg(
            N_TRANSITIONS=("SPEARMAN_RHO", "size"),
            MIN_SPEARMAN_RHO=("SPEARMAN_RHO", "min"),
            MEDIAN_SPEARMAN_RHO=("SPEARMAN_RHO", "median"),
            MAX_SPEARMAN_RHO=("SPEARMAN_RHO", "max"),
        )
    )

    rows: list[dict[str, object]] = []
    for record in stability_summary.to_dict("records"):
        rows.append(
            {
                "VALIDATION_TEST": "ADJACENT_YEAR_SIGNATURE_STABILITY_2015_2020",
                "SCOPE": record["INDICATOR"],
                "N": int(record["N_TRANSITIONS"]),
                "SPEARMAN_RHO": float(record["MIN_SPEARMAN_RHO"]),
                "ERROR": "",
                "ED_DISPLACED_PCT": "",
                "WFD_DISPLACED_PCT": "",
            }
        )

    holdout = pd.read_csv(HOLDOUT_PATH)
    required_holdout = {
        "VARIABLE",
        "EDS_SCORED",
        "ED_SPEARMAN",
        "ED_DISPLACED_PCT",
        "UNIT_SPEARMAN",
        "UNIT_DISPLACED_PCT",
    }
    missing = sorted(required_holdout - set(holdout.columns))
    if missing:
        raise ValueError(f"census temporal holdout missing columns: {missing}")

    dairy = holdout.loc[holdout["VARIABLE"] == "DAIRY_COW"]
    if len(dairy) != 1:
        raise AssertionError("expected exactly one DAIRY_COW temporal holdout row")
    dairy = dairy.iloc[0]
    rows.append(
        {
            "VALIDATION_TEST": "CENSUS_CARRY_FORWARD_2010_2020",
            "SCOPE": "DAIRY_COW",
            "N": int(dairy["EDS_SCORED"]),
            "SPEARMAN_RHO": float(dairy["ED_SPEARMAN"]),
            "ERROR": "",
            "ED_DISPLACED_PCT": float(dairy["ED_DISPLACED_PCT"]),
            "WFD_DISPLACED_PCT": float(dairy["UNIT_DISPLACED_PCT"]),
        }
    )

    output = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_PATH, index=False)

    print(f"Paper 1 validation summary written to: {OUTPUT_PATH}")
    print(output.to_string(index=False))


if __name__ == "__main__":
    main()
