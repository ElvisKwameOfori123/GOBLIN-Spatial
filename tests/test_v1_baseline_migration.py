from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from goblin_spatial.config import load_config
from goblin_spatial.land.panel import _read_aqa06
from goblin_spatial.scenario.endpoint_allocation import _allocate_reduction_total
from goblin_spatial.standard_output.coefficients import load_model_mapping


def test_config_prefers_first_existing_candidate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    config_dir = repo / "configs"
    config_dir.mkdir(parents=True)
    fallback = repo / "legacy.csv"
    fallback.write_text("x\n1\n", encoding="utf-8")
    config = {
        "study": {"base_year": 2020, "expected_eds": 2857},
        "files": {"example": ["data/inputs/new.csv", "legacy.csv"]},
    }
    path = config_dir / "test.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    loaded = load_config(path)
    assert loaded.files["example"] == fallback

    canonical = repo / "data" / "inputs" / "new.csv"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("x\n2\n", encoding="utf-8")
    loaded = load_config(path)
    assert loaded.files["example"] == canonical


def test_standard_output_mapping_accepts_frozen_workbook(tmp_path: Path) -> None:
    source = Path("data/controls/standard_output/GOBLIN_SO_mapping.csv")
    mapping = pd.read_csv(source)
    workbook = tmp_path / "08_IFS2020_Standard_Output_Mapping.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        mapping.to_excel(writer, sheet_name="SO_Mapping", index=False)

    loaded = load_model_mapping(workbook)
    assert set(loaded["MODEL_VARIABLE"]) == set(mapping["MODEL_VARIABLE"].astype(str))
    assert {"TOTAL_CEREALS", "OTHER_CROPS_HA"}.issubset(
        set(loaded.loc[loaded["APPLY_IN_SO"] == "YES", "MODEL_VARIABLE"])
    )


def test_aqa06_reader_accepts_frozen_workbook_shape(tmp_path: Path) -> None:
    source = pd.read_csv("data/raw/land/AQA06_Unpivoted_2013_2025.csv")
    workbook = tmp_path / "06_CSO_AQA06_Agricultural_Land_Use.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        source.to_excel(writer, sheet_name="Unpivoted", index=False)

    loaded = _read_aqa06(workbook)
    assert list(loaded.columns) == list(source.columns)
    assert len(loaded) == len(source)


def test_absolute_endpoint_allocator_closes_and_respects_capacity() -> None:
    base = np.array([10, 5, 0, 20], dtype=np.int64)
    weights = base.astype(float)
    retained, reductions = _allocate_reduction_total(base, 10, weights)

    assert int(reductions.sum()) == 10
    assert np.array_equal(retained, base - reductions)
    assert np.all(retained >= 0)
    assert np.all(retained <= base)
    assert retained[2] == 0
    assert np.all(reductions[base > 0] > 0)
