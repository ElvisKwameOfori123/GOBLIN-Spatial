"""Scientific reporting utilities for GOBLIN-Spatial scenario outputs.

This module is deliberately downstream of the model. It never changes SC1,
SC2 or SC3 mathematics and never overwrites canonical model CSV outputs.

For land accounting, three quantities are kept distinct:

1. GOBLIN parent Available target accounting
   = gross release - five national Stage-A targets.
2. Realised post-Stage-A unallocated released land
   = gross release - realised Stage-A allocation.
3. Final unallocated released land
   = post-Stage-A unallocated land - realised rewetting.

The distinction preserves the parent pathway accounting while exposing spatial
infeasibility and the physical effect of rewetting transparently.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPORTING_VERSION = "1.0"
LAND_ACCOUNTING_TOL = 1e-6

_REQUIRED_SC3_ACCOUNTING_COLUMNS = {
    "SC2_POTENTIAL_RELEASE_HA",
    "SC3_STAGE_A_REALIZED_HA",
    "SC3_STAGE_A_AVAILABLE_HA",
    "SC3_REALIZED_REWETTING_HA",
    "SC3_RESIDUAL_AVAILABLE_LAND_HA",
}


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _finite(value: object, label: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def add_sc3_reporting_aliases(frame: pd.DataFrame) -> pd.DataFrame:
    """Add interpretation-safe aliases and verify ED land accounting."""

    _require_columns(frame, _REQUIRED_SC3_ACCOUNTING_COLUMNS, "SC3 reporting")
    if frame.empty:
        raise ValueError("SC3 reporting requires at least one ED row")

    out = frame.copy()
    release = pd.to_numeric(
        out["SC2_POTENTIAL_RELEASE_HA"], errors="raise"
    ).to_numpy(float)
    stage_a = pd.to_numeric(
        out["SC3_STAGE_A_REALIZED_HA"], errors="raise"
    ).to_numpy(float)
    post_stage_a = pd.to_numeric(
        out["SC3_STAGE_A_AVAILABLE_HA"], errors="raise"
    ).to_numpy(float)
    rewetting = pd.to_numeric(
        out["SC3_REALIZED_REWETTING_HA"], errors="raise"
    ).to_numpy(float)
    final_residual = pd.to_numeric(
        out["SC3_RESIDUAL_AVAILABLE_LAND_HA"], errors="raise"
    ).to_numpy(float)

    for label, values in {
        "released land": release,
        "Stage-A realised land": stage_a,
        "post-Stage-A unallocated land": post_stage_a,
        "rewetting": rewetting,
        "final unallocated land": final_residual,
    }.items():
        if (~np.isfinite(values)).any():
            raise ValueError(f"SC3 {label} must be finite")
        if (values < -LAND_ACCOUNTING_TOL).any():
            raise AssertionError(f"SC3 {label} contains negative hectares")

    if (rewetting - post_stage_a > LAND_ACCOUNTING_TOL).any():
        raise AssertionError(
            "SC3 realised rewetting exceeds post-Stage-A unallocated released land"
        )

    stage_a_closure = stage_a + post_stage_a - release
    strict_closure = stage_a + rewetting + final_residual - release
    if float(np.max(np.abs(stage_a_closure))) > LAND_ACCOUNTING_TOL:
        raise AssertionError("SC3 post-Stage-A land accounting does not close by ED")
    if float(np.max(np.abs(strict_closure))) > LAND_ACCOUNTING_TOL:
        raise AssertionError("SC3 strict post-rewetting land accounting does not close by ED")

    out["SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA"] = post_stage_a
    out["SC3_REWETTING_FROM_RELEASED_LAND_HA"] = rewetting
    out["SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"] = final_residual
    out["SC3_POST_STAGE_A_ACCOUNTING_CLOSURE_HA"] = stage_a_closure
    out["SC3_STRICT_REPORTING_ACCOUNTING_CLOSURE_HA"] = strict_closure
    out["SC3_REPORTING_VERSION"] = REPORTING_VERSION
    return out


def build_sc3_land_accounting_summary(
    frame: pd.DataFrame,
    *,
    gross_release_ha: float,
    stage_a_target_ha: float,
    parent_available_target_ha: float,
    rewetting_target_ha: float,
) -> pd.DataFrame:
    """Build one national row for the three-ledger SC3 land accounting."""

    out = add_sc3_reporting_aliases(frame)
    gross_release = _finite(gross_release_ha, "gross_release_ha")
    stage_a_target = _finite(stage_a_target_ha, "stage_a_target_ha")
    parent_target = _finite(
        parent_available_target_ha, "parent_available_target_ha"
    )
    rewetting_target = _finite(rewetting_target_ha, "rewetting_target_ha")

    if min(gross_release, stage_a_target, parent_target, rewetting_target) < -LAND_ACCOUNTING_TOL:
        raise ValueError("SC3 reporting controls must be non-negative")

    expected_parent = gross_release - stage_a_target
    if expected_parent < -LAND_ACCOUNTING_TOL:
        raise ValueError(
            "Stage-A national targets exceed gross released land; parent Available is negative"
        )
    if abs(parent_target - expected_parent) > LAND_ACCOUNTING_TOL:
        raise AssertionError(
            "parent Available target does not equal gross release minus Stage-A targets"
        )

    release_from_ed = float(
        pd.to_numeric(out["SC2_POTENTIAL_RELEASE_HA"], errors="raise").sum()
    )
    if abs(release_from_ed - gross_release) > LAND_ACCOUNTING_TOL:
        raise AssertionError(
            "SC3 ED released-land total disagrees with the run gross-release control"
        )

    stage_a_realised = float(
        pd.to_numeric(out["SC3_STAGE_A_REALIZED_HA"], errors="raise").sum()
    )
    post_stage_a = float(
        pd.to_numeric(
            out["SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA"], errors="raise"
        ).sum()
    )
    rewetting_realised = float(
        pd.to_numeric(
            out["SC3_REWETTING_FROM_RELEASED_LAND_HA"], errors="raise"
        ).sum()
    )
    final_residual = float(
        pd.to_numeric(
            out["SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"], errors="raise"
        ).sum()
    )

    stage_a_unmet = max(stage_a_target - stage_a_realised, 0.0)
    rewetting_unmet = max(rewetting_target - rewetting_realised, 0.0)
    post_minus_parent = post_stage_a - parent_target

    if abs(post_minus_parent - stage_a_unmet) > LAND_ACCOUNTING_TOL:
        raise AssertionError(
            "post-Stage-A residual minus parent target Available must equal Stage-A unmet land"
        )

    parent_closure = stage_a_target + parent_target - gross_release
    stage_a_spatial_closure = stage_a_realised + post_stage_a - gross_release
    strict_closure = (
        stage_a_realised + rewetting_realised + final_residual - gross_release
    )

    row: dict[str, float | str] = {
        "GROSS_RELEASE_HA": gross_release,
        "STAGE_A_TARGET_HA": stage_a_target,
        "STAGE_A_REALIZED_HA": stage_a_realised,
        "STAGE_A_UNMET_HA": stage_a_unmet,
        "GOBLIN_PARENT_AVAILABLE_TARGET_HA": parent_target,
        "SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA": post_stage_a,
        "POST_STAGE_A_MINUS_PARENT_TARGET_HA": post_minus_parent,
        "REWETTING_TARGET_HA": rewetting_target,
        "REWETTING_REALIZED_HA": rewetting_realised,
        "REWETTING_UNMET_HA": rewetting_unmet,
        "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA": final_residual,
        "PARENT_TARGET_ACCOUNTING_CLOSURE_HA": parent_closure,
        "SPATIAL_STAGE_A_ACCOUNTING_CLOSURE_HA": stage_a_spatial_closure,
        "STRICT_SPATIAL_ACCOUNTING_CLOSURE_HA": strict_closure,
        "PARENT_TARGET_ACCOUNTING_STATUS": (
            "PASS" if abs(parent_closure) <= LAND_ACCOUNTING_TOL else "FAIL"
        ),
        "SPATIAL_STAGE_A_ACCOUNTING_STATUS": (
            "PASS" if abs(stage_a_spatial_closure) <= LAND_ACCOUNTING_TOL else "FAIL"
        ),
        "STRICT_SPATIAL_ACCOUNTING_STATUS": (
            "PASS" if abs(strict_closure) <= LAND_ACCOUNTING_TOL else "FAIL"
        ),
        "REPORTING_VERSION": REPORTING_VERSION,
    }
    return pd.DataFrame([row])


def build_sc3_validation_table(
    frame: pd.DataFrame,
    accounting_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Return explicit scientific PASS/FAIL checks for SC3 land accounting."""

    if len(accounting_summary) != 1:
        raise ValueError("accounting_summary must contain exactly one row")
    out = add_sc3_reporting_aliases(frame)
    row = accounting_summary.iloc[0]

    rewet_minus_post = float(
        (
            pd.to_numeric(
                out["SC3_REWETTING_FROM_RELEASED_LAND_HA"], errors="raise"
            )
            - pd.to_numeric(
                out["SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA"], errors="raise"
            )
        ).max()
    )
    min_final = float(
        pd.to_numeric(
            out["SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA"], errors="raise"
        ).min()
    )

    checks = [
        (
            "Parent GOBLIN target accounting closes",
            0.0,
            float(row["PARENT_TARGET_ACCOUNTING_CLOSURE_HA"]),
        ),
        (
            "Realised Stage-A spatial accounting closes",
            0.0,
            float(row["SPATIAL_STAGE_A_ACCOUNTING_CLOSURE_HA"]),
        ),
        (
            "Strict post-rewetting spatial accounting closes",
            0.0,
            float(row["STRICT_SPATIAL_ACCOUNTING_CLOSURE_HA"]),
        ),
        (
            "Stage-A unmet equals post-Stage-A excess over parent Available",
            float(row["STAGE_A_UNMET_HA"]),
            float(row["POST_STAGE_A_MINUS_PARENT_TARGET_HA"]),
        ),
        (
            "Rewetting does not exceed post-Stage-A unallocated land by ED",
            0.0,
            max(rewet_minus_post, 0.0),
        ),
        (
            "Final unallocated released land is non-negative by ED",
            0.0,
            min(min_final, 0.0),
        ),
    ]

    records = []
    for check, expected, actual in checks:
        passed = abs(actual - expected) <= LAND_ACCOUNTING_TOL
        records.append(
            {
                "CHECK": check,
                "EXPECTED": expected,
                "ACTUAL": actual,
                "TOLERANCE": LAND_ACCOUNTING_TOL,
                "STATUS": "PASS" if passed else "FAIL",
            }
        )
    return pd.DataFrame(records)


