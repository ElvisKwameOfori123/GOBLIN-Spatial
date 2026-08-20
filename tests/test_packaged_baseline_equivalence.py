"""Migration audit for the packaged historical-baseline inputs.

These tests prove that moving the compact frozen inputs to
``data/inputs/baseline`` did not change the scientific information consumed by
the validated historical modules. Where the canonical file format differs from
the legacy repository format, both are passed through the same production
loader before comparison.

The DAFM county-sheep hold-out has no legacy Git-tracked counterpart. Its
integrity is therefore covered by the pinned SHA256 verification in the data
manifest rather than an old-versus-new table comparison here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.cattle.panel import _load_aaa10
from goblin_spatial.land.panel import _read_aqa06
from goblin_spatial.sheep.cohorts import _read_anchors
from goblin_spatial.sheep.panel import _load_workbook
from goblin_spatial.standard_output.coefficients import load_model_mapping


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "inputs" / "baseline"


def _assert_equal(left: pd.DataFrame, right: pd.DataFrame, *, sort_by: list[str]) -> None:
    left = left.sort_values(sort_by, kind="stable").reset_index(drop=True)
    right = right.sort_values(sort_by, kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        left,
        right,
        check_dtype=False,
        check_like=False,
        check_exact=True,
    )


def _read_csv_normalised(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip().lstrip("\ufeff") for column in frame.columns]
    return frame


def test_ed_2020_packaged_file_is_byte_identical_to_validated_legacy_anchor() -> None:
    canonical = CANONICAL / "01_CSO_ED_Agricultural_Baseline_2020.csv"
    legacy = ROOT / "data" / "raw" / "cattle" / "CSO_ED_2020.csv"
    assert canonical.read_bytes() == legacy.read_bytes()


def test_aaa10_packaged_control_is_semantically_identical_to_legacy_control() -> None:
    canonical = _load_aaa10(
        CANONICAL / "01_CSO_AAA10_Cattle_County_2015_2025.csv"
    )
    legacy = _load_aaa10(
        ROOT / "data" / "raw" / "cattle" / "CSO_county_WIDE_2015_2025.csv.xz"
    )
    _assert_equal(canonical, legacy, sort_by=["Year", "County"])


def test_aaa09_packaged_workbook_is_semantically_identical_to_validated_workbook() -> None:
    canonical_crosswalk, canonical_region = _load_workbook(
        CANONICAL / "03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx"
    )
    legacy_crosswalk, legacy_region = _load_workbook(
        ROOT / "data" / "raw" / "sheep" / "CSO_Sheep_County_and_Region_WIDE_2015_2025.xlsx"
    )
    _assert_equal(canonical_crosswalk, legacy_crosswalk, sort_by=["County"])
    _assert_equal(canonical_region, legacy_region, sort_by=["Year", "Region"])


def test_dafm_breed_packaged_csv_is_semantically_identical_to_legacy_zip() -> None:
    canonical = _read_anchors(
        CANONICAL / "05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv"
    )
    legacy = _read_anchors(
        ROOT / "data" / "raw" / "sheep" / "DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.zip"
    )
    _assert_equal(canonical, legacy, sort_by=["YEAR", "CATEGORY", "County"])


def test_shared_goblin_relationships_are_identical_to_validated_control() -> None:
    canonical = _read_csv_normalised(
        CANONICAL / "05C_Cattle_Cohort_Relationships_2012_2020.csv"
    )
    legacy = _read_csv_normalised(ROOT / "data" / "controls" / "cohort2012-2020.csv")
    pd.testing.assert_frame_equal(canonical, legacy, check_dtype=False, check_exact=True)


def test_aqa06_packaged_workbook_is_semantically_identical_to_legacy_tidy_control() -> None:
    canonical = _read_aqa06(
        CANONICAL / "06_CSO_AQA06_Agricultural_Land_Use.xlsx"
    )
    legacy = _read_aqa06(
        ROOT / "data" / "raw" / "land" / "AQA06_Unpivoted_2013_2025.csv"
    )
    _assert_equal(
        canonical,
        legacy,
        sort_by=["Year", "Region", "Type of Land Use"],
    )


def test_farm_structure_packaged_control_is_identical_to_validated_control() -> None:
    canonical = _read_csv_normalised(
        CANONICAL / "06_Farm_Structure_Demographic_Controls.csv"
    )
    legacy = _read_csv_normalised(ROOT / "data" / "controls" / "06_SE_Data_Controls.csv")
    _assert_equal(canonical, legacy, sort_by=["LEVEL", "AREA", "YEAR"])


def test_standard_output_packaged_workbook_is_semantically_identical_to_mapping_csv() -> None:
    canonical = load_model_mapping(
        CANONICAL / "08_IFS2020_Standard_Output_Mapping.xlsx"
    )
    legacy = load_model_mapping(
        ROOT / "data" / "controls" / "standard_output" / "GOBLIN_SO_mapping.csv"
    )
    _assert_equal(canonical, legacy, sort_by=["MODEL_VARIABLE"])
