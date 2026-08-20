"""Command-line interface for GOBLIN-Spatial.

Baseline and data-management commands are intentionally import-independent from
the unfinished scenario stack. Scenario, soil-opportunity and land-allocation
modules are imported lazily only when those commands are explicitly requested.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.data_fetch import fetch_data
from goblin_spatial.pipeline import run_baseline


# CLI-only display default. The scientific target allocator validates the same
# priority again when the downstream command is actually invoked.
CLI_DEFAULT_TARGET_PRIORITY = (
    "REWETTING",
    "FOREST",
    "AD_GRASS",
    "WILLOW",
    "ENERGY_GRASS",
    "NATURE",
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
            "Optional CSV of GOBLIN pasture-DM controls. If omitted, the configured "
            "frozen 2020 GOBLIN feed profile is used when available."
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

    # Legacy share controls remain exposed only for backwards compatibility.
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
        help="Build the complete 2015-2025 historical baseline through Stage 09.",
    )
    build_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )

    # The following commands are retained during migration but their modules are
    # deliberately loaded only after the user explicitly selects the command.
    scenario_parser = sub.add_parser(
        "scenario",
        help="Run a cattle scenario from an existing validated baseline.",
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

    opportunity_parser = sub.add_parser(
        "opportunity",
        help=(
            "Screen potentially spared grassland against the ED soil/opportunity "
            "profile without allocating land-use shares."
        ),
    )
    opportunity_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )
    opportunity_parser.add_argument(
        "--scenario-ed-results",
        required=True,
        help="Path to scenario_ed_results.csv from a completed cattle scenario.",
    )
    opportunity_parser.add_argument(
        "--soil-profile",
        default=None,
        help=(
            "Optional compact ED soil profile. Defaults to agricultural_soil_profile "
            "in the configuration."
        ),
    )
    opportunity_parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to the scenario-results directory.",
    )

    allocate_parser = sub.add_parser(
        "allocate-land",
        help=(
            "Allocate spared grassland to explicit cumulative national hectare targets "
            "using ED opportunity scores."
        ),
    )
    allocate_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )
    allocate_parser.add_argument(
        "--scenario-ed-results",
        required=True,
        help="Path to scenario_ed_results.csv from a completed cattle scenario.",
    )
    allocate_parser.add_argument(
        "--targets",
        required=True,
        help=(
            "CSV of cumulative national hectare targets. Required columns: "
            "MILESTONE_YEAR, FOREST_HA, REWETTING_HA, AD_GRASS_HA, WILLOW_HA, "
            "ENERGY_GRASS_HA, NATURE_HA."
        ),
    )
    allocate_parser.add_argument(
        "--soil-profile",
        default=None,
        help=(
            "Optional compact ED soil profile. Defaults to agricultural_soil_profile "
            "in the configuration."
        ),
    )
    allocate_parser.add_argument(
        "--priority",
        default=",".join(CLI_DEFAULT_TARGET_PRIORITY),
        help=(
            "Comma-separated allocation priority containing each land use exactly once. "
            "Default: %(default)s"
        ),
    )
    allocate_parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to the scenario-results directory.",
    )

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


def _land_use_definition(args: argparse.Namespace, pasture_profiles):
    from goblin_spatial.land.opportunity import LandUseAllocationDefinition

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
    if pasture_profiles is None:
        raise ValueError(
            "alternative-land shares require GOBLIN pasture-DM controls because land "
            "cannot be allocated before potential spared grassland is calculated"
        )
    return LandUseAllocationDefinition(**shares)


def _pasture_profiles(args: argparse.Namespace, cfg, definition):
    # Scenario imports are deliberately lazy so baseline commands do not depend
    # on the unfinished scenario package during the v1 migration.
    from goblin_spatial.pressure import load_pasture_dm_control
    from goblin_spatial.scenario import reduction_schedule

    control = (
        Path(args.pasture_dm_controls)
        if args.pasture_dm_controls is not None
        else cfg.files.get("pasture_dm_controls")
    )
    if control is None:
        return None
    if not Path(control).exists():
        raise FileNotFoundError(f"pasture-DM control table not found: {control}")

    schedule = reduction_schedule(definition)
    years = {
        int(definition.baseline_year),
        *schedule["MILESTONE_YEAR"].astype(int).tolist(),
    }
    return load_pasture_dm_control(control, required_years=years)


def _definition(args: argparse.Namespace):
    from goblin_spatial.scenario import make_cattle_scenario

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


def _resolve_soil_profile(args: argparse.Namespace, cfg) -> Path:
    soil_path = (
        Path(args.soil_profile)
        if args.soil_profile is not None
        else cfg.files.get("agricultural_soil_profile")
    )
    if soil_path is None or not Path(soil_path).exists():
        raise FileNotFoundError(
            "downstream land analysis requires the compact ED agricultural-soil profile. "
            "Generate it with scripts/build_ed_agricultural_soil_profile.py or pass "
            "--soil-profile explicitly."
        )
    return Path(soil_path)


def _read_scenario_ed(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"scenario ED results not found: {path}")
    scenario = pd.read_csv(path, low_memory=False)
    required = {
        "CSOED",
        "County",
        "MILESTONE_YEAR",
        "ALL_GRASSLAND",
        "POTENTIAL_SPARED_GRASSLAND_HA",
    }
    missing = sorted(required - set(scenario.columns))
    if missing:
        raise ValueError(f"scenario results missing columns: {missing}")
    if scenario[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("scenario results must contain one row per ED and milestone")
    return scenario


def _run_opportunity_screen(args: argparse.Namespace) -> None:
    from goblin_spatial.land.envelope import (
        add_spared_land_opportunity_envelope,
        summarise_spared_land_opportunity_envelope,
    )
    from goblin_spatial.soil.context_v2 import add_ed_agricultural_soil

    cfg = load_config(Path(args.config))
    scenario_path = Path(args.scenario_ed_results)
    scenario = _read_scenario_ed(scenario_path)
    soil_path = _resolve_soil_profile(args, cfg)

    enriched = (
        scenario
        if "GOBLIN_SOIL_G1_SHARE" in scenario.columns
        else add_ed_agricultural_soil(scenario, soil_path)
    )
    screened = add_spared_land_opportunity_envelope(enriched)
    national = summarise_spared_land_opportunity_envelope(screened)

    output_dir = (
        Path(args.output_dir) if args.output_dir is not None else scenario_path.parent
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    ed_output = output_dir / "scenario_ed_opportunity_envelope.csv"
    national_output = output_dir / "scenario_national_opportunity_envelope.csv"
    screened.to_csv(ed_output, index=False)
    national.to_csv(national_output, index=False)

    print(f"ED opportunity envelope: {ed_output}")
    print(f"National opportunity envelope: {national_output}")


def _run_land_target_allocation(args: argparse.Namespace) -> None:
    from goblin_spatial.land.targets import (
        allocate_spared_land_to_cumulative_targets,
        read_land_use_targets,
        summarise_land_target_allocation,
    )
    from goblin_spatial.soil.context_v2 import add_ed_agricultural_soil

    cfg = load_config(Path(args.config))
    scenario_path = Path(args.scenario_ed_results)
    scenario = _read_scenario_ed(scenario_path)
    soil_path = _resolve_soil_profile(args, cfg)
    targets = read_land_use_targets(Path(args.targets))
    priority = tuple(
        value.strip().upper()
        for value in str(args.priority).split(",")
        if value.strip()
    )

    enriched = (
        scenario
        if "GOBLIN_SOIL_G1_SHARE" in scenario.columns
        else add_ed_agricultural_soil(scenario, soil_path)
    )
    allocated = allocate_spared_land_to_cumulative_targets(
        enriched,
        targets,
        priority=priority,
    )
    national = summarise_land_target_allocation(allocated)

    output_dir = (
        Path(args.output_dir) if args.output_dir is not None else scenario_path.parent
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    ed_output = output_dir / "scenario_ed_land_target_allocation.csv"
    national_output = output_dir / "scenario_national_land_target_allocation.csv"
    targets_output = output_dir / "land_use_targets_applied.csv"
    allocated.to_csv(ed_output, index=False)
    national.to_csv(national_output, index=False)
    targets.to_csv(targets_output, index=False)

    print(f"ED land-target allocation: {ed_output}")
    print(f"National land-target allocation: {national_output}")
    print(f"Applied cumulative targets: {targets_output}")


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
        result = run_baseline(Path(args.config))
        print(
            "GOBLIN-Spatial historical baseline through Stage 09 complete: "
            f"{len(result):,} ED-year rows"
        )
        return

    if args.command == "opportunity":
        _run_opportunity_screen(args)
        return

    if args.command == "allocate-land":
        _run_land_target_allocation(args)
        return

    if args.command in {"scenario", "run-all"}:
        # Do not import scenario execution code unless a scenario command is
        # explicitly requested. This keeps baseline/data commands independent.
        from goblin_spatial.scenario import (
            build_and_run_cattle_study,
            run_cattle_study,
        )

        cfg = load_config(Path(args.config))
        definition = _definition(args)
        profiles = _pasture_profiles(args, cfg, definition)
        land_use = _land_use_definition(args, profiles)
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
                    f"historical baseline not found: {master_path}. "
                    "Run 'goblin-spatial build' first."
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
        return


if __name__ == "__main__":
    main()
