"""ED land-opportunity screening and sequential allocation of spared grassland.

This module is deliberately downstream of the livestock and grassland engines:

``livestock -> grass required -> potential spared grassland -> opportunity``.

The scores are *screening indicators*, not parcel-level suitability claims. They
use only information already carried by the ED soil profile and can be replaced
or augmented later by higher-resolution GIS evidence.

The default screen uses:

- the GOBLIN production-soil yield-gap ordering (G1=0.85, G2=0.80, G3=0.70)
  as a relative biomass/grass productivity indicator;
- forest Yield Class as the forestry-production indicator;
- Irish Forest Soil peat/cutover codes as a conservative rewetting indicator.

Allocation is cumulative. Land assigned by 2030 remains assigned in 2040 and
2050; only *newly spared* hectares are available for new allocation at the next
milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


LAND_USES = (
    "FOREST",
    "REWETTING",
    "AD_GRASS",
    "WILLOW",
    "ENERGY_GRASS",
    "NATURE",
)

OPPORTUNITY_SCORE_COLUMNS = {
    "FOREST": "FORESTRY_OPPORTUNITY_SCORE",
    "REWETTING": "REWETTING_OPPORTUNITY_SCORE",
    "AD_GRASS": "AD_GRASS_OPPORTUNITY_SCORE",
    "WILLOW": "WILLOW_OPPORTUNITY_SCORE",
    "ENERGY_GRASS": "ENERGY_GRASS_OPPORTUNITY_SCORE",
    "NATURE": "NATURE_OPPORTUNITY_SCORE",
}


@dataclass(frozen=True)
class LandUseAllocationDefinition:
    """Shares of each newly spared hectare targeted to alternative land uses.

    Shares are national/policy allocation assumptions. ED opportunity scores
    determine *where* the requested hectares can be placed. Shares may sum to
    less than one; the residual remains ``RETAINED_GRASSLAND``. If a requested
    land use lacks enough scored ED capacity, the unmet target also remains
    retained and is reported explicitly.
    """

    forest: float = 0.0
    rewetting: float = 0.0
    ad_grass: float = 0.0
    willow: float = 0.0
    energy_grass: float = 0.0
    nature: float = 0.0
    priority: tuple[str, ...] = (
        "REWETTING",
        "FOREST",
        "AD_GRASS",
        "WILLOW",
        "ENERGY_GRASS",
        "NATURE",
    )

    def __post_init__(self) -> None:
        shares = self.as_dict()
        for land_use, value in shares.items():
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(
                    f"land-use share for {land_use} must lie in [0, 1]"
                )
        if sum(shares.values()) > 1.0 + 1e-12:
            raise ValueError("alternative land-use shares cannot sum above 1")
        if set(self.priority) != set(LAND_USES) or len(self.priority) != len(
            LAND_USES
        ):
            raise ValueError(
                "priority must contain each alternative land use exactly once"
            )

    def as_dict(self) -> dict[str, float]:
        return {
            "FOREST": float(self.forest),
            "REWETTING": float(self.rewetting),
            "AD_GRASS": float(self.ad_grass),
            "WILLOW": float(self.willow),
            "ENERGY_GRASS": float(self.energy_grass),
            "NATURE": float(self.nature),
        }


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise ValueError(f"land-opportunity input missing column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def add_ed_land_opportunity_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach transparent ED opportunity-screen scores in the range [0, 1].

    These scores identify relative opportunity from the currently available ED
    soil context. They do not claim the exact location or ecological suitability
    of a released parcel.
    """

    out = frame.copy()
    g1 = _numeric(out, "GOBLIN_SOIL_G1_SHARE")
    g2 = _numeric(out, "GOBLIN_SOIL_G2_SHARE")
    g3 = _numeric(out, "GOBLIN_SOIL_G3_SHARE")
    if ((g1 < 0) | (g2 < 0) | (g3 < 0)).any():
        raise ValueError("GOBLIN soil shares cannot be negative")
    if not np.allclose(g1 + g2 + g3, 1.0, atol=1e-8):
        raise ValueError("GOBLIN G1/G2/G3 shares must close to one")

    # Public GOBLIN grassland_production uses soil yield-gap factors
    # 0.85/0.80/0.70 for G1/G2/G3. Rescale the ED weighted value to [0, 1].
    productivity_index = 0.85 * g1 + 0.80 * g2 + 0.70 * g3
    productivity_score = np.clip(
        (productivity_index - 0.70) / (0.85 - 0.70), 0.0, 1.0
    )
    out["GOBLIN_SOIL_PRODUCTIVITY_INDEX"] = productivity_index
    out["GOBLIN_SOIL_PRODUCTIVITY_SCORE"] = productivity_score

    if "FOREST_YC_WEIGHTED_MEAN" in out.columns:
        yc = pd.to_numeric(
            out["FOREST_YC_WEIGHTED_MEAN"], errors="coerce"
        ).to_numpy(dtype=float)
        forest_score = np.where(
            np.isfinite(yc), np.clip((yc - 14.0) / 10.0, 0.0, 1.0), 0.0
        )
    else:
        forest_score = np.zeros(len(out), dtype=float)
    out["FORESTRY_OPPORTUNITY_SCORE"] = forest_score

    if "IFS_SOIL_DOMINANT" in out.columns:
        code = out["IFS_SOIL_DOMINANT"].astype("string").fillna("")
        upper = code.str.upper()
        is_peat = upper.str.endswith("PT") | upper.eq("CUT")
        if "IFS_SOIL_DOMINANT_SHARE" in out.columns:
            dominant_share = pd.to_numeric(
                out["IFS_SOIL_DOMINANT_SHARE"], errors="coerce"
            ).fillna(0.0).to_numpy(dtype=float)
            dominant_share = np.clip(dominant_share, 0.0, 1.0)
        else:
            dominant_share = np.ones(len(out), dtype=float)
        rewet_score = np.where(is_peat.to_numpy(), dominant_share, 0.0)
    else:
        rewet_score = np.zeros(len(out), dtype=float)
    out["REWETTING_OPPORTUNITY_SCORE"] = rewet_score

    # Productive grass/biomass uses use the GOBLIN production-soil screen. This
    # is intentionally a first-stage physical opportunity index, not a transport,
    # plant-location or profitability model.
    out["AD_GRASS_OPPORTUNITY_SCORE"] = productivity_score
    out["WILLOW_OPPORTUNITY_SCORE"] = productivity_score
    out["ENERGY_GRASS_OPPORTUNITY_SCORE"] = productivity_score

    # Nature/restoration remains broadly possible. Soil information increases
    # the screen for peat and relatively constrained production soils without
    # excluding productive EDs completely.
    out["NATURE_OPPORTUNITY_SCORE"] = np.clip(
        np.maximum(rewet_score, 0.25 + 0.75 * (1.0 - productivity_score)),
        0.0,
        1.0,
    )
    return out