def _read_optional(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path, low_memory=False) if path.exists() else None


def _headline_results(
    controls: pd.DataFrame,
    livestock: pd.DataFrame | None,
    accounting: pd.DataFrame | None,
) -> pd.DataFrame:
    if len(controls) != 1:
        raise ValueError("sc1_control_summary.csv must contain exactly one row")
    c = controls.iloc[0]
    records: list[dict[str, object]] = []

    def add(metric: str, value: object, unit: str, source: str) -> None:
        records.append(
            {"METRIC": metric, "VALUE": value, "UNIT": unit, "SOURCE": source}
        )

    control_items = (
        ("Scenario", "SCENARIO_ID", ""),
        ("Scenario name", "SCENARIO_NAME", ""),
        ("Baseline year", "RUN_START_YEAR", "year"),
        ("Target year", "TARGET_YEAR", "year"),
        ("Allocation policy", "ALLOCATION_POLICY", ""),
        ("Protection strength", "PROTECTION_STRENGTH_LAMBDA", "lambda"),
        ("Gross livestock-land release", "RUN_GROSS_RELEASE_HA", "ha"),
        ("Target livestock land", "TARGET_LIVESTOCK_LAND_HA", "ha"),
        ("Stage-A national target", "STAGE_A_TARGET_HA", "ha"),
        (
            "GOBLIN parent Available target",
            "GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA",
            "ha",
        ),
        ("Rewetting target", "REWETTING_TARGET_HA", "ha"),
    )
    for metric, column, unit in control_items:
        if column in c.index:
            add(metric, c[column], unit, "SC1 control")

    if livestock is not None and len(livestock) == 1:
        l = livestock.iloc[0]
        livestock_items = (
            ("Scenario dairy cows", "SCENARIO_DAIRY_COW", "head"),
            ("Scenario suckler cows", "SCENARIO_SUCKLER_COW", "head"),
            ("Scenario total cattle", "SCENARIO_TOTAL_CATTLE", "head"),
            ("Total cattle change", "TOTAL_CATTLE_CHANGE", "head"),
            ("Total cattle change percent", "TOTAL_CATTLE_CHANGE_PCT", "%"),
        )
        for metric, column, unit in livestock_items:
            if column in l.index:
                add(metric, l[column], unit, "SC1 national livestock summary")

    if accounting is not None and len(accounting) == 1:
        a = accounting.iloc[0]
        accounting_items = (
            ("Stage-A realised", "STAGE_A_REALIZED_HA"),
            ("Stage-A unmet", "STAGE_A_UNMET_HA"),
            (
                "Post-Stage-A unallocated released land",
                "SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA",
            ),
            ("Rewetting realised", "REWETTING_REALIZED_HA"),
            ("Rewetting unmet", "REWETTING_UNMET_HA"),
            (
                "Final unallocated released land",
                "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA",
            ),
        )
        for metric, column in accounting_items:
            add(metric, a[column], "ha", "SC3 land accounting")

    return pd.DataFrame(records)


