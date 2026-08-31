"""CLI for the BE-SG / All-Gas NZ publication visual package."""
from __future__ import annotations

import argparse

from goblin_spatial.publication_visuals import generate_publication_visuals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-publication-visuals",
        description=(
            "Generate SC1-led publication graphs and maps for the Bioeconomy / "
            "Split Gas and All-Gas Net Zero pathways from frozen final results."
        ),
    )
    parser.add_argument(
        "final_results",
        help=(
            "Final-results directory or GOBLIN_Spatial_Final_Results.sqlite. "
            "The directory form is recommended because maps also require "
            "GOBLIN_Spatial_Map_Data.csv."
        ),
    )
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to <final_results>/publication_visuals.")
    parser.add_argument("--geometry", default=None, help="Optional ED Shapefile or GeoPackage. If omitted, resolve from project config.")
    parser.add_argument("--geometry-key", default=None, help="Optional explicit ED identifier field in the geometry source.")
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml", help="Project config used to resolve frozen ED geometry.")
    parser.add_argument("--graphs-only", action="store_true", help="Generate graphs only and skip the GIS mapping stage.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    outputs = generate_publication_visuals(
        args.final_results,
        geometry=args.geometry,
        geometry_key=args.geometry_key,
        config_path=args.config,
        output_dir=args.output_dir,
        graphs_only=args.graphs_only,
    )
    for key, value in outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
