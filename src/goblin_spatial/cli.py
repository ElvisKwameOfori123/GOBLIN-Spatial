"""Command-line interface for the validated GOBLIN-Spatial workflow.

The root command exposes the scientific pipeline and the downstream publication
layers without mixing their mathematics. A user can stop after baseline, SC1,
SC2 or SC3, or work only with already-completed results to regenerate reporting,
figures or maps.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from goblin_spatial.config import load_config
from goblin_spatial.data_fetch import fetch_data
from goblin_spatial.final_study_reporting import export_study_results
from goblin_spatial.map_reporting import export_maps
from goblin_spatial.paper_figures import generate_paper_figures
from goblin_spatial.pipeline import run_baseline
from goblin_spatial.scenario.control_table import read_scenario_control_table
from goblin_spatial.scenario.principal_allocation import (
    PRINCIPAL_ALLOCATION_POLICIES,
    PRINCIPAL_PROTECTION_STRENGTH,
)


THROUGH_STAGES = ("baseline", "sc1", "sc2", "sc3")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial",
        description=(
            "Run the validated GOBLIN-Spatial science through a chosen stage, "
            "or regenerate downstream results, publication figures and maps. "
            "Run with no arguments for the guided scientific-stage menu."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    fetch_parser = sub.add_parser(
        "fetch-data",
        help="Verify repository-contained model inputs. No downloads are performed.",
    )
    fetch_parser.add_argument("--manifest", default="data_manifest.yaml")
    fetch_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Compatibility flag; verification is always local/repository-only.",
    )

    build_parser = sub.add_parser(
        "build",
        help="Build the validated 2015-2025 historical baseline through Stage 09.",
    )
    build_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )

    study_parser = sub.add_parser(
        "study",
        help="Build the baseline and continue only as far as the requested scenario stage.",
    )
    study_parser.add_argument(
        "--through",
        choices=THROUGH_STAGES,
        default="sc3",
        help="Stop after baseline, SC1, SC2 or SC3. Default: sc3.",
    )
    study_parser.add_argument(
        "--scenario",
        default=None,
        help="ACTIVE SCENARIO_ID. Required unless --through baseline.",
    )
    study_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )
    study_parser.add_argument(
        "--baseline-year",
        type=int,
        choices=(2020, 2025),
        default=2020,
        help="Scenario baseline year. SC2/SC3 currently require 2020.",
    )
    study_parser.add_argument(
        "--allocation-rule",
        choices=PRINCIPAL_ALLOCATION_POLICIES,
        default="PRORATA",
        help="Validated principal SC1 incidence policy.",
    )
    study_parser.add_argument(
        "--protection-strength",
        type=float,
        default=PRINCIPAL_PROTECTION_STRENGTH,
        help=(
            "Protection strength lambda for protected SC1 incidence policies. "
            f"Default: {PRINCIPAL_PROTECTION_STRENGTH:.2f}."
        ),
    )
    study_parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional principal scenario output directory.",
    )

    report_parser = sub.add_parser(
        "report",
        help="Build the cross-run workbook/SQLite result package from completed principal runs.",
    )
    report_parser.add_argument("study_root", help="Directory containing completed principal run folders.")
    report_parser.add_argument("--output-dir", default=None)
    report_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow a development subset instead of the exact 3 x 4 principal matrix.",
    )
    report_parser.add_argument(
        "--no-figures",
        action="store_true",
        help="Build numerical reporting outputs without the diagnostic graph suite.",
    )

    figure_parser = sub.add_parser(
        "figures",
        help="Generate the eight publication-facing figures from a frozen final SQLite database.",
    )
    figure_parser.add_argument("database", help="Path to GOBLIN_Spatial_Final_Results.sqlite")
    figure_parser.add_argument("--output-dir", default=None)

    map_parser = sub.add_parser(
        "maps",
        help="Join map-ready ED results to geometry and generate the downstream map package.",
    )
    map_parser.add_argument(
        "results",
        help="Final results directory containing GOBLIN_Spatial_Map_Data.csv, or the CSV itself.",
    )
    map_parser.add_argument("--geometry", default=None, help="Optional ED Shapefile or GeoPackage.")
    map_parser.add_argument("--geometry-key", default=None, help="Optional ED identifier attribute in the geometry source.")
    map_parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    map_parser.add_argument("--output-dir", default=None)
    map_parser.add_argument(
        "--no-static-maps",
        action="store_true",
        help="Create GeoPackages only and skip PNG/SVG maps.",
    )
    return parser


def _choose(prompt: str, options: list[tuple[str, str]]) -> str:
    """Prompt until the user chooses one numbered option."""
    while True:
        print(prompt)
        for number, label in options:
            print(f"  {number}. {label}")
        answer = input("Select: ").strip()
        for number, value in options:
            if answer == number:
                return value
        print("Please choose one of the listed numbers.\n")


def _scenario_options(config_path: str | Path) -> list[tuple[str, str]]:
    cfg = load_config(Path(config_path))
    controls_path = Path(cfg.files["scenario_controls"])
    table = read_scenario_control_table(controls_path)
    active = table.loc[table["ACTIVE"]].reset_index(drop=True)
    if active.empty:
        raise RuntimeError("scenario control table contains no ACTIVE pathways")
    return [
        (str(index + 1), f"{row.SCENARIO_ID} — {row.SCENARIO_NAME}")
        for index, row in active.iterrows()
    ]


def _scenario_id_from_label(label: str) -> str:
    return label.split(" — ", 1)[0].strip()


def _run_study(
    *,
    config_path: str | Path,
    through: str,
    scenario: str | None,
    baseline_year: int,
    allocation_rule: str,
    protection_strength: float,
    output_dir: str | None = None,
) -> None:
    """Build the baseline, then delegate to the validated principal stage runner."""
    stage = str(through).lower()
    if stage not in THROUGH_STAGES:
        raise ValueError(f"through must be one of {THROUGH_STAGES}")
    if stage != "baseline" and not scenario:
        raise ValueError("--scenario is required when --through is SC1, SC2 or SC3")
    if stage in {"sc2", "sc3"} and int(baseline_year) != 2020:
        raise ValueError(
            "SC2/SC3 currently require the frozen 2020 spatial baseline; "
            "2025 is supported for SC1 sensitivity only."
        )

    cfg = load_config(Path(config_path))
    print("Building validated historical baseline through Stage 09...")
    run_baseline(cfg)

    if stage == "baseline":
        print("Baseline completed. Study stopped at the requested baseline stage.")
        return

    command = [
        sys.executable,
        "-m",
        "goblin_spatial.principal_cli",
        str(scenario),
        "--config",
        str(config_path),
        "--baseline-year",
        str(int(baseline_year)),
        "--allocation-rule",
        str(allocation_rule),
        "--protection-strength",
        str(float(protection_strength)),
        "--stage",
        stage.upper(),
    ]
    if output_dir:
        command.extend(["--output-dir", str(output_dir)])

    print(f"Continuing with {scenario} through {stage.upper()} using {allocation_rule}...")
    subprocess.run(command, check=True)
    print(f"Study completed and stopped after {stage.upper()} as requested.")


def _interactive_study() -> None:
    """Friendly guided workflow for the scientific model stages."""
    config_path = "configs/ireland_2015_2025.yaml"
    through = _choose(
        "\nWhat would you like to run?",
        [
            ("1", "Baseline only"),
            ("2", "Baseline + SC1 livestock transition"),
            ("3", "Baseline + SC1 + SC2 opportunity analysis"),
            ("4", "Full scientific chain: Baseline + SC1 + SC2 + SC3"),
        ],
    )
    through = {
        "Baseline only": "baseline",
        "Baseline + SC1 livestock transition": "sc1",
        "Baseline + SC1 + SC2 opportunity analysis": "sc2",
        "Full scientific chain: Baseline + SC1 + SC2 + SC3": "sc3",
    }[through]

    if through == "baseline":
        _run_study(
            config_path=config_path,
            through="baseline",
            scenario=None,
            baseline_year=2020,
            allocation_rule="PRORATA",
            protection_strength=PRINCIPAL_PROTECTION_STRENGTH,
        )
        return

    scenario_label = _choose("\nChoose a national GOBLIN pathway:", _scenario_options(config_path))
    scenario = _scenario_id_from_label(scenario_label)
    allocation_rule = _choose(
        "\nChoose the spatial incidence rule:",
        [(str(index + 1), policy) for index, policy in enumerate(PRINCIPAL_ALLOCATION_POLICIES)],
    )

    if through == "sc1":
        baseline_year = int(_choose("\nChoose the scenario baseline year:", [("1", "2020"), ("2", "2025")]))
    else:
        baseline_year = 2020
        print("\nSC2/SC3 use the validated frozen 2020 spatial context.")

    _run_study(
        config_path=config_path,
        through=through,
        scenario=scenario,
        baseline_year=baseline_year,
        allocation_rule=allocation_rule,
        protection_strength=PRINCIPAL_PROTECTION_STRENGTH,
    )


def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    if args.command is None:
        if sys.stdin.isatty():
            _interactive_study()
        else:
            parser.print_help()
        return

    if args.command == "fetch-data":
        fetch_data(Path(args.manifest), verify_only=True, tracked_only=True)
        return

    if args.command == "build":
        cfg = load_config(Path(args.config))
        run_baseline(cfg)
        return

    if args.command == "study":
        _run_study(
            config_path=args.config,
            through=args.through,
            scenario=args.scenario,
            baseline_year=args.baseline_year,
            allocation_rule=args.allocation_rule,
            protection_strength=args.protection_strength,
            output_dir=args.output_dir,
        )
        return

    if args.command == "report":
        root = Path(args.study_root).resolve()
        out = Path(args.output_dir).resolve() if args.output_dir is not None else None
        outputs = export_study_results(
            root,
            output_dir=out,
            require_complete_matrix=not args.allow_partial,
            generate_figures=not args.no_figures,
        )
        for label, path in outputs.items():
            print(f"{label}: {path}")
        return

    if args.command == "figures":
        database = Path(args.database).resolve()
        out = Path(args.output_dir).resolve() if args.output_dir is not None else database.parent / "paper_figures"
        outputs = generate_paper_figures(database, out)
        for label, path in outputs.items():
            print(f"{label}: {path}")
        return

    if args.command == "maps":
        outputs = export_maps(
            Path(args.results),
            geometry=Path(args.geometry) if args.geometry is not None else None,
            geometry_key=args.geometry_key,
            config_path=Path(args.config),
            output_dir=Path(args.output_dir) if args.output_dir is not None else None,
            generate_static_maps=not args.no_static_maps,
        )
        for label, path in outputs.items():
            print(f"{label}: {path}")
        return

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
