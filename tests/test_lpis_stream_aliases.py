import geopandas as gpd

from goblin_spatial.land.lpis_stream import _harmonise_published_semantic_aliases


def test_2020_permanent_pasture_uses_land_use_group():
    source = gpd.GeoDataFrame(
        {
            "IS_PERMANENT_GRASS": [True, True, False],
            "IS_LOW_INPUT_GRASS": [False, True, False],
            "LAND_USE_GROUP": ["GRASS_PERMANENT", "GRASS_LOW_INPUT", "GRASS_TEMPORARY"],
            "IS_FORESTRY_CONTEXT": [False, False, True],
        }
    )
    out = _harmonise_published_semantic_aliases(source)

    assert out["IS_PERMANENT_PASTURE"].tolist() == [True, False, False]
    assert out["IS_LOW_INPUT_GRASS"].tolist() == [False, True, False]
    assert out["IS_FORESTRY_EXISTING"].tolist() == [False, False, True]


def test_2025_forestry_aliases_are_preserved():
    source = gpd.GeoDataFrame(
        {
            "IS_PERMANENT_PASTURE": [True, False],
            "LAND_USE_GROUP": ["PERMANENT_PASTURE", "OTHER_GRASS"],
            "IS_FORESTRY_ELIGIBLE_2025": [True, False],
            "IS_FORESTRY_INELIGIBLE_2025": [False, True],
        }
    )
    out = _harmonise_published_semantic_aliases(source)

    assert out["IS_PERMANENT_PASTURE"].tolist() == [True, False]
    assert out["IS_FORESTRY_ELIGIBLE_SOURCE"].tolist() == [True, False]
    assert out["IS_FORESTRY_INELIGIBLE_SOURCE"].tolist() == [False, True]


def test_existing_canonical_flags_take_precedence():
    source = gpd.GeoDataFrame(
        {
            "LAND_USE_GROUP": ["GRASS_PERMANENT"],
            "IS_PERMANENT_GRASS": [True],
            "IS_PERMANENT_PASTURE": [False],
            "IS_FORESTRY_CONTEXT": [True],
            "IS_FORESTRY_EXISTING": [False],
        }
    )
    out = _harmonise_published_semantic_aliases(source)

    assert out["IS_PERMANENT_PASTURE"].tolist() == [False]
    assert out["IS_FORESTRY_EXISTING"].tolist() == [False]
