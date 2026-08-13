"""Contracts for the version-pinned published LPIS derivative schemas.

These tests deliberately exercise the compact, publication-safe fields exposed by
the corrected 2020 v2 and validated 2025 v1 GeoParquets.  Geometry is not
required here: the purpose is to prove that record harmonisation preserves the
accounting semantics consumed by the downstream ED overlay.
"""

import pandas as pd
import pytest

from goblin_spatial.land.lpis import normalise_lpis_records


def test_corrected_2020_v2_schema_preserves_claimed_area_and_commonage_shares() -> None:
    source = pd.DataFrame(
        {
            "PARCEL_ID": ["P1", "P2", "P3"],
            "PARCEL_AREA_HA": [12.0, 4.0, 3.0],
            "ELIGIBLE_AREA_HA": [11.0, 4.0, 3.0],
            "CLAIMED_AREA_HA": [10.0, 4.0, 3.0],
            "REFERENCE_AREA_HA": [10.2, 4.0, 3.0],
            "IS_COMMONAGE": [True, False, False],
            "COMMONAGE_FRACTION": [0.25, 1.0, 1.0],
            "SHARE_DIGITISED_HA": [3.0, 4.0, 3.0],
            "SHARE_ELIGIBLE_HA": [2.75, 4.0, 3.0],
            "SHARE_REFERENCE_HA": [2.55, 4.0, 3.0],
            "CROP_DESCRIPTION": [
                "Low Input Permanent Pasture",
                "Traditional Hay Meadow",
                "Grass Year 2",
            ],
            "LAND_USE_GROUP": [
                "GRASS_LOW_INPUT",
                "GRASS_HAY_MEADOW",
                "GRASS_TEMPORARY",
            ],
            "IS_GRASSLAND": [True, True, True],
            "IS_LOW_INPUT_GRASS": [True, False, False],
            "IS_HAY_MEADOW": [False, True, False],
            "IS_TEMPORARY_GRASS": [False, False, True],
            "IS_ANC": [True, False, False],
            "IS_AGRI_ENVIRONMENT": [True, False, False],
            "IS_ORGANIC": [False, True, False],
        }
    )

    out = normalise_lpis_records(source, 2020)

    # CLAIMED_AREA_HA is already the accounting quantity in the published v2
    # derivative and must never be multiplied by COMMONAGE_FRACTION again.
    assert out.loc[0, "CLAIMED_AREA_HA"] == pytest.approx(10.0)
    assert out.loc[0, "COMMONAGE_FRACTION"] == pytest.approx(0.25)
    assert out.loc[0, "SHARE_DIGITISED_HA"] == pytest.approx(3.0)
    assert out.loc[0, "SHARE_ELIGIBLE_HA"] == pytest.approx(2.75)
    assert out.loc[0, "SHARE_REFERENCE_HA"] == pytest.approx(2.55)

    assert out["IS_GRASSLAND"].tolist() == [True, True, True]
    assert out["IS_LOW_INPUT_GRASS"].tolist() == [True, False, False]
    assert out["IS_HAY_MEADOW"].tolist() == [False, True, False]
    assert out["IS_TEMPORARY_GRASS"].tolist() == [False, False, True]
    assert out["IS_ANC"].tolist() == [True, False, False]
    assert out["IS_AGRI_ENVIRONMENT"].tolist() == [True, False, False]
    assert out["IS_ORGANIC"].tolist() == [False, True, False]


def test_validated_2025_v1_schema_preserves_grass_and_scheme_semantics() -> None:
    source = pd.DataFrame(
        {
            "PARCEL_ID": ["A", "B", "C"],
            "PARCEL_AREA_HA": [6.0, 5.0, 4.0],
            "ELIGIBLE_AREA_HA": [6.0, 5.0, 4.0],
            "CLAIMED_AREA_HA": [6.0, 5.0, 4.0],
            "REFERENCE_AREA_HA": [6.0, 5.0, 4.0],
            "IS_COMMONAGE": [False, False, False],
            "COMMONAGE_FRACTION": [1.0, 1.0, 1.0],
            "CROP_DESCRIPTION": [
                "Permanent Pasture",
                "Low Input Peat Grassland",
                "Riparian Grass",
            ],
            "LAND_USE_GROUP": [
                "PERMANENT_PASTURE",
                "PEAT_GRASSLAND",
                "RIPARIAN_GRASS",
            ],
            "IS_GRASSLAND": [True, True, True],
            "IS_PERMANENT_PASTURE": [True, False, False],
            "IS_PEAT_GRASSLAND": [False, True, False],
            "IS_RIPARIAN_GRASS": [False, False, True],
            "IS_ACRES": [True, False, True],
            "IS_ANC": [True, True, False],
            "IS_ORGANIC": [False, True, False],
        }
    )

    out = normalise_lpis_records(source, 2025)

    assert out["GRASSLAND_METHOD"].eq("DAFM_FLAG").all()
    assert out["IS_PERMANENT_PASTURE"].tolist() == [True, False, False]
    assert out["IS_PEAT_GRASSLAND"].tolist() == [False, True, False]
    assert out["IS_RIPARIAN_GRASS"].tolist() == [False, False, True]
    assert out["IS_AGRI_ENVIRONMENT"].tolist() == [True, False, True]
    assert out["IS_ANC"].tolist() == [True, True, False]
    assert out["IS_ORGANIC"].tolist() == [False, True, False]


def test_published_snapshots_normalise_to_the_same_downstream_contract() -> None:
    required = {
        "LPIS_YEAR",
        "PARCEL_ID",
        "CLAIMED_AREA_HA",
        "SHARE_DIGITISED_HA",
        "SHARE_ELIGIBLE_HA",
        "SHARE_REFERENCE_HA",
        "IS_COMMONAGE",
        "COMMONAGE_FRACTION",
        "IS_GRASSLAND",
        "IS_LOW_INPUT_GRASS",
        "IS_PEAT_GRASSLAND",
        "IS_RIPARIAN_GRASS",
        "IS_ANC",
        "IS_AGRI_ENVIRONMENT",
        "IS_ORGANIC",
    }

    for year in (2020, 2025):
        source = pd.DataFrame(
            {
                "PARCEL_ID": [f"P-{year}"],
                "PARCEL_AREA_HA": [1.0],
                "ELIGIBLE_AREA_HA": [1.0],
                "CLAIMED_AREA_HA": [1.0],
                "REFERENCE_AREA_HA": [1.0],
                "IS_COMMONAGE": [False],
                "COMMONAGE_FRACTION": [1.0],
                "CROP_DESCRIPTION": ["Permanent Pasture"],
                "LAND_USE_GROUP": ["PERMANENT_PASTURE"],
                "IS_GRASSLAND": [True],
                "IS_ANC": [False],
                "IS_ORGANIC": [False],
                **(
                    {"IS_AGRI_ENVIRONMENT": [False]}
                    if year == 2020
                    else {"IS_ACRES": [False]}
                ),
            }
        )
        out = normalise_lpis_records(source, year)
        assert required.issubset(out.columns)
        assert out.loc[0, "LPIS_YEAR"] == year
        assert out.loc[0, "CLAIMED_AREA_HA"] == pytest.approx(1.0)
