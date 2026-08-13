import geopandas as gpd

from goblin_spatial.land.lpis_stream import _harmonise_published_semantic_aliases


def test_corrected_2020_published_aliases_are_preserved():
    source = gpd.GeoDataFrame(
        {
            "IS_PERMANENT_GRASS": [True, False],
            "IS_FORESTRY_CONTEXT": [False, True],
        }
    )
    out = _harmonise_published_semantic_aliases(source)

    assert out["IS_PERMANENT_PASTURE"].tolist() == [True, False]
    assert out["IS_FORESTRY_EXISTING"].tolist() == [False, True]


def test_validated_2025_published_forestry_aliases_are_preserved():
    source = gpd.GeoDataFrame(
        {
            "IS_FORESTRY_ELIGIBLE_2025": [True, False],
            "IS_FORESTRY_INELIGIBLE_2025": [False, True],
        }
    )
    out = _harmonise_published_semantic_aliases(source)

    assert out["IS_FORESTRY_ELIGIBLE_SOURCE"].tolist() == [True, False]
    assert out["IS_FORESTRY_INELIGIBLE_SOURCE"].tolist() == [False, True]


def test_canonical_flags_take_precedence_over_snapshot_aliases():
    source = gpd.GeoDataFrame(
        {
            "IS_PERMANENT_GRASS": [True],
            "IS_PERMANENT_PASTURE": [False],
            "IS_FORESTRY_CONTEXT": [True],
            "IS_FORESTRY_EXISTING": [False],
        }
    )
    out = _harmonise_published_semantic_aliases(source)

    assert out["IS_PERMANENT_PASTURE"].tolist() == [False]
    assert out["IS_FORESTRY_EXISTING"].tolist() == [False]