def _weighted_continuous_allocate(
    capacity: np.ndarray,
    score: np.ndarray,
    target: float,
) -> tuple[np.ndarray, float]:
    """Allocate continuous hectares by score without exceeding ED capacity."""

    capacity = np.maximum(np.asarray(capacity, dtype=float), 0.0)
    score = np.clip(np.asarray(score, dtype=float), 0.0, 1.0)
    target = max(float(target), 0.0)
    allocation = np.zeros(len(capacity), dtype=float)
    if target <= 1e-12:
        return allocation, 0.0

    eligible_capacity = np.where(score > 1e-12, capacity, 0.0)
    feasible_target = min(target, float(eligible_capacity.sum()))
    remaining = feasible_target
    residual_capacity = capacity.copy()

    for _ in range(len(capacity) + 3):
        if remaining <= 1e-10:
            break
        active = (residual_capacity > 1e-12) & (score > 1e-12)
        if not active.any():
            break
        weights = np.where(active, residual_capacity * score, 0.0)
        if float(weights.sum()) <= 1e-15:
            break
        proposal = remaining * weights / weights.sum()
        take = np.minimum(proposal, residual_capacity)
        allocation += take
        residual_capacity -= take
        new_remaining = feasible_target - float(allocation.sum())
        if abs(new_remaining - remaining) <= 1e-12:
            break
        remaining = new_remaining

    unmet = max(0.0, target - float(allocation.sum()))
    if (allocation - capacity > 1e-8).any():
        raise AssertionError("land allocation exceeded ED spared-land capacity")
    return allocation, unmet


