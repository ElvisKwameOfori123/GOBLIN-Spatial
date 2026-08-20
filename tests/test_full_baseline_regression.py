"""Full-data regression gates for the historical GOBLIN-Spatial baseline.

This file is executed only when the canonical compact baseline inputs are
present. It deliberately stops at Stage 09 and does not import soil, LPIS or
scenario modules.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import load_config
from goblin_spatial.pipeline import run_baseline
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


CONFIG = Path("configs/ireland_2015_2025.yaml")


def test_full_historical_baseline_through_stage09():
    cfg = load_config(CONFIG)
    baseline = run_baseline(cfg)

    assert len(baseline) == 31_427
    assert baseline["CSOED"].nunique() == 2_857
    assert set(pd.to_numeric(baseline["YEAR"], errors="raise").astype(int)) == set(
        range(2015, 2026)
    )
    assert not baseline[["YEAR", "CSOED"]].duplicated().any()

    cattle = baseline[FINAL_21_COHORTS].apply(pd.to_numeric, errors="raise")
    sheep = baseline[GOBLIN_SHEEP_10].apply(pd.to_numeric, errors="raise")
    total_cattle = pd.to_numeric(baseline["TOTAL_CATTLE"], errors="raise")
    total_sheep = pd.to_numeric(baseline["TOTAL_SHEEP"], errors="raise")

    assert np.array_equal(
        np.rint(cattle.sum(axis=1)).astype(np.int64),
        np.rint(total_cattle).astype(np.int64),
    )
    assert np.array_equal(
        np.rint(sheep.sum(axis=1)).astype(np.int64),
        np.rint(total_sheep).astype(np.int64),
    )
    assert (cattle.to_numpy(dtype=float) >= 0).all()
    assert (sheep.to_numpy(dtype=float) >= 0).all()

    land = baseline[
        ["AREA_FARMED", "ALL_GRASSLAND", "TOTAL_CEREALS", "OTHER_CROPS_HA"]
    ].apply(pd.to_numeric, errors="raise")
    closure = (
        land["ALL_GRASSLAND"]
        + land["TOTAL_CEREALS"]
        + land["OTHER_CROPS_HA"]
        - land["AREA_FARMED"]
    )
    assert float(closure.abs().max()) <= 1e-6
    assert (land.to_numpy(dtype=float) >= -1e-9).all()

    required_structure = {
        "AGRICULTURAL_HOLDINGS",
        "AVERAGE_SIZE_OF_HOLDINGS",
        "AVERAGE_AGE_OF_HOLDER",
        "MEDIAN_AGE_OF_HOLDER",
    }
    assert required_structure.issubset(baseline.columns)

    # Stage 08 is the final value-enrichment stage. Its fixed-2020 valuation
    # must exist for every ED-year while leaving the activity accounting above
    # intact.
    required_so = {
        "SO_LIVESTOCK_2020_EUR",
        "SO_CEREALS_2020_EUR",
        "SO_OTHER_CROPS_2020_EUR",
        "SO_COVERED_TOTAL_2020_EUR",
    }
    assert required_so.issubset(baseline.columns)
    for column in required_so:
        values = pd.to_numeric(baseline[column], errors="raise")
        assert values.notna().all()
        assert (values >= -1e-9).all()

    # Stage 09 is a separate long-form baseline output.
    signature_value = cfg.raw.get("outputs", {}).get(
        "ed_signatures", "data/processed/09_GOBLIN_Spatial_ED_Cohort_Signatures_2020.csv"
    )
    signature_path = Path(signature_value)
    if not signature_path.is_absolute():
        signature_path = cfg.project_root / signature_path
    assert signature_path.exists()

    signatures = pd.read_csv(signature_path)
    assert len(signatures) == 2_857 * 19
    assert signatures["CSOED"].nunique() == 2_857
    assert signatures["COHORT"].nunique() == 19
    assert not signatures[["CSOED", "COHORT"]].duplicated().any()
    assert set(signatures["COHORT_SPATIAL_ROLE"]).issubset(
        {"LOCAL_ED", "COUNTY_RECEIVER", "NATIONAL_ORPHAN", "NONE"}
    )
