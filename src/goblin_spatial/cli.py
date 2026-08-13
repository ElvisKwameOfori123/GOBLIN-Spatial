"""Command-line interface for GOBLIN-Spatial."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.data_fetch import fetch_data
from goblin_spatial.land import LandUseAllocationDefinition
from goblin_spatial.pipeline import build
from goblin_spatial.scenario import (
    build_and_run_cattle_study,
    load_pasture_dm_profiles,
    make_cattle_scenario,
    run_cattle_study,
)


def _add_cattle_scenario_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )
    parser.add_argument("--name", default=None, help="Scenario name.")
    parser.add_argument(
        "--baseline-year",
        type=int,
        choices=(2020, 2025),
        default=2020,
        help="Historical ED state used as the scenario starting point.",
    )
    parser.add_argument(
        "--target-year", type=int, default=2050, help="Final scenario year."
    )
    parser.add_argument(
        "--dairy-reduction",
        type=float,
        default=0.0,
        help="Final dairy-cow reduction fraction in [0,1].",
    )
    parser.add_argument(
        "--suckler-reduction",
        type=float,
        default=0.0,
        help="Final suckler-cow reduction fraction in [0,1].",
    )
    parser.add_argument(
        "--pasture-dm-controls",
        default=None,
        help=(
            "Optional CSV of authoritative GOBLIN YEAR/COHORT/"
            "PASTURE_DM_T_PER_HEAD_YEAR controls. If omitted, the run stops "
            "after the livestock/SO stage and does not report spared land."
        ),
    )
    parser.add_argument(
        "--supply-multiplier",
        type=float,
        default=1.0,
        help="Future pasture supply multiplier used only with pasture-DM controls.",
    )
    parser.add_argument(
        "--no-standard-output",
        action="store_true",
        help="Skip downstream fixed-2020 Standard Output valuation.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Scenario output directory. Defaults under data/processed/scenarios/.",
    )

    # Alternative-land shares are optional policy assumptions. All default to
    # zero so the CLI never invents a land-use pathway.
    parser.add_argument("--forest-share", type=float, default=0.0)
    parser.add_argument("--rewetting-share", type=float, default=0.0)
    parser.add_argument("--ad-grass-share", type=float, default=0.0)
    parser.add_argument("--willow-share", type=float, default=0.0)
    parser.add_argument("--energy-grass-share", type=float, default=0.0)
    parser.add_argument("--nature-share", type=float, default=0.0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial",
        description="Generate and analyse fine-scale GOBLIN-Spatial ED datasets.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_parser = sub.add_parser(
        "fetch-data",
        help="Download or verify the pinned input datasets in data_manifest.yaml.",
    )
    fetch_parser.add_argument(
        "--manifest",
        default="data_manifest.yaml",
        help="Path to the data manifest.",
    )
    fetch_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not download; verify existing files.",
    )
    fetch_parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="Check only Git/local inputs and skip external full-data inputs.",
    )

    build_parser = sub.add_parser(
        "build",
        help="Build the validated 2015-2025 historical baseline through land and SE.",
    )
    build_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )

    scenario_parser = sub.add_parser(
        "scenario",
        help="Run a cattle-only scenario from an existing validated baseline.",
    )
    _add_cattle_scenario_arguments(scenario_parser)
    scenario_parser.add_argument(
        "--baseline-master",
        default=None,
        help=(
            "Existing historical baseline CSV. Defaults to the configured "
            "processed baseline output."
        ),
    )

    run_all_parser = sub.add_parser(
        "run-all",
        help="Build the historical baseline and immediately run a cattle scenario.",
    )
    _add_cattle_scenario_arguments(run_all_parser)

    return parser


def _scenario_name(args: argparse.Namespace) -> str:
    if args.name:
        return str(args.name)
    dairy = int(round(100 * float(args.dairy_reduction)))
    suckler = int(round(100 * float(args.suckler_reduction)))
    return f"D{dairy}_S{suckler}_FROM_{int(args.baseline_year)}"


def _output_dir(args: argparse.Namespace, cfg) -> Path:
    if args.output_dir is not None:
        return Path(args.output_dir)
    return cfg.processed_dir / "scenarios" / _scenario_name(args)


def _land_use_definition(args: argparse.Namespace) -> LandUseAllocationDefinition | None:
    shares = {
        "forest": float(args.forest_share),
        "rewetting": float(args.rewetting_share),
        "ad_grass": float(args.ad_grass_share),
        "willow": float(args.willow_share),
        "energy_grass": float(args.energy_grass_share),
        "nature": float(args.nature_share),
    }
    if sum(shares.values()) <= 1e-12:
        return None
    if args.pasture_dm_controls is None:
        raise ValueError(
            "alternative-land shares require --pasture-dm-controls because land "
            "cannot be allocated before potential spared grassland is calculated"
        )
    return LandUseAllocationDefinition(**shares)


def _pasture_profiles(args: argparse.Namespace):
    if args.pasture_dm_controls is None:
        return None
    return load_pasture_dm_profiles(Path(args.pasture_dm_controls))


def _definition(args: argparse.Namespace):
    return make_cattle_scenario(
        name=_scenario_name(args),
        baseline_year=int(args.baseline_year),
        target_year=int(args.target_year),
        dairy_reduction=float(args.dairy_reduction),
        suckler_reduction=float(args.suckler_reduction),
    )


def _configured_baseline_path(cfg) -> Path:
    value = cfg.raw.get("outputs", {}).get(
        "enriched_master", "data/processed/goblin_spatial_master_2015_2025.csv"
    )
    path = Path(value)
    return path if path.is_absolute() else cfg.project_root / path


def main() -> None:
    args = _parser().parse_args()

    if args.command == "fetch-data":
        resolved = fetch_data(
            Path(args.manifest),
            verify_only=args.verify_only,
            tracked_only=args.tracked_only,
        )
        print(f"GOBLIN-Spatial data check complete: {len(resolved)} inputs")
        return

    if args.command == "build":
        result = build(Path(args.config))
        print(f"GOBLIN-Spatial historical baseline complete: {len(result):,} rows")
        return

    if args.command in {"scenario", "run-all"}:
        cfg = load_config(Path(args.config))
        definition = _definition(args)
        profiles = _pasture_profiles(args)
        land_use = _land_use_definition(args)
        output_dir = _output_dir(args, cfg)

        if args.command == "run-all":
            run = build_and_run_cattle_study(
                cfg,
                definition,
                include_standard_output=not args.no_standard_output,
                pasture_dm_t_per_head_by_year=profiles,
                supply_multiplier_by_year=float(args.supply_multiplier),
                land_use=land_use,
                output_dir=output_dir,
            )
        else:
            master_path = (
                Path(args.baseline_master)
                if args.baseline_master is not None
                else _configured_baseline_path(cfg)
            )
            if not master_path.exists():
                raise FileNotFoundError(
                    f"historical baseline not found: {master_path}. Run 'goblin-spatial build' first."
                )
            panel = pd.read_csv(master_path)
            run = run_cattle_study(
                panel,
                definition,
                config=cfg,
                expected_eds=cfg.expected_eds,
                include_standard_output=not args.no_standard_output,
                pasture_dm_t_per_head_by_year=profiles,
                supply_multiplier_by_year=float(args.supply_multiplier),
                land_use=land_use,
                output_dir=output_dir,
            )

        print(f"GOBLIN-Spatial cattle scenario complete: {definition.name}")
        print(f"Scenario outputs: {run.output_dir}")
        if profiles is None:
            print(
                "Grassland release not calculated: no authoritative GOBLIN pasture-DM control table supplied."
            )
        return


if __name__ == "__main__":
    main()
