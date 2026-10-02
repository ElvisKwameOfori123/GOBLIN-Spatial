"""Tests for transparent historical validation diagnostics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import (
    BXB_COHORTS,
    DXB_COHORTS,
    DXD_COHORTS,
    FOLLOWER_COHORTS,
)
from goblin_spatial.validation.historical import (
    sheep_anchor_holdout,
    spearman_rank,
    temporal_rank_stability,
    validate_achill_benchmark,
    validate_achill_land_benchmark,
    validate_dafm_sheep_counties,
)


def test_spearman_rank_is_order_based():
    observed = pd.Series([10, 20, 30, 40])
    predicted = pd.Series([100, 200, 300, 400])
    assert np.isclose(spearman_rank(observed, predicted), 1.0)


def test_achill_benchmark_matches_repository_2020_anchor():
    master = pd.read_csv(
        "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv"
    ).rename(columns={"CENSUS_YEAR": "YEAR"})
    benchmark = Path(
        "data/validation/external/achill_north/ED_Livestock_2020.csv"
    )

    diagnostics, summary, spatial = validate_achill_benchmark(
        master,
        benchmark,
        county="Mayo",
        year=2020,
    )

    assert len(diagnostics) == 23 * 4
    assert set(summary["VARIABLE"]) == {
        "DAIRY_COW",
        "OTHER_COW",
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
    }
    assert len(spatial) == 23
    assert diagnostics["MODEL_VALUE"].notna().all()
    assert diagnostics["BENCHMARK_VALUE"].notna().all()

    # Both sources ultimately use the 2020 Census of Agriculture, so this is
    # a reproducibility/application check rather than independent validation.
    assert float(diagnostics.loc[diagnostics["VARIABLE"].ne("DAIRY_COW"), "ERROR"].abs().max()) == 0.0

    explicit = spatial.dropna(subset=["Overlap fraction"]).copy()
    assert len(explicit) >= 15
    assert float(explicit["CATTLE_AREA_ERROR"].abs().max()) <= 2.0
    assert float(explicit["SHEEP_AREA_ERROR"].abs().max()) <= 6.0


def test_achill_land_benchmark_matches_repository_2020_anchor():
    master = pd.read_csv(
        "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv"
    ).rename(columns={"CENSUS_YEAR": "YEAR"})
    diagnostics, summary = validate_achill_land_benchmark(
        master,
        "data/validation/external/achill_north/ED_Land_2020.csv",
        county="Mayo",
        year=2020,
    )

    assert len(diagnostics) == 23 * 5
    assert set(summary["VARIABLE"]) == {
        "AGRICULTURAL_HOLDINGS",
        "AVERAGE_SIZE_OF_HOLDINGS",
        "AREA_FARMED",
        "TOTAL_CEREALS",
        "ALL_GRASSLAND",
    }
    assert diagnostics["MODEL_VALUE"].notna().all()
    assert diagnostics["BENCHMARK_VALUE"].notna().all()
    assert float(diagnostics["ERROR"].abs().max()) == 0.0


def test_dafm_county_sheep_validation_covers_all_2020_counties():
    master = pd.read_csv(
        "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv"
    ).rename(columns={"CENSUS_YEAR": "YEAR"})
    diagnostics, summary = validate_dafm_sheep_counties(
        master,
        "data/inputs/baseline/03_0_DAFM_Sheep_County_Totals_2015_2020_2022_2025.csv",
    )

    assert len(diagnostics) == 26
    assert diagnostics["County"].nunique() == 26
    assert set(diagnostics["YEAR"]) == {2020}
    assert len(summary) == 1
    assert int(summary.loc[0, "N"]) == 26
    assert np.isfinite(float(summary.loc[0, "MAE"]))
    assert np.isfinite(float(summary.loc[0, "SPEARMAN_RHO"]))


def test_sheep_2022_holdout_uses_2020_and_2025_only():
    diagnostics, summary = sheep_anchor_holdout(
        "data/inputs/baseline/05A_DAFM_Sheep_Breed_Anchors_2016_2020_2022_2025.csv",
        holdout_year=2022,
        start_year=2020,
        end_year=2025,
    )

    assert len(diagnostics) == 26 * 3 * 4
    assert diagnostics["County"].nunique() == 26
    assert set(diagnostics["CATEGORY"]) == {"EWES", "RAMS", "OTHER"}
    assert set(diagnostics["BREED_GROUP"]) == {
        "MOUNTAIN",
        "MOUNTAIN_CROSS",
        "LOWLAND",
        "LOWLAND_CROSS",
    }
    assert set(diagnostics["HOLDOUT_YEAR"]) == {2022}
    assert len(summary) == 4
    assert summary["MAE_PP"].notna().all()
    assert summary["SPEARMAN_RHO"].notna().all()


def _row(year: int, ed: str, scale: int) -> dict[str, object]:
    row: dict[str, object] = {
        "YEAR": year,
        "CSOED": ed,
        "DAIRY_COW": 10 * scale,
        "OTHER_COW": 5 * scale,
        "TOTAL_CATTLE": 60 * scale,
        "TOTAL_SHEEP": 40 * scale,
    }
    for cohort in FOLLOWER_COHORTS:
        row[cohort] = scale
    # Preserve different origin mixes while keeping monotonic ED ordering.
    for cohort in DXD_COHORTS:
        row[cohort] = 2 * scale
    for cohort in DXB_COHORTS:
        row[cohort] = 3 * scale
    for cohort in BXB_COHORTS:
        row[cohort] = 4 * scale
    return row


def test_temporal_rank_stability_detects_preserved_ordering():
    master = pd.DataFrame(
        [
            _row(2020, "1", 1),
            _row(2020, "2", 2),
            _row(2020, "3", 3),
            _row(2021, "1", 2),
            _row(2021, "2", 4),
            _row(2021, "3", 6),
        ]
    )

    stability = temporal_rank_stability(
        master,
        columns=("TOTAL_CATTLE", "TOTAL_SHEEP"),
    )
    assert len(stability) == 2
    assert set(stability["YEAR_FROM"]) == {2020}
    assert set(stability["YEAR_TO"]) == {2021}
    assert np.allclose(stability["SPEARMAN_RHO"], 1.0, equal_nan=False)
