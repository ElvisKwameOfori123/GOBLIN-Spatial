from __future__ import annotations

import pandas as pd
import pytest

from goblin_spatial.synthesis.lcad_reference import (
    add_lcad_reference_potentials,
    feedstock_record,
    load_lcad_feedstock_reference,
    technical_potential_from_dm,
)


def test_reference_contains_core_spatial_feedstocks() -> None:
    ref = load_lcad_feedstock_reference()
    names = set(ref["feedstock"])
    assert {"Cattle slurry", "Grass", "Grass clover", "Willow"}.issubset(names)


def test_grass_reference_matches_lcad_workbook() -> None:
    grass = feedstock_record("Grass")
    assert grass["methane_yield_m3_ch4_per_t_dm"] == pytest.approx(306.0)
    assert grass["dm_fraction"] == pytest.approx(0.25)
    assert grass["total_n_kg_per_t_dm"] == pytest.approx(21.5)


def test_grass_one_tonne_dm_conversion() -> None:
    result = technical_potential_from_dm("Grass", 1.0)
    assert result["fresh_matter_t"] == pytest.approx(4.0)
    assert result["methane_potential_m3_ch4"] == pytest.approx(306.0)
    assert result["total_n_kg"] == pytest.approx(21.5)
    assert result["p2o5_kg"] == pytest.approx(8.0)
    assert result["k2o_kg"] == pytest.approx(25.0)


def test_vectorised_reference_attachment() -> None:
    resources = pd.DataFrame(
        {
            "CSOED": ["A", "B"],
            "feedstock": ["Grass", "Cattle slurry"],
            "dry_matter_t": [2.0, 3.0],
        }
    )
    out = add_lcad_reference_potentials(resources)
    assert out.loc[0, "methane_potential_m3_ch4"] == pytest.approx(612.0)
    assert out.loc[1, "methane_potential_m3_ch4"] == pytest.approx(420.0)


def test_negative_dm_rejected() -> None:
    with pytest.raises(ValueError):
        technical_potential_from_dm("Grass", -1.0)
