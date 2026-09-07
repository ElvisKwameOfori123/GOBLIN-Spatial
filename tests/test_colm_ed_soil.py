from __future__ import annotations

from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from goblin_spatial.soil.colm_ed import (
    COLM_PHYSICAL_AREA_COLUMNS,
    COLM_PHYSICAL_SHARE_COLUMNS,
    build_colm_model_ed_soil_profile,
    colm_ed_soil_diagnostics,
    prepare_colm_ed_soil_source,
    read_colm_ed_soil_source,
)


def _source() -> pd.DataFrame:
    values = {
        "1001": (40.0, 20.0, 15.0, 10.0, 5.0, 5.0, 5.0),
        "1002": (20.0, 20.0, 20.0, 15.0, 5.0, 15.0, 5.0),
        "1003": (30.0, 10.0, 20.0, 10.0, 10.0, 15.0, 5.0),
    }
    rows = []
    for ed, areas in values.items():
        row = {
            "CSOED": ed,
            "COUNTYNAME": "A" if ed in {"1001", "1002"} else "B",
            "IFS_MAP_PARENT_MATERIAL_DOM": "x",
        }
        row.update(dict(zip(COLM_PHYSICAL_AREA_COLUMNS, areas, strict=True)))
        rows.append(row)
    return pd.DataFrame(rows)


def test_stage1_preparation_keeps_physical_soil_and_does_not_derive_groups() -> None:
    out = prepare_colm_ed_soil_source(_source())

    assert out["COLM_G1_G2_G3_STATUS"].eq("NOT_DERIVED_STAGE_1").all()
    assert not any("SG1" in column or "G1_SHARE" in column for column in out.columns)
    assert np.allclose(out[list(COLM_PHYSICAL_SHARE_COLUMNS)].sum(axis=1), 1.0)
    assert np.allclose(
        out["IFS_MAP_AG_SOIL_HA"],
        out[list(COLM_PHYSICAL_AREA_COLUMNS)].sum(axis=1),
    )


def test_adapter_reads_ed_soil_shares_directly_from_colm_zip(tmp_path) -> None:
    source = _source()
    zip_path = tmp_path / "soil-group-package.zip"
    member = tmp_path / "ed_soil_shares.csv"
    source.to_csv(member, index=False)
    with ZipFile(zip_path, "w") as archive:
        archive.write(member, arcname="soil-group-package/ed_soil_shares.csv")

    out = read_colm_ed_soil_source(zip_path)

    assert len(out) == len(source)
    assert set(out["CSOED"].astype(str)) == set(source["CSOED"].astype(str))


def test_adapter_resolves_direct_and_compound_model_eds_without_fallback() -> None:
    model = pd.DataFrame({"CSOED": ["1001/1002", "1003"]})

    out = build_colm_model_ed_soil_profile(model, _source())

    assert out["COLM_SOIL_PROFILE_SOURCE"].tolist() == [
        "COMPOUND_COMPONENTS",
        "ED",
    ]
    assert out["COLM_G1_G2_G3_STATUS"].eq("NOT_DERIVED_STAGE_1").all()
    assert np.allclose(out[list(COLM_PHYSICAL_SHARE_COLUMNS)].sum(axis=1), 1.0)

    compound = out.iloc[0]
    expected_area = _source().loc[
        _source()["CSOED"].isin(["1001", "1002"]),
        list(COLM_PHYSICAL_AREA_COLUMNS),
    ].sum()
    for column in COLM_PHYSICAL_AREA_COLUMNS:
        assert np.isclose(compound[column], expected_area[column])


def test_adapter_refuses_missing_ed_instead_of_using_county_average() -> None:
    model = pd.DataFrame({"CSOED": ["1001", "9999"]})

    with pytest.raises(ValueError, match="No county/national fallback"):
        build_colm_model_ed_soil_profile(model, _source())


def test_adapter_refuses_negative_physical_area() -> None:
    source = _source()
    source.loc[0, "IFS_MAP_PEAT_HA"] = -1.0

    with pytest.raises(ValueError, match="must be non-negative"):
        prepare_colm_ed_soil_source(source)


def test_diagnostics_make_stage1_status_explicit() -> None:
    model = pd.DataFrame({"CSOED": ["1001/1002", "1003"]})
    out = build_colm_model_ed_soil_profile(model, _source())

    qa = colm_ed_soil_diagnostics(out)

    assert qa["rows"] == 2
    assert qa["direct_ed_profiles"] == 1
    assert qa["compound_profiles"] == 1
    assert qa["grouping_status"] == ["NOT_DERIVED_STAGE_1"]
    assert qa["physical_share_closure_max_abs"] < 1e-12
