#!/usr/bin/env python3
"""Run SI_SG or BE_SG from a validated GOBLIN-Spatial ED master."""

import argparse
from pathlib import Path
import pandas as pd

from goblin_spatial.scenario import (
    AllocationRule,
    build_goblin_reconciliation,
    load_adult_endpoint_controls,
    run_principal_goblin_endpoint,
)

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = ROOT / "configs/styles_split_gas_adult_endpoints.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario-id", choices=("SI_SG", "BE_SG"), required=True)
    parser.add_argument("--baseline-year", type=int, choices=(2020, 2025), required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--allocation-rule",
        choices=tuple(rule.value for rule in AllocationRule),
        default=AllocationRule.PRORATA.value,
    )
    parser.add_argument("--score-column")
    parser.add_argument("--productivity-score-column")
    parser.add_argument("--vulnerability-score-column")
    parser.add_argument("--protection-strength", type=float, default=0.8)
    parser.add_argument("--no-standard-output", action="store_true")
    args = parser.parse_args()

    panel = pd.read_csv(args.master, low_memory=False)
    controls = load_adult_endpoint_controls(
        ENDPOINTS,
        scenario_id=args.scenario_id,
        baseline_year=args.baseline_year,
    )
    ed = run_principal_goblin_endpoint(
        panel,
        controls,
        allocation_rule=AllocationRule(args.allocation_rule),
        score_column=args.score_column,
        productivity_score_column=args.productivity_score_column,
        vulnerability_score_column=args.vulnerability_score_column,
        protection_strength=args.protection_strength,
        expected_eds=2857,
        include_standard_output=not args.no_standard_output,
    )

    summary_columns = [
        "BASE_DAIRY_COW",
        "CHANGE_DAIRY_COW",
        "SCENARIO_DAIRY_COW",
        "BASE_OTHER_COW",
        "CHANGE_OTHER_COW",
        "SCENARIO_OTHER_COW",
        "BASE_ADULT_COWS",
        "REDUCTION_ADULT_COWS",
        "SCENARIO_ADULT_COWS",
        "BASE_TOTAL_CATTLE",
        "CUMULATIVE_REDUCTION_TOTAL_CATTLE",
        "SCENARIO_TOTAL_CATTLE",
    ]
    summary_columns += [
        column
        for column in (
            "BASE_SO_LIVESTOCK_2020_EUR",
            "SCENARIO_SO_LIVESTOCK_2020_EUR",
            "SO_LIVESTOCK_EXPOSURE_2020_EUR",
            "GOBLIN_RELEASED_GRASSLAND_HA",
        )
        if column in ed.columns
    ]
    national = pd.DataFrame([ed[summary_columns].sum(numeric_only=True).to_dict()])
    national["MILESTONE_YEAR"] = controls.target_year
    national["ED_COUNT"] = ed["CSOED"].nunique()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ed.to_csv(args.output_dir / "scenario_ed_results.csv", index=False)
    national.to_csv(args.output_dir / "scenario_national_summary.csv", index=False)
    build_goblin_reconciliation(ed, controls).to_csv(
        args.output_dir / "goblin_reconciliation.csv", index=False
    )


if __name__ == "__main__":
    main()
