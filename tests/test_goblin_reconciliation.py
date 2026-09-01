import pandas as pd

from goblin_spatial.scenario import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
    build_goblin_reconciliation,
)


def _controls() -> GoblinPathwayControls:
    return GoblinPathwayControls(
        scenario_id="SI_SG",
        baseline_year=2020,
        milestones=(
            GoblinNationalMilestone(
                year=2050,
                dairy_cows=100,
                suckler_cows=50,
                total_cattle=450,
                livestock_land_release_ha=1000.0,
            ),
        ),
    )


def test_goblin_reconciliation_closes_controlled_totals():
    frame = pd.DataFrame(
        {
            "CSOED": ["A", "B"],
            "MILESTONE_YEAR": [2050, 2050],
            "SCENARIO_DAIRY_COW": [40, 60],
            "SCENARIO_OTHER_COW": [20, 30],
            "SCENARIO_TOTAL_CATTLE": [200, 250],
            "GOBLIN_RELEASED_GRASSLAND_HA": [400.0, 600.0],
        }
    )
    audit = build_goblin_reconciliation(frame, _controls())
    assert set(audit["STATUS"]) == {"CLOSED"}
    assert (audit["DIFFERENCE"] == 0).all()


def test_goblin_reconciliation_keeps_dm_land_balance_diagnostic_only():
    frame = pd.DataFrame(
        {
            "CSOED": ["A", "B"],
            "MILESTONE_YEAR": [2050, 2050],
            "SCENARIO_DAIRY_COW": [40, 60],
            "SCENARIO_OTHER_COW": [20, 30],
            "SCENARIO_TOTAL_CATTLE": [200, 250],
            "GOBLIN_RELEASED_GRASSLAND_HA": [400.0, 600.0],
            "SIGNED_GRASSLAND_BALANCE_HA": [450.0, 350.0],
            "POTENTIAL_SPARED_GRASSLAND_HA": [450.0, 400.0],
            "ADDITIONAL_GRASSLAND_REQUIRED_HA": [0.0, 50.0],
        }
    )

    audit = build_goblin_reconciliation(frame, _controls())
    closed = audit.loc[audit["STATUS"].eq("CLOSED")]
    diagnostic = audit.loc[audit["STATUS"].eq("DIAGNOSTIC_ONLY")]

    assert (closed["DIFFERENCE"] == 0).all()
    assert set(diagnostic["VARIABLE"]) == {
        "DM_IMPLIED_NET_LAND_RELEASE_HA",
        "DM_IMPLIED_GROSS_POTENTIAL_RELEASE_HA",
        "DM_IMPLIED_GROSS_ADDITIONAL_REQUIRED_HA",
        "DM_IMPLIED_GROSS_SPATIAL_MOVEMENT_HA",
    }

    net = diagnostic.loc[
        diagnostic["VARIABLE"].eq("DM_IMPLIED_NET_LAND_RELEASE_HA")
    ].iloc[0]
    assert net["GOBLIN_TARGET"] == 1000.0
    assert net["ED_SPATIAL_SUM"] == 800.0
    assert net["DIFFERENCE"] == -200.0

    gross = diagnostic.set_index("VARIABLE")["ED_SPATIAL_SUM"]
    assert gross["DM_IMPLIED_GROSS_POTENTIAL_RELEASE_HA"] == 850.0
    assert gross["DM_IMPLIED_GROSS_ADDITIONAL_REQUIRED_HA"] == 50.0
    assert gross["DM_IMPLIED_GROSS_SPATIAL_MOVEMENT_HA"] == 900.0
