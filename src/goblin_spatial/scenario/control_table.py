"""Editable national scenario-control table for GOBLIN-Spatial.

The CSV is deliberately independent of the historical ED baseline.  A run first
selects the 2020 or 2025 baseline, then this loader combines that selected
baseline grassland total with the chosen national endpoint.  Gross released land
is therefore a run-derived quantity::

    selected baseline ALL_GRASSLAND
        - scenario TARGET_LIVESTOCK_LAND_HA
        = run gross livestock-land release

Scenario identifiers, display names, ordering and national endpoint values are
read from the table rather than hard-coded in Python.  Adding a new ACTIVE row is
therefore sufficient to make a new pathway selectable by the generic runner,
provided the endpoint is internally feasible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.scenario.goblin_controls import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
)


REQUIRED_COLUMNS = (
    "SCENARIO_NO",
    "SCENARIO_ID",
    "SCENARIO_NAME",
    "ACTIVE",
    "TARGET_YEAR",
    "TARGET_LIVESTOCK_LAND_HA",
    "DAIRY_COWS",
    "SUCKLER_COWS",
    "AD_GRASS_HA",
    "BIOREFINERY_GRASS_HA",
    "WILLOW_HA",
    "ADDITIONAL_TILLAGE_HA",
    "ADDITIONAL_FOREST_HA",
    "REWETTING_HA",
)

LAND_USE_COLUMNS = {
    "AD_GRASS": "AD_GRASS_HA",
    "BIOREFINERY_GRASS": "BIOREFINERY_GRASS_HA",
    "WILLOW": "WILLOW_HA",
    "ADDITIONAL_TILLAGE": "ADDITIONAL_TILLAGE_HA",
    "FOREST": "ADDITIONAL_FOREST_HA",
    "REWETTING": "REWETTING_HA",
}

STAGE_A_LAND_USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
)


@dataclass(frozen=True)
class ScenarioControlSelection:
    """One editable scenario row resolved against one selected ED baseline."""

    scenario_no: int
    scenario_id: str
    scenario_name: str
    baseline_year: int
    target_year: int
    baseline_grassland_ha: float
    target_livestock_land_ha: float
    gross_release_ha: float
    stage_a_target_ha: float
    rewetting_target_ha: float
    controls: GoblinPathwayControls

    @property
    def stage_a_available_before_rewetting_ha(self) -> float:
        """National released land remaining after the five Stage-A targets."""

        return float(self.gross_release_ha - self.stage_a_target_ha)


def _active(value: object) -> bool:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False
    raise ValueError(f"invalid ACTIVE value: {value!r}")


def _non_negative_number(row: pd.Series, column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid scenario-control value in {column}") from exc
    if not np.isfinite(value) or value < 0:
        raise ValueError(f"{column} must be finite and non-negative")
    return value


def _non_negative_integer(row: pd.Series, column: str) -> int:
    value = _non_negative_number(row, column)
    rounded = int(round(value))
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"{column} must be an integer")
    return rounded


def read_scenario_control_table(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Read and validate the editable scenario table without selecting a run."""

    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source))
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"scenario-control table missing columns: {missing}")

    out = frame.loc[:, REQUIRED_COLUMNS].copy()
    out["SCENARIO_ID"] = out["SCENARIO_ID"].astype(str).str.strip()
    out["SCENARIO_NAME"] = out["SCENARIO_NAME"].astype(str).str.strip()
    if out["SCENARIO_ID"].eq("").any():
        raise ValueError("SCENARIO_ID cannot be empty")
    if out["SCENARIO_NAME"].eq("").any():
        raise ValueError("SCENARIO_NAME cannot be empty")
    if out["SCENARIO_ID"].duplicated().any():
        duplicated = sorted(out.loc[out["SCENARIO_ID"].duplicated(False), "SCENARIO_ID"].unique())
        raise ValueError(f"duplicate SCENARIO_ID values: {duplicated}")

    out["ACTIVE"] = out["ACTIVE"].map(_active)
    integer_columns = ("SCENARIO_NO", "TARGET_YEAR", "DAIRY_COWS", "SUCKLER_COWS")
    for column in integer_columns:
        numeric = pd.to_numeric(out[column], errors="raise")
        if (~np.isfinite(numeric)).any() or (numeric < 0).any():
            raise ValueError(f"{column} must be finite and non-negative")
        rounded = np.rint(numeric.to_numpy(dtype=float)).astype(np.int64)
        if not np.allclose(numeric.to_numpy(dtype=float), rounded, atol=1e-9):
            raise ValueError(f"{column} must contain integers")
        out[column] = rounded

    numeric_columns = (
        "TARGET_LIVESTOCK_LAND_HA",
        *LAND_USE_COLUMNS.values(),
    )
    for column in numeric_columns:
        numeric = pd.to_numeric(out[column], errors="raise").astype(float)
        if (~np.isfinite(numeric)).any() or (numeric < 0).any():
            raise ValueError(f"{column} must be finite and non-negative")
        out[column] = numeric

    return out.sort_values(["SCENARIO_NO", "SCENARIO_ID"], kind="stable").reset_index(drop=True)


