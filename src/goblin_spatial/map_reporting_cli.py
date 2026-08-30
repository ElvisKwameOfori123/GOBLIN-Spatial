"""Command-line entry point for downstream GOBLIN-Spatial maps."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.map_reporting import export_maps


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-maps",
        description=(
            "Join frozen GOBLIN-Spatial ED results to Electoral Division geometry, "
            "write a reusable GeoPackage and generate the selective main map suite."
        ),
    )
    parser.add_argument(
        "results",
        help=(
            "Final results directory containing GOBLIN_Spatial_Map_Data.csv, "
            "or the map-data CSV itself."
        ),
    )
    parser.add_argument(
        "--geometry",
        default=None,
        help=(
            "Optional ED Shapefile or GeoPackage. If omitted, configured frozen "
            "geometry is tried first, then the configured SAPS ED Shapefile."
        ),
    )
    parser.add_argument(
        "--geometry-key",
        default=None,
        help=(
            "Attribute containing ED identifiers. Usually unnecessary because the "
            "renderer detects the field by overlap with result CSOED values."
        ),
    )
    parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Study configuration used to resolve optional geometry paths.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Destination directory. Defaults to a maps folder beside final results.",
    )
    parser.add_argument(
        "--no-static-maps",
        action="store_true",
        help="Create the frozen/joined GeoPackages but skip PNG/SVG maps.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
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


if __name__ == "__main__":
    main()
