#!/usr/bin/env python3
"""Run the principal SI_SG or BE_SG cattle endpoint on an ED master file."""

from __future__ import annotations

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
DEFAULT_MASTER = ROOT / "data/processed/goblin_spatial_master_2015_2025.csv"
DEFAULT_ENDPOINTS = ROOT / "configs/styles_split_gas_adult_endpoints.csv"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Spatialise a sourced Styles/GOBLIN split-gas adult cattle endpoint. "
            "The national reduction is selected-baseline stock minus endpoint."
        )
    )
    parser.add_argument("--scenario-id", choices=("SI_SG", "BE_SG"), required=True)
    parser.add_argument("--baseline-year", type=int, choices=(2020, 2025), required=True)
    parser.add_argument(
        "--allocation-rule",
        choices=tuple(rule.value for rule in AllocationRule),
        default=AllocationRule.PRORATA.value,
    )
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--endpoint-controls", type=Path, default=DEFAULT_ENDPOINTS)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--score-column")
    parser.add_argument("--productivity-score-column")
    parser.add_argument("--vulnerability-score-column")
    parser.add_argument("--protection-strength", type=float, default=0.8)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--expected-eds", type=int, default=2857)
    parser.add_argument("--no-standard-output", action="store_true")
    return parser


def _national_summary(ed: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "BASE_DAIRY_COW",
        "CUMULATIVE_REDUCTION_DAIRY_COW",
        "SCENARIO_DAIRY_COW",
        "BASE_OTHER_COW",
        "CUMULATIVE_REDUCTION_OTHER_COW",
        "SCENARIO_OTHER_COW",
        "BASE_TOTAL_CATTLE",
        "CUMULATIVE_REDUCTION_TOTAL_CATTLE",
        "SCENARIO_TOTAL_CATTLE",
        "BASE_TOTAL_SHEEP",
        "SCENARIO_TOTAL_SHEEP",
    ]
    optional = [
        "BASE_SO_LIVESTOCK_2020_EUR",
        "SCENARIO_SO_LIVESTOCK_2020_EUR",
        "SO_LIVESTOCK_EXPOSURE_2020_EUR",
        "GOBLIN_RELEASED_GRASSLAND_HA",
    ]
    selected = [column for column in columns + optional if column in ed.columns]
    totals = ed[selected].sum(numeric_only=True).to_dict()
    totals["MILESTONE_YEAR"] = int(ed["MILESTONE_YEAR"].iloc[0])
    totals["ED_COUNT"] = int(ed["CSOED"].nunique())
    return pd.DataFrame([totals])


def main() -> None:
    args = _parser().parse_args()
    if not args.master.exists():
        raise FileNotFoundError(f"master file not found: {args.master}")

    panel = pd.read_csv(args.master, low_memory=False)
    controls = load_adult_endpoint_controls(
        args.endpoint_controls,
        scenario_id=args.scenario_id,
        baseline_year=args.baseline_year,
    )
    ed = run_principal_goblin_endpoint(
        panel,
        controls,
        allocation_rule=AllocationRule(args.allocation_rule),
        random_seed=args.random_seed,
        score_column=args.score_column,
        productivity_score_column=args.productivity_score_column,
        vulnerability_score_column=args.vulnerability_score_column,
        protection_strength=args.protection_strength,
        expected_eds=args.expected_eds,
        include_standard_output=not args.no_standard_output,
    )
    reconciliation = build_goblin_reconciliation(ed, controls)
    national = _national_summary(ed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ed.to_csv(args.output_dir / "scenario_ed_results.csv", index=False)
    national.to_csv(args.output_dir / "scenario_national_summary.csv", index=False)
    reconciliation.to_csv(args.output_dir / "goblin_reconciliation.csv", index=False)

    applied = pd.DataFrame(
        [
            {
                "SCENARIO_ID": controls.scenario_id,
                "BASELINE_YEAR": controls.baseline_year,
                "TARGET_YEAR": controls.target_year,
                "DAIRY_COWS": controls.milestone(controls.target_year).dairy_cows,
                "SUCKLER_COWS": controls.milestone(controls.target_year).suckler_cows,
                "ALLOCATION_RULE": args.allocation_rule,
                "SOURCE_NOTE": controls.source_note,
            }
        ]
    )
    applied.to_csv(args.output_dir / "pathway_controls_applied.csv", index=False)


if __name__ == "__main__":
    main()
