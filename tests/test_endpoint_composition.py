import numpy as np

from goblin_spatial.scenario.endpoint_composition import reconcile_endpoint_composition


def test_composition_shift_can_raise_dairy_without_seeding_categories():
    dairy = np.array([40, 30, 0, 20], dtype=np.int64)
    suckler = np.array([0, 30, 40, 20], dtype=np.int64)
    # Baseline adults = 180; retained endpoint = 130. Every active ED has room to decline.
    preferred = np.array([30, 40, 30, 30], dtype=np.int64)
    preferred = preferred - np.array([0, 5, 0, 5], dtype=np.int64)  # sum = 130

    scenario_d, scenario_s = reconcile_endpoint_composition(
        dairy, suckler, preferred, target_dairy=95, target_suckler=35
    )

    assert scenario_d.sum() == 95
    assert scenario_s.sum() == 35
    assert scenario_d.sum() > dairy.sum()
    assert scenario_d[2] == 0
    assert scenario_s[0] == 0
    assert ((scenario_d + scenario_s)[dairy + suckler > 0] < (dairy + suckler)[dairy + suckler > 0]).all()
