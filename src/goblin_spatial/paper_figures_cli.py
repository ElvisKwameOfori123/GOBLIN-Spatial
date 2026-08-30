"""Command-line entry point for publication-facing GOBLIN-Spatial figures."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.paper_figures import generate_paper_figures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-paper-figures",
        description=(
            "Generate the eight agreed high-impact manuscript figures from the "
            "final GOBLIN-Spatial SQLite results database."
        ),
    )
    parser.add_argument("database", help="Path to GOBLIN_Spatial_Final_Results.sqlite")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Destination directory. Defaults to a paper_figures folder beside the database.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    database = Path(args.database).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir is not None
        else database.parent / "paper_figures"
    )
    outputs = generate_paper_figures(database, output_dir)
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
