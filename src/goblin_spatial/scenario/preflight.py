"""No-download preflight checks for the Colm-direct principal scenario pipeline.

The normal runtime verifies only repository-contained controls. It never fetches,
rebuilds or spatially intersects LPIS parcels, soil packages or ED geography.

SC1 requires only the validated historical livestock/grassland/SO baseline plus
national scenario and pasture/cohort controls. It does not require soil or LPIS.
SC2/SC3 additionally require the frozen 2020 Colm physical-soil + LPIS context.
Scientific eligibility and rewetting-capacity controls are caller-supplied and
are validated by the stage runner rather than silently defaulted here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.land.colm_lpis_context import read_colm_lpis_context
from goblin_spatial.scenario.control_table import read_scenario_control_table
from goblin_spatial.soil import canonical_csoed


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


def preflight_principal_inputs(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
) -> pd.DataFrame:
    """Return readiness checks without rebuilding or downloading spatial inputs."""

    baseline_year = int(baseline_year)
    if baseline_year not in (2020, 2025):
        raise ValueError("principal preflight supports baseline_year 2020 or 2025")
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
            years = pd.read_csv(baseline_path, usecols=["YEAR", "CSOED"])
            selected = years.loc[
                pd.to_numeric(years["YEAR"], errors="raise").astype(int).eq(baseline_year)
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

    # SC1 deliberately stops here with respect to spatial land evidence.
    if stage in {"SC2", "SC3"}:
        context_path = Path(cfg.files["land_context_2020"])
        if baseline_year != 2020:
            _status(
                rows,
                "SPATIAL_BASELINE_SUPPORT",
                context_path,
                False,
                (
                    "Colm-direct SC2/SC3 currently support the validated frozen "
                    "2020 Colm+LPIS context only; a separate validated 2025 context "
                    "has not been supplied"
                ),
            )
        elif not context_path.exists():
            _status(
                rows,
                "COLM_LPIS_CONTEXT_2020",
                context_path,
                False,
                "missing repository-contained Colm physical-soil + LPIS control",
            )
        else:
            try:
                context = read_colm_lpis_context(context_path)
                ok = (
                    len(context) == int(cfg.expected_eds)
                    and not context["CSOED"].duplicated().any()
                )
                _status(
                    rows,
                    "COLM_LPIS_CONTEXT_2020",
                    context_path,
                    ok,
                    (
                        f"rows={len(context):,}; expected={cfg.expected_eds:,}; "
                        "legacy 08B not required"
                    ),
                )
            except Exception as exc:
                _status(
                    rows,
                    "COLM_LPIS_CONTEXT_2020",
                    context_path,
                    False,
                    f"invalid: {exc}",
                )

    return pd.DataFrame(rows)


def assert_principal_ready(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
) -> pd.DataFrame:
    """Raise one compact error listing every missing or invalid requested input."""

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
