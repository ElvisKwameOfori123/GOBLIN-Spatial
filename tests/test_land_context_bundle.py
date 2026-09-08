"""Repository gate for the frozen 2020 Colm + LPIS runtime context."""

from pathlib import Path

from goblin_spatial.land.colm_lpis_context import (
    COLM_PHYSICAL_FILE,
    COLM_PHYSICAL_SHA256,
    LAND_CONTEXT_EXPECTED_COLUMNS,
    LAND_CONTEXT_EXPECTED_EDS,
    LPIS_CONTEXT_FILE,
    LPIS_CONTEXT_SHA256,
    read_colm_lpis_context,
)
from goblin_spatial.data_fetch import sha256_file

BUNDLE = Path("data/controls/land/ED_Land_Context_2020")


def test_exact_runtime_component_files_are_tracked() -> None:
    expected = {COLM_PHYSICAL_FILE, LPIS_CONTEXT_FILE, "README.md", "manifest.json"}
    assert {path.name for path in BUNDLE.iterdir() if path.is_file()} == expected


def test_runtime_component_hashes_and_contract() -> None:
    assert sha256_file(BUNDLE / COLM_PHYSICAL_FILE) == COLM_PHYSICAL_SHA256
    assert sha256_file(BUNDLE / LPIS_CONTEXT_FILE) == LPIS_CONTEXT_SHA256
    frame = read_colm_lpis_context(BUNDLE, verify_sha256=True)
    assert len(frame) == LAND_CONTEXT_EXPECTED_EDS
    assert frame["CSOED"].nunique() == LAND_CONTEXT_EXPECTED_EDS
    assert len(frame.columns) == LAND_CONTEXT_EXPECTED_COLUMNS
