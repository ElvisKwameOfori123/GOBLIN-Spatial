from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.land.sc2_colm_direct import COLM_PHYSICAL_CATEGORIES
from goblin_spatial.land.sc3_colm_allocation import SC3_USES, STAGE_A_USES
from goblin_spatial.land.sc3_feasible_geographies import (
    exact_colm_sc3_ed_use_bounds,
    sample_colm_sc3_feasible_geographies,
)


def _symmetric_reference() -> pd.DataFrame:
    """Reference solution where the same forest end-use could sit in either ED."""

    frame = pd.DataFrame(
        {
            "CSOED": ["E1", "E2"],
            "County": ["A", "B"],
            "GOBLIN_RELEASED_GRASSLAND_HA": [100.0, 100.0],
        }
    )
    for category in COLM_PHYSICAL_CATEGORIES:
        frame[f"COLM_RELEASED_{category}_HA"] = (
            [100.0, 100.0] if category == "DEEP_WELL_DRAINED" else [0.0, 0.0]
        )

    for use in SC3_USES:
        frame[f"SC3_{use}_ALLOCATED_HA"] = (
            [100.0, 0.0] if use == "FOREST" else [0.0, 0.0]
        )
        frame[f"SC3_{use}_NATIONAL_REALISED_HA"] = (
            100.0 if use == "FOREST" else 0.0
        )
        for category in COLM_PHYSICAL_CATEGORIES:
            frame[f"SC3_{use}_{category}_HA"] = (
                [100.0, 0.0]
                if use == "FOREST" and category == "DEEP_WELL_DRAINED"
                else [0.0, 0.0]
            )
    return frame


def _rules() -> dict[str, dict[str, float]]:
    rules = {
        use: {category: 0.0 for category in COLM_PHYSICAL_CATEGORIES}
        for use in STAGE_A_USES
    }
    rules["FOREST"]["DEEP_WELL_DRAINED"] = 1.0
    return rules


def test_sampled_geographies_preserve_same_national_end_use_vector() -> None:
    ensemble = sample_colm_sc3_feasible_geographies(
        _symmetric_reference(),
        eligibility_rules=_rules(),
        n_alternatives=4,
        seed=123,
    )

    assert set(ensemble.allocations["SOLUTION_ID"]) >= {"REFERENCE", "ALT_001"}
    for _, solution in ensemble.allocations.groupby("SOLUTION_ID"):
        realised = solution.groupby("USE")["ALLOCATED_HA"].sum()
        assert realised["FOREST"] == pytest.approx(100.0)
        for use in set(SC3_USES) - {"FOREST"}:
            assert realised[use] == pytest.approx(0.0)

    diagnostic = ensemble.diagnostics.iloc[0]
    assert bool(diagnostic["PER_USE_NATIONAL_REALISED_VECTOR_FIXED"])
    assert bool(diagnostic["SAMPLED_NOT_EXACT_ENVELOPE"])
    assert not bool(diagnostic["OPPORTUNITY_OBJECTIVE_PRESERVED"])


def test_sampled_geographies_expose_spatial_flexibility_not_one_solver_map() -> None:
    ensemble = sample_colm_sc3_feasible_geographies(
        _symmetric_reference(),
        eligibility_rules=_rules(),
        n_alternatives=4,
        seed=123,
    )
    forest = ensemble.flexibility.loc[ensemble.flexibility["USE"].eq("FOREST")]
    forest = forest.set_index("CSOED")

    for ed in ("E1", "E2"):
        assert forest.loc[ed, "MIN_SAMPLED_HA"] == pytest.approx(0.0)
        assert forest.loc[ed, "MAX_SAMPLED_HA"] == pytest.approx(100.0)
        assert forest.loc[ed, "RANGE_SAMPLED_HA"] == pytest.approx(100.0)
        assert not bool(forest.loc[ed, "ROBUST_POSITIVE_SAMPLED"])


def test_exact_bounds_hold_same_end_use_and_recover_full_symmetric_range() -> None:
    bounds = exact_colm_sc3_ed_use_bounds(
        _symmetric_reference(),
        eligibility_rules=_rules(),
        queries=[("E1", "FOREST"), ("E2", "FOREST")],
    ).set_index("CSOED")

    assert np.allclose(bounds["EXACT_MIN_HA"].to_numpy(float), 0.0)
    assert np.allclose(bounds["EXACT_MAX_HA"].to_numpy(float), 100.0)
    assert np.allclose(bounds["EXACT_RANGE_HA"].to_numpy(float), 100.0)
    assert np.allclose(bounds["FIXED_NATIONAL_REALISED_HA"].to_numpy(float), 100.0)


def test_exact_bounds_reject_unknown_ed_or_use() -> None:
    with pytest.raises(ValueError, match="unknown CSOED"):
        exact_colm_sc3_ed_use_bounds(
            _symmetric_reference(),
            eligibility_rules=_rules(),
            queries=[("NO_SUCH_ED", "FOREST")],
        )

    with pytest.raises(ValueError, match="unsupported use"):
        exact_colm_sc3_ed_use_bounds(
            _symmetric_reference(),
            eligibility_rules=_rules(),
            queries=[("E1", "NO_SUCH_USE")],
        )
