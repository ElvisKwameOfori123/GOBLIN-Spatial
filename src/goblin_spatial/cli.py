"""Command-line interface for GOBLIN-Spatial."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.data_fetch import fetch_data
from goblin_spatial.pipeline import build


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial",
        description="Generate fine-scale GOBLIN-Spatial agricultural datasets.",
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
        help="Run cattle, sheep, land and SE modules and build the full dataset.",
    )
    build_parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Path to the YAML build configuration.",
    )

    return parser


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
        print(f"GOBLIN-Spatial build complete: {len(result):,} rows")
        return


if __name__ == "__main__":
    main()
