"""Tests for fixed-2020 Standard Output valuation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.baseline.standard_output import add_standard_output
from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.config import load_config
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.standard_output import (
    COHORT_PRODUCT_CODE,
    add_baseline_standard_output,
    add_pathway_standard_output,
    cereal_composite_coefficients,
    fadn_region_for_county,
    load_model_mapping,
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
    assert fadn_region_for_county("Laois") == "381"
    assert fadn_region_for_county("Cork") == "382"
    assert fadn_region_for_county("Tipperary") == "382"
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
    assert lookup[("A4110K", "381")] == 129.82
    assert lookup[("A4110K", "382")] == 122.55
    assert lookup[("A4120", "381")] == 51.61
    assert lookup[("A4120", "382")] == 49.09


def test_model_mapping_covers_all_31_cohorts_without_parent_sheep_code() -> None:
    mapping = load_model_mapping()
    livestock = mapping.loc[mapping["DOMAIN"].isin(["CATTLE", "SHEEP"])]

    assert len(COHORT_PRODUCT_CODE) == 31
    assert set(livestock["MODEL_VARIABLE"]) == set(COHORT_PRODUCT_CODE)
    assert set(livestock["IFS_PRODUCT_CODE"]) <= {
        "A2010", "A2120", "A2130", "A2220", "A2230",
        "A2300F", "A2300G", "A4110K", "A4120",
    }
    assert "A4100" not in set(livestock["IFS_PRODUCT_CODE"])

    by_variable = livestock.set_index("MODEL_VARIABLE")
    assert by_variable.loc["Lowland ewes", "IFS_PRODUCT_CODE"] == "A4110K"
    assert by_variable.loc["Upland ewes", "IFS_PRODUCT_CODE"] == "A4110K"
    other_sheep = set(GOBLIN_SHEEP_10) - {"Lowland ewes", "Upland ewes"}
    assert set(by_variable.loc[sorted(other_sheep), "IFS_PRODUCT_CODE"]) == {"A4120"}


def test_cereal_composite_coefficients_are_reproducible() -> None:
    composite = cereal_composite_coefficients()
    assert np.isclose(composite["381"], 1582.156794611131)
    assert np.isclose(composite["382"], 1786.1348808802604)

    mapping = load_model_mapping().set_index("MODEL_VARIABLE")
    assert np.isclose(mapping.loc["TOTAL_CEREALS", "SOC_EUR_381"], composite["381"])
    assert np.isclose(mapping.loc["TOTAL_CEREALS", "SOC_EUR_382"], composite["382"])


def test_other_crop_composite_and_conservative_values_are_frozen() -> None:
    mapping = load_model_mapping().set_index("MODEL_VARIABLE")
    row = mapping.loc["OTHER_CROPS_HA"]
    assert row["IMPUTED"] == "YES"
    assert np.isclose(row["SOC_EUR_381"], 1915.1395145631068)
    assert np.isclose(row["SOC_EUR_382"], 3160.0518068965516)
    assert np.isclose(row["SENSITIVITY_SOC_EUR_381"], 1190.5161650485436)
    assert np.isclose(row["SENSITIVITY_SOC_EUR_382"], 2902.2530344827587)


def test_baseline_standard_output_uses_mapping_csv_and_values_other_crops() -> None:
    row = _zero_31_row("Mayo")
    row.update(
        {
            "dairy_cows": 2,
            "suckler_cows": 3,
            "Lowland ewes": 4,
            "Upland ewes": 5,
            "TOTAL_CEREALS": 5.0,
            "OTHER_CROPS_HA": 7.0,
            "AGRICULTURAL_HOLDINGS": 2,
        }
    )
    out = add_baseline_standard_output(pd.DataFrame([row])).iloc[0]

    expected_livestock = (
        2 * 2468.88
        + 3 * 876.03
        + 4 * 129.82
        + 5 * 129.82
    )
    expected_cereals = 5 * 1582.156794611131
    expected_other = 7 * 1915.1395145631068
    expected_other_conservative = 7 * 1190.5161650485436
    expected_total = expected_livestock + expected_cereals + expected_other
    expected_total_conservative = (
        expected_livestock + expected_cereals + expected_other_conservative
    )

    assert out["FADN_REGION"] == "381"
    assert np.isclose(out["SO_LIVESTOCK_2020_EUR"], expected_livestock)
    assert np.isclose(out["SO_CEREALS_2020_EUR"], expected_cereals)
    assert np.isclose(out["SO_OTHER_CROPS_2020_EUR"], expected_other)
    assert np.isclose(
        out["SO_OTHER_CROPS_CONSERVATIVE_2020_EUR"],
        expected_other_conservative,
    )
    assert out["SO_OTHER_CROPS_IMPUTED_HA"] == 7.0
    assert np.isclose(out["SO_COVERED_TOTAL_2020_EUR"], expected_total)
    assert np.isclose(
        out["SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR"],
        expected_total_conservative,
    )
    assert np.isclose(
        out["SO_COVERED_PER_HOLDING_2020_EUR"], expected_total / 2
    )


def test_pathway_standard_output_reports_exposure_and_null_identity() -> None:
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



def test_stage08_wrapper_preserves_activity_fields_and_accounting() -> None:
    cfg = load_config("configs/ireland_2015_2025.yaml")
    row = _zero_31_row("Mayo")
    row.update(
        {
            "YEAR": 2020,
            "CSOED": "TEST001",
            "TOTAL_CEREALS": 5.0,
            "OTHER_CROPS_HA": 7.0,
            "AGRICULTURAL_HOLDINGS": 2,
            "dairy_cows": 2,
            "suckler_cows": 3,
            "bulls": 1,
            "Lowland ewes": 4,
            "Upland ewes": 5,
        }
    )
    baseline = pd.DataFrame([row])
    valued = add_standard_output(baseline, cfg)

    assert valued[baseline.columns].equals(baseline)
    assert valued.loc[0, "FADN_REGION"] == "381"

    livestock_components = (
        valued.loc[0, "SO_DAIRY_COWS_2020_EUR"]
        + valued.loc[0, "SO_SUCKLER_COWS_2020_EUR"]
        + valued.loc[0, "SO_BULLS_2020_EUR"]
        + valued.loc[0, "SO_FOLLOWERS_2020_EUR"]
        + valued.loc[0, "SO_SHEEP_2020_EUR"]
    )
    assert np.isclose(
        valued.loc[0, "SO_LIVESTOCK_2020_EUR"], livestock_components
    )
    assert np.isclose(
        valued.loc[0, "SO_COVERED_TOTAL_2020_EUR"],
        valued.loc[0, "SO_LIVESTOCK_2020_EUR"]
        + valued.loc[0, "SO_CEREALS_2020_EUR"]
        + valued.loc[0, "SO_OTHER_CROPS_2020_EUR"],
    )
    assert np.isclose(
        valued.loc[0, "SO_COVERED_PER_HOLDING_2020_EUR"],
        valued.loc[0, "SO_COVERED_TOTAL_2020_EUR"] / 2,
    )
