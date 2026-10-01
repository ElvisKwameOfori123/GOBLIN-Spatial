"""Command-line interface for the validated GOBLIN-Spatial historical baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.config import load_config
from goblin_spatial.data_fetch import fetch_data
from goblin_spatial.pipeline import run_baseline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial",
        description="Verify inputs or build the validated 2015-2025 GOBLIN-Spatial historical baseline.",
    )
    sub = parser.add_subparsers(dest="command")

    fetch_parser = sub.add_parser(
        "fetch-data",
        help="Verify repository-contained historical-baseline inputs.",
    )
    fetch_parser.add_argument("--manifest", default="data_manifest.yaml")
    fetch_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Compatibility flag; verification is always local and downloads nothing.",
    )

    build_parser = sub.add_parser(
        "build",
        help="Build the validated 2015-2025 historical baseline.",
    )
    build_parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "fetch-data":
        fetch_data(Path(args.manifest), verify_only=True, tracked_only=True)
        return
    if args.command == "build":
        run_baseline(load_config(Path(args.config)))
        return

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
