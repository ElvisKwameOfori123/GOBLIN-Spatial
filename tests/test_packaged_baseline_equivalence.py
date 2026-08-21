"""Migration audit for the packaged historical-baseline inputs.

These tests prove that moving the compact frozen inputs to
``data/inputs/baseline`` did not change the scientific information consumed by
the validated historical modules. When a frozen workbook adds provenance or
audit columns, the comparison is deliberately limited to the columns consumed
by the production baseline (or, where appropriate, to every column present in
the validated legacy control).

The DAFM county-sheep hold-out has no legacy Git-tracked counterpart. Its
integrity is therefore covered by the pinned SHA256 verification in the data
manifest rather than an old-versus-new table comparison here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.panel import _load_aaa10
from goblin_spatial.land.panel import _read_aqa06
from goblin_spatial.sheep.cohorts import _read_anchors
from goblin_spatial.sheep.panel import REGION_SOURCE_COLS, _load_workbook, _normalise_county
from goblin_spatial.standard_output.coefficients import load_model_mapping


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "inputs" / "baseline"
YEARS = set(range(2015, 2026))

SO_RUNTIME_COLUMNS = [
    "MODEL_VARIABLE",
    "DOMAIN",
    "IFS_PRODUCT_CODE",
    "SOC_EUR_381",
    "SOC_EUR_382",
    "APPLY_IN_SO",
    "IMPUTED",
    "SENSITIVITY_SOC_EUR_381",
    "SENSITIVITY_SOC_EUR_382",
]


def _assert_equal(left: pd.DataFrame, right: pd.DataFrame, *, sort_by: list[str]) -> None:
    left = left.sort_values(sort_by, kind="stable").reset_index(drop=True)
    right = right.sort_values(sort_by, kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        left,
        right,
        check_dtype=False,
        check_like=False,
        check_exact=False,
        rtol=0.0,
        atol=1e-12,
    )


def _read_csv_normalised(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip().lstrip("\ufeff") for column in frame.columns]
    return frame


def _legacy_sheep_controls() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recreate the production AAA09 inputs from the valid legacy split CSVs.

    The old combined ``.xlsx`` object in Git history is not a valid workbook on
    a fresh checkout, so it is not a trustworthy migration reference. The two
    compressed CSVs are the validated tables from which that workbook was
    assembled and remain readable in CI.
    """

    county = pd.read_csv(
        ROOT / "data" / "raw" / "sheep" / "CSO_Sheep_County_WIDE_2015_2025.csv.xz"
    )
    county.columns = [str(column).strip() for column in county.columns]
    required_county = {"County", "Region", "NUTS2"}
    assert required_county.issubset(county.columns)
    county["County"] = county["County"].map(_normalise_county)
    crosswalk = (
        county[["County", "Region", "NUTS2"]]
        .drop_duplicates()
        .sort_values("County", kind="stable")
        .reset_index(drop=True)
    )

    region = pd.read_csv(
        ROOT / "data" / "raw" / "sheep" / "CSO_Sheep_Region_WIDE_2015_2025.csv.xz"
    )
    region.columns = [str(column).strip() for column in region.columns]
    region["Year"] = pd.to_numeric(region["Year"], errors="raise").astype(int)
    region = region.loc[
        (region["Region_Level"] == "Detailed region") & region["Year"].isin(YEARS)
    ].copy()

    numeric = ["Total sheep", *REGION_SOURCE_COLS]
    for column in numeric:
        values = pd.to_numeric(region[column], errors="raise")
        region[column] = values
        region[f"{column}__HEAD"] = np.rint(values * 1000.0).astype(np.int64)

    production_columns = [
        "Year",
        "Region",
        "Region_Level",
        "UNIT",
        "Total sheep",
        *REGION_SOURCE_COLS,
        *[f"{column}__HEAD" for column in numeric],
    ]
    return crosswalk, region[production_columns].copy()


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


def test_aaa09_packaged_workbook_matches_validated_split_controls() -> None:
    canonical_crosswalk, canonical_region = _load_workbook(
        CANONICAL / "03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx"
    )
    legacy_crosswalk, legacy_region = _legacy_sheep_controls()

    region_columns = list(legacy_region.columns)
    _assert_equal(canonical_crosswalk, legacy_crosswalk, sort_by=["County"])
    _assert_equal(
        canonical_region[region_columns],
        legacy_region,
        sort_by=["Year", "Region"],
    )


def test_dafm_breed_packaged_csv_preserves_all_legacy_scientific_columns() -> None:
    canonical = _read_anchors(
        CANONICAL / "05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv"
    )
    legacy = _read_anchors(
        ROOT / "data" / "raw" / "sheep" / "DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.zip"
    )
    # The frozen CSV adds provenance/audit fields. Every column used by the
    # legacy validated control must nevertheless remain unchanged.
    _assert_equal(
        canonical[list(legacy.columns)],
        legacy,
        sort_by=["YEAR", "CATEGORY", "County"],
    )


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


def test_standard_output_packaged_workbook_preserves_runtime_mapping() -> None:
    canonical = load_model_mapping(
        CANONICAL / "08_IFS2020_Standard_Output_Mapping.xlsx"
    )
    legacy = load_model_mapping(
        ROOT / "data" / "controls" / "standard_output" / "GOBLIN_SO_mapping.csv"
    )
    # MODEL_MEANING/NOTES are documentation and were deliberately improved in
    # the frozen workbook. These nine fields are the production mapping and
    # coefficients actually used by Stage 08, and must remain unchanged.
    _assert_equal(
        canonical[SO_RUNTIME_COLUMNS],
        legacy[SO_RUNTIME_COLUMNS],
        sort_by=["MODEL_VARIABLE"],
    )
