#!/usr/bin/env python
"""Run transparent validation diagnostics for the historical GOBLIN-Spatial baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel, lsu_check_2020
from goblin_spatial.validation.historical import (
    sheep_anchor_holdout,
    temporal_rank_stability,
    validate_achill_benchmark,
    validate_achill_land_benchmark,
    validate_dafm_sheep_counties,
)


def _configured_output(cfg, key: str, default: str) -> Path:
    raw = cfg.raw.get("outputs", {}).get(key, default)
    path = Path(raw)
    return path if path.is_absolute() else cfg.project_root / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run historical GOBLIN-Spatial validation diagnostics."
    )
    parser.add_argument(
        "--config",
        default="configs/ireland_2015_2025.yaml",
        help="Historical baseline configuration.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/validation/historical",
        help="Directory for validation diagnostics.",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    master_path = _configured_output(
        cfg,
        "standard_output_master",
        "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
    )
    if not master_path.exists():
        raise FileNotFoundError(
            f"{master_path} does not exist. Run 'goblin-spatial build' first."
        )

    master = pd.read_csv(master_path)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = cfg.project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    overview_rows: list[dict[str, object]] = []

    # 1. DAFM county-pattern fidelity diagnostic.
    # The same DAFM ewe geography informs the production county-share prior,
    # so this is not independent validation of the sheep reconstruction.
    dafm_diag, dafm_summary = validate_dafm_sheep_counties(
        master,
        cfg.files["dafm_sheep_county_pattern"],
    )
    dafm_diag.to_csv(output_dir / "dafm_county_sheep_diagnostics.csv", index=False)
    dafm_summary.to_csv(output_dir / "dafm_county_sheep_summary.csv", index=False)
    for row in dafm_summary.to_dict("records"):
        overview_rows.extend(
            [
                {
                    "VALIDATION_FAMILY": "DAFM_SHEEP_PATTERN_FIDELITY",
                    "SCOPE": str(int(row["YEAR"])),
                    "METRIC": "MAE_HEAD",
                    "VALUE": row["MAE"],
                    "INTERPRETATION": "Pattern-fidelity diagnostic against the DAFM county source used for relative county weighting; CSO/AAA09 remains the population control.",
                },
                *(
                    [
                        {
                            "VALIDATION_FAMILY": "DAFM_SHEEP_PATTERN_FIDELITY",
                            "SCOPE": str(int(row["YEAR"])),
                            "METRIC": "SPEARMAN_RHO",
                            "VALUE": row["SPEARMAN_RHO"],
                            "INTERPRETATION": "County spatial-ranking fidelity to the DAFM ewe geography used in the production allocation prior; not independent validation.",
                        }
                    ]
                    if np.isfinite(row["SPEARMAN_RHO"])
                    else []
                ),
            ]
        )

    # 2. Genuine holdout of the 2022 DAFM sheep-composition anchor.
    holdout_diag, holdout_summary = sheep_anchor_holdout(
        cfg.files["sheep_breed_anchors"],
        holdout_year=2022,
        start_year=2020,
        end_year=2025,
    )
    holdout_diag.to_csv(output_dir / "sheep_composition_holdout_2022.csv", index=False)
    holdout_summary.to_csv(
        output_dir / "sheep_composition_holdout_2022_summary.csv",
        index=False,
    )
    for row in holdout_summary.to_dict("records"):
        overview_rows.extend(
            [
                {
                    "VALIDATION_FAMILY": "HOLDOUT_SHEEP_COMPOSITION",
                    "SCOPE": row["BREED_GROUP"],
                    "METRIC": "MAE_PERCENTAGE_POINTS",
                    "VALUE": row["MAE_PP"],
                    "INTERPRETATION": "2022 anchor omitted and reconstructed by interpolation from 2020 and 2025.",
                },
                *(
                    [
                        {
                            "VALIDATION_FAMILY": "HOLDOUT_SHEEP_COMPOSITION",
                            "SCOPE": row["BREED_GROUP"],
                            "METRIC": "SPEARMAN_RHO",
                            "VALUE": row["SPEARMAN_RHO"],
                            "INTERPRETATION": "Spatial/compositional ranking agreement for the omitted 2022 anchor.",
                        }
                    ]
                    if np.isfinite(row["SPEARMAN_RHO"])
                    else []
                ),
            ]
        )

    # 3. Achill North external applied benchmark.
    achill_path = (
        cfg.project_root
        / "data/validation/external/achill_north/ED_Livestock_2020.csv"
    )
    achill_diag, achill_summary, achill_spatial = validate_achill_benchmark(
        master,
        achill_path,
        county="Mayo",
        year=2020,
    )
    achill_diag.to_csv(output_dir / "achill_ed_2020_diagnostics.csv", index=False)
    achill_summary.to_csv(output_dir / "achill_ed_2020_summary.csv", index=False)
    achill_spatial.to_csv(
        output_dir / "achill_area_allocation_reproduction.csv",
        index=False,
    )
    for row in achill_summary.to_dict("records"):
        overview_rows.extend(
            [
                {
                    "VALIDATION_FAMILY": "ACHILL_APPLIED_BENCHMARK",
                    "SCOPE": row["VARIABLE"],
                    "METRIC": "MAE_HEAD",
                    "VALUE": row["MAE"],
                    "INTERPRETATION": "Applied 2020 ED benchmark; not statistically independent because the survey also uses Census of Agriculture 2020.",
                },
                *(
                    [
                        {
                            "VALIDATION_FAMILY": "ACHILL_APPLIED_BENCHMARK",
                            "SCOPE": row["VARIABLE"],
                            "METRIC": "SPEARMAN_RHO",
                            "VALUE": row["SPEARMAN_RHO"],
                            "INTERPRETATION": "Agreement in ED livestock spatial ordering.",
                        }
                    ]
                    if np.isfinite(row["SPEARMAN_RHO"])
                    else []
                ),
            ]
        )

    achill_land_path = (
        cfg.project_root
        / "data/validation/external/achill_north/ED_Land_2020.csv"
    )
    achill_land_diag, achill_land_summary = validate_achill_land_benchmark(
        master,
        achill_land_path,
        county="Mayo",
        year=2020,
    )
    achill_land_diag.to_csv(
        output_dir / "achill_land_2020_diagnostics.csv",
        index=False,
    )
    achill_land_summary.to_csv(
        output_dir / "achill_land_2020_summary.csv",
        index=False,
    )
    for row in achill_land_summary.to_dict("records"):
        overview_rows.extend(
            [
                {
                    "VALIDATION_FAMILY": "ACHILL_APPLIED_LAND_BENCHMARK",
                    "SCOPE": row["VARIABLE"],
                    "METRIC": "MAE",
                    "VALUE": row["MAE"],
                    "INTERPRETATION": "Applied 2020 ED land/farm-structure benchmark; not statistically independent because the survey also uses Census of Agriculture 2020.",
                },
                *(
                    [
                        {
                            "VALIDATION_FAMILY": "ACHILL_APPLIED_LAND_BENCHMARK",
                            "SCOPE": row["VARIABLE"],
                            "METRIC": "SPEARMAN_RHO",
                            "VALUE": row["SPEARMAN_RHO"],
                            "INTERPRETATION": "Agreement in ED land/farm-structure spatial ordering.",
                        }
                    ]
                    if np.isfinite(row["SPEARMAN_RHO"])
                    else []
                ),
            ]
        )

    explicit = achill_spatial.dropna(
        subset=["CATTLE_AREA_CALC", "SHEEP_AREA_CALC"]
    ).copy()
    overview_rows.extend(
        [
            {
                "VALIDATION_FAMILY": "ACHILL_SPATIAL_TRANSFER",
                "SCOPE": "CATTLE",
                "METRIC": "MAX_ABS_ROUNDING_DIFFERENCE_HEAD",
                "VALUE": float(explicit["CATTLE_AREA_ERROR"].abs().max()),
                "INTERPRETATION": "Reproduction of the survey's simple ED-area overlap correction using published rounded overlap percentages.",
            },
            {
                "VALIDATION_FAMILY": "ACHILL_SPATIAL_TRANSFER",
                "SCOPE": "SHEEP",
                "METRIC": "MAX_ABS_ROUNDING_DIFFERENCE_HEAD",
                "VALUE": float(explicit["SHEEP_AREA_ERROR"].abs().max()),
                "INTERPRETATION": "Reproduction of the survey's simple ED-area overlap correction using published rounded overlap percentages.",
            },
        ]
    )

    # 4. Prespecified 2020 LSU plausibility/model-selection diagnostic for
    # the ED age prior. This is not independent validation: published LSU was
    # used to evaluate the alternative age-prior representation.
    cattle_panel, _ = build_annual_ed_panel(cfg)
    age_rows = []
    for mode in ("dafm_log_odds", "flat_county"):
        age_panel = build_annual_age_sex_panel(cfg, cattle_panel, mode=mode)
        check = lsu_check_2020(cfg, age_panel)
        age_rows.append(
            {
                "AGE_PRIOR": mode,
                **check,
            }
        )
        overview_rows.extend(
            [
                {
                    "VALIDATION_FAMILY": "CATTLE_AGE_PRIOR_PLAUSIBILITY",
                    "SCOPE": mode,
                    "METRIC": "MEDIAN_ABS_RESIDUAL_LSU",
                    "VALUE": check["median_abs_residual"],
                    "INTERPRETATION": "Model-selection/plausibility diagnostic against published 2020 ED LSU; not independent validation.",
                },
                {
                    "VALIDATION_FAMILY": "CATTLE_AGE_PRIOR_PLAUSIBILITY",
                    "SCOPE": mode,
                    "METRIC": "ELIGIBLE_EDS",
                    "VALUE": check["eligible_eds"],
                    "INTERPRETATION": "Number of EDs eligible for the LSU age-prior comparison.",
                },
            ]
        )
    age_summary = pd.DataFrame(age_rows)
    age_summary.to_csv(output_dir / "cattle_lsu_age_prior_summary.csv", index=False)

    # 5. Adjacent-year spatial-rank stability for counts and transparent signatures.
    stability = temporal_rank_stability(master)
    stability.to_csv(output_dir / "temporal_rank_stability.csv", index=False)
    stability_summary = stability.groupby(
        "INDICATOR", as_index=False
    ).agg(
        MIN_RHO=("SPEARMAN_RHO", "min"),
        MEDIAN_RHO=("SPEARMAN_RHO", "median"),
        MAX_RHO=("SPEARMAN_RHO", "max"),
    )
    stability_summary.to_csv(
        output_dir / "temporal_rank_stability_summary.csv",
        index=False,
    )
    for row in stability_summary.to_dict("records"):
        if np.isfinite(row["MIN_RHO"]):
            overview_rows.append(
                {
                    "VALIDATION_FAMILY": "TEMPORAL_STABILITY_DIAGNOSTIC",
                    "SCOPE": row["INDICATOR"],
                    "METRIC": "MIN_ADJACENT_YEAR_SPEARMAN_RHO",
                    "VALUE": row["MIN_RHO"],
                    "INTERPRETATION": "Diagnostic for accidental year-to-year spatial discontinuity; not independent validation.",
                }
            )

    # 6. Preserve the existing accounting-verification summary in the overview.
    accounting_path = cfg.processed_dir / "validation_summary.csv"
    if accounting_path.exists():
        accounting = pd.read_csv(accounting_path)
        if len(accounting) == 1:
            row = accounting.iloc[0]
            for metric in (
                "max_cattle_cohort_diff",
                "max_sheep_cohort_diff",
                "max_land_accounting_diff_ha",
                "max_2020_lock_change",
            ):
                if metric in row.index:
                    overview_rows.append(
                        {
                            "VALIDATION_FAMILY": "ACCOUNTING_VERIFICATION",
                            "SCOPE": "NATIONAL_HISTORICAL_BUILD",
                            "METRIC": metric.upper(),
                            "VALUE": float(row[metric]),
                            "INTERPRETATION": "Internal accounting/lock verification; not independent validation.",
                        }
                    )

    overview = pd.DataFrame(overview_rows)
    if overview["VALUE"].isna().any():
        # A rho can be undefined only if a comparison has no variation. That
        # should be explicit rather than silently written as a result.
        bad = overview.loc[overview["VALUE"].isna(), ["VALIDATION_FAMILY", "SCOPE", "METRIC"]]
        raise AssertionError(f"validation overview contains undefined metrics:\n{bad}")

    overview.to_csv(output_dir / "historical_validation_overview.csv", index=False)

    print(f"Historical validation diagnostics written to: {output_dir}")
    print(f"DAFM county sheep rows: {len(dafm_diag)}")
    print(f"2022 sheep-composition holdout rows: {len(holdout_diag)}")
    print(f"Achill livestock benchmark rows: {len(achill_diag)}")
    print(f"Achill land benchmark rows: {len(achill_land_diag)}")
    print(f"LSU age-prior comparison rows: {len(age_summary)}")
    print(f"Temporal stability diagnostics: {len(stability)}")
    print(overview.to_string(index=False))


if __name__ == "__main__":
    main()
