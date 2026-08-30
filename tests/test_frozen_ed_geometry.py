from __future__ import annotations

import hashlib
from pathlib import Path

import geopandas as gpd
import pandas as pd

from goblin_spatial.map_reporting import prepare_model_geometry


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg"
CHECKSUM = ROOT / "data/inputs/spatial/SC2_ED_Boundaries_Frozen.sha256"
BASELINE = ROOT / "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_frozen_ed_geometry_matches_repository_model_universe() -> None:
    """The repository geometry must join exactly to the 2,857 agricultural EDs."""
    assert GEOMETRY.is_file()
    assert CHECKSUM.is_file()
    assert BASELINE.is_file()

    expected_sha = CHECKSUM.read_text(encoding="utf-8").split()[0].strip().lower()
    assert _sha256(GEOMETRY) == expected_sha

    layers = gpd.list_layers(GEOMETRY)
    assert layers["name"].tolist() == ["electoral_divisions"]

    source = gpd.read_file(GEOMETRY, layer="electoral_divisions")
    assert len(source) == 3409
    assert source.crs is not None
    assert source.crs.to_epsg() == 29902
    assert source.geometry.notna().all()
    assert (~source.geometry.is_empty).all()
    assert source.geometry.is_valid.all()
    assert set(source.geometry.geom_type.astype(str)) == {"MultiPolygon"}
    assert source["CSOED"].astype("string").nunique(dropna=True) == 3409

    baseline = pd.read_csv(BASELINE, dtype={"CSOED": "string"}, low_memory=False)
    assert len(baseline) == 2857
    assert baseline["CSOED"].nunique(dropna=True) == 2857

    model_geometry, detected_key = prepare_model_geometry(
        baseline[["CSOED"]],
        GEOMETRY,
        geometry_key="CSOED",
    )
    assert detected_key == "CSOED"
    assert len(model_geometry) == 2857
    assert model_geometry["CSOED"].nunique(dropna=True) == 2857
    assert model_geometry.geometry.notna().all()

    # Composite source geographies use the first listed ED code only for the
    # cartographic key, while the original source identifier remains auditable.
    composite = model_geometry.loc[model_geometry["CSOED"].eq("8045")]
    assert len(composite) == 1
    assert composite.iloc[0]["CSOED_GEOMETRY_SOURCE"] == "08045/08046"
