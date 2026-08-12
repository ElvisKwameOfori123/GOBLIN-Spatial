"""Full-data regression test against the frozen validated Ireland build."""

from pathlib import Path

import numpy as np
import pytest

from goblin_spatial.config import load_config
from goblin_spatial.export import build_clean_sheets
from goblin_spatial.pipeline import build


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


@pytest.mark.full_data
def test_complete_build_regression() -> None:
    config = load_config(CONFIG)
    for key in ("cso_ed_2020", "cso_land"):
        if not config.files[key].exists():
            pytest.skip(f"external full-data input not present: {config.files[key]}")

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
    assert np.isclose(master.loc[master["YEAR"] == 2020, "AREA_FARMED"].sum(), 4504866.7)

    # SO is downstream valuation: it must exist, remain non-negative and leave
    # the already-validated biological/land schemas unchanged.
    required_so = {
        "FADN_REGION",
        "SO_DAIRY_COWS_2020_EUR",
        "SO_SUCKLER_COWS_2020_EUR",
        "SO_FOLLOWERS_2020_EUR",
        "SO_SHEEP_2020_EUR",
        "SO_LIVESTOCK_2020_EUR",
        "SO_CEREALS_2020_EUR",
        "SO_COVERED_TOTAL_2020_EUR",
        "SO_OTHER_CROPS_IMPUTED_HA",
    }
    assert required_so.issubset(master.columns)
    assert set(master["FADN_REGION"].astype(str).unique()) == {"381", "382"}
    assert (master[list(required_so - {"FADN_REGION"})] >= 0).all().all()

    sheets = build_clean_sheets(master)
    assert sheets["CSO_All_Years"].shape == (31427, 35)
    assert sheets["GOBLIN_All_Years"].shape == (31427, 50)
    assert sheets["CSO_2020"].shape == (2857, 35)
    assert sheets["GOBLIN_2020"].shape == (2857, 50)
    assert "Standard_Output" in sheets
    assert len(sheets["Standard_Output"]) == 31427
    assert "SO_COVERED_TOTAL_2020_EUR" in sheets["Standard_Output"].columns
    assert "SO_OTHER_CROPS_IMPUTED_HA" in sheets["Standard_Output"].columns
