from pathlib import Path
import pytest
from goblin_spatial.config import load_config
from goblin_spatial.pipeline import build
from goblin_spatial.scenario import load_adult_endpoint_controls, run_principal_goblin_endpoint

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
ENDPOINTS = ROOT / "configs/styles_split_gas_adult_endpoints.csv"
BASE = {2020: (1_567_600, 983_500), 2025: (1_588_100, 778_800)}

@pytest.fixture(scope="module")
def master():
    cfg = load_config(CONFIG)
    if not cfg.files["cso_ed_2020"].exists():
        pytest.skip("external full-data input not present")
    return build(cfg)

@pytest.mark.full_data
@pytest.mark.parametrize("year", [2020, 2025])
@pytest.mark.parametrize("sid,dairy,suckler", [("SI_SG",1_600_000,160_000),("BE_SG",1_540_000,154_000)])
def test_styles_endpoint(master, year, sid, dairy, suckler):
    block = master.loc[master["YEAR"].eq(year)]
    bd, bs = BASE[year]
    assert (int(block["DAIRY_COW"].sum()), int(block["OTHER_COW"].sum())) == (bd, bs)
    assert bd + bs > dairy + suckler
    controls = load_adult_endpoint_controls(ENDPOINTS, scenario_id=sid, baseline_year=year)
    out = run_principal_goblin_endpoint(master, controls, expected_eds=2857, include_standard_output=False)
    assert int(out["SCENARIO_DAIRY_COW"].sum()) == dairy
    assert int(out["SCENARIO_OTHER_COW"].sum()) == suckler
    assert (out.loc[out["BASE_ADULT_COWS"] > 0, "REDUCTION_ADULT_COWS"] > 0).all()
    cattle = out["BASE_TOTAL_CATTLE"] > 0
    assert (out.loc[cattle, "SCENARIO_TOTAL_CATTLE"] < out.loc[cattle, "BASE_TOTAL_CATTLE"]).all()
    assert (dairy > bd) if sid == "SI_SG" else (dairy < bd)
