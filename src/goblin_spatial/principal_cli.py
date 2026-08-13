"""One-command runner for the principal Styles SI_SG / BE_SG study."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.land.lpis import add_ed_lpis_context
from goblin_spatial.land.styles_targets import (
    allocate_styles_released_land_targets,
    summarise_styles_released_land_targets,
)
from goblin_spatial.pressure import load_pasture_dm_control
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.scenario.reconciliation import build_goblin_reconciliation
from goblin_spatial.scenario.styles_pathway_controls import (
    load_styles_split_gas_pathway_controls,
)
from goblin_spatial.soil import add_ed_agricultural_soil


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goblin-spatial-principal",
        description=(
            "Run the sourced SI_SG or BE_SG 2050 endpoint on the validated ED baseline."
        ),
    )
    parser.add_argument("scenario", choices=("SI_SG", "BE_SG"))
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument("--baseline-year", type=int, choices=(2020, 2025), default=2020)
    parser.add_argument(
        "--allocation-rule",
        choices=tuple(rule.value for rule in AllocationRule),
        default=AllocationRule.PRORATA.value,
    )
    parser.add_argument("--baseline-master", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--score-column", default=None)
    parser.add_argument("--productivity-score-column", default=None)
    parser.add_argument("--vulnerability-score-column", default=None)
    parser.add_argument("--protection-strength", type=float, default=0.8)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--no-standard-output", action="store_true")
    parser.add_argument(
        "--skip-land-allocation",
        action="store_true",
        help=(
            "Stop after livestock, Standard Output and authoritative released-land "
            "spatialisation. By default a 2020 run also applies the same-pathway "
            "Styles land targets using the configured soil and LPIS ED profiles."
        ),
    )
    return parser


def _configured_output(cfg, key: str, default: str) -> Path:
    value = cfg.raw.get("outputs", {}).get(key, default)
    path = Path(value)
    return path if path.is_absolute() else cfg.project_root / path


def _required_file(cfg, key: str) -> Path:
    path = cfg.files.get(key)
    if path is None:
        raise KeyError(f"configuration missing files.{key}")
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"configured file not found for {key}: {path}")
    return path


def _output_dir(args, cfg) -> Path:
    if args.output_dir is not None:
        return Path(args.output_dir)
    name = f"{args.scenario}_{int(args.baseline_year)}_{args.allocation_rule}"
    return cfg.processed_dir / "principal" / name


def _national_livestock_summary(ed: pd.DataFrame) -> pd.DataFrame:
    row = {
        "PATHWAY_NAME": str(ed["PATHWAY_NAME"].iloc[0]),
        "PATHWAY_BASELINE_YEAR": int(ed["PATHWAY_BASELINE_YEAR"].iloc[0]),
        "MILESTONE_YEAR": int(ed["MILESTONE_YEAR"].iloc[0]),
        "PATHWAY_ALLOCATION_RULE": str(ed["PATHWAY_ALLOCATION_RULE"].iloc[0]),
        "NATIONAL_COHORT_TARGET_SOURCE": str(ed["NATIONAL_COHORT_TARGET_SOURCE"].iloc[0]),
        "SCENARIO_DAIRY_COW": int(pd.to_numeric(ed["SCENARIO_DAIRY_COW"], errors="raise").sum()),
        "SCENARIO_SUCKLER_COW": int(pd.to_numeric(ed["SCENARIO_OTHER_COW"], errors="raise").sum()),
        "SCENARIO_TOTAL_CATTLE": int(pd.to_numeric(ed["SCENARIO_TOTAL_CATTLE"], errors="raise").sum()),
        "BASE_TOTAL_CATTLE": int(pd.to_numeric(ed["BASE_TOTAL_CATTLE"], errors="raise").sum()),
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
    return pd.DataFrame([row])


def main() -> None:
    args = _parser().parse_args()
    cfg = load_config(Path(args.config))

    baseline_path = (
        Path(args.baseline_master)
        if args.baseline_master is not None
        else _configured_output(
            cfg,
            "enriched_master",
            "data/processed/goblin_spatial_master_2015_2025.csv",
        )
    )
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"validated historical baseline not found: {baseline_path}. Run the historical build first."
        )
    panel = pd.read_csv(baseline_path, low_memory=False)

    controls_path = _required_file(cfg, "styles_split_gas_pathway_controls")
    controls = load_styles_split_gas_pathway_controls(
        controls_path,
        scenario_id=args.scenario,
        baseline_year=int(args.baseline_year),
    )
    target_year = int(controls.target_year)

    cohort_reference = _required_file(cfg, "goblin_cohorts")
    pasture_control = _required_file(cfg, "pasture_dm_controls")
    pasture_profiles = load_pasture_dm_control(
        pasture_control,
        required_years={int(args.baseline_year), target_year},
    )

    mapping = None
    coefficients = None
    if not args.no_standard_output:
        mapping = str(_required_file(cfg, "standard_output_mapping"))
        coefficients = str(_required_file(cfg, "standard_output_coefficients"))

    rule = AllocationRule(args.allocation_rule)
    ed = run_principal_goblin_endpoint(
        panel,
        controls,
        allocation_rule=rule,
        random_seed=int(args.random_seed),
        score_column=args.score_column,
        productivity_score_column=args.productivity_score_column,
        vulnerability_score_column=args.vulnerability_score_column,
        protection_strength=float(args.protection_strength),
        expected_eds=int(cfg.expected_eds),
        include_standard_output=not args.no_standard_output,
        mapping_path=mapping,
        coefficient_path=coefficients,
        cohort_reference_path=str(cohort_reference),
        cohort_reference_year=2020,
        pasture_dm_t_per_head_by_year=pasture_profiles,
    )

    outdir = _output_dir(args, cfg)
    outdir.mkdir(parents=True, exist_ok=True)
    ed_path = outdir / "principal_ed_results.csv"
    livestock_summary_path = outdir / "principal_national_livestock_summary.csv"
    reconciliation_path = outdir / "principal_goblin_reconciliation.csv"
    ed.to_csv(ed_path, index=False)
    _national_livestock_summary(ed).to_csv(livestock_summary_path, index=False)
    build_goblin_reconciliation(ed, controls).to_csv(reconciliation_path, index=False)

    print(f"Principal ED results: {ed_path}")
    print(f"National livestock summary: {livestock_summary_path}")
    print(f"GOBLIN reconciliation: {reconciliation_path}")

    milestone = controls.milestone(target_year)
    can_allocate_land = (
        not args.skip_land_allocation
        and milestone.livestock_land_release_ha is not None
        and bool(milestone.land_use_targets_ha)
    )
    if not can_allocate_land:
        if int(args.baseline_year) == 2025 and not args.skip_land_allocation:
            print(
                "2025 livestock endpoint completed. Styles Table S3 land controls are "
                "2020-to-2050 and are deliberately withheld from a 2025-to-2050 land run."
            )
        return

    soil_profile = _required_file(cfg, "agricultural_soil_profile")
    lpis_profile = _required_file(cfg, "lpis_ed_profile")
    enriched = (
        ed
        if "GOBLIN_SOIL_G1_SHARE" in ed.columns
        else add_ed_agricultural_soil(ed, soil_profile)
    )
    if "LPIS_GRASS_CONTEXT_AVAILABLE" not in enriched.columns:
        enriched = add_ed_lpis_context(
            enriched,
            lpis_profile,
            baseline_year=int(args.baseline_year),
        )
    allocated = allocate_styles_released_land_targets(
        enriched,
        controls,
        released_column="GOBLIN_RELEASED_GRASSLAND_HA",
        attach_scores=True,
    )
    land_summary = summarise_styles_released_land_targets(allocated)
    land_ed_path = outdir / "principal_ed_styles_land_allocation.csv"
    land_nat_path = outdir / "principal_national_styles_land_allocation.csv"
    allocated.to_csv(land_ed_path, index=False)
    land_summary.to_csv(land_nat_path, index=False)
    print(f"Styles ED land allocation: {land_ed_path}")
    print(f"Styles national land allocation: {land_nat_path}")


if __name__ == "__main__":
    main()
