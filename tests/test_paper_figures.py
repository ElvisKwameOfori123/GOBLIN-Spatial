from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd

from goblin_spatial.paper_figures import generate_paper_figures
from goblin_spatial.study_reporting import PRINCIPAL_SCENARIOS, SC3_USES, USE_LABELS


def _write_table(con: sqlite3.Connection, name: str, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_sql(name, con, if_exists="replace", index=False)


def _synthetic_final_database(path: Path) -> None:
    with sqlite3.connect(path) as con:
        national = []
        for i, scenario in enumerate(PRINCIPAL_SCENARIOS):
            national.append({
                "SCENARIO_ID": scenario,
                "ALLOCATION_POLICY": "PRORATA",
                "SCENARIO_DAIRY_COW": 1600000 - i * 250000,
                "SCENARIO_SUCKLER_COW": 160000 - i * 25000,
                "SCENARIO_TOTAL_CATTLE": 3200000 - i * 500000,
                "TARGET_LIVESTOCK_LAND_HA": 2443000 - i * 350000,
                "RUN_GROSS_RELEASE_HA": 1593000 + i * 350000,
            })
        _write_table(con, "national_results", national)

        lorenz = []
        for scenario in PRINCIPAL_SCENARIOS:
            for metric in ("Cattle reduction", "Standard Output gross loss"):
                for x, y in ((0, 0), (25, 6), (50, 20), (75, 48), (100, 100)):
                    lorenz.append({
                        "STUDY_SCENARIO_ID": scenario,
                        "STUDY_ALLOCATION_POLICY": "PRORATA",
                        "METRIC": metric,
                        "CUMULATIVE_ED_SHARE_PCT": x,
                        "CUMULATIVE_EXPOSURE_SHARE_PCT": y,
                    })
        _write_table(con, "lorenz_data", lorenz)

        redistribution = []
        rules = ["DAIRY_PROTECTION", "ECONOMIC_CAPACITY_PROTECTION", "SOCIAL_VULNERABILITY_PROTECTION"]
        for si, scenario in enumerate(PRINCIPAL_SCENARIOS):
            for ri, rule in enumerate(rules):
                cattle = 40000 + si * 10000 + ri * 5000
                so = 25000000 + si * 5000000 + ri * 2500000
                redistribution.append({
                    "PATHWAY_NAME": scenario,
                    "PATHWAY_ALLOCATION_RULE": rule,
                    "TOTAL_PROTECTION_RELIEF_TOTAL_CATTLE_REDUCTION_HEAD": cattle,
                    "TOTAL_DISPLACED_BURDEN_TOTAL_CATTLE_REDUCTION_HEAD": cattle,
                    "TOTAL_PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_2020_EUR": so,
                    "TOTAL_DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_2020_EUR": so,
                })
        _write_table(con, "redistribution", redistribution)

        robust = []
        for i in range(20):
            robust.append({
                "CSOED": str(i + 1),
                "PATHWAY_SENSITIVITY_CATTLE_REDUCTION_PCT": 2.0 + i * 0.4,
                "ALLOCATION_SENSITIVITY_CATTLE_REDUCTION_PCT": 1.0 + (19 - i) * 0.25,
            })
        _write_table(con, "robust_exposure", robust)

        persistence = []
        for freq in range(13):
            persistence.append({"METRIC": "Cattle reduction", "FREQUENCY": freq, "ED_COUNT": 5 + freq})
            persistence.append({"METRIC": "SO exposure", "FREQUENCY": freq, "ED_COUNT": 8 + freq})
        _write_table(con, "persistence_histogram", persistence)

        release = []
        for i, scenario in enumerate(PRINCIPAL_SCENARIOS):
            gross = 1500000 + i * 300000
            release.append({
                "STUDY_SCENARIO_ID": scenario,
                "STUDY_ALLOCATION_POLICY": "PRORATA",
                "GROSS_RELEASE_HA": gross,
                "DAIRY_RELEASE_HA": gross * 0.40,
                "BEEF_RELEASE_HA": gross * 0.50,
                "SHEEP_RELEASE_HA": gross * 0.10,
                "G1_RELEASE_HA": gross * 0.45,
                "G2_RELEASE_HA": gross * 0.45,
                "G3_RELEASE_HA": gross * 0.10,
            })
        _write_table(con, "land_release_summary", release)

        conditions = []
        for i in range(40):
            conditions.append({
                "STUDY_SCENARIO_ID": "ALL_GAS_NZ",
                "STUDY_ALLOCATION_POLICY": "PRORATA",
                "CSOED": str(i + 1),
                "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": 4.0 + i * 0.8,
                "SOCIAL_VULNERABILITY_SCORE": (i % 10) / 9.0,
                "GOBLIN_RELEASED_GRASSLAND_HA": 20.0 + i * 3.0,
                "AD_GRASS_ELIGIBILITY_COVERAGE_PCT": 40.0 + (i % 7) * 2.0,
                "BIOREFINERY_GRASS_ELIGIBILITY_COVERAGE_PCT": 38.0 + (i % 5) * 2.0,
                "WILLOW_ELIGIBILITY_COVERAGE_PCT": 20.0 + (i % 11) * 3.0,
                "ADDITIONAL_TILLAGE_ELIGIBILITY_COVERAGE_PCT": 15.0 + (i % 8) * 4.0,
                "FOREST_ELIGIBILITY_COVERAGE_PCT": 50.0 + (i % 9) * 2.5,
                "REWETTING_ELIGIBILITY_COVERAGE_PCT": 5.0 + (i % 6) * 3.0,
            })
        _write_table(con, "transition_conditions", conditions)

        mobilisation = []
        for i, scenario in enumerate(PRINCIPAL_SCENARIOS):
            for use in SC3_USES:
                target = 100000.0 + i * 10000.0
                unmet = 25000.0 if use == "ADDITIONAL_TILLAGE" else (5000.0 if use == "REWETTING" else 0.0)
                realised = target - unmet
                eligible = target * (1.8 if use != "REWETTING" else 1.3)
                mobilisation.append({
                    "STUDY_SCENARIO_ID": scenario,
                    "STUDY_ALLOCATION_POLICY": "PRORATA",
                    "LAND_USE": use,
                    "LAND_USE_LABEL": USE_LABELS[use],
                    "ELIGIBLE_HA": eligible,
                    "TARGET_HA": target,
                    "REALISED_HA": realised,
                    "UNMET_HA": unmet,
                    "OPPORTUNITY_MOBILISATION_PCT": 100.0 * realised / eligible,
                })
        _write_table(con, "opportunity_mobilisation", mobilisation)

        pools = []
        for i, scenario in enumerate(PRINCIPAL_SCENARIOS):
            for j, pool in enumerate(("TILLAGE_WILLOW", "AD_BIOREFINERY", "FOREST_MINERAL")):
                pools.append({
                    "STUDY_SCENARIO_ID": scenario,
                    "STUDY_ALLOCATION_POLICY": "PRORATA",
                    "SHARED_POOL": pool,
                    "CAPACITY_HA": 400000.0,
                    "USED_HA": 220000.0 + i * 20000.0 + j * 30000.0,
                    "UTILISATION_PCT": 55.0 + i * 5.0 + j * 7.0,
                })
        _write_table(con, "shared_pool_summary", pools)


def test_paper_figure_suite_creates_eight_png_and_svg_outputs(tmp_path: Path) -> None:
    database = tmp_path / "GOBLIN_Spatial_Final_Results.sqlite"
    _synthetic_final_database(database)
    out = tmp_path / "paper_figures"
    outputs = generate_paper_figures(database, out)

    assert outputs["paper_figure_manifest"].exists()
    expected = [
        "paper_fig01_national_transition",
        "paper_fig02_transition_concentration",
        "paper_fig03_protection_redistribution",
        "paper_fig04_persistence_sensitivity",
        "paper_fig05_released_land_composition",
        "paper_fig06_transition_conditions",
        "paper_fig07_target_delivery",
        "paper_fig08_opportunity_constraints",
    ]
    for stem in expected:
        assert (out / f"{stem}.png").exists()
        assert (out / f"{stem}.svg").exists()

    manifest = pd.read_csv(outputs["paper_figure_manifest"])
    assert len(manifest) == 8
    fig6 = manifest.loc[manifest["FIGURE_ID"].eq("P06")].iloc[0]
    assert "tillage" in str(fig6["NOTE"]).lower()
