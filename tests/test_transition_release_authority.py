import pandas as pd
import pytest

from goblin_spatial.land import transition_release_column


def test_goblin_release_precedes_internal_diagnostic():
    frame = pd.DataFrame({
        "GOBLIN_RELEASED_GRASSLAND_HA": [10.0],
        "POTENTIAL_SPARED_GRASSLAND_HA": [20.0],
    })
    assert transition_release_column(frame) == "GOBLIN_RELEASED_GRASSLAND_HA"


def test_internal_release_remains_legacy_fallback():
    frame = pd.DataFrame({"POTENTIAL_SPARED_GRASSLAND_HA": [20.0]})
    assert transition_release_column(frame) == "POTENTIAL_SPARED_GRASSLAND_HA"


def test_transition_release_requires_one_supported_accounting_column():
    with pytest.raises(ValueError, match="requires"):
        transition_release_column(pd.DataFrame({"OTHER": [1]}))
