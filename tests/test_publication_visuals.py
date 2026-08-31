from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from goblin_spatial.publication_visuals import PAPER_RULES, PAPER_SCENARIOS
from goblin_spatial.publication_visuals_final import (
    _classify,
    _tercile_breaks,
    generate_final_publication_visuals,
    generate_polished_bivariate_map,
    generate_polished_released_land_map,
)
from goblin_spatial.study_reporting import SC3_USES, USE_LABELS


def _write_table(con: sqlite3.Connection, name: str, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_sql(name, con, if_exists="replace", index=False)


def _synthetic_database(path: Path) -> None:
    with sqlite3.connect(path) as con:
        lorenz = []
        for s_i, scenario in enumerate(PAPER_SCENARIOS):
            for metric in ("Cattle reduction", "Standard Output gross loss"):
                for x, y in ((0, 0), (25, 5 + s_i), (50, 18 + 2 * s_i), (75, 48 + 2 * s_i), (100, 100)):
                    lorenz.append(
                        {
                            "STUDY_SCENARIO_ID": scenario,
                            "STUDY_ALLOCATION_POLICY": "PRORATA",
                            "METRIC": metric,
                            "CUMULATIVE_ED_SHARE_PCT": x,
                            "CUMULATIVE_EXPOSURE_SHARE_PCT": y,
                        }
                    )
        _write_table(con, "lorenz_data", lorenz)

        conditions = []
        for s_i, scenario in enumerate(PAPER_SCENARIOS):
            for r_i, rule in enumerate(PAPER_RULES):
                for ed in range(30):
                    signed_cattle = 0.0 if rule == "PRORATA" else ((ed % 5) - 2) * (2.0 + r_i)
                    signed_so = 0.0 if rule == "PRORATA" else ((ed % 7) - 3) * (1.0e6 + r_i * 1.5e5)
                    conditions.append(
                        {
                            "STUDY_SCENARIO_ID": scenario,
                            "STUDY_ALLOCATION_POLICY": rule,
                            "CSOED": str(1000 + ed),
                            "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE": 10.0 + 8.0 * s_i + 0.3 * ed + r_i,
                            "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": 8.0 + 7.0 * s_i + 0.25 * ed + 0.5 * r_i,
                            "GOBLIN_RELEASED_GRASSLAND_HA": 25.0 + 5.0 * s_i + ed,
                            "ECONOMIC_VULNERABILITY_SCORE": (ed % 10) / 9.0,
                            "SOCIAL_VULNERABILITY_SCORE": ((ed + 3) % 10) / 9.0,
                            "SIGNED_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_HEAD": signed_cattle,
                            "SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR": signed_so,
                        }
                    )
        _write_table(con, "transition_conditions", conditions)

        mobilisation = []
        for s_i, scenario in enumerate(PAPER_SCENARIOS):
            for use_i, use in enumerate(SC3_USES):
                target = 100000.0 + 12000.0 * s_i + 5000.0 * use_i
                unmet = 15000.0 if use == "ADDITIONAL_TILLAGE" else 0.0
                mobilisation.append(
                    {
                        "STUDY_SCENARIO_ID": scenario,
                        "STUDY_ALLOCATION_POLICY": "PRORATA",
                        "LAND_USE": use,
                        "LAND_USE_LABEL": USE_LABELS[use],
                        "TARGET_HA": target,
                        "REALISED_HA": target - unmet,
                        "UNMET_HA": unmet,
                    }
                )
        _write_table(con, "opportunity_mobilisation", mobilisation)


def _synthetic_map_data() -> pd.DataFrame:
    rows = []
    for s_i, scenario in enumerate(PAPER_SCENARIOS):
        for r_i, rule in enumerate(PAPER_RULES):
            for ed in range(30):
                relief = 0.0
                burden = 0.0
                if rule != "PRORATA":
                    if ed % 4 in (0, 1):
                        relief = 1.0 + 0.15 * r_i + 0.03 * ed
                    else:
                        burden = 1.0 + 0.15 * r_i + 0.03 * ed
                rows.append(
                    {
                        "STUDY_SCENARIO_ID": scenario,
                        "STUDY_ALLOCATION_POLICY": rule,
                        "CSOED": str(1000 + ed),
                        "County": f"County {(ed // 10) + 1}",
                        "TOTAL_CATTLE_REDUCTION_HEAD": 25.0 + 4.0 * s_i + ed,
                        "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE": 8.0 + 7.0 * s_i + 0.35 * ed + 0.4 * r_i,
                        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR": 500000.0 + 120000.0 * s_i + 15000.0 * ed,
                        "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": 6.0 + 8.0 * s_i + 0.45 * ed + 0.2 * r_i,
                        "GOBLIN_RELEASED_GRASSLAND_HA": 20.0 + 9.0 * s_i + 1.8 * ed,
                        "ECONOMIC_VULNERABILITY_SCORE": (ed % 10) / 9.0,
                        "SOCIAL_VULNERABILITY_SCORE": ((ed + 4) % 10) / 9.0,
                        "PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": relief,
                        "DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": burden,
                        "FOREST_ELIGIBILITY_COVERAGE_PCT": 35.0 + (ed % 8) * 5.0,
                        "AD_GRASS_ELIGIBILITY_COVERAGE_PCT": 30.0 + (ed % 7) * 6.0,
                        "WILLOW_ELIGIBILITY_COVERAGE_PCT": 20.0 + (ed % 6) * 7.0,
                    }
                )
    return pd.DataFrame(rows)


def _synthetic_geometry(path: Path) -> None:
    gpd = pytest.importorskip("geopandas")
    geometry = pytest.importorskip("shapely.geometry")
    boxes = []
    ids = []
    size = 10000.0
    for ed in range(30):
        row, col = divmod(ed, 6)
        x0 = col * size
        y0 = row * size
        boxes.append(geometry.box(x0, y0, x0 + size, y0 + size))
        ids.append(str(1000 + ed))
    gdf = gpd.GeoDataFrame({"CSOED": ids, "geometry": boxes}, crs="EPSG:2157")
    gdf.to_file(path, layer="eds", driver="GPKG")


def test_final_publication_graphs_focus_on_be_and_all_gas_nz(tmp_path: Path) -> None:
    database = tmp_path / "GOBLIN_Spatial_Final_Results.sqlite"
    _synthetic_database(database)
    out = tmp_path / "publication_visuals"

    outputs = generate_final_publication_visuals(database, output_dir=out, graphs_only=True)

    assert outputs["graph_manifest"].exists()
    expected = [
        "pub_fig01_exposure_concentration",
        "pub_fig02_ed_exposure_distributions",
        "pub_fig03_protection_redistribution",
        "pub_fig04_exposure_vulnerability",
        "pub_fig05_target_realised_unmet",
    ]
    for stem in expected:
        assert (out / "graphs" / f"{stem}.png").exists()
        assert (out / "graphs" / f"{stem}.svg").exists()

    manifest = pd.read_csv(outputs["graph_manifest"])
    assert len(manifest) == 5
    assert set(manifest["FIGURE_ID"]) == {"G01", "G02", "G03", "G04", "G05"}
    g04 = manifest.loc[manifest["FIGURE_ID"].eq("G04")].iloc[0]
    assert "common pooled exposure" in str(g04["NOTE"]).lower()
    assert "early-attention" in str(g04["NOTE"]).lower()


def test_common_tercile_classes_have_same_numeric_meaning() -> None:
    pooled = pd.Series(range(1, 100), dtype=float)
    breaks = _tercile_breaks(pooled)
    assert breaks is not None
    low_pathway = _classify(pd.Series([10.0, 40.0, 80.0]), breaks)
    high_pathway = _classify(pd.Series([10.0, 40.0, 80.0]), breaks)
    assert low_pathway.tolist() == high_pathway.tolist()
    assert low_pathway.tolist() == [0.0, 1.0, 2.0]


def test_polished_publication_maps_render_with_shared_classes_and_callouts(tmp_path: Path) -> None:
    map_csv = tmp_path / "GOBLIN_Spatial_Map_Data.csv"
    _synthetic_map_data().to_csv(map_csv, index=False)
    geometry = tmp_path / "eds.gpkg"
    _synthetic_geometry(geometry)
    out = tmp_path / "maps"

    bivariate = generate_polished_bivariate_map(
        map_csv,
        geometry=geometry,
        geometry_key="CSOED",
        output_dir=out,
    )
    released = generate_polished_released_land_map(
        map_csv,
        geometry=geometry,
        geometry_key="CSOED",
        output_dir=out,
    )

    assert bivariate.exists()
    assert released.exists()
    assert (out / "pub_map03_exposure_vulnerability.svg").exists()
    assert (out / "pub_map05_released_grassland.svg").exists()
