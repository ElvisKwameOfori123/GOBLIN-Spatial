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


def _status(rows: list[dict[str, object]], item: str, path: Path, ok: bool, detail: str) -> None:
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


def preflight_principal_inputs(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
) -> pd.DataFrame:
    """Return compact readiness checks without rebuilding any spatial input."""

    baseline_year = int(baseline_year)
    if baseline_year not in (2020, 2025):
        raise ValueError("principal preflight supports baseline_year 2020 or 2025")
    stage = str(stage).upper()
    if stage not in {"SC1", "SC2"}:
        raise ValueError("preflight stage must be SC1 or SC2")

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
            years = pd.read_csv(baseline_path, usecols=["YEAR", "CSOED"])
            selected = years.loc[
                pd.to_numeric(years["YEAR"], errors="raise").astype(int).eq(baseline_year)
            ]
            ok = len(selected) == int(cfg.expected_eds) and not selected["CSOED"].duplicated().any()
            _status(
                rows,
                "STAGE08_BASELINE",
                baseline_path,
                ok,
                f"{baseline_year} rows={len(selected):,}; expected={cfg.expected_eds:,}",
            )

    controls_path = Path(cfg.files["scenario_controls"])
    if not controls_path.exists():
        _status(rows, "SCENARIO_CONTROLS", controls_path, False, "missing")
    else:
        controls = read_scenario_control_table(controls_path)
        active = controls.loc[controls["ACTIVE"], "SCENARIO_ID"].astype(str).tolist()
        _status(
            rows,
            "SCENARIO_CONTROLS",
            controls_path,
            bool(active),
            f"ACTIVE={active}",
        )

    soil_path = Path(cfg.files["agricultural_soil_profile"])
    if not soil_path.exists():
        _status(rows, "COMPACT_08B", soil_path, False, "missing; build once outside scenario runtime")
    else:
        soil = pd.read_csv(soil_path, low_memory=False)
        required = {"CSOED", *GROUP_SHARE_COLUMNS}
        missing = sorted(required - set(soil.columns))
        keys = soil["CSOED"].map(canonical_csoed) if "CSOED" in soil.columns else pd.Series(dtype=str)
        ok = not missing and not keys.eq("").any() and not keys.duplicated().any()
        _status(
            rows,
            "COMPACT_08B",
            soil_path,
            ok,
            "valid compact ED source profile" if ok else f"missing={missing}",
        )

    if stage == "SC2":
        lpis_path = Path(cfg.files["lpis_ed_profile"])
        if not lpis_path.exists():
            _status(rows, "COMPACT_LPIS", lpis_path, False, "missing; do not trigger heavy rebuild automatically")
        else:
            lpis = read_ed_lpis_profile(lpis_path)
            counts = lpis.groupby("LPIS_YEAR").size().to_dict()
            expected = {2020: int(cfg.expected_eds), 2025: int(cfg.expected_eds)}
            _status(
                rows,
                "COMPACT_LPIS",
                lpis_path,
                counts == expected,
                f"rows by year={counts}",
            )

        physical_path = Path(cfg.files["physical_soil_profile"])
        if not physical_path.exists():
            _status(rows, "COMPACT_08C", physical_path, False, "missing; reduce source package once before SC2")
        else:
            physical = pd.read_csv(physical_path, low_memory=False)
            required = {"CSOED", *PHYSICAL_AREA_COLUMNS}
            missing = sorted(required - set(physical.columns))
            keys = physical["CSOED"].map(canonical_csoed) if "CSOED" in physical.columns else pd.Series(dtype=str)
            ok = not missing and not keys.eq("").any() and not keys.duplicated().any()
            _status(
                rows,
                "COMPACT_08C",
                physical_path,
                ok,
                "valid compact mapped physical-soil profile" if ok else f"missing={missing}",
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
