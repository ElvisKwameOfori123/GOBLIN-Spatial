"""National target-versus-spatial-sum reconciliation for GOBLIN pathways."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.goblin_controls import GoblinPathwayControls


def build_goblin_reconciliation(
    ed: pd.DataFrame,
    controls: GoblinPathwayControls,
) -> pd.DataFrame:
    """Return one tidy audit table for external GOBLIN controls.

    Livestock and authoritative released-land controls are expected to close
    exactly. Future land-use targets and residual available land remain marked
    ``PENDING_DOWNSTREAM`` until the land-allocation stage is completed.
    """

    rows: list[dict[str, object]] = []

    for milestone in controls.milestones:
        year = int(milestone.year)
        years = pd.to_numeric(ed["MILESTONE_YEAR"], errors="raise").astype(int)
        block = ed.loc[years.eq(year)]
        if block.empty:
            raise ValueError(f"scenario output missing GOBLIN milestone {year}")

        def add_closed(variable: str, target: float, actual: float, stage: str) -> None:
            difference = float(actual) - float(target)
            rows.append(
                {
                    "SCENARIO_ID": controls.scenario_id,
                    "BASELINE_YEAR": int(controls.baseline_year),
                    "MILESTONE_YEAR": year,
                    "STAGE": stage,
                    "VARIABLE": variable,
                    "GOBLIN_TARGET": float(target),
                    "ED_SPATIAL_SUM": float(actual),
                    "DIFFERENCE": difference,
                    "STATUS": "CLOSED" if abs(difference) <= 1e-7 else "FAILED",
                }
            )

        add_closed(
            "DAIRY_COW",
            milestone.dairy_cows,
            pd.to_numeric(block["SCENARIO_DAIRY_COW"], errors="raise").sum(),
            "LIVESTOCK",
        )
        add_closed(
            "SUCKLER_COW",
            milestone.suckler_cows,
            pd.to_numeric(block["SCENARIO_OTHER_COW"], errors="raise").sum(),
            "LIVESTOCK",
        )

        if milestone.total_cattle is not None:
            add_closed(
                "TOTAL_CATTLE",
                milestone.total_cattle,
                pd.to_numeric(block["SCENARIO_TOTAL_CATTLE"], errors="raise").sum(),
                "LIVESTOCK",
            )

        if milestone.cattle_cohorts is not None:
            for cohort in FINAL_21_COHORTS:
                add_closed(
                    f"CATTLE_COHORT::{cohort}",
                    milestone.cattle_cohorts[cohort],
                    pd.to_numeric(block[f"SCENARIO_COHORT_{cohort}"], errors="raise").sum(),
                    "LIVESTOCK",
                )

        if milestone.livestock_land_release_ha is not None:
            if "GOBLIN_RELEASED_GRASSLAND_HA" not in block.columns:
                raise ValueError(
                    "GOBLIN pathway supplies livestock_land_release_ha but the "
                    "authoritative ED land-release spatialisation has not been run"
                )
            add_closed(
                "LIVESTOCK_LAND_RELEASE_HA",
                milestone.livestock_land_release_ha,
                pd.to_numeric(block["GOBLIN_RELEASED_GRASSLAND_HA"], errors="raise").sum(),
                "LAND_RELEASE",
            )

        for land_use, target in milestone.land_use_targets_ha.items():
            rows.append(
                {
                    "SCENARIO_ID": controls.scenario_id,
                    "BASELINE_YEAR": int(controls.baseline_year),
                    "MILESTONE_YEAR": year,
                    "STAGE": "LAND_USE",
                    "VARIABLE": f"LAND_USE_TARGET::{land_use}",
                    "GOBLIN_TARGET": float(target),
                    "ED_SPATIAL_SUM": np.nan,
                    "DIFFERENCE": np.nan,
                    "STATUS": "PENDING_DOWNSTREAM",
                }
            )

        if milestone.available_land_residual_ha is not None:
            rows.append(
                {
                    "SCENARIO_ID": controls.scenario_id,
                    "BASELINE_YEAR": int(controls.baseline_year),
                    "MILESTONE_YEAR": year,
                    "STAGE": "LAND_RESIDUAL",
                    "VARIABLE": "AVAILABLE_LAND_RESIDUAL_HA",
                    "GOBLIN_TARGET": float(milestone.available_land_residual_ha),
                    "ED_SPATIAL_SUM": np.nan,
                    "DIFFERENCE": np.nan,
                    "STATUS": "PENDING_DOWNSTREAM",
                }
            )

    return pd.DataFrame(rows)