def active_scenario_ids(source: str | Path | pd.DataFrame) -> tuple[str, ...]:
    """Return active scenario identifiers in editable display order."""

    table = read_scenario_control_table(source)
    return tuple(table.loc[table["ACTIVE"], "SCENARIO_ID"].astype(str))


def load_scenario_controls(
    source: str | Path | pd.DataFrame,
    *,
    scenario_id: str,
    baseline_year: int,
    baseline_grassland_ha: float,
) -> ScenarioControlSelection:
    """Resolve one active scenario row against the selected 2020/2025 baseline.

    ``baseline_grassland_ha`` must be calculated from the selected ED baseline,
    normally ``sum(ALL_GRASSLAND)`` after filtering to ``baseline_year``.  It is
    never read from or stored in the scenario-control table.
    """

    table = read_scenario_control_table(source)
    requested = str(scenario_id).strip()
    match = table.loc[table["SCENARIO_ID"].eq(requested)]
    if len(match) != 1:
        raise ValueError(f"unknown scenario ID: {requested}")
    row = match.iloc[0]
    if not bool(row["ACTIVE"]):
        raise ValueError(f"scenario is inactive: {requested}")

    baseline_land = float(baseline_grassland_ha)
    if not np.isfinite(baseline_land) or baseline_land < 0:
        raise ValueError("baseline_grassland_ha must be finite and non-negative")

    target_land = _non_negative_number(row, "TARGET_LIVESTOCK_LAND_HA")
    gross_release = baseline_land - target_land
    if gross_release < -1e-7:
        raise ValueError(
            f"{requested} target livestock land ({target_land:,.3f} ha) exceeds "
            f"the selected {baseline_year} ED baseline grassland ({baseline_land:,.3f} ha)"
        )
    gross_release = max(gross_release, 0.0)

    target_year = _non_negative_integer(row, "TARGET_YEAR")
    dairy = _non_negative_integer(row, "DAIRY_COWS")
    suckler = _non_negative_integer(row, "SUCKLER_COWS")
    land_targets = {
        name: _non_negative_number(row, column)
        for name, column in LAND_USE_COLUMNS.items()
    }
    stage_a = float(sum(land_targets[name] for name in STAGE_A_LAND_USES))

    milestone = GoblinNationalMilestone(
        year=target_year,
        dairy_cows=dairy,
        suckler_cows=suckler,
        livestock_land_release_ha=gross_release,
        land_use_targets_ha=land_targets,
    )
    controls = GoblinPathwayControls(
        scenario_id=requested,
        baseline_year=int(baseline_year),
        milestones=(milestone,),
        source_note=str(row["SCENARIO_NAME"]),
    )

    return ScenarioControlSelection(
        scenario_no=_non_negative_integer(row, "SCENARIO_NO"),
        scenario_id=requested,
        scenario_name=str(row["SCENARIO_NAME"]),
        baseline_year=int(baseline_year),
        target_year=target_year,
        baseline_grassland_ha=baseline_land,
        target_livestock_land_ha=target_land,
        gross_release_ha=gross_release,
        stage_a_target_ha=stage_a,
        rewetting_target_ha=float(land_targets["REWETTING"]),
        controls=controls,
    )
