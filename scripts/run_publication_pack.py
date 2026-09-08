"""Build the final eight-run GOBLIN-Spatial publication result pack.

This script deliberately reuses the frozen scientific engine. It does not alter
SC1, SC2 or SC3 mathematics. It runs the two principal pathways across the four
validated allocation rules, builds the transparent central rewetting proxy used
for this paper, executes SC3, samples same-outcome post-SC3 feasible geographies,
validates accounting closure, materialises canonical report data, and writes a
small publication synthesis pack.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

from goblin_spatial.land.colm_rules import load_colm_eligibility_control
from goblin_spatial.land.sc3_feasible_geographies import (
    infer_rewetting_capacity_columns,
    sample_colm_sc3_feasible_geographies,
)
from goblin_spatial.scenario.control_table import read_scenario_control_table


SCENARIOS = ("BE_SG", "ALL_GAS_NZ")
RULES = (
    "PRORATA",
    "DAIRY_PROTECTION",
    "ECONOMIC_CAPACITY_PROTECTION",
    "SOCIAL_VULNERABILITY_PROTECTION",
)
USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
    "REWETTING",
)
BASELINE_YEAR = 2020
PROTECTION_STRENGTH = 0.50
EXPECTED_EDS = 2857
POSITIVE_TOL_HA = 1e-6


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True)


def ensure_rows(path: Path, expected: int = EXPECTED_EDS) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"CSOED": str}, low_memory=False)
    if len(frame) != expected:
        raise AssertionError(f"{path} has {len(frame):,} rows; expected {expected:,}")
    if "CSOED" in frame.columns and frame["CSOED"].duplicated().any():
        raise AssertionError(f"{path} contains duplicate CSOED values")
    return frame


def validate_sc3_summary(summary: pd.Series, controls: pd.Series) -> dict[str, object]:
    record: dict[str, object] = {}
    for use in USES:
        target_col = f"{use}_TARGET_HA"
        realised_col = f"{use}_REALISED_HA"
        unmet_col = f"{use}_UNMET_HA"
        target = float(summary[target_col])
        realised = float(summary[realised_col])
        unmet = float(summary[unmet_col])
        if min(target, realised, unmet) < -1e-7:
            raise AssertionError(f"negative SC3 quantity for {use}")
        if abs(target - realised - unmet) > 1e-5:
            raise AssertionError(f"SC3 target identity fails for {use}")
        control_col = {
            "AD_GRASS": "AD_GRASS_HA",
            "BIOREFINERY_GRASS": "BIOREFINERY_GRASS_HA",
            "WILLOW": "WILLOW_HA",
            "ADDITIONAL_TILLAGE": "ADDITIONAL_TILLAGE_HA",
            "FOREST": "ADDITIONAL_FOREST_HA",
            "REWETTING": "REWETTING_HA",
        }[use]
        expected_target = float(controls[control_col])
        if abs(target - expected_target) > 1e-5:
            raise AssertionError(
                f"SC3 target for {use} ({target}) does not match scenario control ({expected_target})"
            )
        record[f"{use}_TARGET_HA"] = target
        record[f"{use}_REALISED_HA"] = realised
        record[f"{use}_UNMET_HA"] = unmet
        record[f"{use}_REALISED_SHARE"] = 1.0 if target <= 1e-12 else realised / target
        record[f"{use}_UNMET_SHARE"] = 0.0 if target <= 1e-12 else unmet / target

    released = float(summary["TOTAL_RELEASED_HA"])
    allocated = float(summary["TOTAL_ALLOCATED_HA"])
    residual = float(summary["RESIDUAL_RELEASED_HA"])
    if min(released, allocated, residual) < -1e-7:
        raise AssertionError("negative total SC3 land-accounting quantity")
    if abs(released - allocated - residual) > 1e-5:
        raise AssertionError("SC3 released = allocated + residual identity fails")
    record["TOTAL_RELEASED_HA"] = released
    record["TOTAL_ALLOCATED_HA"] = allocated
    record["RESIDUAL_RELEASED_HA"] = residual
    record["TARGET_LIVESTOCK_LAND_HA"] = float(controls["TARGET_LIVESTOCK_LAND_HA"])
    record["INFERRED_BASELINE_ALL_GRASSLAND_HA"] = (
        released + float(controls["TARGET_LIVESTOCK_LAND_HA"])
    )
    record["OPPORTUNITY_RANKING_APPLIED"] = bool(summary["OPPORTUNITY_RANKING_APPLIED"])
    record["REWETTING_CAPACITY_STATUS"] = str(summary["REWETTING_CAPACITY_STATUS"])
    return record


def build_flexibility(
    run_dir: Path,
    *,
    rules: dict[str, dict[str, float]],
    scenario: str,
    allocation_rule: str,
    n_alternatives: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reference = pd.read_csv(run_dir / "sc3_ed_results.csv", dtype={"CSOED": str}, low_memory=False)
    rewetting_mapping = infer_rewetting_capacity_columns(reference)
    ensemble = sample_colm_sc3_feasible_geographies(
        reference,
        eligibility_rules=rules,
        rewetting_capacity_columns=rewetting_mapping,
        n_alternatives=int(n_alternatives),
    )

    allocations = ensemble.allocations.copy()
    flexibility = ensemble.flexibility.copy()
    diagnostics = ensemble.diagnostics.copy()
    for frame in (allocations, flexibility, diagnostics):
        frame.insert(0, "ALLOCATION_RULE", allocation_rule)
        frame.insert(0, "SCENARIO_ID", scenario)
        frame.insert(0, "RUN_ID", run_dir.name)

    allocations.to_csv(run_dir / "sc3_flexibility_allocations.csv", index=False)
    flexibility.to_csv(run_dir / "sc3_flexibility_summary.csv", index=False)
    diagnostics.to_csv(run_dir / "sc3_flexibility_diagnostics.csv", index=False)
    return allocations, flexibility, diagnostics


def build_national_long(inventory: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in inventory.iterrows():
        for use in USES:
            rows.append(
                {
                    "RUN_ID": row["RUN_ID"],
                    "SCENARIO_ID": row["SCENARIO_ID"],
                    "ALLOCATION_RULE": row["ALLOCATION_RULE"],
                    "USE": use,
                    "TARGET_HA": float(row[f"{use}_TARGET_HA"]),
                    "REALISED_HA": float(row[f"{use}_REALISED_HA"]),
                    "UNMET_HA": float(row[f"{use}_UNMET_HA"]),
                    "REALISED_SHARE": float(row[f"{use}_REALISED_SHARE"]),
                    "UNMET_SHARE": float(row[f"{use}_UNMET_SHARE"]),
                    "TOTAL_RELEASED_HA": float(row["TOTAL_RELEASED_HA"]),
                    "RESIDUAL_RELEASED_HA": float(row["RESIDUAL_RELEASED_HA"]),
                }
            )
    return pd.DataFrame(rows)


def build_sc3_sensitivity(national_long: pd.DataFrame) -> pd.DataFrame:
    grouped = national_long.groupby(["SCENARIO_ID", "USE"], sort=False)["REALISED_SHARE"]
    out = grouped.agg(
        MIN_REALISED_SHARE_ACROSS_RULES="min",
        MEAN_REALISED_SHARE_ACROSS_RULES="mean",
        MAX_REALISED_SHARE_ACROSS_RULES="max",
    ).reset_index()
    out["IMPLEMENTATION_RANGE_REALISED_SHARE"] = (
        out["MAX_REALISED_SHARE_ACROSS_RULES"] - out["MIN_REALISED_SHARE_ACROSS_RULES"]
    )
    return out


def build_crossrun_flexibility(all_flex: pd.DataFrame) -> pd.DataFrame:
    work = all_flex.copy()
    work["_REFERENCE_POSITIVE"] = work["REFERENCE_HA"].to_numpy(float) > POSITIVE_TOL_HA
    work["_ROBUST_POSITIVE"] = work["ROBUST_POSITIVE_SAMPLED"].astype(bool)
    grouped = work.groupby(["CSOED", "USE"], sort=False)
    out = grouped.agg(
        N_RUNS=("RUN_ID", "nunique"),
        N_RUNS_REFERENCE_POSITIVE=("_REFERENCE_POSITIVE", "sum"),
        N_RUNS_ROBUST_POSITIVE_SAMPLED=("_ROBUST_POSITIVE", "sum"),
        MIN_POSITIVE_FREQUENCY_SAMPLED=("POSITIVE_FREQUENCY_SAMPLED", "min"),
        MEAN_POSITIVE_FREQUENCY_SAMPLED=("POSITIVE_FREQUENCY_SAMPLED", "mean"),
        MAX_POSITIVE_FREQUENCY_SAMPLED=("POSITIVE_FREQUENCY_SAMPLED", "max"),
        MIN_OF_SAMPLED_MIN_HA=("MIN_SAMPLED_HA", "min"),
        MAX_OF_SAMPLED_MAX_HA=("MAX_SAMPLED_HA", "max"),
        MEAN_REFERENCE_HA=("REFERENCE_HA", "mean"),
    ).reset_index()
    out["PERSISTENT_REFERENCE_POSITIVE_ALL_RUNS"] = (
        out["N_RUNS_REFERENCE_POSITIVE"] == out["N_RUNS"]
    )
    out["PERSISTENT_ROBUST_POSITIVE_SAMPLED_ALL_RUNS"] = (
        out["N_RUNS_ROBUST_POSITIVE_SAMPLED"] == out["N_RUNS"]
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--principal-root", default="data/processed/principal")
    parser.add_argument("--report-data-root", default="reporting/report_data")
    parser.add_argument("--publication-root", default="reporting/publication")
    parser.add_argument(
        "--eligibility",
        default="data/controls/sc3/SC3_StageA_Eligibility_Principal_v1.csv",
    )
    parser.add_argument("--n-flex-alternatives", type=int, default=8)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    principal_root = Path(args.principal_root)
    report_data_root = Path(args.report_data_root)
    publication_root = Path(args.publication_root)
    eligibility = Path(args.eligibility)
    principal_root.mkdir(parents=True, exist_ok=True)
    publication_root.mkdir(parents=True, exist_ok=True)

    rules, eligibility_version, eligibility_evidence = load_colm_eligibility_control(eligibility)
    controls_table = read_scenario_control_table("data/controls/scenario/GOBLIN_Scenario_Controls.csv")
    controls_table = controls_table.set_index("SCENARIO_ID")

    inventory_rows: list[dict[str, object]] = []
    flex_frames: list[pd.DataFrame] = []
    flex_diag_frames: list[pd.DataFrame] = []

    for scenario in SCENARIOS:
        controls = controls_table.loc[scenario]
        for allocation_rule in RULES:
            run_id = f"{scenario}_{BASELINE_YEAR}_{allocation_rule}"
            run_dir = principal_root / run_id
            if args.clean and run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(parents=True, exist_ok=True)

            base = [
                "goblin-spatial-principal",
                scenario,
                "--baseline-year",
                str(BASELINE_YEAR),
                "--allocation-rule",
                allocation_rule,
                "--protection-strength",
                str(PROTECTION_STRENGTH),
                "--colm-eligibility-rules",
                str(eligibility),
                "--output-dir",
                str(run_dir),
            ]
            run([*base, "--stage", "SC2"])
            rewetting_proxy = run_dir / "rewetting_proxy.csv"
            run(
                [
                    sys.executable,
                    "scripts/build_rewetting_proxy_control.py",
                    "--sc2",
                    str(run_dir / "sc2_ed_context.csv"),
                    "--output",
                    str(rewetting_proxy),
                ]
            )
            run([*base, "--stage", "SC3", "--rewetting-capacity", str(rewetting_proxy)])

            sc1 = ensure_rows(run_dir / "sc1_ed_results.csv")
            sc2 = ensure_rows(run_dir / "sc2_ed_context.csv")
            sc3 = ensure_rows(run_dir / "sc3_ed_results.csv")
            if not sc1["CSOED"].equals(sc2["CSOED"]) or not sc1["CSOED"].equals(sc3["CSOED"]):
                raise AssertionError(f"ED order/key mismatch in {run_id}")

            summary_frame = pd.read_csv(run_dir / "sc3_national_summary.csv")
            if len(summary_frame) != 1:
                raise AssertionError(f"{run_id} SC3 national summary must contain one row")
            accounting = validate_sc3_summary(summary_frame.iloc[0], controls)
            accounting.update(
                {
                    "RUN_ID": run_id,
                    "SCENARIO_ID": scenario,
                    "ALLOCATION_RULE": allocation_rule,
                    "BASELINE_YEAR": BASELINE_YEAR,
                    "PROTECTION_STRENGTH_LAMBDA": PROTECTION_STRENGTH,
                    "ELIGIBILITY_VERSION": eligibility_version,
                    "N_EDS": len(sc3),
                }
            )
            inventory_rows.append(accounting)

            _, flexibility, diagnostics = build_flexibility(
                run_dir,
                rules=rules,
                scenario=scenario,
                allocation_rule=allocation_rule,
                n_alternatives=int(args.n_flex_alternatives),
            )
            flex_frames.append(flexibility)
            flex_diag_frames.append(diagnostics)

    inventory = pd.DataFrame(inventory_rows)
    if len(inventory) != 8:
        raise AssertionError(f"publication pack has {len(inventory)} runs; expected 8")

    # Fixed national endpoint means gross release must not change across allocation
    # rules within one pathway. The selected 2020 baseline must also be common.
    for scenario, block in inventory.groupby("SCENARIO_ID", sort=False):
        if block["TOTAL_RELEASED_HA"].max() - block["TOTAL_RELEASED_HA"].min() > 1e-5:
            raise AssertionError(f"gross release varies across allocation rules for {scenario}")
    if inventory["INFERRED_BASELINE_ALL_GRASSLAND_HA"].max() - inventory["INFERRED_BASELINE_ALL_GRASSLAND_HA"].min() > 1e-5:
        raise AssertionError("principal runs do not share one frozen 2020 ALL_GRASSLAND baseline")

    inventory.to_csv(publication_root / "publication_run_inventory.csv", index=False)
    national_long = build_national_long(inventory)
    national_long.to_csv(publication_root / "sc3_crossrun_national_long.csv", index=False)
    sensitivity = build_sc3_sensitivity(national_long)
    sensitivity.to_csv(publication_root / "sc3_feasibility_sensitivity.csv", index=False)

    all_flex = pd.concat(flex_frames, ignore_index=True, sort=False)
    all_flex.to_csv(publication_root / "sc3_flexibility_ed_all_runs.csv", index=False)
    crossrun_flex = build_crossrun_flexibility(all_flex)
    crossrun_flex.to_csv(
        publication_root / "sc3_crossrun_flexibility_robustness.csv", index=False
    )
    pd.concat(flex_diag_frames, ignore_index=True, sort=False).to_csv(
        publication_root / "sc3_flexibility_diagnostics_all_runs.csv", index=False
    )

    run(
        [
            "goblin-spatial-report-data",
            "--principal-root",
            str(principal_root),
            "--output-root",
            str(report_data_root),
        ]
    )

    report_manifest = json.loads((report_data_root / "report_data_manifest.json").read_text())
    if int(report_manifest["RUN_COUNT"]) != 8:
        raise AssertionError("canonical report-data manifest does not contain all eight runs")

    manifest = {
        "PUBLICATION_PACK_VERSION": "1.0",
        "MODEL_COMMIT": os.environ.get("GITHUB_SHA"),
        "BASELINE_YEAR": BASELINE_YEAR,
        "SCENARIOS": list(SCENARIOS),
        "ALLOCATION_RULES": list(RULES),
        "RUN_COUNT": 8,
        "PROTECTION_STRENGTH_LAMBDA": PROTECTION_STRENGTH,
        "EXPECTED_EDS": EXPECTED_EDS,
        "ELIGIBILITY_VERSION": eligibility_version,
        "ELIGIBILITY_EVIDENCE": eligibility_evidence,
        "REWETTING_CONTROL": "SC3_REWETTING_PROXY_CENTRAL_V1",
        "FLEXIBILITY_ALTERNATIVES_REQUESTED_PER_RUN": int(args.n_flex_alternatives),
        "FLEXIBILITY_INTERPRETATION": "SAMPLED_NOT_COMPLETE_FEASIBLE_ENVELOPE",
        "FILES": [
            "publication_run_inventory.csv",
            "sc3_crossrun_national_long.csv",
            "sc3_feasibility_sensitivity.csv",
            "sc3_flexibility_ed_all_runs.csv",
            "sc3_crossrun_flexibility_robustness.csv",
            "sc3_flexibility_diagnostics_all_runs.csv",
        ],
        "SCIENTIFIC_BOUNDARY": (
            "FROZEN_SC1_SC2_SC3_ENGINE_PLUS_POST_SC3_SAME_OUTCOME_FLEXIBILITY; "
            "NO_NEW_PRIORITISATION_SCORE"
        ),
    }
    (publication_root / "publication_pack_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\nPublication pack complete.")
    print(inventory[[
        "RUN_ID",
        "TOTAL_RELEASED_HA",
        "TOTAL_ALLOCATED_HA",
        "RESIDUAL_RELEASED_HA",
        "REWETTING_UNMET_HA",
    ]].to_string(index=False))
    print(f"Frozen 2020 ALL_GRASSLAND baseline: {inventory['INFERRED_BASELINE_ALL_GRASSLAND_HA'].iloc[0]:,.3f} ha")
    print(f"Canonical report data: {report_data_root}")
    print(f"Publication synthesis: {publication_root}")


if __name__ == "__main__":
    main()
