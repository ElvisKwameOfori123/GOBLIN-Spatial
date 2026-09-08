"""Tests for the no-download Colm-direct principal preflight contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.config import SpatialConfig
import goblin_spatial.scenario.preflight as preflight


def _cfg(tmp_path: Path) -> SpatialConfig:
    processed = tmp_path / "processed"
    controls = tmp_path / "controls"
    land_context = controls / "land" / "ED_Land_Context_2020"
    processed.mkdir()
    controls.mkdir()
    files = {
        "scenario_controls": controls / "scenarios.csv",
        "land_context_2020": land_context,
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


def _mock_valid_colm_lpis_context(monkeypatch, cfg: SpatialConfig) -> None:
    cfg.files["land_context_2020"].mkdir(parents=True)
    frame = pd.DataFrame({"CSOED": ["1001", "1002"]})
    monkeypatch.setattr(preflight, "read_colm_lpis_context", lambda path: frame)


def _write_runtime_prerequisites(cfg: SpatialConfig) -> None:
    _write_stage08(cfg)
    _write_controls(cfg)


def test_sc2_preflight_accepts_frozen_2020_colm_lpis_runtime_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg = _cfg(tmp_path)
    _write_runtime_prerequisites(cfg)
    _mock_valid_colm_lpis_context(monkeypatch, cfg)

    report = preflight.preflight_principal_inputs(cfg, baseline_year=2020, stage="SC2")

    assert report["OK"].all(), report.to_dict("records")
    context = report.set_index("ITEM").loc["COLM_LPIS_CONTEXT_2020"]
    assert "rows=2" in context["DETAIL"]
    assert "legacy 08B not required" in context["DETAIL"]


def test_missing_land_context_does_not_block_sc1(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_runtime_prerequisites(cfg)

    report = preflight.preflight_principal_inputs(cfg, baseline_year=2020, stage="SC1")

    assert report["OK"].all(), report.to_dict("records")
    assert "COLM_LPIS_CONTEXT_2020" not in set(report["ITEM"])


def test_missing_colm_lpis_context_blocks_sc2(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_runtime_prerequisites(cfg)

    report = preflight.preflight_principal_inputs(cfg, baseline_year=2020, stage="SC2")
    context = report.set_index("ITEM").loc["COLM_LPIS_CONTEXT_2020"]

    assert not bool(context["OK"])
    assert "missing repository-contained Colm physical-soil + LPIS control" in context["DETAIL"]


def test_2025_sc1_is_soil_independent(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_runtime_prerequisites(cfg)

    report = preflight.preflight_principal_inputs(cfg, baseline_year=2025, stage="SC1")

    assert report["OK"].all(), report.to_dict("records")
    assert "COLM_LPIS_CONTEXT_2020" not in set(report["ITEM"])


def test_2025_sc2_sc3_are_blocked_until_separate_context_exists(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    _write_runtime_prerequisites(cfg)

    report = preflight.preflight_principal_inputs(cfg, baseline_year=2025, stage="SC3")
    support = report.set_index("ITEM").loc["SPATIAL_BASELINE_SUPPORT"]

    assert not bool(support["OK"])
    assert "2020 Colm+LPIS context only" in support["DETAIL"]
