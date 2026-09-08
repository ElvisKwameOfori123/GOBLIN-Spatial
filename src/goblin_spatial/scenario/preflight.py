"""No-download preflight checks for the Colm-direct principal scenario pipeline.

The normal runtime verifies only repository-contained controls. It never fetches,
rebuilds or spatially intersects LPIS parcels, soil packages or ED geography.

SC1 requires only the validated historical livestock/grassland/SO baseline plus
national scenario controls. It does not require soil or LPIS. SC2 additionally
requires the frozen 2020 Colm physical-soil + LPIS context. SC3 additionally
requires an explicit, versioned Stage-A eligibility control and, whenever the
selected pathway has a positive rewetting target, a validated rewetting-capacity
control. Missing scientific controls are surfaced as a not-ready state rather
than replaced by defaults.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from goblin_spatial.config import SpatialConfig
from goblin_spatial.land.colm_lpis_context import read_colm_lpis_context
from goblin_spatial.land.colm_rules import load_colm_eligibility_control
from goblin_spatial.land.rewetting_capacity import load_rewetting_capacity_control
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
    path: Path | None,
    ok: bool,
    detail: str,
) -> None:
    rows.append(
        {
            "ITEM": item,
            "PATH": "<not configured>" if path is None else str(path),
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


def _optional_runtime_path(
    cfg: SpatialConfig,
    key: str,
    override: str | Path | None,
) -> Path | None:
    if override is not None:
        path = Path(override)
    else:
        value = cfg.files.get(key)
        if value is None:
            return None
        path = Path(value)
    return path if path.is_absolute() else cfg.project_root / path


def _selected_control_rows(
    controls: pd.DataFrame | None,
    scenario_id: str | None,
) -> pd.DataFrame | None:
    if controls is None:
        return None
    active = controls.loc[controls["ACTIVE"]].copy()
    if scenario_id is None:
        return active
    requested = str(scenario_id).strip()
    selected = active.loc[active["SCENARIO_ID"].astype(str).eq(requested)].copy()
    return selected


def preflight_principal_inputs(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
    scenario_id: str | None = None,
    eligibility_rules: str | Path | None = None,
    rewetting_capacity: str | Path | None = None,
) -> pd.DataFrame:
    """Return stage-specific readiness checks without rebuilding spatial inputs."""

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
                f"{baseline_year} rows={len(selected):,}; expected={cfg.expected_eds:,}",
            )

    controls_path = Path(cfg.files["scenario_controls"])
    if not controls_path.is_absolute():
        controls_path = cfg.project_root / controls_path
    controls: pd.DataFrame | None = None
    if not controls_path.exists():
        _status(rows, "SCENARIO_CONTROLS", controls_path, False, "missing")
    else:
        controls = read_scenario_control_table(controls_path)
        active = controls.loc[controls["ACTIVE"], "SCENARIO_ID"].astype(str).tolist()
        selected_controls = _selected_control_rows(controls, scenario_id)
        scenario_ok = bool(active) and selected_controls is not None and not selected_controls.empty
        detail = f"ACTIVE={active}"
        if scenario_id is not None:
            detail += f"; requested={scenario_id!r}"
        _status(rows, "SCENARIO_CONTROLS", controls_path, scenario_ok, detail)

    # SC1 deliberately has no dependency on Colm soil, LPIS, eligibility or
    # rewetting-capacity evidence.
    if stage == "SC1":
        return pd.DataFrame(rows)

    context_path = Path(cfg.files["land_context_2020"])
    if not context_path.is_absolute():
        context_path = cfg.project_root / context_path
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

    if stage == "SC2":
        return pd.DataFrame(rows)

    # SC3 is deliberately blocked until its scientific controls exist. This
    # avoids turning a provisional suitability assumption into a hidden default.
    rules_path = _optional_runtime_path(cfg, "colm_eligibility_rules", eligibility_rules)
    if rules_path is None:
        _status(
            rows,
            "COLM_STAGE_A_ELIGIBILITY",
            None,
            False,
            "not configured; SC3 requires an explicit evidence-backed Stage-A eligibility control",
        )
    elif not rules_path.exists():
        _status(rows, "COLM_STAGE_A_ELIGIBILITY", rules_path, False, "missing")
    else:
        try:
            _, version, evidence = load_colm_eligibility_control(rules_path)
            _status(
                rows,
                "COLM_STAGE_A_ELIGIBILITY",
                rules_path,
                True,
                f"version={version}; evidence={evidence}",
            )
        except Exception as exc:
            _status(
                rows,
                "COLM_STAGE_A_ELIGIBILITY",
                rules_path,
                False,
                f"invalid: {exc}",
            )

    selected_controls = _selected_control_rows(controls, scenario_id)
    requires_rewetting = False
    selected_names: list[str] = []
    if selected_controls is not None and not selected_controls.empty:
        selected_names = selected_controls["SCENARIO_ID"].astype(str).tolist()
        requires_rewetting = bool(
            pd.to_numeric(selected_controls["REWETTING_HA"], errors="raise").gt(0).any()
        )

    capacity_path = _optional_runtime_path(cfg, "rewetting_capacity", rewetting_capacity)
    if not requires_rewetting:
        _status(
            rows,
            "REWETTING_CAPACITY",
            capacity_path,
            True,
            f"not required for selected scenarios={selected_names}",
        )
    elif capacity_path is None:
        _status(
            rows,
            "REWETTING_CAPACITY",
            None,
            False,
            (
                "not configured; positive pathway rewetting target requires a "
                "validated drained-organic/agricultural capacity control"
            ),
        )
    elif not capacity_path.exists():
        _status(rows, "REWETTING_CAPACITY", capacity_path, False, "missing")
    else:
        try:
            _, _, version, evidence = load_rewetting_capacity_control(
                capacity_path,
                expected_eds=int(cfg.expected_eds),
            )
            _status(
                rows,
                "REWETTING_CAPACITY",
                capacity_path,
                True,
                f"version={version}; evidence={evidence}",
            )
        except Exception as exc:
            _status(
                rows,
                "REWETTING_CAPACITY",
                capacity_path,
                False,
                f"invalid: {exc}",
            )

    return pd.DataFrame(rows)


def assert_principal_ready(
    cfg: SpatialConfig,
    *,
    baseline_year: int,
    stage: str = "SC1",
    scenario_id: str | None = None,
    eligibility_rules: str | Path | None = None,
    rewetting_capacity: str | Path | None = None,
) -> pd.DataFrame:
    """Raise one compact error listing every missing or invalid requested input."""

    report = preflight_principal_inputs(
        cfg,
        baseline_year=baseline_year,
        stage=stage,
        scenario_id=scenario_id,
        eligibility_rules=eligibility_rules,
        rewetting_capacity=rewetting_capacity,
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
