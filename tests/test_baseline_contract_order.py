from goblin_spatial.baseline_contract import (
    BASELINE_BACKBONE,
    BASELINE_SEQUENCE,
    CANONICAL_BASELINE,
    validate_baseline_contract,
)


def test_canonical_baseline_contract():
    validate_baseline_contract()
    assert BASELINE_BACKBONE == ("YEAR", "CSOED")
    assert len(CANONICAL_BASELINE.cso13) == 13
    assert len(CANONICAL_BASELINE.cso_cattle9) == 9
    assert len(CANONICAL_BASELINE.cso_sheep4) == 4
    assert len(CANONICAL_BASELINE.goblin31) == 31
    assert len(CANONICAL_BASELINE.goblin_cattle21) == 21
    assert len(CANONICAL_BASELINE.goblin_sheep10) == 10


def test_biological_products_come_before_optional_layers():
    assert BASELINE_SEQUENCE[:2] == ("CSO_13", "GOBLIN_31")
    assert BASELINE_SEQUENCE.index("CSO_13") < BASELINE_SEQUENCE.index("LAND_FARM_STRUCTURE")
    assert BASELINE_SEQUENCE.index("GOBLIN_31") < BASELINE_SEQUENCE.index("STANDARD_OUTPUT")
    assert BASELINE_SEQUENCE.index("GOBLIN_31") < BASELINE_SEQUENCE.index("SYNTHESIS_REFERENCE_LAYERS")
