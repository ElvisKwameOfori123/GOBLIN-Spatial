from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from goblin_spatial.map_reporting import export_maps
from goblin_spatial.study_reporting import PRINCIPAL_RULES, PRINCIPAL_SCENARIOS


def _map_data() -> pd.DataFrame:
    rows = []
    for s_i, scenario in enumerate(PRINCIPAL_SCENARIOS):
        for r_i, rule in enumerate(PRINCIPAL_RULES):
            for e_i, ed in enumerate(("1003", "08045/08046")):
                relief = 0.0
                burden = 0.0
                if rule != "PRORATA":
                    relief = 2.0 + r_i if e_i == 0 else 0.0
                    burden = 2.0 + r_i if e_i == 1 else 0.0
                rows.append({
                    "STUDY_SCENARIO_ID": scenario,
                    "STUDY_ALLOCATION_POLICY": rule,
                    "CSOED": ed,
                    "County": "A" if e_i == 0 else "B",
                    "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": 10.0 + 5.0 * s_i + e_i,
                    "TOP_DECILE_SO_FREQUENCY": 12 if e_i == 0 else 3,
                    "PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": relief,
                    "DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": burden,
                    "FOREST_ELIGIBILITY_COVERAGE_PCT": 70.0 - 10.0 * e_i,
                    "WILLOW_ELIGIBILITY_COVERAGE_PCT": 30.0 + 10.0 * e_i,
                    "AD_GRASS_ELIGIBILITY_COVERAGE_PCT": 50.0,
                    "ALTERNATIVE_USE_UPTAKE_PCT_OF_RELEASE": 60.0 + 5.0 * s_i,
                    "FINAL_UNALLOCATED_PCT_OF_RELEASE": 40.0 - 5.0 * s_i,
                })
    return pd.DataFrame(rows)


def test_map_reporting_accepts_source_ed_codes_and_freezes_model_geometry(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _map_data().to_csv(results / "GOBLIN_Spatial_Map_Data.csv", index=False)

    source = tmp_path / "source.shp"
    geometry = gpd.GeoDataFrame(
        {
            "CSOED": ["01003", "08045/08046", "99999"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1), box(3, 0, 4, 1)],
        },
        crs="EPSG:2157",
    )
    geometry.to_file(source)

    outputs = export_maps(results, geometry=source, output_dir=tmp_path / "maps")

    assert outputs["frozen_geometry"].exists()
    assert outputs["joined_map_layer"].exists()
    assert outputs["map_manifest"].exists()
    assert (outputs["map_directory"] / "map01_persistent_exposure.png").exists()
    assert (outputs["map_directory"] / "map02_standard_output_exposure.svg").exists()
    assert (outputs["map_directory"] / "map03_protection_redistribution.png").exists()
    assert (outputs["map_directory"] / "map05_alternative_use_uptake.png").exists()
    assert (outputs["map_directory"] / "map06_final_unallocated_land.svg").exists()

    frozen = gpd.read_file(outputs["frozen_geometry"])
    assert set(frozen["CSOED"].astype(str)) == {"1003", "8045"}
    assert set(frozen["CSOED_GEOMETRY_SOURCE"].astype(str)) == {"01003", "08045/08046"}

    joined = gpd.read_file(outputs["joined_map_layer"])
    assert len(joined) == 2 * len(PRINCIPAL_SCENARIOS) * len(PRINCIPAL_RULES)
    assert set(joined["CSOED"].astype(str)) == {"1003", "8045"}
    assert set(joined["CSOED_SOURCE"].astype(str)) == {"1003", "08045/08046"}
