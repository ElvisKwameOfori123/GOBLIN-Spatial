import pandas as pd

from goblin_spatial.scenario import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
    build_goblin_reconciliation,
)


def test_goblin_reconciliation_closes_controlled_totals():
    frame = pd.DataFrame({
        "CSOED": ["A", "B"],
        "MILESTONE_YEAR": [2050, 2050],
        "SCENARIO_DAIRY_COW": [40, 60],
        "SCENARIO_OTHER_COW": [20, 30],
        "SCENARIO_TOTAL_CATTLE": [200, 250],
        "GOBLIN_RELEASED_GRASSLAND_HA": [400.0, 600.0],
    })
    controls = GoblinPathwayControls(
        scenario_id="SI_SG",
        baseline_year=2020,
        milestones=(GoblinNationalMilestone(
            year=2050,
            dairy_cows=100,
            suckler_cows=50,
            total_cattle=450,
            livestock_land_release_ha=1000.0,
        ),),
    )
    audit = build_goblin_reconciliation(frame, controls)
    assert set(audit["STATUS"]) == {"CLOSED"}
    assert (audit["DIFFERENCE"] == 0).all()
