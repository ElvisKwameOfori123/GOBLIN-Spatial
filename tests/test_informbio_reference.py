import pytest

from goblin_spatial.synthesis.informbio_reference import (
    load_informbio_reference,
    resource_content_from_dm,
)


def test_reference_table_loads():
    rows = load_informbio_reference()
    assert len(rows) >= 15
    assert any(r["material"] == "Winter wheat straw" for r in rows)


def test_reference_resource_content_from_dm():
    result = resource_content_from_dm("Winter wheat straw", 100.0)
    assert result["carbon_t"] == pytest.approx(47.91)
    assert result["nitrogen_t"] == pytest.approx(0.39)


def test_manure_reference_is_blocked_by_default():
    with pytest.raises(ValueError, match="reference-only"):
        resource_content_from_dm("Slurry - Dairy Cattle", 100.0)


def test_manure_reference_can_be_used_explicitly_for_sensitivity_only():
    result = resource_content_from_dm(
        "Slurry - Dairy Cattle",
        100.0,
        allow_restricted_reference=True,
    )
    assert result["nitrogen_t"] == pytest.approx(1.7)
