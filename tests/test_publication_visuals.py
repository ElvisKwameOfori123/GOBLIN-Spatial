from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd

from goblin_spatial.publication_visuals import PAPER_RULES, PAPER_SCENARIOS, generate_publication_graphs
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
                            "CSOED": str(ed + 1),
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


def test_publication_graphs_focus_on_be_and_all_gas_nz(tmp_path: Path) -> None:
    database = tmp_path / "GOBLIN_Spatial_Final_Results.sqlite"
    _synthetic_database(database)
    out = tmp_path / "publication_graphs"

    outputs = generate_publication_graphs(database, out)

    assert outputs["graph_manifest"].exists()
    expected = [
        "pub_fig01_exposure_concentration",
        "pub_fig02_ed_exposure_distributions",
        "pub_fig03_protection_redistribution",
        "pub_fig04_exposure_vulnerability",
        "pub_fig05_target_realised_unmet",
    ]
    for stem in expected:
        assert (out / f"{stem}.png").exists()
        assert (out / f"{stem}.svg").exists()

    manifest = pd.read_csv(outputs["graph_manifest"])
    assert len(manifest) == 5
    assert set(manifest["FIGURE_ID"]) == {"G01", "G02", "G03", "G04", "G05"}
    assert manifest["NOTE"].fillna("").str.contains("Standard Output|SC1|PRORATA|composite", case=False, regex=True).any()
