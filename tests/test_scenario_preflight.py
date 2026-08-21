from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.scenario.preflight import preflight_principal_inputs
from goblin_spatial.soil import CLASS_SHARE_COLUMNS, GROUP_SHARE_COLUMNS, PHYSICAL_AREA_COLUMNS


def _cfg(tmp_path: Path) -> SpatialConfig:
    processed = tmp_path / "processed"
    controls = tmp_path / "controls"
    processed.mkdir()
    controls.mkdir()
    files = {
        "scenario_controls": controls / "scenarios.csv",
        "agricultural_soil_profile": controls / "08b.csv",
        "lpis_ed_profile": controls / "lpis.csv",
        "physical_soil_profile": controls / "08c.csv",
    }
    return SpatialConfig(
        project_root=tmp_path,
        raw_dir=tmp_path / "raw",
        controls_dir=controls,
        interim_dir=tmp_path / "interim",
        processed_dir=processed,
        start_year=2015,
        end_year=2025,
        base_year=2020,
        expected_eds=2,
        files=files,
        raw={"outputs": {"standard_output_master": "processed/stage08.csv"}},
    )


def _write_stage08(cfg: SpatialConfig) -> None:
    rows = []
    for year in (2020, 2025):
        for ed in ("1001", "1002"):
            rows.append(
                {
                    "YEAR": year,
                    "CSOED": ed,
                    "County": "A",
                    "ALL_GRASSLAND": 100.0,
                    "AGRICULTURAL_HOLDINGS": 10,
                    "AVERAGE_SIZE_OF_HOLDINGS": 20.0,
                    "MEDIAN_AGE_OF_HOLDER": 55.0,
                    "SO_LIVESTOCK_2020_EUR": 1000.0,
                }
            )
    pd.DataFrame(rows).to_csv(cfg.project_root / "processed/stage08.csv", index=False)


def _write_controls(cfg: SpatialConfig) -> None:
    pd.DataFrame(
        [
            {
                "SCENARIO_NO": 1,
                "SCENARIO_ID": "TEST",
                "SCENARIO_NAME": "Test",
                "ACTIVE": True,
                "TARGET_YEAR": 2050,
                "TARGET_LIVESTOCK_LAND_HA": 100.0,
                "DAIRY_COWS": 1,
                "SUCKLER_COWS": 1,
                "AD_GRASS_HA": 0.0,
                "BIOREFINERY_GRASS_HA": 0.0,
                "WILLOW_HA": 0.0,
                "ADDITIONAL_TILLAGE_HA": 0.0,
                "ADDITIONAL_FOREST_HA": 0.0,
                "REWETTING_HA": 0.0,
            }
        ]
    ).to_csv(cfg.files["scenario_controls"], index=False)


def _write_08b(cfg: SpatialConfig, *, complete: bool = True) -> None:
    rows = []
    for ed in ("1001", "1002", "1003"):
        row = {"CSOED": ed, "SOIL_SOURCE_UAA_HA": 100.0}
        classes = (0.20, 0.20, 0.20, 0.20, 0.10, 0.10)
        row.update(dict(zip(CLASS_SHARE_COLUMNS, classes, strict=True)))
        row[GROUP_SHARE_COLUMNS[0]] = 0.40
        row[GROUP_SHARE_COLUMNS[1]] = 0.40
        row[GROUP_SHARE_COLUMNS[2]] = 0.20
        if complete:
            row["FOREST_YC_WEIGHTED_MEAN"] = 18.0
            row["IFS_PEAT_CUTOVER_UAA_SHARE"] = 0.10
        rows.append(row)
    pd.DataFrame(rows).to_csv(cfg.files["agricultural_soil_profile"], index=False)


def _write_lpis(cfg: SpatialConfig) -> None:
    rows = []
    for year in (2020, 2025):
        for ed in ("1001", "1002"):
            rows.append(
                {
                    "LPIS_YEAR": year,
                    "CSOED": ed,
                    "LPIS_CLAIMED_GRASS_HA": 90.0,
                    "LPIS_ELIGIBLE_GRASS_HA": 80.0,
                }
            )
    pd.DataFrame(rows).to_csv(cfg.files["lpis_ed_profile"], index=False)


def _write_minimal_08c(cfg: SpatialConfig) -> None:
    rows = []
    for ed in ("1001", "1002", "1003"):
        row = {"CSOED": ed}
        row.update(
            dict(
                zip(
                    PHYSICAL_AREA_COLUMNS,
                    (30.0, 20.0, 20.0, 10.0, 5.0, 10.0, 5.0),
                    strict=True,
                )
            )
        )
        rows.append(row)
    pd.DataFrame(rows).to_csv(cfg.files["physical_soil_profile"], index=False)


def _write_all(cfg: SpatialConfig, *, complete_08b: bool = True) -> None:
    _write_stage08(cfg)
    _write_controls(cfg)
    _write_08b(cfg, complete=complete_08b)
    _write_lpis(cfg)
    _write_minimal_08c(cfg)


def test_sc3_preflight_accepts_source_universes_and_minimal_08c(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_all(cfg)

    report = preflight_principal_inputs(cfg, baseline_year=2020, stage="SC3")

    assert report["OK"].all(), report.to_dict("records")
    assert report.set_index("ITEM").loc["COMPACT_08B", "DETAIL"].endswith("rows=3")
    assert report.set_index("ITEM").loc["COMPACT_08C", "DETAIL"].endswith("rows=3")


def test_sc1_preflight_does_not_require_sc3_yc_or_peat_fields(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_stage08(cfg)
    _write_controls(cfg)
    _write_08b(cfg, complete=False)

    report = preflight_principal_inputs(cfg, baseline_year=2020, stage="SC1")

    assert report["OK"].all(), report.to_dict("records")


def test_sc3_preflight_fails_cheaply_when_mature_08b_fields_are_missing(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_all(cfg, complete_08b=False)

    report = preflight_principal_inputs(cfg, baseline_year=2020, stage="SC3")
    soil = report.set_index("ITEM").loc["COMPACT_08B"]

    assert not bool(soil["OK"])
    assert "FOREST_YC_WEIGHTED_MEAN" in soil["DETAIL"]
    assert "IFS_PEAT_CUTOVER_UAA_SHARE" in soil["DETAIL"]
