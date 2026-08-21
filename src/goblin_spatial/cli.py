"""Command-line interface for historical GOBLIN-Spatial data management.

The root ``goblin-spatial`` command is deliberately limited to the validated
historical baseline and explicit data-management operations. Principal scenario
runs use the separate ``goblin-spatial-principal`` entry point so old scenario
experiments cannot be mistaken for the production SC1-SC3 workflow.

Normal data management is repository-only. External soil, LPIS and geography
sources are first-principles reconstruction inputs and are considered only when
the user explicitly opts in.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.config import load_config
from goblin_spatial.data_fetch import fetch_data
from goblin_spatial.pipeline import run_baseline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial",
        description="Build and manage the validated GOBLIN-Spatial historical baseline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_parser = sub.add_parser(
        "fetch-data",
        help="Verify repository-contained model inputs; external rebuild sources are opt-in.",
    )
    fetch_parser.add_argument("--manifest", default="data_manifest.yaml")
    fetch_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not download anything; verify files that are already present.",
    )
    fetch_parser.add_argument(
        "--include-reconstruction-sources",
        action="store_true",
        help=(
            "Explicitly include optional external first-principles reconstruction "
            "sources. Without this flag, fetch-data is repository-only and does "
            "not contact Zenodo or any other external source."
        ),
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
    return parser


def main() -> None:
    args = _parser().parse_args()

    if args.command == "fetch-data":
        include_reconstruction = bool(args.include_reconstruction_sources)
        fetch_data(
            Path(args.manifest),
            verify_only=bool(args.verify_only),
            tracked_only=not include_reconstruction,
        )
        return

    if args.command == "build":
        cfg = load_config(Path(args.config))
        run_baseline(cfg)
        return

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
