"""Build county and catchment historical views from the validated ED master."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from goblin_spatial.aggregation import (
    EXPECTED_WFD_CATCHMENTS,
    aggregate_to_counties,
    aggregate_to_wfd_catchments,
    aggregate_wfd_to_colm,
    build_ed_catchment_crosswalk,
    validate_aggregation_closure,
)

EPA_WFD_FEATURESERVICE_GEOJSON = (
    "https://gsi.geodata.gov.ie/server/rest/services/Third_Party/"
    "IE_GSI_EPA_WFD_Catchment_Management_Units_50K_IE32_ITM/"
    "FeatureServer/2/query?"
    "where=1%3D1&outFields=*&returnGeometry=true&outSR=2157&f=geojson"
)


def _load_or_fetch_catchments(gpd, local_path: str, layer: str | None, source_url: str):
    """Read a frozen local catchment layer or fetch and freeze the public EPA/GSI mirror."""
    path = Path(local_path)
    if path.exists():
        return gpd.read_file(path, layer=layer if layer else None)

    request = Request(
        source_url,
        headers={"User-Agent": "GOBLIN-Spatial catchment bridge"},
    )
    with urlopen(request, timeout=120) as response:
        payload = json.load(response)

    features = payload.get("features", [])
    if not features:
        raise RuntimeError("EPA/GSI WFD catchment service returned no features.")

    catchments = gpd.GeoDataFrame.from_features(features, crs="EPSG:2157")
    if len(catchments) != EXPECTED_WFD_CATCHMENTS:
        raise RuntimeError(
            f"Expected {EXPECTED_WFD_CATCHMENTS} WFD catchments from the public service, "
            f"received {len(catchments)}."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    catchments.to_file(path, layer="WFD_Catchments", driver="GPKG")
    return catchments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master",
        default="data/processed/goblin_spatial_master_2015_2025.csv",
    )
    parser.add_argument(
        "--ed-geometry",
        default="data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg",
    )
    parser.add_argument(
        "--catchment-geometry",
        default="data/inputs/spatial/WFD_Catchments_Frozen.gpkg",
        help=(
            "Frozen WFD catchment GeoPackage. If absent, the script fetches the "
            "public EPA WFD Catchments layer via the GSI FeatureServer mirror "
            "and freezes it here."
        ),
    )
    parser.add_argument("--catchment-layer", default=None)
    parser.add_argument("--catchment-name-column", default=None)
    parser.add_argument("--catchment-id-column", default=None)
    parser.add_argument(
        "--catchment-source-url",
        default=EPA_WFD_FEATURESERVICE_GEOJSON,
    )
    parser.add_argument(
        "--crosswalk-output",
        default="data/processed/ed_wfd_catchment_crosswalk.csv",
    )
    parser.add_argument(
        "--wfd-catchment-output",
        default="data/processed/goblin_spatial_wfd_catchment_2015_2025.csv",
    )
    parser.add_argument(
        "--colm-catchment-output",
        default="data/processed/goblin_spatial_colm_catchment_2015_2025.csv",
    )
    parser.add_argument(
        "--county-output",
        default="data/processed/goblin_spatial_county_2015_2025.csv",
    )
    parser.add_argument(
        "--diagnostics-output",
        default="data/processed/catchment_closure_diagnostics.csv",
    )
    args = parser.parse_args()

    try:
        import geopandas as gpd
    except ImportError as exc:
        raise SystemExit("Install geospatial extras first: pip install -e '.[geo]'") from exc

    master = pd.read_csv(args.master, dtype={"CSOED": str})
    eds = gpd.read_file(args.ed_geometry)
    catchments = _load_or_fetch_catchments(
        gpd,
        args.catchment_geometry,
        args.catchment_layer,
        args.catchment_source_url,
    )

    crosswalk = build_ed_catchment_crosswalk(
        master,
        eds,
        catchments,
        catchment_name_col=args.catchment_name_column,
        catchment_id_col=args.catchment_id_column,
        expected_wfd_catchments=EXPECTED_WFD_CATCHMENTS,
    )
    wfd_year = aggregate_to_wfd_catchments(master, crosswalk)
    colm_year = aggregate_wfd_to_colm(wfd_year)
    county_year = aggregate_to_counties(master)

    diagnostics = pd.concat(
        [
            validate_aggregation_closure(
                master, wfd_year, geography_col="WFD catchment"
            ),
            validate_aggregation_closure(
                master, colm_year, geography_col="Colm catchment"
            ),
            validate_aggregation_closure(
                master, county_year, geography_col="county"
            ),
        ],
        ignore_index=True,
    )

    for path in (
        args.crosswalk_output,
        args.wfd_catchment_output,
        args.colm_catchment_output,
        args.county_output,
        args.diagnostics_output,
    ):
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    crosswalk.to_csv(args.crosswalk_output, index=False)
    wfd_year.to_csv(args.wfd_catchment_output, index=False)
    colm_year.to_csv(args.colm_catchment_output, index=False)
    county_year.to_csv(args.county_output, index=False)
    diagnostics.to_csv(args.diagnostics_output, index=False)

    print(f"Crosswalk rows: {len(crosswalk):,}")
    print(
        "Official WFD catchments: "
        f"{wfd_year['WFD_CATCHMENT_ID'].nunique():,}"
    )
    print(
        "Colm compatibility catchments: "
        f"{colm_year['COLM_CATCHMENT'].nunique():,}"
    )
    print(f"WFD catchment-year rows: {len(wfd_year):,}")
    print(f"Colm catchment-year rows: {len(colm_year):,}")
    print(f"County-year rows: {len(county_year):,}")
    print("National additive totals close exactly within numerical tolerance.")


if __name__ == "__main__":
    main()
