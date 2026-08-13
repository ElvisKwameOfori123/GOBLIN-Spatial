"""Load the sourced Styles split-gas controls used by the principal study.

The source table keeps published pathway labels (SI, BE) separate from the
internal scenario identifiers (SI_SG, BE_SG). Adult livestock endpoints come
from Styles Table 2. The 2050 land areas and Available residual come from Table
S3. Gross livestock-land release is the exact difference from the 2020 Table S3
livestock land baseline.
"""

from __future__ import annotations

import csv
from pathlib import Path

from goblin_spatial.scenario.goblin_controls import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
)


EXPECTED_SOURCE_MAPPING = {
    "SI_SG": ("SI", "SPLIT_GAS"),
    "BE_SG": ("BE", "SPLIT_GAS"),
}

LAND_TARGET_FIELDS = {
    "AD_GRASS": "AD_GRASS_HA",
    "BIOREFINERY_GRASS": "BIOREFINERY_GRASS_HA",
    "WILLOW": "WILLOW_HA",
    "ADDITIONAL_TILLAGE": "ADDITIONAL_TILLAGE_HA",
    "FOREST": "ADDITIONAL_FOREST_HA",
}


def _integer(row: dict[str, str], field: str) -> int:
    try:
        value = int(str(row[field]).strip())
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer field {field}") from exc
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def load_styles_split_gas_pathway_controls(
    path: str | Path,
    *,
    scenario_id: str,
    baseline_year: int,
) -> GoblinPathwayControls:
    """Return one internally consistent SI_SG or BE_SG pathway package.

    Table S3 land controls are cumulative from the published 2020 baseline. For
    a 2025 livestock starting-state analysis the same 2050 adult endpoint may be
    used, but the 2020-to-2050 land-release control is withheld because Table S3
    alone does not provide the remaining 2025-to-2050 release.
    """

    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    requested = str(scenario_id).strip().upper()
    if requested not in EXPECTED_SOURCE_MAPPING:
        raise ValueError(f"unsupported Styles split-gas scenario: {scenario_id}")
    matches = [
        row for row in rows
        if str(row.get("MODEL_SCENARIO_ID", "")).strip().upper() == requested
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one pathway row for {requested}; found {len(matches)}"
        )
    row = matches[0]

    expected_source, expected_constraint = EXPECTED_SOURCE_MAPPING[requested]
    source_pathway = str(row.get("SOURCE_PATHWAY", "")).strip().upper()
    climate_constraint = str(row.get("CLIMATE_CONSTRAINT", "")).strip().upper()
    if source_pathway != expected_source or climate_constraint != expected_constraint:
        raise ValueError(
            "Styles pathway provenance mismatch: "
            f"expected {expected_source}/{expected_constraint}, "
            f"found {source_pathway}/{climate_constraint}"
        )

    target_year = _integer(row, "TARGET_YEAR")
    dairy = _integer(row, "DAIRY_COWS")
    suckler = _integer(row, "SUCKLER_COWS")

    base_livestock_land = sum(
        _integer(row, field)
        for field in ("BASE_DAIRY_LAND_HA", "BASE_BEEF_LAND_HA", "BASE_SHEEP_LAND_HA")
    )
    target_livestock_land = sum(
        _integer(row, field)
        for field in ("TARGET_DAIRY_LAND_HA", "TARGET_BEEF_LAND_HA", "TARGET_SHEEP_LAND_HA")
    )
    release = _integer(row, "LIVESTOCK_LAND_RELEASE_HA")
    if base_livestock_land - target_livestock_land != release:
        raise ValueError(
            "Styles livestock-land release does not close to the Table S3 land balance"
        )

    targets = {
        land_use: float(_integer(row, field))
        for land_use, field in LAND_TARGET_FIELDS.items()
    }
    residual = _integer(row, "AVAILABLE_RESIDUAL_HA")
    if int(round(sum(targets.values()))) + residual != release:
        raise ValueError(
            "Styles released-land uses plus Available residual do not close to gross release"
        )

    source_note = str(row.get("SOURCE_NOTE", "")).strip() or None
    use_2020_land_controls = int(baseline_year) == 2020

    return GoblinPathwayControls(
        scenario_id=requested,
        baseline_year=int(baseline_year),
        milestones=(
            GoblinNationalMilestone(
                year=target_year,
                dairy_cows=dairy,
                suckler_cows=suckler,
                livestock_land_release_ha=(float(release) if use_2020_land_controls else None),
                land_use_targets_ha=(targets if use_2020_land_controls else {}),
                available_land_residual_ha=(float(residual) if use_2020_land_controls else None),
            ),
        ),
        source_note=source_note,
    )
