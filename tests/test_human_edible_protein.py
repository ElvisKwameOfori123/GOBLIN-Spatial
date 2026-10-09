from goblin_spatial.synthesis.human_edible_protein import (
    edible_protein_conversion_ratio,
    land_use_ratio,
    net_export_human_edible_protein,
    net_human_edible_protein_production,
)


def test_net_human_edible_protein_production():
    assert net_human_edible_protein_production(
        human_food_protein_kt=100.0,
        export_human_edible_protein_kt=250.0,
        import_human_edible_protein_kt=80.0,
    ) == 270.0


def test_net_export_human_edible_protein():
    assert net_export_human_edible_protein(
        export_human_edible_protein_kt=250.0,
        import_human_edible_protein_kt=80.0,
    ) == 170.0


def test_epcr():
    assert edible_protein_conversion_ratio(
        human_digestible_protein_feed=22.0,
        human_digestible_protein_output=100.0,
    ) == 0.22


def test_lur():
    assert land_use_ratio(
        potential_crop_human_digestible_protein=58.0,
        livestock_human_digestible_protein_output=100.0,
    ) == 0.58
