"""Command-line entry point for downstream report-data materialisation."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.reporting.build import build_report_data


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-report-data",
        description=(
            "Build canonical reporting tables from completed GOBLIN-Spatial "
            "principal runs without rerunning model science."
        ),
    )
    parser.add_argument(
        "--principal-root",
        default="data/processed/principal",
        help="Directory containing completed principal run folders.",
    )
    parser.add_argument(
        "--output-root",
        default="reporting/report_data",
        help="Generated downstream report-data directory.",
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--expected-eds", type=int, default=2857)
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Write CSV only. Default writes canonical Parquet plus CSV companions.",
    )
    parser.add_argument(
        "--model-commit",
        default=None,
        help="Optional explicit scientific-engine commit for provenance.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = build_report_data(
        principal_root=Path(args.principal_root),
        output_root=Path(args.output_root),
        project_root=Path(args.project_root),
        expected_eds=int(args.expected_eds),
        parquet=not bool(args.csv_only),
        csv=True,
        model_commit=args.model_commit,
    )
    print(f"Report-data root: {result.output_root}")
    print(f"Runs catalogued: {len(result.run_registry)}")
    print(f"Source files hashed: {len(result.source_files)}")
    print(f"Manifest: {result.manifest_path}")
    print("Reporting boundary preserved: no model science was recalculated.")


if __name__ == "__main__":
    main()
