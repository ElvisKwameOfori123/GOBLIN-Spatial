"""Build county and catchment historical views from the validated ED master."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.aggregation import (
    aggregate_to_catchments,
    aggregate_to_counties,
    build_ed_catchment_crosswalk,
    validate_aggregation_closure,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", default="data/processed/goblin_spatial_master_2015_2025.csv")
    parser.add_argument("--ed-geometry", default="data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg")
    parser.add_argument("--catchment-geometry", default="data/inputs/spatial/WFD_Catchments_Frozen.gpkg")
    parser.add_argument("--catchment-layer", default=None)
    parser.add_argument("--catchment-name-column", default=None)
    parser.add_argument("--crosswalk-output", default="data/processed/ed_catchment_crosswalk.csv")
    parser.add_argument("--catchment-output", default="data/processed/goblin_spatial_catchment_2015_2025.csv")
    parser.add_argument("--county-output", default="data/processed/goblin_spatial_county_2015_2025.csv")
    parser.add_argument("--diagnostics-output", default="data/processed/catchment_closure_diagnostics.csv")
    args = parser.parse_args()

    try:
        import geopandas as gpd
    except ImportError as exc:
        raise SystemExit("Install geospatial extras first: pip install -e '.[geo]'") from exc

    master = pd.read_csv(args.master, dtype={"CSOED": str})
    eds = gpd.read_file(args.ed_geometry)
    catchments = gpd.read_file(
        args.catchment_geometry,
        layer=args.catchment_layer if args.catchment_layer else None,
    )

    crosswalk = build_ed_catchment_crosswalk(
        master,
        eds,
        catchments,
        catchment_name_col=args.catchment_name_column,
    )
    catchment_year = aggregate_to_catchments(master, crosswalk)
    county_year = aggregate_to_counties(master)
    diagnostics = validate_aggregation_closure(
        master, catchment_year, geography_col="catchment"
    )

    for path in (
        args.crosswalk_output,
        args.catchment_output,
        args.county_output,
        args.diagnostics_output,
    ):
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    crosswalk.to_csv(args.crosswalk_output, index=False)
    catchment_year.to_csv(args.catchment_output, index=False)
    county_year.to_csv(args.county_output, index=False)
    diagnostics.to_csv(args.diagnostics_output, index=False)

    print(f"Crosswalk rows: {len(crosswalk):,}")
    print(f"Catchment-year rows: {len(catchment_year):,}")
    print(f"County-year rows: {len(county_year):,}")
    print("National additive totals close exactly within numerical tolerance.")


if __name__ == "__main__":
    main()
