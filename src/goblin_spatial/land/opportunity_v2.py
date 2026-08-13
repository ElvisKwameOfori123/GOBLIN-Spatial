"""LPIS-aware ED land-opportunity screen.

Version 2 retains the policy-neutral accounting boundary of the original screen
but improves the evidence used to rank Electoral Divisions.  Production-soil
shares remain the biomass productivity signal; forestry yield class remains a
forestry-production context; the richer continuous peat/cutover soil share is
preferred for rewetting when available; and an optional 2020/2025 LPIS profile
adds observed grassland composition at the selected scenario baseline.

The scores remain screening indices.  They are not parcel suitability classes,
land conversion decisions or hectare targets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .opportunity import add_ed_land_opportunity_scores as _add_v1_scores


def _share(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        return np.zeros(len(frame), dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    return np.clip(np.nan_to_num(values, nan=0.0), 0.0, 1.0)


def add_ed_land_opportunity_scores_v2(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the preferred soil + LPIS opportunity screen to ED results.

    LPIS is optional.  When no matching LPIS grass context is attached, the
    screen remains fully usable as an improved soil-only opportunity layer.
    There is deliberately no fixed positive floor for nature/restoration: the
    score is driven by peat/sensitive grass evidence and lower production-soil
    opportunity instead.
    """

    out = _add_v1_scores(frame)
    productivity = pd.to_numeric(
        out["GOBLIN_SOIL_PRODUCTIVITY_SCORE"], errors="raise"
    ).to_numpy(dtype=float)
    productivity = np.clip(productivity, 0.0, 1.0)

    # Prefer the full source-UAA peat/cutover share from soil-context v2.  Old
    # compact profiles remain compatible by falling back to the conservative
    # dominant-IFS signal already calculated by v1.
    v1_rewet = pd.to_numeric(
        out["REWETTING_OPPORTUNITY_SCORE"], errors="raise"
    ).to_numpy(dtype=float)
    if "IFS_PEAT_CUTOVER_UAA_SHARE" in out.columns:
        peat = pd.to_numeric(
            out["IFS_PEAT_CUTOVER_UAA_SHARE"], errors="coerce"
        ).to_numpy(dtype=float)
        soil_peat = np.where(np.isfinite(peat), np.clip(peat, 0.0, 1.0), v1_rewet)
        soil_peat_method = np.where(np.isfinite(peat), "IFS_FULL_SHARE", "IFS_DOMINANT_FALLBACK")
    else:
        soil_peat = np.clip(v1_rewet, 0.0, 1.0)
        soil_peat_method = np.full(len(out), "IFS_DOMINANT_FALLBACK", dtype=object)

    if "LPIS_GRASS_CONTEXT_AVAILABLE" in out.columns:
        lpis_available = out["LPIS_GRASS_CONTEXT_AVAILABLE"].fillna(False).astype(bool).to_numpy()
    else:
        lpis_available = np.zeros(len(out), dtype=bool)

    low_input = _share(out, "LPIS_LOW_INPUT_GRASS_SHARE")
    peat_grass = _share(out, "LPIS_PEAT_GRASS_SHARE")
    riparian = _share(out, "LPIS_RIPARIAN_GRASS_SHARE")
    sensitive = np.clip(low_input + peat_grass + riparian, 0.0, 1.0)
    sensitive = np.where(lpis_available, sensitive, 0.0)
    productive_context = np.where(lpis_available, 1.0 - sensitive, 1.0)

    # Existing yield-class evidence is retained, but sensitive observed grass
    # context lowers the ranking for afforestation and dedicated biomass uses.
    forest_base = pd.to_numeric(
        out["FORESTRY_OPPORTUNITY_SCORE"], errors="raise"
    ).to_numpy(dtype=float)
    out["FORESTRY_OPPORTUNITY_SCORE"] = np.clip(
        forest_base * productive_context, 0.0, 1.0
    )

    out["REWETTING_OPPORTUNITY_SCORE"] = np.clip(
        np.maximum(soil_peat, np.where(lpis_available, peat_grass, 0.0)),
        0.0,
        1.0,
    )

    biomass = np.clip(productivity * productive_context, 0.0, 1.0)
    out["AD_GRASS_OPPORTUNITY_SCORE"] = biomass
    out["WILLOW_OPPORTUNITY_SCORE"] = biomass
    out["ENERGY_GRASS_OPPORTUNITY_SCORE"] = biomass

    # Nature/restoration evidence comes from sensitive grass/peat context and
    # constrained production soils.  Unlike v1 there is no arbitrary 0.25 floor.
    out["NATURE_OPPORTUNITY_SCORE"] = np.clip(
        np.maximum.reduce(
            [
                out["REWETTING_OPPORTUNITY_SCORE"].to_numpy(dtype=float),
                np.where(lpis_available, low_input, 0.0),
                np.where(lpis_available, riparian, 0.0),
                1.0 - productivity,
            ]
        ),
        0.0,
        1.0,
    )

    out["LPIS_SENSITIVE_GRASS_SHARE"] = np.where(lpis_available, sensitive, np.nan)
    out["LPIS_PRODUCTIVE_GRASS_CONTEXT_SHARE"] = np.where(
        lpis_available, productive_context, np.nan
    )
    out["OPPORTUNITY_LPIS_CONTEXT_USED"] = lpis_available
    out["OPPORTUNITY_SOIL_PEAT_METHOD"] = soil_peat_method
    out["OPPORTUNITY_SCREEN_VERSION"] = "2.0"
    return out
