"""Installed command for building the compact 2020/2025 ED LPIS control."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.land.lpis_stream import build_ed_lpis_profile_from_parquet


def main() -> None:
    p = argparse.ArgumentParser(prog="goblin-spatial-lpis")
    p.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    p.add_argument("--year", choices=("2020", "2025", "both"), default="both")
    p.add_argument("--lpis-2020", default=None)
    p.add_argument("--lpis-2025", default=None)
    p.add_argument("--ed-shapefile", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--batch-size", type=int, default=50000)
    args = p.parse_args()

    cfg = load_config(args.config)
    baseline = pd.read_csv(
        cfg.files["cso_ed_2020"], dtype={"CSOED": "string"}, low_memory=False
    ).drop_duplicates("CSOED")
    if len(baseline) != cfg.expected_eds:
        raise AssertionError("baseline ED count does not equal configured expected_eds")

    ed_path = Path(args.ed_shapefile) if args.ed_shapefile else cfg.files["saps_ed_geography"]
    if not ed_path.exists():
        raise FileNotFoundError(ed_path)
    ed = gpd.read_file(ed_path)

    years = (2020, 2025) if args.year == "both" else (int(args.year),)
    profiles = []
    for year in years:
        supplied = args.lpis_2020 if year == 2020 else args.lpis_2025
        path = Path(supplied) if supplied else cfg.files[f"lpis_{year}_parcels"]
        print(f"Streaming LPIS {year}: {path}")
        profile = build_ed_lpis_profile_from_parquet(
            path,
            ed,
            baseline,
            year=year,
            batch_size=args.batch_size,
        )
        if len(profile) != cfg.expected_eds:
            raise AssertionError("LPIS profile does not contain the exact model ED universe")
        profiles.append(profile)
        print(
            f"{year}: EDs={len(profile):,}; "
            f"claimed grass={profile['LPIS_CLAIMED_GRASS_HA'].sum():,.2f} ha"
        )

    result = pd.concat(profiles, ignore_index=True)
    output = Path(args.output) if args.output else cfg.files["lpis_ed_profile"]
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, compression="infer", float_format="%.10f")
    print(f"ED LPIS control: {output}")
    print(f"Rows: {len(result):,}")
    print("ALL_GRASSLAND remains authoritative; LPIS is downstream context only.")


if __name__ == "__main__":
    main()
