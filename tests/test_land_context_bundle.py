"""Repository gate for the frozen 2020 compact land-context bundle."""

from pathlib import Path

from goblin_spatial.land.context import (
    LAND_CONTEXT_CANONICAL_SHA256,
    LAND_CONTEXT_COMPONENT_FILES,
    LAND_CONTEXT_COMPONENT_SHA256,
    LAND_CONTEXT_EXPECTED_COLUMNS,
    LAND_CONTEXT_EXPECTED_EDS,
    land_context_sha256,
    read_land_context_table,
    validate_land_context,
)


BUNDLE = Path("data/controls/land/ED_Land_Context_2020")


def test_all_three_authoritative_component_files_are_tracked() -> None:
    for label, filename in LAND_CONTEXT_COMPONENT_FILES.items():
        path = BUNDLE / filename
        assert path.is_file(), f"missing frozen {label} runtime control: {path}"


def test_frozen_bundle_hashes_and_scientific_contract() -> None:
    frame = read_land_context_table(BUNDLE, verify_sha256=True)
    qa = validate_land_context(frame)

    assert len(frame) == LAND_CONTEXT_EXPECTED_EDS
    assert frame["CSOED"].nunique() == LAND_CONTEXT_EXPECTED_EDS
    assert len(frame.columns) == LAND_CONTEXT_EXPECTED_COLUMNS
    assert qa["08b_provenance"] == {"ED": 2820, "COUNTY_FALLBACK": 37}
    assert qa["08b_class_closure_max_abs"] <= 1e-8
    assert qa["08b_group_closure_max_abs"] <= 1e-8
    assert qa["08b_class_pair_to_g_max_abs"] <= 1e-8
    assert qa["lpis_grass_partition_max_abs_ha"] <= 1e-6
    assert land_context_sha256(BUNDLE) == LAND_CONTEXT_CANONICAL_SHA256


def test_component_hash_constants_are_frozen() -> None:
    assert LAND_CONTEXT_COMPONENT_SHA256 == {
        "08B": "55014e27c872666cffaf2b876eaa856eccbab1e915513a2f91780177b0b0c2c4",
        "08C": "9892059c3f67c92d04427ad48220aa7565325df0251be6d53090388046b6bae4",
        "LPIS_2020": "c8a6b66c9166ea3da0121def6225698037951d3022af02e5b42f2b54f4f13b2b",
    }
