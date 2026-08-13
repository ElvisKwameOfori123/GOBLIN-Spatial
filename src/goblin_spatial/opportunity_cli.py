"""Standalone downstream LPIS + soil opportunity command.

This command deliberately starts from a completed scenario ED output. It never
changes the historical livestock baseline or the GOBLIN grassland-release result.
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
from goblin_spatial.land.targets import (
    DEFAULT_TARGET_PRIORITY,
    allocate_spared_land_to_cumulative_targets,
    read_land_use_targets,
    summarise_land_target_allocation,
)
from goblin_spatial.soil import add_ed_agricultural_soil


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goblin-spatial-opportunity")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("screen", "allocate"):
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
    return parser


def _read_scenario(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    required = {
        "CSOED",
        "County",
        "MILESTONE_YEAR",
        "ALL_GRASSLAND",
        "POTENTIAL_SPARED_GRASSLAND_HA",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"scenario results missing columns: {missing}")
    return frame


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
    scenario = _read_scenario(scenario_path)
    enriched = _context(args, cfg, scenario)
    outdir = Path(args.output_dir) if args.output_dir else scenario_path.parent
    outdir.mkdir(parents=True, exist_ok=True)

    if args.command == "screen":
        screened = add_spared_land_opportunity_envelope(enriched, attach_scores=False)
        national = summarise_spared_land_opportunity_envelope(screened)
        ed_path = outdir / "scenario_ed_opportunity_v2.csv"
        nat_path = outdir / "scenario_national_opportunity_v2.csv"
        screened.to_csv(ed_path, index=False)
        national.to_csv(nat_path, index=False)
        print(f"ED opportunity v2: {ed_path}")
        print(f"National opportunity v2: {nat_path}")
        return

    targets = read_land_use_targets(args.targets)
    priority = tuple(v.strip().upper() for v in args.priority.split(",") if v.strip())
    allocated = allocate_spared_land_to_cumulative_targets(
        enriched,
        targets,
        priority=priority,
        attach_scores=False,
    )
    national = summarise_land_target_allocation(allocated)
    ed_path = outdir / "scenario_ed_land_target_allocation_v2.csv"
    nat_path = outdir / "scenario_national_land_target_allocation_v2.csv"
    allocated.to_csv(ed_path, index=False)
    national.to_csv(nat_path, index=False)
    print(f"ED target allocation v2: {ed_path}")
    print(f"National target allocation v2: {nat_path}")


if __name__ == "__main__":
    main()
