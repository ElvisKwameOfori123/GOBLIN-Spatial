"""Build county and catchment historical views from the validated ED master."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.aggregation import (
    EXPECTED_WFD_CATCHMENTS,
    aggregate_to_counties,
    aggregate_to_national,
    aggregate_to_wfd_catchments,
    aggregate_wfd_to_colm,
    build_ed_catchment_crosswalk,
    validate_aggregation_closure,
)
from goblin_spatial.data_fetch import sha256_file


def _load_frozen_catchments(
    gpd,
    local_path: str,
    layer: str | None,
    checksum_path: str | None = None,
):
    """Read the repository-frozen WFD geometry after verifying its SHA-256."""

    path = Path(local_path)
    if not path.is_file():
        raise FileNotFoundError(
            "Frozen WFD catchment geometry is missing. "
            f"Expected repository file: {path}"
        )

    sidecar = (
        Path(checksum_path)
        if checksum_path is not None
        else Path(str(path) + ".sha256")
    )
    if not sidecar.is_file():
        raise FileNotFoundError(
            "Frozen WFD catchment checksum is missing. "
            f"Expected: {sidecar}"
        )

    fields = sidecar.read_text(encoding="utf-8").strip().split()
    if not fields or len(fields[0]) != 64:
        raise ValueError(f"Invalid SHA-256 sidecar: {sidecar}")
    expected = fields[0].lower()
    actual = sha256_file(path).lower()
    if actual != expected:
        raise RuntimeError(
            "Frozen WFD catchment geometry checksum mismatch: "
            f"expected {expected}, got {actual}"
        )

    catchments = gpd.read_file(path, layer=layer if layer else None)
    if len(catchments) != EXPECTED_WFD_CATCHMENTS:
        raise RuntimeError(
            f"Expected {EXPECTED_WFD_CATCHMENTS} frozen WFD catchments, "
            f"found {len(catchments)}."
        )
    return catchments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master",
        default="data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
    )
    parser.add_argument(
        "--ed-geometry",
        default="data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg",
    )
    parser.add_argument(
        "--catchment-geometry",
        default="data/inputs/spatial/WFD_Catchments_Frozen.gpkg",
        help=(
            "Repository-frozen WFD catchment GeoPackage. The build is offline "
            "and fails if this file or its checksum is missing or changed."
        ),
    )
    parser.add_argument(
        "--catchment-checksum",
        default=None,
        help=(
            "SHA-256 sidecar for --catchment-geometry. Defaults to "
            "<catchment-geometry>.sha256."
        ),
    )
    parser.add_argument("--catchment-layer", default=None)
    parser.add_argument("--catchment-name-column", default=None)
    parser.add_argument("--catchment-id-column", default=None)
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
        "--national-output",
        default="data/processed/goblin_spatial_national_2015_2025.csv",
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
    catchments = _load_frozen_catchments(
        gpd,
        args.catchment_geometry,
        args.catchment_layer,
        args.catchment_checksum,
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
    national_year = aggregate_to_national(master)

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
            validate_aggregation_closure(
                master, national_year, geography_col="national"
            ),
        ],
        ignore_index=True,
    )

    for path in (
        args.crosswalk_output,
        args.wfd_catchment_output,
        args.colm_catchment_output,
        args.county_output,
        args.national_output,
        args.diagnostics_output,
    ):
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    crosswalk.to_csv(args.crosswalk_output, index=False)
    wfd_year.to_csv(args.wfd_catchment_output, index=False)
    colm_year.to_csv(args.colm_catchment_output, index=False)
    county_year.to_csv(args.county_output, index=False)
    national_year.to_csv(args.national_output, index=False)
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
    print(f"National-year rows: {len(national_year):,}")
    print("National additive totals close exactly within numerical tolerance.")


if __name__ == "__main__":
    main()
