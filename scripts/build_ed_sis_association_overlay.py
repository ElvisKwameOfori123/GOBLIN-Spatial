"""Build the first neutral GOBLIN-Spatial ED x SIS soil profile.

The authoritative GOBLIN-Spatial baseline defines the ED universe; the SAPS
geography is filtered to those CSOEDs before intersection with raw SIS soil
associations. No functional soil or future-land-use classification is applied.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import geopandas as gpd
import pandas as pd

from goblin_spatial.soil import overlay_soil_associations


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = PROJECT_ROOT / "data" / "raw" / "cattle" / "CSO_ED_2020.csv"
DEFAULT_ED = (
    PROJECT_ROOT
    / "data"
    / "external"
    / "spatial"
    / "ed"
    / "Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.shp"
)
DEFAULT_SOIL = (
    PROJECT_ROOT
    / "data"
    / "external"
    / "spatial"
    / "sis_soils"
    / "INSM250k_ING.shp"
)
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "interim" / "soil"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help=(
            "Authoritative GOBLIN-Spatial baseline CSV containing CSOED. "
            "Defaults to data/raw/cattle/CSO_ED_2020.csv."
        ),
    )
    parser.add_argument("--ed-shp", type=Path, default=DEFAULT_ED)
    parser.add_argument("--soil-shp", type=Path, default=DEFAULT_SOIL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--target-crs", default="EPSG:2157")
    parser.add_argument("--min-intersection-ha", type=float, default=0.01)
    args = parser.parse_args()

    for path in (args.baseline, args.ed_shp, args.soil_shp):
        if not path.exists():
            raise FileNotFoundError(
                f"Missing required input: {path}. Run 'goblin-spatial fetch-data' "
                "first for the external spatial inputs."
            )

    baseline = pd.read_csv(args.baseline, dtype={"CSOED": str}, low_memory=False)
    if "CSOED" not in baseline.columns:
        raise KeyError("Baseline must contain a CSOED column")

    ed = gpd.read_file(args.ed_shp)
    soil = gpd.read_file(args.soil_shp)

    profile, diagnostics = overlay_soil_associations(
        baseline,
        ed,
        soil,
        target_crs=args.target_crs,
        min_intersection_ha=args.min_intersection_ha,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    profile_path = args.out_dir / "ED_SIS_association_profile.csv"
    diagnostic_path = args.out_dir / "ED_SIS_overlay_diagnostics.json"

    profile.to_csv(profile_path, index=False)
    diagnostic_path.write_text(
        json.dumps(asdict(diagnostics), indent=2),
        encoding="utf-8",
    )

    print("Neutral ED x SIS association overlay complete")
    print(f"  baseline rows:       {diagnostics.baseline_rows:,}")
    print(f"  EDs selected:        {diagnostics.ed_rows_selected:,}")
    print(f"  EDs with soil:       {diagnostics.eds_with_soil:,}")
    print(f"  SIS associations:    {diagnostics.soil_associations:,}")
    print(f"  mean soil coverage:  {diagnostics.mean_soil_coverage:.4f}")
    print(f"  median coverage:     {diagnostics.median_soil_coverage:.4f}")
    print(f"  profile:             {profile_path}")
    print(f"  diagnostics:         {diagnostic_path}")
    print(
        "\nSTOP HERE for the first soil stage: do not yet classify associations "
        "as GOBLIN G1/G2/G3 or future land uses."
    )


if __name__ == "__main__":
    main()
