"""Stage-aware runner for the principal GOBLIN-Spatial scenario study.

Normal 2020 scenario runs are offline with respect to spatial source data. They
consume the repository Stage-08 historical panel plus one frozen 2,857-ED land
context carrying 08B capability, independent 08C physical soil and LPIS 2020.
Heavy source processing is never triggered by this runner.

SC1
    selected 2020/2025 Stage-08 baseline
    -> frozen model-ED 08B capability attachment
    -> adult dairy/suckler endpoint allocation
    -> Stage-09 21-cohort propagation
    -> unchanged sheep
    -> fixed-2020 Standard Output exposure
    -> 08B-constrained authoritative released-land geography

SC2 (2020 spatial baseline only)
    frozen SC1
    -> LPIS 2020 + independent 08C from ED_Land_Context_2020
    -> mature v3.1 opportunity and physical eligibility

SC3 (2020 spatial baseline only)
    editable national land-use targets
    -> mature v2.7 joint Stage-A allocation
    -> sequential rewetting within post-Stage-A residual capacity
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.land.context import read_land_context_table
from goblin_spatial.land.context_attach import add_frozen_08b_context
from goblin_spatial.land.sc2_context import prepare_sc2_context
from goblin_spatial.land.sc3_allocation import allocate_sc3_targets, summarise_sc3_allocation
from goblin_spatial.pressure import load_pasture_dm_control
from goblin_spatial.scenario.control_table import active_scenario_ids, load_scenario_controls
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.metrics import build_sc1_county_summary, build_sc1_national_metrics
from goblin_spatial.scenario.principal_allocation import (
    PRINCIPAL_ALLOCATION_POLICIES,
    PRINCIPAL_PROTECTION_STRENGTH,
)
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.scenario.reconciliation import build_goblin_reconciliation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-principal",
        description="Run an ACTIVE GOBLIN pathway from the validated ED baseline.",
    )
    parser.add_argument("scenario", help="SCENARIO_ID from the editable control CSV")
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument("--baseline-year", type=int, choices=(2020, 2025), default=2020)
    parser.add_argument("--scenario-controls", default=None)
    parser.add_argument(
        "--allocation-rule",
        choices=PRINCIPAL_ALLOCATION_POLICIES,
        default="PRORATA",
        help="Validated principal SC1 incidence policy.",
    )
    parser.add_argument(
        "--protection-strength",
        type=float,
        default=PRINCIPAL_PROTECTION_STRENGTH,
        help="Principal protection strength lambda; default 0.50.",
    )
    parser.add_argument("--baseline-master", default=None)
    parser.add_argument("--land-context", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--stage", choices=("SC1", "SC2", "SC3"), default="SC1")
    return parser


def _configured_output(cfg, key: str, default: str) -> Path:
    value = cfg.raw.get("outputs", {}).get(key, default)
    path = Path(value)
    return path if path.is_absolute() else cfg.project_root / path


def _configured_path(cfg, key: str, override: str | None = None) -> Path:
    if override is not None:
        path = Path(override)
        return path if path.is_absolute() else cfg.project_root / path
    path = cfg.files.get(key)
    if path is None:
        raise KeyError(f"configuration missing files.{key}")
    path = Path(path)
    return path if path.is_absolute() else cfg.project_root / path


def _required_path(cfg, key: str, override: str | None = None) -> Path:
    path = _configured_path(cfg, key, override)
    if not path.exists():
        raise FileNotFoundError(
            f"required repository/input control not found for {key}: {path}. "
            "Principal scenario runs never auto-download or rebuild spatial sources."
        )
    return path


def _output_dir(args, cfg) -> Path:
    if args.output_dir is not None:
        path = Path(args.output_dir)
        return path if path.is_absolute() else cfg.project_root / path
    name = f"{args.scenario}_{int(args.baseline_year)}_{args.allocation_rule}"
    return cfg.processed_dir / "principal" / name


def _validate_stage08_baseline(panel: pd.DataFrame, *, baseline_year: int, expected_eds: int) -> pd.DataFrame:
    baseline = select_baseline_year(panel, baseline_year, expected_eds=expected_eds)
    required = {
        "CSOED",
        "County",
        "ALL_GRASSLAND",
        "AGRICULTURAL_HOLDINGS",
        "AVERAGE_SIZE_OF_HOLDINGS",
        "MEDIAN_AGE_OF_HOLDER",
        "SO_LIVESTOCK_2020_EUR",
    }
    missing = sorted(required - set(baseline.columns))
    if missing:
        raise ValueError(
            "principal SC1 must start from the Stage-08 Standard Output-enriched "
            f"baseline; missing columns={missing}"
        )
    return baseline


def _national_livestock_summary(ed: pd.DataFrame) -> pd.DataFrame:
    row = {
        "PATHWAY_NAME": str(ed["PATHWAY_NAME"].iloc[0]),
        "PATHWAY_BASELINE_YEAR": int(ed["PATHWAY_BASELINE_YEAR"].iloc[0]),
        "MILESTONE_YEAR": int(ed["MILESTONE_YEAR"].iloc[0]),
        "PATHWAY_ALLOCATION_RULE": str(ed["PATHWAY_ALLOCATION_RULE"].iloc[0]),
        "PROTECTION_STRENGTH_LAMBDA": float(ed["PROTECTION_STRENGTH_LAMBDA"].iloc[0]),
        "NATIONAL_COHORT_TARGET_SOURCE": str(ed["NATIONAL_COHORT_TARGET_SOURCE"].iloc[0]),
        "SCENARIO_DAIRY_COW": int(pd.to_numeric(ed["SCENARIO_DAIRY_COW"], errors="raise").sum()),
        "SCENARIO_SUCKLER_COW": int(pd.to_numeric(ed["SCENARIO_OTHER_COW"], errors="raise").sum()),
        "SCENARIO_TOTAL_CATTLE": int(pd.to_numeric(ed["SCENARIO_TOTAL_CATTLE"], errors="raise").sum()),
        "BASE_TOTAL_CATTLE": int(pd.to_numeric(ed["BASE_TOTAL_CATTLE"], errors="raise").sum()),
    }
    row["TOTAL_CATTLE_CHANGE"] = row["SCENARIO_TOTAL_CATTLE"] - row["BASE_TOTAL_CATTLE"]
    row["TOTAL_CATTLE_CHANGE_PCT"] = (
        0.0 if row["BASE_TOTAL_CATTLE"] == 0
        else 100.0 * row["TOTAL_CATTLE_CHANGE"] / row["BASE_TOTAL_CATTLE"]
    )
    if "GOBLIN_RELEASED_GRASSLAND_HA" in ed.columns:
        row["GOBLIN_RELEASED_GRASSLAND_HA"] = float(pd.to_numeric(ed["GOBLIN_RELEASED_GRASSLAND_HA"], errors="raise").sum())
        for group in (1, 2, 3):
            column = f"GOBLIN_RELEASED_G{group}_HA"
            if column in ed.columns:
                row[column] = float(pd.to_numeric(ed[column], errors="raise").sum())
        for system in ("DAIRY", "BEEF", "SHEEP"):
            column = f"GOBLIN_RELEASED_{system}_LAND_HA"
            if column in ed.columns:
                row[column] = float(pd.to_numeric(ed[column], errors="raise").sum())
    return pd.DataFrame([row])


def main() -> None:
    args = _parser().parse_args()
    cfg = load_config(Path(args.config))

    if args.stage in {"SC2", "SC3"} and int(args.baseline_year) != 2020:
        raise ValueError(
            "SC2/SC3 currently require the frozen 2020 spatial baseline. "
            "A validated 2025 land-context control has not yet been supplied."
        )

    baseline_path = (
        _configured_path(cfg, "_override", args.baseline_master)
        if args.baseline_master is not None
        else _configured_output(cfg, "standard_output_master", "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv")
    )
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Stage-08 Standard Output baseline not found: {baseline_path}. "
            "Run the validated historical baseline first."
        )

    panel = pd.read_csv(baseline_path, low_memory=False)
    _validate_stage08_baseline(
        panel,
        baseline_year=int(args.baseline_year),
        expected_eds=int(cfg.expected_eds),
    )

    land_context_path = _required_path(cfg, "land_context_2020", args.land_context)
    land_context = read_land_context_table(land_context_path)

    # The frozen 08B model-ED control is a fixed agricultural-capability reference
    # and can be attached to either selectable livestock baseline year. Its 2,820
    # direct and 37 county-fallback provenance labels are preserved exactly.
    # LPIS and 08C fields remain outside the livestock state until SC2.
    panel = add_frozen_08b_context(panel, land_context)
    baseline = select_baseline_year(
        panel,
        int(args.baseline_year),
        expected_eds=int(cfg.expected_eds),
    )
    baseline_grassland_ha = float(pd.to_numeric(baseline["ALL_GRASSLAND"], errors="raise").sum())

    controls_path = _required_path(cfg, "scenario_controls", args.scenario_controls)
    active_ids = active_scenario_ids(controls_path)
    if args.scenario not in active_ids:
        raise ValueError(f"scenario {args.scenario!r} is not ACTIVE; available scenarios={active_ids}")
    selection = load_scenario_controls(
        controls_path,
        scenario_id=args.scenario,
        baseline_year=int(args.baseline_year),
        baseline_grassland_ha=baseline_grassland_ha,
    )
    controls = selection.controls
    target_year = int(selection.target_year)

    cohort_reference = _required_path(cfg, "goblin_cohorts")
    pasture_control = _required_path(cfg, "pasture_dm_controls")
    pasture_profiles = load_pasture_dm_control(
        pasture_control,
        required_years={int(args.baseline_year), target_year},
    )
    mapping = str(_required_path(cfg, "standard_output_mapping"))
    coefficients = str(_required_path(cfg, "standard_output_coefficients"))

    ed = run_principal_goblin_endpoint(
        panel,
        controls,
        allocation_rule=AllocationRule(args.allocation_rule),
        protection_strength=float(args.protection_strength),
        expected_eds=int(cfg.expected_eds),
        include_standard_output=True,
        mapping_path=mapping,
        coefficient_path=coefficients,
        cohort_reference_path=str(cohort_reference),
        cohort_reference_year=2020,
        pasture_dm_t_per_head_by_year=pasture_profiles,
    )
    ed["SCENARIO_DISPLAY_NAME"] = selection.scenario_name
    ed["RUN_BASELINE_GRASSLAND_HA"] = selection.baseline_grassland_ha
    ed["TARGET_LIVESTOCK_LAND_HA"] = selection.target_livestock_land_ha
    ed["RUN_GROSS_RELEASE_HA"] = selection.gross_release_ha

    outdir = _output_dir(args, cfg)
    outdir.mkdir(parents=True, exist_ok=True)
    ed_path = outdir / "sc1_ed_results.csv"
    livestock_summary_path = outdir / "sc1_national_livestock_summary.csv"
    metrics_path = outdir / "sc1_national_metrics.csv"
    county_path = outdir / "sc1_county_summary.csv"
    controls_summary_path = outdir / "sc1_control_summary.csv"
    reconciliation_path = outdir / "sc1_goblin_reconciliation.csv"

    control_summary = pd.DataFrame([{
        "SCENARIO_NO": selection.scenario_no,
        "SCENARIO_ID": selection.scenario_id,
        "SCENARIO_NAME": selection.scenario_name,
        "RUN_START_YEAR": selection.baseline_year,
        "TARGET_YEAR": selection.target_year,
        "ALLOCATION_POLICY": args.allocation_rule,
        "PROTECTION_STRENGTH_LAMBDA": float(args.protection_strength),
        "BASELINE_GRASSLAND_HA": selection.baseline_grassland_ha,
        "TARGET_LIVESTOCK_LAND_HA": selection.target_livestock_land_ha,
        "RUN_GROSS_RELEASE_HA": selection.gross_release_ha,
        "STAGE_A_TARGET_HA": selection.stage_a_target_ha,
        "GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA": selection.stage_a_available_before_rewetting_ha,
        "REWETTING_TARGET_HA": selection.rewetting_target_ha,
    }])

    ed.to_csv(ed_path, index=False)
    _national_livestock_summary(ed).to_csv(livestock_summary_path, index=False)
    build_sc1_national_metrics(ed).to_csv(metrics_path, index=False)
    build_sc1_county_summary(ed).to_csv(county_path, index=False)
    control_summary.to_csv(controls_summary_path, index=False)
    build_goblin_reconciliation(ed, controls).to_csv(reconciliation_path, index=False)

    print(f"SC1 ED results: {ed_path}")
    print(f"SC1 national livestock summary: {livestock_summary_path}")
    print(f"SC1 national metrics: {metrics_path}")
    print(f"SC1 county summary: {county_path}")
    print(f"SC1 control summary: {controls_summary_path}")
    print(f"SC1 GOBLIN reconciliation: {reconciliation_path}")

    if args.stage == "SC1":
        print("SC1 completed and frozen. No spatial source rebuild was invoked.")
        return

    sc2 = prepare_sc2_context(
        ed,
        land_context=land_context,
        baseline_year=int(args.baseline_year),
    )
    sc2_path = outdir / "sc2_ed_context.csv"
    sc2.to_csv(sc2_path, index=False)
    print(f"SC2 ED opportunity/context: {sc2_path}")

    if args.stage == "SC2":
        print("SC2 mature v3.1 completed from the frozen 2020 land context.")
        return

    milestone = controls.milestone(target_year)
    sc3 = allocate_sc3_targets(sc2, dict(milestone.land_use_targets_ha))
    sc3_path = outdir / "sc3_ed_results.csv"
    sc3_summary_path = outdir / "sc3_national_summary.csv"
    sc3.to_csv(sc3_path, index=False)
    summarise_sc3_allocation(sc3).to_csv(sc3_summary_path, index=False)
    print(f"SC3 ED results: {sc3_path}")
    print(f"SC3 national summary: {sc3_summary_path}")
    print("SC3 mature v2.7 completed with explicit targets and strict land accounting.")


if __name__ == "__main__":
    main()
