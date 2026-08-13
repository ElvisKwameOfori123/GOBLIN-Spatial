"""Screen potentially spared grassland against the ED soil/opportunity profile.

This is deliberately a downstream, policy-neutral stage.  It does not allocate
hectares to forestry, rewetting, bioenergy or nature.  Instead it reports the
overlapping opportunity envelope for each land use so study-specific conversion
shares can be chosen later without contaminating the physical livestock result.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.land import (
    add_spared_land_opportunity_envelope,
    summarise_spared_land_opportunity_envelope,
)
from goblin_spatial.soil import add_ed_agricultural_soil


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attach the compact ED agricultural-soil profile to scenario results "
            "and produce overlapping, policy-neutral land-opportunity envelopes."
        )
    )
    parser.add_argument(
        "scenario_ed_results",
        type=Path,
        help="Path to scenario_ed_results.csv from the cattle study workflow.",
    )
    parser.add_argument(
        "soil_profile",
        type=Path,
        help="Compact ED agricultural-soil profile generated from the Cathal/NFS source.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output directory. Defaults to the scenario-results directory."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_path = args.scenario_ed_results.resolve()
    soil_path = args.soil_profile.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else scenario_path.parent
    )

    scenario = pd.read_csv(scenario_path, low_memory=False)
    required = {"CSOED", "County", "MILESTONE_YEAR", "ALL_GRASSLAND", "POTENTIAL_SPARED_GRASSLAND_HA"}
    missing = sorted(required - set(scenario.columns))
    if missing:
        raise ValueError(f"scenario results missing columns: {missing}")
    if scenario[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("scenario results must contain one row per ED and milestone")

    enriched = add_ed_agricultural_soil(scenario, soil_path)
    screened = add_spared_land_opportunity_envelope(enriched)
    national = summarise_spared_land_opportunity_envelope(screened)

    output_dir.mkdir(parents=True, exist_ok=True)
    ed_output = output_dir / "scenario_ed_opportunity_envelope.csv"
    national_output = output_dir / "scenario_national_opportunity_envelope.csv"
    screened.to_csv(ed_output, index=False)
    national.to_csv(national_output, index=False)

    print(f"ED opportunity envelope: {ed_output}")
    print(f"National opportunity envelope: {national_output}")
    print(
        "These envelopes overlap and are screening diagnostics only; no hectares "
        "have been assigned to an alternative land use."
    )


if __name__ == "__main__":
    main()
