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
    """Return one tidy audit table for externally supplied GOBLIN controls.

    Livestock and authoritative gross released-land controls are expected to
    close exactly. Future land-use targets and residual available land remain
    ``PENDING_DOWNSTREAM`` until the land-allocation stage is completed.

    The principal runtime deliberately has no externally supplied dairy/beef/
    sheep decomposition of released land. System attribution is derived inside
    the single symmetric pasture-DM spatialisation route and is diagnostic, not
    a second national control.

    When the independent pasture-DM land balance is present, the table also
    reports its net, gross-release and additional-requirement quantities as
    ``DIAGNOSTIC_ONLY`` rows. The net diagnostic is compared with the parent
    GOBLIN land-release target without being forced to close to it.
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

        def add_diagnostic(
            variable: str,
            actual: float,
            *,
            target: float | None = None,
        ) -> None:
            target_value = np.nan if target is None else float(target)
            difference = (
                np.nan if target is None else float(actual) - float(target)
            )
            rows.append(
                {
                    "SCENARIO_ID": controls.scenario_id,
                    "BASELINE_YEAR": int(controls.baseline_year),
                    "MILESTONE_YEAR": year,
                    "STAGE": "LAND_PRESSURE_DIAGNOSTIC",
                    "VARIABLE": variable,
                    "GOBLIN_TARGET": target_value,
                    "ED_SPATIAL_SUM": float(actual),
                    "DIFFERENCE": difference,
                    "STATUS": "DIAGNOSTIC_ONLY",
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
                pd.to_numeric(
                    block["SCENARIO_TOTAL_CATTLE"], errors="raise"
                ).sum(),
                "LIVESTOCK",
            )

        if milestone.cattle_cohorts is not None:
            for cohort in FINAL_21_COHORTS:
                add_closed(
                    f"CATTLE_COHORT::{cohort}",
                    milestone.cattle_cohorts[cohort],
                    pd.to_numeric(
                        block[f"SCENARIO_COHORT_{cohort}"], errors="raise"
                    ).sum(),
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
                pd.to_numeric(
                    block["GOBLIN_RELEASED_GRASSLAND_HA"], errors="raise"
                ).sum(),
                "LAND_RELEASE",
            )

            diagnostic_columns = {
                "SIGNED_GRASSLAND_BALANCE_HA",
                "POTENTIAL_SPARED_GRASSLAND_HA",
                "ADDITIONAL_GRASSLAND_REQUIRED_HA",
            }
            present = diagnostic_columns.intersection(block.columns)
            if present and present != diagnostic_columns:
                missing = sorted(diagnostic_columns - set(block.columns))
                raise ValueError(
                    "incomplete independent DM land diagnostic; "
                    f"missing columns={missing}"
                )
            if diagnostic_columns.issubset(block.columns):
                signed = pd.to_numeric(
                    block["SIGNED_GRASSLAND_BALANCE_HA"], errors="raise"
                ).sum()
                gross_release = pd.to_numeric(
                    block["POTENTIAL_SPARED_GRASSLAND_HA"], errors="raise"
                ).sum()
                gross_additional = pd.to_numeric(
                    block["ADDITIONAL_GRASSLAND_REQUIRED_HA"], errors="raise"
                ).sum()
                if abs(float(signed) - float(gross_release - gross_additional)) > 1e-7:
                    raise AssertionError(
                        "independent DM land diagnostic does not close nationally"
                    )
                add_diagnostic(
                    "DM_IMPLIED_NET_LAND_RELEASE_HA",
                    float(signed),
                    target=float(milestone.livestock_land_release_ha),
                )
                add_diagnostic(
                    "DM_IMPLIED_GROSS_POTENTIAL_RELEASE_HA",
                    float(gross_release),
                )
                add_diagnostic(
                    "DM_IMPLIED_GROSS_ADDITIONAL_REQUIRED_HA",
                    float(gross_additional),
                )
                add_diagnostic(
                    "DM_IMPLIED_GROSS_SPATIAL_MOVEMENT_HA",
                    float(gross_release + gross_additional),
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
