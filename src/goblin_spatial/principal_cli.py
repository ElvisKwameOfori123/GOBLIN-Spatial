"""Stage-aware runner for the Colm-direct GOBLIN-Spatial scenario study.

SC1
    selected 2020/2025 Stage-08 livestock/grassland/SO baseline
    -> adult dairy/suckler endpoint allocation
    -> Stage-09 21-cohort propagation
    -> unchanged sheep
    -> fixed-2020 Standard Output exposure
    -> authoritative GOBLIN release spatialised from livestock/pasture-DM pressure
       with ALL_GRASSLAND as the only land-capacity bound

    No 08B, Colm soil or LPIS suitability evidence is loaded into SC1.

SC2 (2020 spatial baseline only)
    frozen SC1 release
    -> Colm mapped physical soil + LPIS 2020
    -> seven-category released physical-resource partition
    -> optional explicit, versioned, evidence-backed eligibility rules

SC3 (2020 spatial baseline only)
    explicit same-pathway national land-use targets
    -> five Stage-A uses compete jointly for finite ED x Colm-soil resource cells
    -> realised + unmet + residual land
    -> rewetting only from an explicit validated drained-organic/agricultural
       capacity control; mapped peat alone is never accepted as capacity

The legacy 08B/G1-G2-G3 runtime remains available on the historical main branch
as a benchmark but is not part of this Colm-direct decision chain.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.land.colm_rules import load_colm_eligibility_control
from goblin_spatial.land.rewetting_capacity import (
    attach_rewetting_capacity,
    load_rewetting_capacity_control,
)
from goblin_spatial.land.sc2_context import prepare_sc2_context
from goblin_spatial.land.sc3_colm_allocation import (
    allocate_colm_sc3_targets,
    summarise_colm_sc3_allocation,
)
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
        description="Run an ACTIVE GOBLIN pathway through Colm-direct GOBLIN-Spatial.",
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
    parser.add_argument(
        "--land-context",
        default=None,
        help=(
            "Colm physical-soil + LPIS context source used only by SC2/SC3. "
            "The default repository directory may still contain 08B, but the "
            "Colm-direct reader ignores it."
        ),
    )
    parser.add_argument(
        "--colm-eligibility-rules",
        default=None,
        help=(
            "Versioned Stage-A use x seven-Colm-soil eligibility CSV. Optional "
            "for SC2 physical-resource inspection; required for SC3."
        ),
    )
    parser.add_argument(
        "--rewetting-capacity",
        default=None,
        help=(
            "Versioned ED-level validated drained-organic/agricultural rewetting "
            "capacity control. Required by SC3 when the pathway rewetting target is positive."
        ),
    )
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


def _user_path(cfg, value: str | None, *, label: str) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    path = path if path.is_absolute() else cfg.project_root / path
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def _output_dir(args, cfg) -> Path:
    if args.output_dir is not None:
        path = Path(args.output_dir)
        return path if path.is_absolute() else cfg.project_root / path
    name = f"{args.scenario}_{int(args.baseline_year)}_{args.allocation_rule}"
    return cfg.processed_dir / "principal" / name


def _validate_stage08_baseline(
    panel: pd.DataFrame,
    *,
    baseline_year: int,
    expected_eds: int,
) -> pd.DataFrame:
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
        "SCENARIO_DAIRY_COW": int(
            pd.to_numeric(ed["SCENARIO_DAIRY_COW"], errors="raise").sum()
        ),
        "SCENARIO_SUCKLER_COW": int(
            pd.to_numeric(ed["SCENARIO_OTHER_COW"], errors="raise").sum()
        ),
        "SCENARIO_TOTAL_CATTLE": int(
            pd.to_numeric(ed["SCENARIO_TOTAL_CATTLE"], errors="raise").sum()
        ),
        "BASE_TOTAL_CATTLE": int(
            pd.to_numeric(ed["BASE_TOTAL_CATTLE"], errors="raise").sum()
        ),
    }
    row["TOTAL_CATTLE_CHANGE"] = row["SCENARIO_TOTAL_CATTLE"] - row["BASE_TOTAL_CATTLE"]
    row["TOTAL_CATTLE_CHANGE_PCT"] = (
        0.0
        if row["BASE_TOTAL_CATTLE"] == 0
        else 100.0 * row["TOTAL_CATTLE_CHANGE"] / row["BASE_TOTAL_CATTLE"]
    )
    if "GOBLIN_RELEASED_GRASSLAND_HA" in ed.columns:
        row["GOBLIN_RELEASED_GRASSLAND_HA"] = float(
            pd.to_numeric(ed["GOBLIN_RELEASED_GRASSLAND_HA"], errors="raise").sum()
        )
        for system in ("DAIRY", "BEEF", "SHEEP"):
            column = f"GOBLIN_RELEASED_{system}_LAND_HA"
            if column in ed.columns:
                row[column] = float(pd.to_numeric(ed[column], errors="raise").sum())
    for column in (
        "SIGNED_GRASSLAND_BALANCE_HA",
        "POTENTIAL_SPARED_GRASSLAND_HA",
        "ADDITIONAL_GRASSLAND_REQUIRED_HA",
    ):
        if column in ed.columns:
            row[column] = float(pd.to_numeric(ed[column], errors="raise").sum())
    return pd.DataFrame([row])


def main() -> None:
    args = _parser().parse_args()
    cfg = load_config(Path(args.config))

    if args.stage in {"SC2", "SC3"} and int(args.baseline_year) != 2020:
        raise ValueError(
            "Colm-direct SC2/SC3 currently require the frozen 2020 spatial baseline. "
            "A validated 2025 Colm+LPIS context has not yet been supplied."
        )

    baseline_path = (
        _configured_path(cfg, "_override", args.baseline_master)
        if args.baseline_master is not None
        else _configured_output(
            cfg,
            "standard_output_master",
            "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
        )
    )
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Stage-08 Standard Output baseline not found: {baseline_path}. "
            "Run the validated historical baseline first."
        )

    panel = pd.read_csv(baseline_path, low_memory=False)
    baseline = _validate_stage08_baseline(
        panel,
        baseline_year=int(args.baseline_year),
        expected_eds=int(cfg.expected_eds),
    )
    baseline_grassland_ha = float(
        pd.to_numeric(baseline["ALL_GRASSLAND"], errors="raise").sum()
    )

    controls_path = _required_path(cfg, "scenario_controls", args.scenario_controls)
    active_ids = active_scenario_ids(controls_path)
    if args.scenario not in active_ids:
        raise ValueError(
            f"scenario {args.scenario!r} is not ACTIVE; available scenarios={active_ids}"
        )
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

    # SC1 receives the validated historical panel directly. No land-context file
    # is read or attached here, which makes soil/LPIS independence executable.
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

    control_summary = pd.DataFrame(
        [
            {
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
                "GOBLIN_PARENT_AVAILABLE_BEFORE_REWETTING_HA": (
                    selection.stage_a_available_before_rewetting_ha
                ),
                "REWETTING_TARGET_HA": selection.rewetting_target_ha,
                "SC1_SOIL_OR_LPIS_USED": False,
            }
        ]
    )

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
        print("SC1 completed and frozen. No soil or LPIS context was loaded.")
        return

    land_context_path = _required_path(cfg, "land_context_2020", args.land_context)
    rule_path = _user_path(
        cfg,
        args.colm_eligibility_rules,
        label="Colm eligibility rule control",
    )
    rules = None
    rule_version = None
    evidence_note = None
    if rule_path is not None:
        rules, rule_version, evidence_note = load_colm_eligibility_control(rule_path)

    sc2 = prepare_sc2_context(
        ed,
        land_context=land_context_path,
        baseline_year=int(args.baseline_year),
        eligibility_rules=rules,
        rule_version=rule_version,
        evidence_note=evidence_note,
    )
    sc2_path = outdir / "sc2_ed_context.csv"
    sc2.to_csv(sc2_path, index=False)
    print(f"SC2 Colm+LPIS ED context: {sc2_path}")

    if args.stage == "SC2":
        if rules is None:
            print(
                "SC2 completed as physical-resource + LPIS context only; "
                "no unvalidated eligibility assumptions were applied."
            )
        else:
            print(f"SC2 completed with explicit eligibility rule version {rule_version}.")
        return

    if rules is None:
        raise ValueError(
            "SC3 requires --colm-eligibility-rules. No default land-use "
            "suitability assumptions are permitted in the Colm-direct architecture."
        )

    milestone = controls.milestone(target_year)
    targets = dict(milestone.land_use_targets_ha)

    rewetting_mapping = None
    rewetting_path = _user_path(
        cfg,
        args.rewetting_capacity,
        label="rewetting capacity control",
    )
    if float(targets.get("REWETTING", 0.0)) > 1e-7:
        if rewetting_path is None:
            raise ValueError(
                "this pathway has a positive REWETTING target, so SC3 requires "
                "--rewetting-capacity. Colm mapped peat alone is not treated as "
                "drained agricultural organic-soil capacity."
            )
        rewet_control, rewetting_mapping, rewet_version, rewet_evidence = (
            load_rewetting_capacity_control(
                rewetting_path,
                expected_eds=int(cfg.expected_eds),
            )
        )
        sc2 = attach_rewetting_capacity(sc2, rewet_control)
        sc2["SC3_REWETTING_CAPACITY_VERSION"] = rewet_version
        sc2["SC3_REWETTING_CAPACITY_EVIDENCE"] = rewet_evidence

    sc3 = allocate_colm_sc3_targets(
        sc2,
        targets,
        eligibility_rules=rules,
        opportunity_columns=None,
        rewetting_capacity_columns=rewetting_mapping,
    )
    sc3_path = outdir / "sc3_ed_results.csv"
    sc3_summary_path = outdir / "sc3_national_summary.csv"
    sc3.to_csv(sc3_path, index=False)
    summarise_colm_sc3_allocation(sc3).to_csv(sc3_summary_path, index=False)
    print(f"SC3 Colm-resource ED results: {sc3_path}")
    print(f"SC3 national realised/unmet/residual summary: {sc3_summary_path}")
    print(
        "SC3 completed as a joint finite-resource feasibility test. No arbitrary "
        "opportunity ranking was applied."
    )


if __name__ == "__main__":
    main()
