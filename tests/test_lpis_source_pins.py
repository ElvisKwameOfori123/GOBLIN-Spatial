from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_lpis_source_versions_are_pinned_deliberately() -> None:
    pins = yaml.safe_load((ROOT / "LPIS_SOURCE_PINS.yaml").read_text(encoding="utf-8"))
    sources = pins["sources"]

    y2020 = sources["lpis_2020_corrected_v2"]
    assert y2020["record_id"] == 21922002
    assert y2020["filename"] == "LPIS_2020_GOBLIN_reduced_v2.parquet"
    assert y2020["zenodo_md5"] == "ef6ff159320a13d7059770d20d1a0c3a"

    y2025 = sources["lpis_2025_validated_v1"]
    assert y2025["record_id"] == 21918924
    assert y2025["filename"] == "LPIS_2025_GOBLIN_reduced.parquet"
    assert y2025["zenodo_md5"] == "8c10e49514997b9bedec77bebd5d52ed"

    bridge = pins["spatial_bridge"]
    assert bridge["expected_model_eds"] == 2857
    assert bridge["expected_lpis_ed_profile_rows"] == 5714
    assert bridge["join_authority"] == "CSOED"


def test_runtime_config_uses_the_pinned_lpis_filenames() -> None:
    config = yaml.safe_load(
        (ROOT / "configs" / "ireland_2015_2025.yaml").read_text(encoding="utf-8")
    )
    files = config["files"]

    assert files["lpis_2020_parcels"].endswith(
        "LPIS_2020_GOBLIN_reduced_v2.parquet"
    )
    assert files["lpis_2025_parcels"].endswith(
        "LPIS_2025_GOBLIN_reduced.parquet"
    )
