"""Command-line entry point for cross-run GOBLIN-Spatial reporting."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.final_study_reporting import export_study_results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-study-report",
        description=(
            "Combine completed principal SC1-SC3 runs into the final integrated "
            "scientific workbook, SQLite database, map-ready tables and high-resolution graph package."
        ),
    )
    parser.add_argument(
        "study_root",
        help=(
            "Directory containing completed principal run folders. Run folders "
            "are discovered recursively through sc1_control_summary.csv."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Destination directory. By default a final_results directory is "
            "created beneath study_root."
        ),
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help=(
            "Allow a development subset of the study matrix. The default requires "
            "the exact 3 pathways x 4 allocation rules principal matrix."
        ),
    )
    parser.add_argument(
        "--no-figures",
        action="store_true",
        help="Create workbook/database outputs without PNG/SVG figures.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    study_root = Path(args.study_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir is not None else None
    outputs = export_study_results(
        study_root,
        output_dir=output_dir,
        require_complete_matrix=not args.allow_partial,
        generate_figures=not args.no_figures,
    )
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
