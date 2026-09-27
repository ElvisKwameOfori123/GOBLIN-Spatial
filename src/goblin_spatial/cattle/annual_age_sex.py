"""Age-sex split of ED OTHER_CATTLE on the CSO annual panel, 2015-2025.

Input: the CSO-only annual ED panel (``annual_panel.build_annual_ed_panel``),
which fixes each ED's OTHER_CATTLE every year (2020 = published census).

For every county and year the ED x seven CSO age-sex groups table
(bulls; male/female under 1; male/female 1-2; male/female 2+) is built so that

* rows    = each ED's OTHER_CATTLE from the annual panel (exact, never changed);
* columns = the seven AAA10 county age-sex groups for that year, taken as
            proportions and Hamilton-scaled to the county's OTHER_CATTLE.
            In 2015-2019 and 2021-2025 that total is AAA10 itself; in 2020 it is
            the published census county total, because 2020 ED values are kept
            as published and CSO publishes no census age-sex split
            (AVA28 / AVA42 give only dairy cows, other cows, other cattle).

Starting pattern (prior) before IPF:

* ``dafm_log_odds`` (production): the 2020 DAFM/AIM ED average age profile
  describes each ED's young-stock composition relative to its county,
  q = (0-12 months) / (0-24 months). Only the under-1 versus 1-2 split is
  shifted, on the log-odds scale, by logit(q_ED) - logit(q_county). Bulls,
  2+ groups and sex within age keep the county CSO mix. Unmatched EDs get the
  county q, i.e. no shift. The 2020 signature is a composition, never a count,
  and is applied to every year.
* ``flat_county`` (null): every ED gets its county mix.

IPF then restores exact ED rows and exact county columns and the result is
rounded to whole animals without changing any margin
(``age_sex.allocate_age_sex``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.age_sex import (
    AGE_SEX_PRIOR_MODES,
    DEFAULT_LOGIT_EPSILON,
    allocate_age_sex,
    build_dafm_age_signal,
)
from goblin_spatial.cattle.annual_panel import KNOWN_YEAR, YEARS, build_annual_ed_panel
from goblin_spatial.cattle.panel import AAA_AGE_SEX_COLS, AGE_SEX_COLS, _load_aaa10
from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate

# IFS / Eurostat livestock-unit coefficients used for the held-out LSU check.
LSU_COEFFICIENTS = {
    "DAIRY_COW": 1.0,
    "OTHER_COW": 0.8,
    "BULLS": 1.0,
    "CATTLE_MALE_UNDER_1": 0.4,
    "CATTLE_FEMALE_UNDER_1": 0.4,
    "CATTLE_MALE_1_2": 0.7,
    "CATTLE_FEMALE_1_2": 0.7,
    "CATTLE_MALE_2_PLUS": 1.0,
    "CATTLE_FEMALE_2_PLUS": 0.8,
}
SHEEP_LSU = 0.1


def _mode(config: SpatialConfig, mode: str | None) -> str:
    value = mode or str(config.raw.get("cattle", {}).get("age_sex_prior", "dafm_log_odds"))
    if value not in AGE_SEX_PRIOR_MODES:
        raise ValueError("age-sex prior must be one of " + ", ".join(sorted(AGE_SEX_PRIOR_MODES)))
    return value


def county_age_sex_targets(county: pd.DataFrame, year: int, county_name: str, other_cattle: int) -> np.ndarray:
    """Seven AAA10 age-sex groups as proportions, Hamilton-scaled to ``other_cattle``."""

    source = county.loc[(county["Year"] == year) & (county["County"] == county_name)]
    if len(source) != 1:
        raise AssertionError(f"{county_name} {year}: expected one AAA10 row")
    raw = source[[f"{c}__HEAD" for c in AAA_AGE_SEX_COLS]].to_numpy(dtype=float)[0]
    if raw.sum() <= 0:
        raise AssertionError(f"{county_name} {year}: zero AAA10 age-sex total")
    return hamilton_allocate(raw / raw.sum(), int(other_cattle))


def build_annual_age_sex_panel(
    config: SpatialConfig,
    annual_panel: pd.DataFrame | None = None,
    mode: str | None = None,
) -> pd.DataFrame:
    """Return the annual panel with the seven CSO age-sex columns added."""

    mode = _mode(config, mode)
    epsilon = float(config.raw.get("cattle", {}).get("dafm_logit_epsilon", DEFAULT_LOGIT_EPSILON))
    if annual_panel is None:
        annual_panel, _ = build_annual_ed_panel(config)
    panel = annual_panel.sort_values(["YEAR", "County", "CSOED"], kind="stable").reset_index(drop=True)
    county = _load_aaa10(config.files["cso_cattle_county"])

    # 2020 ED age-composition signature, one value per ED, used for every year
    frame = panel.loc[panel["YEAR"] == KNOWN_YEAR, ["CSOED", "County", "ED"]].reset_index(drop=True)
    if mode == "dafm_log_odds":
        signal = build_dafm_age_signal(frame, config.files["dafm_aim_ed_cattle_profile_2020"])
        signal["CSOED"] = frame["CSOED"].to_numpy()
        signal = signal.set_index("CSOED")
    else:
        signal = None

    for column in AGE_SEX_COLS:
        panel[column] = np.int64(0)
    values = np.zeros((len(panel), len(AGE_SEX_COLS)), dtype=np.int64)

    for (year, county_name), idx in panel.groupby(["YEAR", "County"]).groups.items():
        idx = np.asarray(idx)
        rows = panel.loc[idx, "OTHER_CATTLE"].to_numpy(dtype=np.int64)
        source = county.loc[(county["Year"] == year) & (county["County"] == county_name)]
        raw = source[[f"{c}__HEAD" for c in AAA_AGE_SEX_COLS]].to_numpy(dtype=float)[0]
        if signal is None:
            allocation, _ = allocate_age_sex(rows, raw, mode="flat_county", epsilon=epsilon)
        else:
            eds = panel.loc[idx, "CSOED"]
            allocation, _ = allocate_age_sex(
                rows,
                raw,
                mode="dafm_log_odds",
                local_q=signal.loc[eds, "DAFM_Q_LOCAL"].to_numpy(dtype=float),
                county_q=float(signal.loc[eds, "DAFM_Q_COUNTY"].iloc[0]),
                epsilon=epsilon,
            )
        values[idx] = allocation

    for j, column in enumerate(AGE_SEX_COLS):
        panel[column] = values[:, j]
    panel["AGE_SEX_PRIOR"] = mode
    _validate(panel, county)
    return panel


def _validate(panel: pd.DataFrame, county: pd.DataFrame) -> None:
    if (panel[AGE_SEX_COLS] < 0).any().any():
        raise AssertionError("negative age-sex value")
    if not (panel[AGE_SEX_COLS].sum(axis=1) == panel["OTHER_CATTLE"]).all():
        raise AssertionError("age-sex groups do not sum to ED OTHER_CATTLE")
    for (year, county_name), group in panel.groupby(["YEAR", "County"]):
        target = county_age_sex_targets(county, year, county_name, int(group["OTHER_CATTLE"].sum()))
        if not np.array_equal(group[AGE_SEX_COLS].sum().to_numpy(dtype=np.int64), target):
            raise AssertionError(f"{county_name} {year}: county age-sex totals do not match AAA10")
    if set(panel["YEAR"]) != set(YEARS):
        raise AssertionError("age-sex panel years are not 2015-2025")


def lsu_check_2020(config: SpatialConfig, panel: pd.DataFrame) -> dict:
    """Held-out check: model cattle LSU + 0.1 x sheep against published 2020 ED LSU.

    Eligible EDs: cattle present, published LSU positive and not above the
    maximum any age-sex split could give (dairy + 0.8 other cows + other
    cattle + 0.1 sheep, plus 1). Returns the median absolute residual.
    """

    published = pd.read_csv(config.files["cso_ed_2020"])
    published["CSOED"] = published["CSOED"].astype(str)
    published = published.set_index("CSOED")
    x = panel.loc[panel["YEAR"] == KNOWN_YEAR].set_index("CSOED")
    model = sum(x[c] * w for c, w in LSU_COEFFICIENTS.items()) + SHEEP_LSU * published.loc[x.index, "TOTAL_SHEEP"]
    lsu = published.loc[x.index, "LSU"].astype(float)
    lsu_max = x["DAIRY_COW"] + 0.8 * x["OTHER_COW"] + x["OTHER_CATTLE"] + SHEEP_LSU * published.loc[x.index, "TOTAL_SHEEP"]
    eligible = (x["TOTAL_CATTLE"] > 0) & (lsu > 0) & (lsu <= lsu_max + 1)
    residual = (lsu - model)[eligible]
    return {
        "eligible_eds": int(eligible.sum()),
        "median_abs_residual": float(residual.abs().median()),
        "mean_residual": float(residual.mean()),
    }
