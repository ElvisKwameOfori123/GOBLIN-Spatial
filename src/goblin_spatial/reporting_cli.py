"""Command-line entry point for scientific scenario reporting."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.reporting import export_scientific_results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-report",
        description=(
            "Build interpretation-safe scientific summaries and an Excel workbook "
            "from one completed GOBLIN-Spatial principal scenario run."
        ),
    )
    parser.add_argument(
        "run_dir",
        help=(
            "Principal scenario output directory containing sc1_control_summary.csv "
            "and, for full land accounting, sc3_ed_results.csv."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional workbook path. By default the workbook is written as "
            "GOBLIN_Spatial_Scientific_Results.xlsx inside the run directory."
        ),
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    outputs = export_scientific_results(
        Path(args.run_dir),
        output_path=Path(args.output) if args.output is not None else None,
    )
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
