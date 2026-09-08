"""Contract tests for the GOBLIN-Spatial historical baseline boundary."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.baseline.signatures import FOLLOWER_COHORTS, build_signatures
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import SpatialConfig, load_config
from goblin_spatial.land.panel import AQA_REGIONS, COUNTY_TO_AQA_REGION


def _small_config(expected_eds: int) -> SpatialConfig:
    root = Path(".").resolve()
    return SpatialConfig(
        project_root=root,
        raw_dir=root / "data/raw",
        controls_dir=root / "data/controls",
        interim_dir=root / "data/interim",
        processed_dir=root / "data/processed",
        start_year=2015,
        end_year=2025,
        base_year=2020,
        expected_eds=expected_eds,
        files={},
        raw={},
    )


def test_stage09_is_part_of_baseline_and_has_19_followers():
    assert len(FINAL_21_COHORTS) == 21
    assert len(FOLLOWER_COHORTS) == 19
    assert "dairy_cows" not in FOLLOWER_COHORTS
    assert "suckler_cows" not in FOLLOWER_COHORTS
    assert "bulls" in FOLLOWER_COHORTS


def test_stage09_signature_shape_and_roles():
    rows = []
    for ed, county, dairy, suckler in (
        ("ED001", "Cork", 10, 5),
        ("ED002", "Cork", 0, 3),
    ):
        row = {
            "YEAR": 2020,
            "CSOED": ed,
            "County": county,
            "DAIRY_COW": dairy,
            "OTHER_COW": suckler,
        }
        for cohort in FINAL_21_COHORTS:
            if cohort == "dairy_cows":
                row[cohort] = dairy
            elif cohort == "suckler_cows":
                row[cohort] = suckler
            else:
                row[cohort] = 2 if ed == "ED001" else 1
        rows.append(row)

    signatures = build_signatures(pd.DataFrame(rows), _small_config(2))

    assert len(signatures) == 2 * 19
    assert not signatures[["CSOED", "COHORT"]].duplicated().any()
    assert set(signatures["COHORT_SPATIAL_ROLE"]).issubset(
        {"LOCAL_ED", "COUNTY_RECEIVER", "NATIONAL_ORPHAN", "NONE"}
    )

    dairy_receiver = signatures.loc[
        (signatures["CSOED"] == "ED002")
        & (signatures["ADULT_ORIGIN"] == "DAIRY")
        & (signatures["BASE_COHORT_HEAD"] > 0)
    ]
    assert not dairy_receiver.empty
    assert set(dairy_receiver["COHORT_SPATIAL_ROLE"]) == {"COUNTY_RECEIVER"}


def test_validated_aqa06_mapping_is_complete():
    assert len(COUNTY_TO_AQA_REGION) == 26
    assert set(COUNTY_TO_AQA_REGION.values()) == set(AQA_REGIONS)
    assert COUNTY_TO_AQA_REGION["Cork"] == "South-West"
    assert COUNTY_TO_AQA_REGION["Tipperary"] == "Mid-West"
    assert COUNTY_TO_AQA_REGION["Louth"] == "Dublin and Mid-East"


def test_config_separates_baseline_from_downstream_spatial_inputs():
    config = load_config("configs/ireland_2015_2025.yaml")

    baseline_keys = {
        "cso_ed_2020",
        "cso_cattle_county",
        "cso_sheep_workbook",
        "sheep_breed_anchors",
        "goblin_cohorts",
        "cso_land",
        "se_controls",
        "standard_output_mapping",
    }
    assert baseline_keys.issubset(config.files)

    # Retained validation evidence is not a production sheep-control key.
    assert "dafm_sheep_county_validation" in config.files
    assert "county_region_map" not in config.files

    # The production land context is the frozen 2020 soil + LPIS bundle.
    assert "land_context_2020" in config.files

    # Superseded 08B/08C source/reconstruction paths must not re-enter the
    # production configuration. Their development history remains in Git.
    assert "agricultural_soil_source" not in config.files
    assert "physical_soil_package" not in config.files

    # Geometry is reserved for downstream reporting and does not enter the
    # baseline or SC1-SC3 scientific calculations.
    assert "ed_boundaries_frozen" in config.files
