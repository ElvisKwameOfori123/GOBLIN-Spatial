"""Full-data regression test against the frozen validated Ireland build."""

from pathlib import Path

import numpy as np
import pytest

from goblin_spatial.config import load_config
from goblin_spatial.export import build_clean_sheets
from goblin_spatial.pipeline import build
from goblin_spatial.scenario import (
    PRE_ADULT_CATTLE_COHORTS,
    make_cattle_scenario,
    run_cattle_study,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"

EXPECTED_CATTLE = {
    2015: 6963800,
    2016: 7221100,
    2017: 7363500,
    2018: 7348200,
    2019: 7208600,
    2020: 7314500,
    2021: 7358700,
    2022: 7396300,
    2023: 7341500,
    2024: 7183300,
    2025: 6904800,
}
EXPECTED_SHEEP = {
    2015: 5138700,
    2016: 5179100,
    2017: 5197100,
    2018: 5109300,
    2019: 5145700,
    2020: 5520200,
    2021: 5609400,
    2022: 5967700,
    2023: 5674400,
    2024: 5175700,
    2025: 5098500,
}
EXPECTED_HOLDINGS = {
    2015: 138079,
    2016: 137401,
    2017: 136771,
    2018: 136141,
    2019: 135511,
    2020: 134881,
    2021: 134261,
    2022: 133640,
    2023: 133020,
    2024: 133020,
    2025: 133020,
}


def _assert_cattle_scenario_closure(
    result, *, baseline_year: int, dairy: float, suckler: float
) -> None:
    national = result.national.set_index("MILESTONE_YEAR")
    target = national.loc[2050]

    base_dairy = int(target["BASE_DAIRY_COW"])
    base_suckler = int(target["BASE_OTHER_COW"])
    assert int(target["SCENARIO_DAIRY_COW"]) == int(
        round(base_dairy * (1.0 - dairy))
    )
    assert int(target["SCENARIO_OTHER_COW"]) == int(
        round(base_suckler * (1.0 - suckler))
    )

    # Sheep are context in this cattle study and must remain unchanged.
    assert int(target["SCENARIO_TOTAL_SHEEP"]) == int(target["BASE_TOTAL_SHEEP"])

    assert set(result.ed["PATHWAY_BASELINE_YEAR"]) == {baseline_year}
    assert (result.ed["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] >= 0).all()
    assert (result.ed["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"] >= 0).all()


@pytest.mark.full_data
def test_complete_build_regression() -> None:
    config = load_config(CONFIG)
    for key in ("cso_ed_2020", "cso_land"):
        if not config.files[key].exists():
            pytest.skip(f"external full-data input not present: {config.files[key]}")

    # Historical baseline: livestock/cohorts + land + SE only.
    master = build(config)
    assert len(master) == 31427
    assert master["CSOED"].nunique() == 2857
    assert set(master["YEAR"].unique()) == set(range(2015, 2026))

    cattle = master.groupby("YEAR")["TOTAL_CATTLE"].sum().astype(int).to_dict()
    sheep = master.groupby("YEAR")["TOTAL_SHEEP"].sum().astype(int).to_dict()
    holdings = (
        master.groupby("YEAR")["AGRICULTURAL_HOLDINGS"].sum().astype(int).to_dict()
    )
    assert cattle == EXPECTED_CATTLE
    assert sheep == EXPECTED_SHEEP
    assert holdings == EXPECTED_HOLDINGS

    land_diff = (
        master["ALL_GRASSLAND"]
        + master["TOTAL_CEREALS"]
        + master["OTHER_CROPS_HA"]
        - master["AREA_FARMED"]
    )
    assert float(land_diff.abs().max()) < 1e-6
    assert np.isclose(
        master.loc[master["YEAR"] == 2020, "AREA_FARMED"].sum(), 4504866.7
    )

    # Soil and Standard Output are deliberately downstream of the historical
    # baseline and must not silently redefine it.
    assert "GOBLIN_SOIL_G1_SHARE" not in master.columns
    assert "SO_LIVESTOCK_2020_EUR" not in master.columns

    sheets = build_clean_sheets(master)
    assert sheets["CSO_All_Years"].shape == (31427, 35)
    assert sheets["GOBLIN_All_Years"].shape == (31427, 50)
    assert sheets["CSO_2020"].shape == (2857, 35)
    assert sheets["GOBLIN_2020"].shape == (2857, 50)
    assert "Standard_Output" not in sheets
    assert "Soil_Profile" not in sheets

    # Real-data scenario acceptance test. The principal study changes cattle
    # only; sheep remain fixed context. Standard Output is attached here, after
    # the physical herd is solved, not in the historical baseline.
    scenarios = [
        make_cattle_scenario(
            name="DAIRY_30_FROM_2020",
            baseline_year=2020,
            target_year=2050,
            dairy_reduction=0.30,
            suckler_reduction=0.0,
        ),
        make_cattle_scenario(
            name="SUCKLER_30_FROM_2020",
            baseline_year=2020,
            target_year=2050,
            dairy_reduction=0.0,
            suckler_reduction=0.30,
        ),
        make_cattle_scenario(
            name="BOTH_30_FROM_2020",
            baseline_year=2020,
            target_year=2050,
            dairy_reduction=0.30,
            suckler_reduction=0.30,
        ),
        make_cattle_scenario(
            name="BOTH_30_FROM_2025",
            baseline_year=2025,
            target_year=2050,
            dairy_reduction=0.30,
            suckler_reduction=0.30,
        ),
    ]

    runs = {}
    for definition in scenarios:
        run = run_cattle_study(
            master,
            definition,
            config=config,
            expected_eds=2857,
            include_standard_output=True,
        )
        runs[definition.name] = run
        _assert_cattle_scenario_closure(
            run.scenario,
            baseline_year=definition.baseline_year,
            dairy=definition.dairy_reduction,
            suckler=definition.suckler_reduction,
        )

        # Every real run must expose the exact ED x 18 pre-adult relationship
        # table and the milestone-specific long cohort audit.
        assert len(run.dependency) == 2857 * 18
        assert run.dependency["CSOED"].nunique() == 2857
        assert set(run.dependency["COHORT"].unique()) == set(PRE_ADULT_CATTLE_COHORTS)
        expected_audit_rows = len(run.scenario.schedule) * 2857 * 18
        assert len(run.cohort_audit) == expected_audit_rows
        assert not run.cohort_audit[["CSOED", "MILESTONE_YEAR", "COHORT"]].duplicated().any()

        # Standard Output is downstream and must be available on the scenario
        # result without appearing in the historical baseline.
        assert "SO_LIVESTOCK_EXPOSURE_2020_EUR" in run.scenario.ed.columns
        assert (
            run.scenario.ed["SO_LIVESTOCK_EXPOSURE_2020_EUR"] >= -1e-6
        ).all()

    # Dairy-only contraction must not mechanically reduce the BxB follower
    # family; suckler-only contraction must not mechanically reduce DxD/DxB.
    dairy = runs["DAIRY_30_FROM_2020"].scenario.ed
    suckler = runs["SUCKLER_30_FROM_2020"].scenario.ed
    bxb_reductions = [
        c for c in dairy.columns if c.startswith("CUMULATIVE_REDUCTION_COHORT_BxB_")
    ]
    dairy_origin_reductions = [
        c
        for c in suckler.columns
        if c.startswith("CUMULATIVE_REDUCTION_COHORT_DxD_")
        or c.startswith("CUMULATIVE_REDUCTION_COHORT_DxB_")
    ]
    assert bxb_reductions and int(dairy[bxb_reductions].to_numpy().sum()) == 0
    assert dairy_origin_reductions and int(
        suckler[dairy_origin_reductions].to_numpy().sum()
    ) == 0

    # Real Ireland must contain receiver/orphan ED x cohort cases: young stock
    # with no matching parent adults locally but a relevant parent pool in the
    # same county. Those rows must still receive a positive ripple when county
    # breeding adults contract.
    both_run = runs["BOTH_30_FROM_2020"]
    dependency = both_run.dependency
    receivers = dependency["COHORT_SPATIAL_ROLE"] == "COUNTY_RECEIVER"
    assert receivers.any()
    assert (dependency.loc[receivers, "BASE_ORIGIN_ADULTS"] == 0).all()
    assert (dependency.loc[receivers, "COUNTY_ORIGIN_ADULT_TOTAL"] > 0).all()

    audit = both_run.cohort_audit
    receiver_audit = audit["COHORT_SPATIAL_ROLE"] == "COUNTY_RECEIVER"
    assert receiver_audit.any()
    assert (audit.loc[receiver_audit, "CUMULATIVE_REDUCTION_HEAD"] > 0).any()
