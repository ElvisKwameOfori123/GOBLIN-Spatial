"""Standalone downstream LPIS + soil opportunity command.

This command deliberately starts from a completed scenario ED output. It never
changes the historical livestock baseline or the preceding land-release result.
When an authoritative GOBLIN national release has already been spatialised, that
``GOBLIN_RELEASED_GRASSLAND_HA`` column is preferred. The older internally
calculated ``POTENTIAL_SPARED_GRASSLAND_HA`` remains a diagnostic fallback.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.land.envelope import (
    add_spared_land_opportunity_envelope,
    summarise_spared_land_opportunity_envelope,
)
from goblin_spatial.land.lpis import add_ed_lpis_context
from goblin_spatial.land.opportunity_v2 import add_ed_land_opportunity_scores_v2
from goblin_spatial.land.styles_targets import (
    allocate_styles_released_land_targets,
    summarise_styles_released_land_targets,
)
from goblin_spatial.land.targets import (
    DEFAULT_TARGET_PRIORITY,
    allocate_spared_land_to_cumulative_targets,
    read_land_use_targets,
    summarise_land_target_allocation,
)
from goblin_spatial.scenario.styles_pathway_controls import (
    load_styles_split_gas_pathway_controls,
)
from goblin_spatial.soil import add_ed_agricultural_soil


AUTHORITATIVE_RELEASE_COLUMN = "GOBLIN_RELEASED_GRASSLAND_HA"
DIAGNOSTIC_RELEASE_COLUMN = "POTENTIAL_SPARED_GRASSLAND_HA"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goblin-spatial-opportunity")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("screen", "allocate", "styles-allocate"):
        p = sub.add_parser(name)
        p.add_argument("--config", default="configs/ireland_2015_2025.yaml")
        p.add_argument("--scenario-ed-results", required=True)
        p.add_argument("--baseline-year", type=int, choices=(2020, 2025), required=True)
        p.add_argument("--soil-profile", default=None)
        p.add_argument("--lpis-profile", default=None)
        p.add_argument("--output-dir", default=None)
        if name == "allocate":
            p.add_argument("--targets", required=True)
            p.add_argument("--priority", default=",".join(DEFAULT_TARGET_PRIORITY))
        if name == "styles-allocate":
            p.add_argument("--scenario-id", choices=("SI_SG", "BE_SG"), required=True)
    return parser


def _read_scenario(path: Path) -> tuple[pd.DataFrame, str]:
    frame = pd.read_csv(path, low_memory=False)
    required = {"CSOED", "County", "MILESTONE_YEAR", "ALL_GRASSLAND"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"scenario results missing columns: {missing}")

    if AUTHORITATIVE_RELEASE_COLUMN in frame.columns:
        released_column = AUTHORITATIVE_RELEASE_COLUMN
    elif DIAGNOSTIC_RELEASE_COLUMN in frame.columns:
        released_column = DIAGNOSTIC_RELEASE_COLUMN
    else:
        raise ValueError(
            "scenario results contain neither authoritative GOBLIN released land "
            "nor the diagnostic potential-spared-grassland column"
        )
    return frame, released_column


def _context(args, cfg, scenario: pd.DataFrame) -> pd.DataFrame:
    soil_path = Path(args.soil_profile) if args.soil_profile else cfg.files.get("agricultural_soil_profile")
    if soil_path is None or not Path(soil_path).exists():
        raise FileNotFoundError("compact ED agricultural-soil profile not found")
    out = scenario if "GOBLIN_SOIL_G1_SHARE" in scenario.columns else add_ed_agricultural_soil(scenario, soil_path)

    lpis_path = Path(args.lpis_profile) if args.lpis_profile else cfg.files.get("lpis_ed_profile")
    if lpis_path is not None and Path(lpis_path).exists():
        out = add_ed_lpis_context(out, lpis_path, baseline_year=args.baseline_year)
        print(f"LPIS context attached: {lpis_path} [{args.baseline_year}]")
    else:
        print("LPIS ED control not present: using soil-only opportunity v2.")

    return add_ed_land_opportunity_scores_v2(out)


def main() -> None:
    args = _parser().parse_args()
    cfg = load_config(args.config)
    scenario_path = Path(args.scenario_ed_results)
    scenario, released_column = _read_scenario(scenario_path)
    print(f"Released-land accounting column: {released_column}")
    enriched = _context(args, cfg, scenario)
    outdir = Path(args.output_dir) if args.output_dir else scenario_path.parent
    outdir.mkdir(parents=True, exist_ok=True)

    if args.command == "screen":
        screened = add_spared_land_opportunity_envelope(
            enriched,
            spared_column=released_column,
            attach_scores=False,
        )
        national = summarise_spared_land_opportunity_envelope(
            screened,
            spared_column=released_column,
        )
        ed_path = outdir / "scenario_ed_opportunity_v2.csv"
        nat_path = outdir / "scenario_national_opportunity_v2.csv"
        screened.to_csv(ed_path, index=False)
        national.to_csv(nat_path, index=False)
        print(f"ED opportunity v2: {ed_path}")
        print(f"National opportunity v2: {nat_path}")
        return

    if args.command == "styles-allocate":
        controls_path = cfg.files.get("styles_split_gas_pathway_controls")
        if controls_path is None or not Path(controls_path).exists():
            raise FileNotFoundError("Styles split-gas pathway control table not found")
        controls = load_styles_split_gas_pathway_controls(
            controls_path,
            scenario_id=args.scenario_id,
            baseline_year=args.baseline_year,
        )
        allocated = allocate_styles_released_land_targets(
            enriched,
            controls,
            released_column=released_column,
            attach_scores=False,
        )
        national = summarise_styles_released_land_targets(
            allocated,
            released_column=released_column,
        )
        ed_path = outdir / f"scenario_ed_{args.scenario_id.lower()}_styles_land_allocation.csv"
        nat_path = outdir / f"scenario_national_{args.scenario_id.lower()}_styles_land_allocation.csv"
        allocated.to_csv(ed_path, index=False)
        national.to_csv(nat_path, index=False)
        print(f"ED Styles land allocation: {ed_path}")
        print(f"National Styles land reconciliation: {nat_path}")
        return

    targets = read_land_use_targets(args.targets)
    priority = tuple(v.strip().upper() for v in args.priority.split(",") if v.strip())
    allocated = allocate_spared_land_to_cumulative_targets(
        enriched,
        targets,
        spared_column=released_column,
        priority=priority,
        attach_scores=False,
    )
    national = summarise_land_target_allocation(
        allocated,
        spared_column=released_column,
    )
    ed_path = outdir / "scenario_ed_land_target_allocation_v2.csv"
    nat_path = outdir / "scenario_national_land_target_allocation_v2.csv"
    allocated.to_csv(ed_path, index=False)
    national.to_csv(nat_path, index=False)
    print(f"ED target allocation v2: {ed_path}")
    print(f"National target allocation v2: {nat_path}")


if __name__ == "__main__":
    main()
