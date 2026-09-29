"""Command-line interface for the validated GOBLIN-Spatial scientific engine."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from goblin_spatial.config import load_config
from goblin_spatial.data_fetch import fetch_data
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
        description="Run the validated GOBLIN-Spatial scientific pipeline through a chosen stage.",
    )
    sub = parser.add_subparsers(dest="command")

    fetch_parser = sub.add_parser("fetch-data", help="Verify repository-contained model inputs.")
    fetch_parser.add_argument("--manifest", default="data_manifest.yaml")
    fetch_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Compatibility flag; verification is always local.",
    )

    build_parser = sub.add_parser(
        "build",
        help="Build the validated 2015-2025 historical baseline.",
    )
    build_parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")

    study_parser = sub.add_parser(
        "study",
        help="Build the baseline and continue through the requested scenario stage.",
    )
    study_parser.add_argument(
        "--through",
        choices=THROUGH_STAGES,
        default="baseline",
        help="Stage to run to. Default: baseline (SC1-SC3 are deferred; pass them explicitly).",
    )
    study_parser.add_argument(
        "--scenario",
        default=None,
        help="ACTIVE SCENARIO_ID; required beyond baseline.",
    )
    study_parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    study_parser.add_argument(
        "--baseline-year",
        type=int,
        choices=(2020, 2025),
        default=2020,
    )
    study_parser.add_argument(
        "--allocation-rule",
        choices=PRINCIPAL_ALLOCATION_POLICIES,
        default="PRORATA",
    )
    study_parser.add_argument(
        "--protection-strength",
        type=float,
        default=PRINCIPAL_PROTECTION_STRENGTH,
    )
    study_parser.add_argument(
        "--colm-eligibility-rules",
        default=None,
        help="Versioned evidence-backed Stage-A soil eligibility control; required for SC3.",
    )
    study_parser.add_argument(
        "--rewetting-capacity",
        default=None,
        help="Validated rewetting-capacity control when required by the pathway.",
    )
    study_parser.add_argument("--output-dir", default=None)
    return parser


def _choose(prompt: str, options: list[tuple[str, str]]) -> str:
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
    colm_eligibility_rules: str | None = None,
    rewetting_capacity: str | None = None,
) -> None:
    stage = str(through).lower()
    if stage not in THROUGH_STAGES:
        raise ValueError(f"through must be one of {THROUGH_STAGES}")
    if stage != "baseline" and not scenario:
        raise ValueError("--scenario is required when --through is SC1, SC2 or SC3")
    if stage in {"sc2", "sc3"} and int(baseline_year) != 2020:
        raise ValueError("SC2/SC3 currently require the frozen 2020 soil + LPIS spatial baseline")
    if stage == "sc3" and not colm_eligibility_rules:
        raise ValueError(
            "--colm-eligibility-rules is required for SC3; "
            "no default suitability assumptions are supplied"
        )

    cfg = load_config(Path(config_path))
    print("Building validated historical baseline...")
    run_baseline(cfg)
    if stage == "baseline":
        print("Baseline completed.")
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
    if colm_eligibility_rules:
        command.extend(["--colm-eligibility-rules", str(colm_eligibility_rules)])
    if rewetting_capacity:
        command.extend(["--rewetting-capacity", str(rewetting_capacity)])
    subprocess.run(command, check=True)
    print(f"Study completed through {stage.upper()}.")


SCENARIO_MENU_ENV = "GOBLIN_SPATIAL_SCENARIOS"


def _interactive_study() -> None:
    config_path = "configs/ireland_2015_2025.yaml"
    # SC1-SC3 are dormant while the historical baseline is finalised. The
    # guided runner offers the baseline only; scenario stages remain available
    # explicitly (``study --through sc1|sc2|sc3`` or ``goblin-spatial-principal``)
    # and in this menu when GOBLIN_SPATIAL_SCENARIOS=1.
    if os.environ.get(SCENARIO_MENU_ENV) == "1":
        stage = _choose(
            "\nWhat would you like to run?",
            [("1", "baseline"), ("2", "sc1"), ("3", "sc2"), ("4", "sc3")],
        )
    else:
        print(
            "\nRunning the 2015-2025 historical baseline. "
            "Scenario stages (SC1-SC3) are dormant; run them explicitly with "
            "'goblin-spatial study --through sc1|sc2|sc3' if needed."
        )
        stage = "baseline"
    if stage == "baseline":
        _run_study(
            config_path=config_path,
            through="baseline",
            scenario=None,
            baseline_year=2020,
            allocation_rule="PRORATA",
            protection_strength=PRINCIPAL_PROTECTION_STRENGTH,
        )
        return

    scenario = _scenario_id_from_label(
        _choose("\nChoose a national GOBLIN pathway:", _scenario_options(config_path))
    )
    allocation_rule = _choose(
        "\nChoose the spatial incidence rule:",
        [(str(index + 1), policy) for index, policy in enumerate(PRINCIPAL_ALLOCATION_POLICIES)],
    )
    baseline_year = (
        int(_choose("\nChoose baseline year:", [("1", "2020"), ("2", "2025")]))
        if stage == "sc1"
        else 2020
    )

    eligibility = None
    rewetting = None
    if stage == "sc3":
        eligibility = input("Path to validated soil eligibility-rule CSV: ").strip()
        if not eligibility:
            raise ValueError("SC3 requires a validated soil eligibility-rule CSV")
        rewetting = input(
            "Path to validated rewetting-capacity CSV, if required: "
        ).strip() or None

    _run_study(
        config_path=config_path,
        through=stage,
        scenario=scenario,
        baseline_year=baseline_year,
        allocation_rule=allocation_rule,
        protection_strength=PRINCIPAL_PROTECTION_STRENGTH,
        colm_eligibility_rules=eligibility,
        rewetting_capacity=rewetting,
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
        run_baseline(load_config(Path(args.config)))
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
            colm_eligibility_rules=args.colm_eligibility_rules,
            rewetting_capacity=args.rewetting_capacity,
        )
        return

    raise ValueError(f"unknown command: {args.command}")
