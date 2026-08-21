"""Build the compact ED agricultural-soil control used by GOBLIN-Spatial."""

from __future__ import annotations

import argparse
from pathlib import Path

from goblin_spatial.soil import build_ed_agricultural_soil_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate Cathal/NFS holding-linked soil records to ED-level "
            "GOBLIN soil-group and forestry-context shares."
        )
    )
    parser.add_argument(
        "source",
        type=Path,
        help=(
            "Path to the source cathal CSV; holding records are not written "
            "to the model control output."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/controls/soil/ED_GOBLIN_soil_profile.csv.xz"
        ),
        help="Compact ED control output (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = build_ed_agricultural_soil_profile(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile.to_csv(
        args.output,
        index=False,
        compression="infer",
        float_format="%.10f",
    )

    shares = [f"GOBLIN_SOIL_G{i}_SHARE" for i in (1, 2, 3)]
    print(f"ED soil profile: {args.output}")
    print(f"EDs represented: {profile['CSOED'].nunique():,}")
    print(
        "Source holdings represented: "
        f"{int(profile['SOIL_SOURCE_HOLDINGS'].sum()):,}"
    )
    print(
        "Source UAA represented: "
        f"{profile['SOIL_SOURCE_UAA_HA'].sum():,.1f} ha"
    )
    print(
        "Maximum G1/G2/G3 closure error: "
        f"{(profile[shares].sum(axis=1) - 1.0).abs().max():.3e}"
    )


if __name__ == "__main__":
    main()
