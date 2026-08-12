"""Tests for fixed-2020 Standard Output valuation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.standard_output import (
    add_baseline_standard_output,
    add_pathway_standard_output,
    cereal_composite_coefficients,
    fadn_region_for_county,
    load_soc2020_controls,
)


def _zero_31_row(county: str = "Mayo") -> dict[str, object]:
    row: dict[str, object] = {"County": county}
    row.update({cohort: 0 for cohort in FINAL_21_COHORTS})
    row.update({cohort: 0 for cohort in GOBLIN_SHEEP_10})
    return row


def test_correct_irish_fadn_region_mapping() -> None:
    assert fadn_region_for_county("Mayo") == "381"
    assert fadn_region_for_county("Louth") == "381"
    assert fadn_region_for_county("Cork") == "382"
    assert fadn_region_for_county("Wexford") == "382"


def test_soc2020_controls_match_source_workbook_values() -> None:
    controls = load_soc2020_controls()
    lookup = {
        (str(row.CD_PRODUCT), str(row.FADN_REGION)): float(row.SOC_EUR)
        for row in controls.itertuples(index=False)
    }

    assert lookup[("A2300G", "381")] == 876.03
    assert lookup[("A2300G", "382")] == 807.62
    assert lookup[("A2300F", "381")] == 2468.88
    assert lookup[("A2300F", "382")] == 2449.47
    assert lookup[("A4120", "381")] == 51.61
    assert lookup[("A4120", "382")] == 49.09


def test_cereal_composite_coefficients_are_reproducible() -> None:
    composite = cereal_composite_coefficients()
    assert np.isclose(composite["381"], 1582.156794611131)
    assert np.isclose(composite["382"], 1786.1348808802604)


def test_baseline_standard_output_uses_fixed_regional_coefficients() -> None:
    row = _zero_31_row("Mayo")
    row.update(
        {
            "dairy_cows": 2,
            "suckler_cows": 3,
            "Lowland ewes": 4,
            "TOTAL_CEREALS": 5.0,
            "OTHER_CROPS_HA": 7.0,
            "AGRICULTURAL_HOLDINGS": 2,
        }
    )
    out = add_baseline_standard_output(pd.DataFrame([row])).iloc[0]

    expected_livestock = 2 * 2468.88 + 3 * 876.03 + 4 * 129.82
    expected_cereals = 5 * 1582.156794611131

    assert out["FADN_REGION"] == "381"
    assert np.isclose(out["SO_LIVESTOCK_2020_EUR"], expected_livestock)
    assert np.isclose(out["SO_CEREALS_2020_EUR"], expected_cereals)
    assert np.isclose(
        out["SO_COVERED_TOTAL_2020_EUR"], expected_livestock + expected_cereals
    )
    assert out["SO_OTHER_CROPS_UNVALUED_HA"] == 7.0
    assert np.isclose(
        out["SO_COVERED_PER_HOLDING_2020_EUR"],
        (expected_livestock + expected_cereals) / 2,
    )


def test_pathway_standard_output_reports_exposure_and_null_identity() -> None:
    base = _zero_31_row("Cork")
    pathway: dict[str, object] = {"County": "Cork"}

    for cohort in FINAL_21_COHORTS:
        value = 10 if cohort == "dairy_cows" else 0
        pathway[f"BASE_COHORT_{cohort}"] = value
        pathway[f"SCENARIO_COHORT_{cohort}"] = value
    for cohort in GOBLIN_SHEEP_10:
        pathway[f"BASE_SHEEP_COHORT_{cohort}"] = 0
        pathway[f"SCENARIO_SHEEP_COHORT_{cohort}"] = 0

    null = add_pathway_standard_output(pd.DataFrame([pathway])).iloc[0]
    assert null["FADN_REGION"] == "382"
    assert np.isclose(null["SO_LIVESTOCK_EXPOSURE_2020_EUR"], 0.0)
    assert np.isclose(null["SO_LIVESTOCK_CHANGE_2020_EUR"], 0.0)

    pathway["SCENARIO_COHORT_dairy_cows"] = 8
    reduced = add_pathway_standard_output(pd.DataFrame([pathway])).iloc[0]
    expected_exposure = 2 * 2449.47
    assert np.isclose(
        reduced["SO_LIVESTOCK_EXPOSURE_2020_EUR"], expected_exposure
    )
    assert np.isclose(
        reduced["SO_LIVESTOCK_CHANGE_2020_EUR"], -expected_exposure
    )
    assert np.isclose(reduced["SO_LIVESTOCK_CHANGE_PCT"], -20.0)
