import pandas as pd
import pytest

from goblin_spatial.scenario.cattle_study import make_cattle_scenario_from_goblin_endpoint
from goblin_spatial.scenario.goblin_controls import GoblinNationalMilestone, GoblinPathwayControls


def test_endpoint_bridge_uses_selected_baseline_distance():
    panel = pd.DataFrame([
        {"YEAR": 2020, "CSOED": "A", "DAIRY_COW": 100, "OTHER_COW": 50},
        {"YEAR": 2020, "CSOED": "B", "DAIRY_COW": 100, "OTHER_COW": 50},
        {"YEAR": 2025, "CSOED": "A", "DAIRY_COW": 90, "OTHER_COW": 40},
        {"YEAR": 2025, "CSOED": "B", "DAIRY_COW": 90, "OTHER_COW": 40},
    ])
    endpoint = GoblinNationalMilestone(year=2050, dairy_cows=160, suckler_cows=60)
    c20 = GoblinPathwayControls("SI_SG", 2020, (endpoint,))
    c25 = GoblinPathwayControls("SI_SG", 2025, (endpoint,))

    s20 = make_cattle_scenario_from_goblin_endpoint(panel, c20, expected_eds=2)
    s25 = make_cattle_scenario_from_goblin_endpoint(panel, c25, expected_eds=2)

    assert s20.dairy_reduction == pytest.approx(0.20)
    assert s20.suckler_reduction == pytest.approx(0.40)
    assert s25.dairy_reduction == pytest.approx(20 / 180)
    assert s25.suckler_reduction == pytest.approx(20 / 80)
    assert s20.sheep_reduction == s25.sheep_reduction == 0.0
