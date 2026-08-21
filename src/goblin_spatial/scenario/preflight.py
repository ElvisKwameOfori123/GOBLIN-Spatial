"""No-download preflight checks for the principal scenario pipeline.

This module deliberately never fetches, rebuilds or spatially intersects heavy
inputs. It only verifies that the compact controls needed by a requested stage
already exist and have the minimum schema needed by the runtime.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.land.lpis import read_ed_lpis_profile
from goblin_spatial.scenario.control_table import read_scenario_control_table
from goblin_spatial.soil import (
    CLASS_SHARE_COLUMNS,
    GROUP_SHARE_COLUMNS,
    PHYSICAL_AREA_COLUMNS,
    canonical_csoed,
)


BASELINE_REQUIRED = {
    "YEAR",
    "CSOED",
    "County",
    "ALL_GRASSLAND",
    "AGRICULTURAL_HOLDINGS",
    "AVERAGE_SIZE_OF_HOLDINGS",
    "MEDIAN_AGE_OF_HOLDER",
    "SO_LIVESTOCK_2020_EUR",
}

SC1_08B_REQUIRED = {
    "CSOED",
    "SOIL_SOURCE_UAA_HA",
    *CLASS_SHARE_COLUMNS,
    *GROUP_SHARE_COLUMNS,
}

# The mature SC2/SC3 principal science needs these two additional 08B fields:
# Yield Class is a hard forest eligibility control in SC3, while the continuous
# peat/cutover share spatialises the externally anchored drained-organic stock.
SC2_SC3_08B_REQUIRED = {
    "FOREST_YC_WEIGHTED_MEAN",
    "IFS_PEAT_CUTOVER_UAA_SHARE",
}

# A compact 08C control only needs the mapped physical-area fields. The runtime
# reproduces Colm's documented physical shares and SG1/SG2/SG3 crosswalk from
# these seven areas, so storing all derived columns is optional rather than a
# preflight requirement.
SC2_08C_REQUIRED = {"CSOED", *PHYSICAL_AREA_COLUMNS}


def _status(
    rows: list[dict[str, object]],
    item: str,
    path: Path,
    ok: bool,
    detail: str,
) -> None:
    rows.append(
        {
            "ITEM": item,
            "PATH": str(path),
            "OK": bool(ok),
            "DETAIL": detail,
        }
    )


def _configured_output(cfg: SpatialConfig, key: str) -> Path:
    value = cfg.raw.get("outputs", {}).get(key)
    if value is None:
        raise KeyError(f"configuration missing outputs.{key}")
    path = Path(value)
    return path if path.is_absolute() else cfg.project_root / path


def _compact_keys(frame: pd.DataFrame) -> pd.Series:
    if "CSOED" not in frame.columns:
        return pd.Series(dtype="string")
    return frame["CSOED"].map(canonical_csoed).astype("string")


def preflight_principal_inputs(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
) -> pd.DataFrame:
    """Return compact readiness checks without rebuilding any spatial input."""

    baseline_year = int(baseline_year)
    if baseline_year not in (2020, 2025):
        raise ValueError(
            "principal preflight supports baseline_year 2020 or 2025"
        )
    stage = str(stage).upper()
    if stage not in {"SC1", "SC2", "SC3"}:
        raise ValueError("preflight stage must be SC1, SC2 or SC3")

    rows: list[dict[str, object]] = []

    baseline_path = _configured_output(cfg, "standard_output_master")
    if not baseline_path.exists():
        _status(rows, "STAGE08_BASELINE", baseline_path, False, "missing")
    else:
        header = pd.read_csv(baseline_path, nrows=0)
        missing = sorted(BASELINE_REQUIRED - set(header.columns))
        if missing:
            _status(
                rows,
                "STAGE08_BASELINE",
                baseline_path,
                False,
                f"missing columns={missing}",
            )
        else:
            years = pd.read_csv(
                baseline_path,
                usecols=["YEAR", "CSOED"],
            )
            selected = years.loc[
                pd.to_numeric(years["YEAR"], errors="raise")
                .astype(int)
                .eq(baseline_year)
            ].copy()
            selected_keys = selected["CSOED"].map(canonical_csoed)
            ok = (
                len(selected) == int(cfg.expected_eds)
                and not selected_keys.eq("").any()
                and not selected_keys.duplicated().any()
            )
            _status(
                rows,
                "STAGE08_BASELINE",
                baseline_path,
                ok,
                f"{baseline_year} rows={len(selected):,}; "
                f"expected={cfg.expected_eds:,}",
            )

    controls_path = Path(cfg.files["scenario_controls"])
    if not controls_path.exists():
        _status(
            rows,
            "SCENARIO_CONTROLS",
            controls_path,
            False,
            "missing",
        )
    else:
        controls = read_scenario_control_table(controls_path)
        active = controls.loc[
            controls["ACTIVE"],
            "SCENARIO_ID",
        ].astype(str).tolist()
        _status(
            rows,
            "SCENARIO_CONTROLS",
            controls_path,
            bool(active),
            f"ACTIVE={active}",
        )

    # The compact 08B source universe is intentionally not required to contain
    # exactly 2,857 rows. Mature 08B can contain a larger source-ED universe and
    # the runtime resolves it to the model EDs by direct match, compound
    # components, then the validated 08B fallback hierarchy.
    soil_path = Path(cfg.files["agricultural_soil_profile"])
    if not soil_path.exists():
        _status(
            rows,
            "COMPACT_08B",
            soil_path,
            False,
            "missing; build/package once outside scenario runtime",
        )
    else:
        soil = pd.read_csv(soil_path, low_memory=False)
        required = set(SC1_08B_REQUIRED)
        if stage in {"SC2", "SC3"}:
            required.update(SC2_SC3_08B_REQUIRED)
        missing = sorted(required - set(soil.columns))
        keys = _compact_keys(soil)
        ok = (
            not missing
            and len(keys) == len(soil)
            and not keys.eq("").any()
            and not keys.duplicated().any()
        )
        _status(
            rows,
            "COMPACT_08B",
            soil_path,
            ok,
            (
                f"valid compact agricultural-capability source profile; rows={len(soil):,}"
                if ok
                else f"rows={len(soil):,}; missing={missing}"
            ),
        )

    if stage in {"SC2", "SC3"}:
        lpis_path = Path(cfg.files["lpis_ed_profile"])
        if not lpis_path.exists():
            _status(
                rows,
                "COMPACT_LPIS",
                lpis_path,
                False,
                "missing; recover/reuse compact ED control before any heavy rebuild",
            )
        else:
            lpis = read_ed_lpis_profile(lpis_path)
            counts = lpis.groupby("LPIS_YEAR").size().to_dict()
            expected = {
                2020: int(cfg.expected_eds),
                2025: int(cfg.expected_eds),
            }
            snapshot_keys_ok = True
            for year in (2020, 2025):
                block = lpis.loc[lpis["LPIS_YEAR"].eq(year)]
                keys = block["CSOED_CANONICAL"].astype("string")
                snapshot_keys_ok &= (
                    len(block) == int(cfg.expected_eds)
                    and not keys.eq("").any()
                    and not keys.duplicated().any()
                )
            _status(
                rows,
                "COMPACT_LPIS",
                lpis_path,
                counts == expected and snapshot_keys_ok,
                f"rows by year={counts}",
            )

        # Colm's compact 08C source may contain more than 2,857 mapped ED rows.
        # Runtime accepts direct mapped EDs and complete compound components only;
        # it deliberately refuses synthetic county/national physical-soil fallback.
        physical_path = Path(cfg.files["physical_soil_profile"])
        if not physical_path.exists():
            _status(
                rows,
                "COMPACT_08C",
                physical_path,
                False,
                "missing; recover/package compact mapped-soil profile before SC2",
            )
        else:
            physical = pd.read_csv(physical_path, low_memory=False)
            missing = sorted(SC2_08C_REQUIRED - set(physical.columns))
            keys = _compact_keys(physical)
            ok = (
                not missing
                and len(keys) == len(physical)
                and not keys.eq("").any()
                and not keys.duplicated().any()
            )
            _status(
                rows,
                "COMPACT_08C",
                physical_path,
                ok,
                (
                    f"valid compact mapped physical-soil source profile; rows={len(physical):,}"
                    if ok
                    else f"rows={len(physical):,}; missing={missing}"
                ),
            )

    return pd.DataFrame(rows)


def assert_principal_ready(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
) -> pd.DataFrame:
    """Raise one compact error listing every missing/invalid requested input."""

    report = preflight_principal_inputs(
        cfg,
        baseline_year=baseline_year,
        stage=stage,
    )
    failed = report.loc[~report["OK"]]
    if not failed.empty:
        details = "; ".join(
            f"{row.ITEM}: {row.DETAIL} ({row.PATH})"
            for row in failed.itertuples(index=False)
        )
        raise RuntimeError(
            "principal scenario preflight failed. No heavy rebuild was attempted. "
            + details
        )
    return report