def allocate_spared_land_sequentially(
    frame: pd.DataFrame,
    definition: LandUseAllocationDefinition,
    *,
    spared_column: str = "POTENTIAL_SPARED_GRASSLAND_HA",
) -> pd.DataFrame:
    """Allocate newly spared hectares cumulatively using ED opportunity scores.

    A milestone can allocate only the additional land released since the
    previous milestone in the same ED. Previously allocated forest, rewetting,
    bioenergy or nature land is never silently returned to livestock use.
    """

    required = {"CSOED", "MILESTONE_YEAR", spared_column}
    required.update(OPPORTUNITY_SCORE_COLUMNS.values())
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"sequential land allocation missing columns: {missing}")

    ordered = frame.sort_values(
        ["MILESTONE_YEAR", "CSOED"], kind="stable"
    ).copy()
    if ordered[["CSOED", "MILESTONE_YEAR"]].duplicated().any():
        raise ValueError("land allocation requires one row per ED and milestone")

    years = sorted(
        pd.to_numeric(ordered["MILESTONE_YEAR"], errors="raise")
        .astype(int)
        .unique()
    )
    first = ordered.loc[ordered["MILESTONE_YEAR"] == years[0]].copy()
    ed_order = first.sort_values("CSOED", kind="stable")["CSOED"].astype(str).tolist()
    n_ed = len(ed_order)

    previous_spared = np.zeros(n_ed, dtype=float)
    cumulative = {
        land_use: np.zeros(n_ed, dtype=float) for land_use in LAND_USES
    }
    cumulative_retained = np.zeros(n_ed, dtype=float)
    shares = definition.as_dict()
    rows: list[pd.DataFrame] = []

    for year in years:
        block = ordered.loc[ordered["MILESTONE_YEAR"] == year].copy()
        block = block.sort_values("CSOED", kind="stable").reset_index(drop=True)
        if block["CSOED"].astype(str).tolist() != ed_order:
            raise AssertionError("ED membership/order changed between land milestones")

        spared = _numeric(block, spared_column)
        if (spared < -1e-10).any():
            raise ValueError("potential spared grassland cannot be negative")
        incremental_spared = spared - previous_spared
        if (incremental_spared < -1e-7).any():
            raise ValueError(
                "spared grassland fell between milestones; cumulative land-use "
                "allocation cannot silently reverse earlier conversions"
            )
        incremental_spared = np.maximum(incremental_spared, 0.0)
        remaining_capacity = incremental_spared.copy()
        total_new = float(incremental_spared.sum())
        block["INCREMENTAL_SPARED_GRASSLAND_HA"] = incremental_spared

        for land_use in definition.priority:
            score = _numeric(block, OPPORTUNITY_SCORE_COLUMNS[land_use])
            target = total_new * shares[land_use]
            allocation, unmet = _weighted_continuous_allocate(
                remaining_capacity, score, target
            )
            remaining_capacity = np.maximum(
                0.0, remaining_capacity - allocation
            )
            cumulative[land_use] += allocation
            block[f"INCREMENTAL_{land_use}_HA"] = allocation
            block[f"CUMULATIVE_{land_use}_HA"] = cumulative[land_use]
            block[f"NATIONAL_TARGET_{land_use}_HA"] = target
            block[f"NATIONAL_UNMET_{land_use}_TARGET_HA"] = unmet

        incremental_retained = remaining_capacity
        cumulative_retained += incremental_retained
        block["INCREMENTAL_RETAINED_GRASSLAND_HA"] = incremental_retained
        block["CUMULATIVE_RETAINED_GRASSLAND_HA"] = cumulative_retained

        cumulative_columns = [
            f"CUMULATIVE_{land_use}_HA" for land_use in LAND_USES
        ] + ["CUMULATIVE_RETAINED_GRASSLAND_HA"]
        block["CUMULATIVE_LAND_ALLOCATION_TOTAL_HA"] = block[
            cumulative_columns
        ].sum(axis=1)
        block["LAND_ALLOCATION_CLOSURE_HA"] = (
            block["CUMULATIVE_LAND_ALLOCATION_TOTAL_HA"] - spared
        )
        if not np.allclose(
            block["CUMULATIVE_LAND_ALLOCATION_TOTAL_HA"].to_numpy(dtype=float),
            spared,
            atol=1e-7,
        ):
            raise AssertionError(
                "cumulative alternative land allocation does not close to spared land"
            )

        previous_spared = spared.copy()
        rows.append(block)

    result = pd.concat(rows, ignore_index=True)
    return result.sort_values(
        ["MILESTONE_YEAR", "CSOED"], kind="stable"
    ).reset_index(drop=True)