def _data_dictionary() -> pd.DataFrame:
    rows = [
        (
            "GOBLIN_PARENT_AVAILABLE_TARGET_HA",
            "ha",
            "Parent pathway target-accounting residual: gross release minus the five national Stage-A targets. This reproduces the parent pathway accounting and is not a realised ED allocation.",
        ),
        (
            "SC3_POST_STAGE_A_UNALLOCATED_RELEASE_HA",
            "ha",
            "Realised released land remaining after feasible Stage-A allocations. It can exceed parent Available when Stage-A targets are spatially unmet.",
        ),
        (
            "STAGE_A_UNMET_HA",
            "ha",
            "National Stage-A target hectares not spatially realised. Nationally this equals post-Stage-A unallocated release minus parent Available target accounting.",
        ),
        (
            "SC3_REWETTING_FROM_RELEASED_LAND_HA",
            "ha",
            "Realised rewetting allocated from the post-Stage-A released-land residual and constrained by drained-organic-grassland stock.",
        ),
        (
            "SC3_FINAL_UNALLOCATED_RELEASED_LAND_HA",
            "ha",
            "Strict physical residual after realised Stage-A uses and realised rewetting. Do not label this as the parent GOBLIN Available category.",
        ),
    ]
    return pd.DataFrame(rows, columns=["VARIABLE", "UNIT", "INTERPRETATION"])


