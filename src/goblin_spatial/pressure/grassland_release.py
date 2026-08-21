"""GOBLIN-style grassland requirement and spared-area accounting at ED level.

The upstream GOBLIN ``grassland_production`` package calculates grassland area
as pasture dry-matter requirement divided by effective grass yield and
utilisation, then defines spared area as calibration-year grassland area minus
target-year grassland area.

GOBLIN-Spatial follows the same accounting structure while preserving the
validated ED grassland baseline.  It calibrates each ED's baseline effective
pasture-DM supply so that the baseline cohort demand exactly occupies the
observed ``ALL_GRASSLAND`` area.  Future changes in yield/utilisation can be
represented with an explicit supply multiplier.  This keeps the spatial
baseline authoritative without pretending that national-average grass yields
are directly observed for every ED.

The module deliberately separates a signed grassland balance from positive
``POTENTIAL_SPARED_GRASSLAND_HA``.  If a scenario requires more grassland than
its baseline, the excess is reported as ``ADDITIONAL_GRASSLAND_REQUIRED_HA``
rather than being hidden by a zero floor.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10


PASTURE_DM_COHORTS = tuple(FINAL_21_COHORTS) + tuple(GOBLIN_SHEEP_10)


def _validate_profile(profile: Mapping[str, float], year: int) -> dict[str, float]:
    missing = sorted(set(PASTURE_DM_COHORTS) - set(profile))
    extra = sorted(set(profile) - set(PASTURE_DM_COHORTS))
    if missing or extra:
        raise ValueError(
            f"invalid pasture-DM profile for {year}; missing={missing}, extra={extra}"
        )
    out = {key: float(profile[key]) for key in PASTURE_DM_COHORTS}
    if any((not np.isfinite(value)) or value < 0 for value in out.values()):
        raise ValueError(f"pasture-DM profile for {year} must be finite and non-negative")
    return out


def _profile_for_year(
    profiles: Mapping[int, Mapping[str, float]], year: int
) -> dict[str, float]:
    if int(year) not in profiles:
        raise ValueError(f"missing pasture-DM profile for year {year}")
    return _validate_profile(profiles[int(year)], int(year))


def _supply_multiplier(
    multipliers: float | Mapping[int, float], year: int
) -> float:
    if isinstance(multipliers, Mapping):
        if int(year) not in multipliers:
            raise ValueError(f"missing pasture-supply multiplier for year {year}")
        value = float(multipliers[int(year)])
    else:
        value = float(multipliers)
    if not np.isfinite(value) or value <= 0:
        raise ValueError("pasture-supply multiplier must be finite and > 0")
    return value


def _cohort_column(cohort: str, state: str) -> str:
    if cohort in FINAL_21_COHORTS:
        return f"{state}_COHORT_{cohort}"
    return f"{state}_SHEEP_COHORT_{cohort}"


def _pasture_dm_demand(
    frame: pd.DataFrame,
    *,
    state: str,
    profile: Mapping[str, float],
) -> np.ndarray:
    demand = np.zeros(len(frame), dtype=float)
    for cohort in PASTURE_DM_COHORTS:
        column = _cohort_column(cohort, state)
        if column not in frame.columns:
            raise ValueError(f"grassland release missing cohort column: {column}")
        counts = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
        if (~np.isfinite(counts)).any() or (counts < 0).any():
            raise ValueError(f"invalid livestock counts in {column}")
        demand += counts * float(profile[cohort])
    return demand


def calculate_spared_grassland(
    livestock_pathway: pd.DataFrame,
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]],
    *,
    supply_multiplier_by_year: float | Mapping[int, float] = 1.0,
    grassland_column: str = "ALL_GRASSLAND",
) -> pd.DataFrame:
    """Calculate ED grassland requirement and GOBLIN-style spared area.

    Parameters
    ----------
    livestock_pathway:
        Output from ``build_full_livestock_pathway``: one row per ED and
        milestone with baseline and scenario cattle/sheep cohorts.
    pasture_dm_t_per_head_by_year:
        Mapping ``year -> cohort -> tonnes pasture DM/head/year``.  The baseline
        year and every milestone year must be supplied.  These coefficients are
        intended to come from the same GOBLIN cattle/sheep feed logic used by
        ``grassland_production``; they are deliberately not guessed here.
    supply_multiplier_by_year:
        Explicit future multiplier on baseline effective pasture supply per ha.
        ``1.0`` means no change in yield/utilisation.  A value above one can
        represent GOBLIN-consistent grass-yield/utilisation improvement.
    grassland_column:
        Validated agricultural grassland area.  Defaults to ``ALL_GRASSLAND``.

    Notes
    -----
    For ED e and milestone t, the accounting is:

    ``DM_demand = sum(population_k * pasture_DM_per_head_k)``

    ``baseline_effective_supply = baseline_DM_demand / baseline_grassland``

    ``scenario_required_grassland = scenario_DM_demand /``
    ``(baseline_effective_supply * supply_multiplier_t)``

    ``signed_balance = baseline_grassland - scenario_required_grassland``

    This mirrors the GOBLIN structure ``DM / yield / utilisation`` while
    calibrating the ED baseline exactly to observed grassland.
    """

    required = {
        "CSOED",
        "PATHWAY_BASELINE_YEAR",
        "MILESTONE_YEAR",
        grassland_column,
    }
    missing = sorted(required - set(livestock_pathway.columns))
    if missing:
        raise ValueError(f"grassland release missing required columns: {missing}")

    out = livestock_pathway.copy()
    baseline_years = pd.to_numeric(out["PATHWAY_BASELINE_YEAR"], errors="raise").astype(int).unique()
    if len(baseline_years) != 1:
        raise ValueError("grassland release requires one pathway baseline year")
    baseline_year = int(baseline_years[0])
    base_profile = _profile_for_year(pasture_dm_t_per_head_by_year, baseline_year)

    grassland = pd.to_numeric(out[grassland_column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(grassland)).any() or (grassland < 0).any():
        raise ValueError(f"{grassland_column} must be finite and non-negative")

    baseline_dm = _pasture_dm_demand(out, state="BASE", profile=base_profile)
    if ((grassland <= 0) & (baseline_dm > 1e-12)).any():
        bad = out.loc[(grassland <= 0) & (baseline_dm > 1e-12), "CSOED"].astype(str).head(10).tolist()
        raise AssertionError(
            "positive baseline pasture demand occurs in EDs with zero grassland: "
            f"{bad}"
        )

    # Calibrate the effective ED grass supply so the validated baseline is an
    # exact fixed point of the feed-balance accounting.
    effective_supply = np.divide(
        baseline_dm,
        grassland,
        out=np.full(len(out), np.nan, dtype=float),
        where=grassland > 0,
    )

    scenario_dm = np.zeros(len(out), dtype=float)
    scenario_supply = np.full(len(out), np.nan, dtype=float)
    required_grass = np.zeros(len(out), dtype=float)
    status = np.full(len(out), "CALIBRATED", dtype=object)
    applied_multiplier = np.ones(len(out), dtype=float)

    for year in sorted(pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).unique()):
        mask = pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").astype(int).to_numpy() == year
        profile = _profile_for_year(pasture_dm_t_per_head_by_year, int(year))
        multiplier = _supply_multiplier(supply_multiplier_by_year, int(year))
        dm = _pasture_dm_demand(out.loc[mask].copy(), state="SCENARIO", profile=profile)
        scenario_dm[mask] = dm
        applied_multiplier[mask] = multiplier

        local_supply = effective_supply[mask] * multiplier
        scenario_supply[mask] = local_supply

        local_grass = grassland[mask]
        local_base_dm = baseline_dm[mask]

        no_baseline_demand = (local_grass > 0) & (local_base_dm <= 1e-12)
        if (no_baseline_demand & (dm > 1e-12)).any():
            raise AssertionError(
                "scenario pasture demand appears where baseline pasture demand was zero"
            )

        # Grassland with no modelled baseline ruminant demand is not declared
        # 'spared'.  It remains outside the livestock feed-balance attribution.
        local_required = np.divide(
            dm,
            local_supply,
            out=np.zeros_like(dm, dtype=float),
            where=np.isfinite(local_supply) & (local_supply > 0),
        )
        local_required[no_baseline_demand] = local_grass[no_baseline_demand]
        required_grass[mask] = local_required
        status[np.where(mask)[0][no_baseline_demand]] = "NO_BASELINE_PASTURE_DEMAND"

    signed_balance = grassland - required_grass
    potential_spared = np.maximum(0.0, signed_balance)
    additional_required = np.maximum(0.0, -signed_balance)
    retained_within_baseline = grassland - potential_spared

    out["BASELINE_PASTURE_DM_DEMAND_T"] = baseline_dm
    out["SCENARIO_PASTURE_DM_DEMAND_T"] = scenario_dm
    out["PASTURE_DM_CHANGE_T"] = scenario_dm - baseline_dm
    out["BASELINE_EFFECTIVE_PASTURE_DM_SUPPLY_T_PER_HA"] = effective_supply
    out["PASTURE_SUPPLY_MULTIPLIER"] = applied_multiplier
    out["SCENARIO_EFFECTIVE_PASTURE_DM_SUPPLY_T_PER_HA"] = scenario_supply
    out["SCENARIO_REQUIRED_GRASSLAND_HA"] = required_grass
    out["SIGNED_GRASSLAND_BALANCE_HA"] = signed_balance
    out["POTENTIAL_SPARED_GRASSLAND_HA"] = potential_spared
    out["ADDITIONAL_GRASSLAND_REQUIRED_HA"] = additional_required
    out["RETAINED_GRASSLAND_WITHIN_BASELINE_HA"] = retained_within_baseline
    out["POTENTIAL_SPARED_GRASSLAND_SHARE"] = np.divide(
        potential_spared,
        grassland,
        out=np.zeros(len(out), dtype=float),
        where=grassland > 0,
    )
    out["GRASSLAND_RELEASE_STATUS"] = status

    # Accounting identities.
    if not np.allclose(
        grassland - required_grass,
        out["SIGNED_GRASSLAND_BALANCE_HA"].to_numpy(dtype=float),
        atol=1e-9,
    ):
        raise AssertionError("signed grassland balance failed")
    if (out["POTENTIAL_SPARED_GRASSLAND_HA"] < -1e-12).any():
        raise AssertionError("potential spared grassland became negative")
    if (out["POTENTIAL_SPARED_GRASSLAND_HA"] - grassland > 1e-8).any():
        raise AssertionError("spared grassland exceeds baseline grassland")

    return out
