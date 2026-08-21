"""Command-line interface for the validated GOBLIN-Spatial baseline.

The root command manages repository-contained inputs and the historical build.
Principal scenario runs use ``goblin-spatial-principal``. No command downloads
or resolves model data from an external service.
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
        description="Build and verify the validated GOBLIN-Spatial model.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

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
    return parser


def main() -> None:
    args = _parser().parse_args()

    if args.command == "fetch-data":
        fetch_data(Path(args.manifest), verify_only=True, tracked_only=True)
        return

    if args.command == "build":
        cfg = load_config(Path(args.config))
        run_baseline(cfg)
        return

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
