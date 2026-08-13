from pathlib import Path

import pytest

from goblin_spatial.config import load_config
from goblin_spatial.pipeline import build
from goblin_spatial.scenario import load_adult_endpoint_controls, run_principal_goblin_endpoint

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
ENDPOINTS = ROOT / "configs/styles_split_gas_adult_endpoints.csv"


@pytest.mark.full_data
@pytest.mark.parametrize("baseline_year", [2020, 2025])
@pytest.mark.parametrize(
    "scenario_id,target_dairy,target_suckler",
    [("SI_SG", 1_600_000, 160_000), ("BE_SG", 1_540_000, 154_000)],
)
def test_styles_endpoint_closure(
    baseline_year: int,
    scenario_id: str,
    target_dairy: int,
    target_suckler: int,
) -> None:
    config = load_config(CONFIG)
    if not config.files["cso_ed_2020"].exists():
        pytest.skip("external full-data input not present")
    master = build(config)
    baseline = master.loc[master["YEAR"].eq(baseline_year)]

    assert int(baseline["DAIRY_COW"].sum()) >= target_dairy
    assert int(baseline["OTHER_COW"].sum()) >= target_suckler

    controls = load_adult_endpoint_controls(
        ENDPOINTS,
        scenario_id=scenario_id,
        baseline_year=baseline_year,
    )
    out = run_principal_goblin_endpoint(
        master,
        controls,
        expected_eds=2857,
        include_standard_output=False,
    )

    assert len(out) == 2857
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == target_dairy
    assert int(out["SCENARIO_OTHER_COW"].sum()) == target_suckler
    assert (out.loc[out["BASE_DAIRY_COW"] > 0, "CUMULATIVE_REDUCTION_DAIRY_COW"] > 0).all()
    assert (out.loc[out["BASE_OTHER_COW"] > 0, "CUMULATIVE_REDUCTION_OTHER_COW"] > 0).all()
    assert (out["SCENARIO_TOTAL_CATTLE"] <= out["BASE_TOTAL_CATTLE"]).all()