def _format_sheet(writer: pd.ExcelWriter, name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[name]
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(1, 0)
    if len(frame.columns) > 0:
        worksheet.autofilter(0, 0, max(len(frame), 1), len(frame.columns) - 1)

    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1F4E78",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    number = workbook.add_format({"num_format": "#,##0.00"})
    integer = workbook.add_format({"num_format": "#,##0"})

    for col, column in enumerate(frame.columns):
        worksheet.write(0, col, column, header)
        width = max(12, min(42, len(str(column)) + 2))
        if column in {"INTERPRETATION", "CHECK", "METRIC", "SOURCE", "VALUE"}:
            width = 42
        upper = str(column).upper()
        fmt = None
        if upper.endswith("_HA") or upper in {"EXPECTED", "ACTUAL", "TOLERANCE"}:
            fmt = number
        elif upper.endswith("_YEAR") or upper.endswith("_COW") or upper.endswith("_CATTLE"):
            fmt = integer
        worksheet.set_column(col, col, width, fmt)
    worksheet.set_row(0, 28)


def export_scientific_results(
    run_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Path]:
    """Create scientific summaries and a workbook from one principal run."""

    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"scenario run directory not found: {run_dir}")

    controls_path = run_dir / "sc1_control_summary.csv"
    if not controls_path.exists():
        raise FileNotFoundError(f"missing required SC1 control summary: {controls_path}")
    controls = pd.read_csv(controls_path)
    if len(controls) != 1:
        raise ValueError("sc1_control_summary.csv must contain exactly one row")

    livestock = _read_optional(run_dir / "sc1_national_livestock_summary.csv")
    metrics = _read_optional(run_dir / "sc1_national_metrics.csv")
    reconciliation = _read_optional(run_dir / "sc1_goblin_reconciliation.csv")
    county = _read_optional(run_dir / "sc1_county_summary.csv")
    sc1_ed = _read_optional(run_dir / "sc1_ed_results.csv")
    sc2_ed = _read_optional(run_dir / "sc2_ed_context.csv")
    sc3_ed = _read_optional(run_dir / "sc3_ed_results.csv")
    sc3_national = _read_optional(run_dir / "sc3_national_summary.csv")

    accounting: pd.DataFrame | None = None
    validation: pd.DataFrame | None = None
    enriched_sc3: pd.DataFrame | None = None
    outputs: dict[str, Path] = {}

    if sc3_ed is not None:
        required_control = {
            "RUN_GROSS_RELEASE_HA",
            "STAGE_A_TARGET_HA",
            "GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA",
            "REWETTING_TARGET_HA",
        }
        missing = sorted(required_control - set(controls.columns))
        if missing:
            raise ValueError(
                "SC3 scientific reporting requires control columns: "
                f"{missing}"
            )
        c = controls.iloc[0]
        enriched_sc3 = add_sc3_reporting_aliases(sc3_ed)
        accounting = build_sc3_land_accounting_summary(
            enriched_sc3,
            gross_release_ha=float(c["RUN_GROSS_RELEASE_HA"]),
            stage_a_target_ha=float(c["STAGE_A_TARGET_HA"]),
            parent_available_target_ha=float(
                c["GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA"]
            ),
            rewetting_target_ha=float(c["REWETTING_TARGET_HA"]),
        )
        validation = build_sc3_validation_table(enriched_sc3, accounting)

        accounting_csv = run_dir / "sc3_land_accounting_summary.csv"
        validation_csv = run_dir / "sc3_scientific_validation.csv"
        accounting.to_csv(accounting_csv, index=False)
        validation.to_csv(validation_csv, index=False)
        outputs["land_accounting_csv"] = accounting_csv
        outputs["validation_csv"] = validation_csv

    headline = _headline_results(controls, livestock, accounting)
    read_me = pd.DataFrame(
        [
            {
                "ITEM": "Purpose",
                "VALUE": "Scientific reporting view generated from canonical GOBLIN-Spatial CSV outputs.",
            },
            {
                "ITEM": "Canonical-data rule",
                "VALUE": "This workbook is derived reporting output. Canonical model CSV files remain the machine-readable source of truth.",
            },
            {
                "ITEM": "Available-land rule",
                "VALUE": "Parent GOBLIN Available target accounting, realised post-Stage-A unallocated release, and final post-rewetting residual are reported separately.",
            },
            {"ITEM": "Reporting version", "VALUE": REPORTING_VERSION},
            {"ITEM": "Run directory", "VALUE": str(run_dir)},
        ]
    )

    if output_path is None:
        workbook_path = run_dir / "GOBLIN_Spatial_Scientific_Results.xlsx"
    else:
        workbook_path = Path(output_path)
        if not workbook_path.is_absolute():
            workbook_path = run_dir / workbook_path
    workbook_path.parent.mkdir(parents=True, exist_ok=True)

    sheets: list[tuple[str, pd.DataFrame]] = [
        ("00_Read_Me", read_me),
        ("01_Run_Controls", controls),
        ("02_Headline_Results", headline),
    ]
    if accounting is not None:
        sheets.append(("03_SC3_Land_Accounting", accounting))
    if validation is not None:
        sheets.append(("04_Validation", validation))
    if sc3_national is not None:
        sheets.append(("05_SC3_National", sc3_national))
    if livestock is not None:
        sheets.append(("06_SC1_Livestock", livestock))
    if metrics is not None:
        sheets.append(("07_SC1_Metrics", metrics))
    if reconciliation is not None:
        sheets.append(("08_Reconciliation", reconciliation))
    if county is not None:
        sheets.append(("09_County_Results", county))
    sheets.append(("10_Data_Dictionary", _data_dictionary()))
    if enriched_sc3 is not None:
        sheets.append(("11_ED_Results", enriched_sc3))
    elif sc2_ed is not None:
        sheets.append(("11_ED_Results", sc2_ed))
    elif sc1_ed is not None:
        sheets.append(("11_ED_Results", sc1_ed))

    with pd.ExcelWriter(
        workbook_path,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_urls": False}},
    ) as writer:
        for name, frame in sheets:
            frame.to_excel(writer, sheet_name=name, index=False)
            _format_sheet(writer, name, frame)

    if not workbook_path.exists():
        raise AssertionError("scientific results workbook was not created")
    outputs["workbook"] = workbook_path
    return outputs
