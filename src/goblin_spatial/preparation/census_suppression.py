"""Suppression-aware preparation of the 2010 and 2020 CSO ED livestock census inputs.

Stage 00 of GOBLIN-Spatial. It runs before the model and only prepares inputs;
nothing in the model runtime imports it.

The CSO Census of Agriculture ED table (AVA42) distinguishes three kinds of
livestock cell: published values, published zeros and blank (unpublished) cells.
The census also publishes exact county totals (2010 Tables 8A/8B, 2020 Tables
4.2/4.4) that sum to the State totals, so the number of animals held in blank
cells is known for every county, livestock type and census year:

    hidden_{c,v} = CountyTotal_{c,v} - sum(published ED values of v in c).

Rules (the scientific contract):

* Published ED values and published zeros are never changed.
* Only blank cells are filled.
* Census county totals, and therefore State totals, are reproduced exactly for
  every variable in both census years; no animal crosses a county boundary.
* Fill order: total cattle -> dairy cows -> other cows -> sheep; other cattle is
  the residual T - D - S and is never negative.
* Reconstructed cows (D + S) in a filled ED are capped at the 99th percentile of
  the cow share of cattle among published EDs with at least 200 cattle.
  Published cells are never capped. Where a county's exact hidden total cannot
  fit under the cap, the cap is relaxed in that county only, up to the ED's
  cattle, and the excess is recorded.
* Prior source chains are frozen in ``PRIOR_SPECS``. Within each control unit
  the blank cells share the hidden total by the prior shrunk toward an equal
  split, lambda * p_i / sum(p) + (1 - lambda) / n. Lambda is selected per
  variable and census year by the hidden-cell test in this module: small
  published cells are hidden and predicted, and each method is scored by the
  share of hidden animals it places in the wrong ED.
* DAFM/AIM rows are matched to census EDs by county and name only where the
  name is unique on both sides.
* Every filled cell records the prior source used and the measured hidden-cell
  error of that source; the confidence class is only a summary of that number.

The full 3,409-ED census universe is reconciled. Animals filled into EDs outside
the 2,857-ED model universe are reported as a coverage residual, never moved
into model EDs.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

VARIABLES = ("T", "D", "S", "SH")
AVA_LABELS = {
    "Total cattle": "T",
    "Dairy cows": "D",
    "Other cows": "S",
    "Total sheep": "SH",
}
STATE_LABELS = {v: k for k, v in AVA_LABELS.items()}
MODEL_COLUMNS = {"T": "TOTAL_CATTLE", "D": "DAIRY_COW", "S": "OTHER_COW", "SH": "TOTAL_SHEEP"}
RESIDUAL_COLUMN = "OTHER_CATTLE"
COW_CAP_QUANTILE = 0.99
COW_CAP_MIN_CATTLE = 200
TEST_SEED = 20261003
TEST_REPETITIONS = 40
TEST_SIZE_QUANTILES = (1 / 3, 1 / 6, 1 / 10)
# Allocation weight within a unit's blank cells:
#   lambda * (prior_i / sum prior) + (1 - lambda) / n_blank.
# A blank cell is suppressed, not zero, so it holds few holdings and its value
# lies in a narrow range; shrinkage toward an equal split is selected per
# variable and census year by the hidden-cell test from this grid.
SHRINKAGE_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)

# Prior source chains, in order of use. A share prior is multiplied by the
# ED's total cattle; a count prior is used directly as a relative weight.
PRIOR_SPECS: dict[str, dict[int, dict[str, tuple[str, ...]]]] = {
    "joint": {
        2020: {
            "T": ("CENSUS_2010", "AIM_LOCAL", "CENSUS_2000"),
            "D": ("CENSUS_2010", "AIM_LOCAL", "CENSUS_2000", "AIM_COUNTY"),
            "S": ("BLEND_2010_AIM", "CENSUS_2010", "AIM_LOCAL", "CENSUS_2000", "AIM_COUNTY"),
            "SH": ("CENSUS_2010", "CENSUS_2000"),
        },
        2010: {
            "T": ("CENSUS_2000", "CENSUS_2020"),
            "D": ("CENSUS_2000", "CENSUS_2020", "NATIONAL"),
            "S": ("CENSUS_2000", "CENSUS_2020", "NATIONAL"),
            "SH": ("CENSUS_2000", "CENSUS_2020"),
        },
    },
    # Robustness variant C: contemporary AIM evidence first in 2020.
    "aim_first": {
        2020: {
            "T": ("AIM_LOCAL", "CENSUS_2010", "CENSUS_2000"),
            "D": ("AIM_LOCAL", "CENSUS_2010", "CENSUS_2000", "AIM_COUNTY"),
            "S": ("AIM_LOCAL", "CENSUS_2010", "CENSUS_2000", "AIM_COUNTY"),
            "SH": ("CENSUS_2010", "CENSUS_2000"),
        },
    },
}
PRIOR_SPECS["aim_first"][2010] = PRIOR_SPECS["joint"][2010]
BLEND_WEIGHT_2010 = 0.5  # 30-70% weights tested; hidden-cell error is practically identical

# Labels summarise TEST_ERROR_PCT, the weighted absolute error of hidden test
# cells that used the same prior source: sum|pred - obs| / sum(obs).
CONFIDENCE_BANDS = ((25.0, "HIGH"), (50.0, "MODERATE"), (float("inf"), "LOW"))


# ------------------------------------------------------------------ keys


def canonical_key(value: object) -> str:
    """Compound-aware canonical CSO ED key, e.g. '08045/08046' -> '8045/8046'."""

    parts = [p.strip() for p in str(value).split("/") if p.strip()]
    if not parts:
        raise ValueError(f"invalid ED code: {value!r}")
    return "/".join(str(x) for x in sorted(int(float(p)) for p in parts))


def normalise_county(value: object) -> str:
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).upper())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def strict_ed_name(value: object) -> str:
    """ED name key keeping qualifiers, e.g. 'Clooney (Quin)' -> 'CLOONEYQUIN'."""

    return re.sub(r"[^A-Z0-9]+", "", _fold(value))


def normalise_ed_name(value: object) -> str:
    """Loose ED name key without parenthesised qualifiers or Rural/Urban."""

    text = re.sub(r"\([^)]*\)", " ", _fold(value))
    text = re.sub(r"\b(?:RURAL|URBAN)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


# ------------------------------------------------------------------ loading


def load_ava42(path: str | Path) -> tuple[dict[int, pd.DataFrame], pd.DataFrame]:
    """Return {year: ED frame} and State totals from the raw AVA42 CSV.

    ED frames are indexed by canonical key with columns ED_NAME, COUNTY and the
    four livestock variables; blank cells are NaN, published zeros are 0.
    """

    raw = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    needed = {"Census Year", "Electoral Division", "Type of Livestock", "VALUE"}
    if needed - set(raw.columns):
        raise ValueError(f"AVA42 missing columns: {sorted(needed - set(raw.columns))}")
    raw = raw.loc[raw["Type of Livestock"].isin(AVA_LABELS)].copy()
    text = raw["VALUE"].str.strip()
    raw["V"] = pd.to_numeric(text.mask(text.eq("")), errors="raise")
    if (raw["V"].dropna() < 0).any():
        raise ValueError("negative AVA42 value")
    raw["YEAR"] = raw["Census Year"].astype(int)
    is_state = raw["Electoral Division"].str.strip().eq("State")
    state = raw.loc[is_state].pivot(index="YEAR", columns="Type of Livestock", values="V")
    state = state.rename(columns=AVA_LABELS).astype(np.int64)
    eds = raw.loc[~is_state].copy()
    label = eds["Electoral Division"]
    eds["KEY"] = label.str.rsplit(",", n=1).str[-1].map(canonical_key)
    eds["ED_NAME"] = label.str.rsplit(", Co.", n=1).str[0].str.strip()
    eds["COUNTY"] = label.str.extract(r",\s*Co\.([^,]+),\s*[^,]+$")[0].map(normalise_county)
    frames: dict[int, pd.DataFrame] = {}
    for year, group in eds.groupby("YEAR"):
        if group.duplicated(["KEY", "Type of Livestock"]).any():
            raise AssertionError(f"AVA42 {year}: duplicate ED x livestock rows")
        wide = group.pivot(index="KEY", columns="Type of Livestock", values="V").rename(columns=AVA_LABELS)
        meta = group.drop_duplicates("KEY").set_index("KEY")[["ED_NAME", "COUNTY"]]
        frames[int(year)] = meta.join(wide)[["ED_NAME", "COUNTY", *VARIABLES]]
    return frames, state


AIM_COLUMNS = (
    "AVERAGE_NUMBER_CATTLE",
    "AVERAGE_CATTLE_DAIRY",
    "AVERAGE_CATTLE_BEEF",
    "AVERAGE_CATTLE_AGE_36MTH_PLUS",
)


def load_aim(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """AIM 2020 ED rows usable for local matching, and county sums of all rows.

    "DED <5 HERDS" rows enter county sums only.
    """

    aim = pd.read_csv(path)
    low_herd = aim["ELECTORAL_DIVISION"].astype(str).str.contains(
        r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
    )
    aim["COUNTY"] = aim["COUNTY"].map(normalise_county)
    county = aim.groupby("COUNTY")[list(AIM_COLUMNS)].sum()
    local = aim.loc[~low_herd, ["COUNTY", "ELECTORAL_DIVISION", *AIM_COLUMNS]].copy()
    local["STRICT"] = local["ELECTORAL_DIVISION"].map(strict_ed_name)
    local["LOOSE"] = local["ELECTORAL_DIVISION"].map(normalise_ed_name)
    return local.reset_index(drop=True), county


def match_aim(eds: pd.DataFrame, aim_local: pd.DataFrame) -> pd.DataFrame:
    """One-to-one match of AIM rows to census EDs by county and name.

    A strict name key (qualifiers kept) is tried first, then a loose key
    (parenthesised qualifiers and Rural/Urban removed). A match is accepted
    only when the key is unique on both sides within the county, and a census
    ED that shares its loose name with another ED of the county is matched
    only by an AIM name carrying its own qualifier. Ambiguous names (two
    'Clooney' EDs in Clare; 'Kilbarry' and 'Kilbarry (Part Rural)') are
    discarded, not guessed, and receive no local AIM evidence. Returns AIM
    columns indexed by census KEY plus AIM_MATCH (STRICT, LOOSE or NONE).
    """

    census = pd.DataFrame(
        {
            "KEY": eds.index,
            "COUNTY": eds["COUNTY"].to_numpy(),
            "STRICT": eds["ED_NAME"].map(strict_ed_name).to_numpy(),
            "LOOSE": eds["ED_NAME"].map(normalise_ed_name).to_numpy(),
        }
    )
    aim = aim_local.reset_index(drop=True).copy()
    aim["ROW"] = aim.index
    matched = []
    used_keys: set = set()
    used_rows: set = set()
    loose_shared = census.duplicated(["COUNTY", "LOOSE"], keep=False)
    for level in ("STRICT", "LOOSE"):
        c = census.loc[~census["KEY"].isin(used_keys)]
        a = aim.loc[~aim["ROW"].isin(used_rows)]
        c = c.loc[~c.duplicated(["COUNTY", level], keep=False)]
        a = a.loc[~a.duplicated(["COUNTY", level], keep=False)]
        if level == "STRICT":
            # An unqualified AIM name ("KILBARRY") cannot pick between census
            # EDs that differ only by a qualifier ("Kilbarry", "Kilbarry (Part
            # Rural)"); only a qualified AIM name may match such an ED.
            qualified = a["STRICT"].ne(a["LOOSE"])
            c_shared = c.loc[loose_shared.loc[c.index]]
            c_unique = c.loc[~loose_shared.loc[c.index]]
            m_unique = c_unique.merge(a[["COUNTY", level, "ROW"]], on=["COUNTY", level], how="inner", validate="one_to_one")
            m_shared = c_shared.merge(
                a.loc[qualified, ["COUNTY", level, "ROW"]], on=["COUNTY", level], how="inner", validate="one_to_one"
            )
            m = pd.concat([m_unique, m_shared], ignore_index=True)
            m["AIM_MATCH"] = level
            matched.append(m[["KEY", "ROW", "AIM_MATCH"]])
            used_keys |= set(m["KEY"])
            used_rows |= set(m["ROW"])
            continue
        m = c.merge(a[["COUNTY", level, "ROW"]], on=["COUNTY", level], how="inner", validate="one_to_one")
        m["AIM_MATCH"] = level
        matched.append(m[["KEY", "ROW", "AIM_MATCH"]])
        used_keys |= set(m["KEY"])
        used_rows |= set(m["ROW"])
    links = pd.concat(matched, ignore_index=True)
    out = links.join(aim[list(AIM_COLUMNS)], on="ROW").set_index("KEY").drop(columns="ROW")
    out = out.reindex(eds.index)
    out["AIM_MATCH"] = out["AIM_MATCH"].fillna("NONE")
    return out


COUNTY_TABLE_COLUMNS = {"T": "TOTAL_CATTLE", "D": "DAIRY_COW", "S": "OTHER_COW", "SH": "TOTAL_SHEEP"}


def load_census_county(path: str | Path) -> dict[int, pd.DataFrame]:
    """Exact Census of Agriculture county livestock totals, {year: frame by COUNTY}."""

    raw = pd.read_csv(path, encoding="utf-8-sig")
    out = {}
    for year, g in raw.groupby("CENSUS_YEAR"):
        g = g.assign(COUNTY=g["COUNTY"].map(normalise_county))
        frame = g.groupby("COUNTY")[list(COUNTY_TABLE_COLUMNS.values())].sum().astype(np.int64)
        frame.columns = list(COUNTY_TABLE_COLUMNS)
        out[int(year)] = frame
    return out


def load_aaa10_2020(path: str | Path) -> pd.DataFrame:
    a = pd.read_csv(path, encoding="utf-8-sig")
    a = a.loc[(a["Year"] == 2020) & (a["UNIT"] == "000 Head")].copy()
    a["COUNTY"] = a["Region and County"].map(normalise_county)
    if a["COUNTY"].duplicated().any():
        raise AssertionError("duplicate AAA10 2020 county")
    out = a.set_index("COUNTY")[["Total cattle", "Dairy cows", "Other cows"]].astype(float)
    out = (out * 1000).round().astype(np.int64)
    out.columns = ["T", "D", "S"]
    return out


def load_aaa09_2020(path: str | Path) -> tuple[pd.Series, pd.Series]:
    region = pd.read_excel(path, sheet_name="Region_WIDE")
    region = region.loc[(region["Year"] == 2020) & (region["Region_Level"] == "Detailed region")]
    totals = (region.set_index("Region")["Total sheep"] * 1000).round().astype(np.int64)
    county = pd.read_excel(path, sheet_name="County_WIDE").drop_duplicates("County")
    county_region = county.set_index("County")["Region"]
    county_region.index = county_region.index.map(normalise_county)
    return totals, county_region


# ------------------------------------------------------------------ frame


@dataclass
class CensusFrame:
    """All 3,409 census EDs for one target year with the evidence needed for priors."""

    year: int
    frame: pd.DataFrame
    state: pd.Series
    status: dict[str, np.ndarray] = field(default_factory=dict)


def build_frame(
    year: int,
    census: dict[int, pd.DataFrame],
    state: pd.DataFrame,
    aim_local: pd.DataFrame,
    aim_county: pd.DataFrame,
    model_keys: set[str],
) -> CensusFrame:
    base = census[year].copy()
    for other in (2000, 2010, 2020):
        if other != year:
            base = base.join(census[other][list(VARIABLES)].add_suffix(f"_{other}"))
    base["IN_MODEL"] = base.index.isin(model_keys)
    merged = base.join(match_aim(census[2020], aim_local))
    n = merged["AVERAGE_NUMBER_CATTLE"]
    merged["AIM_N"] = n
    merged["AIM_DAIRY_SHARE"] = merged["AVERAGE_CATTLE_DAIRY"] / n
    merged["AIM_COW_PROXY"] = (merged["AVERAGE_CATTLE_BEEF"] / n) * (
        merged["AVERAGE_CATTLE_AGE_36MTH_PLUS"] / n
    )
    cn = aim_county["AVERAGE_NUMBER_CATTLE"]
    merged["AIM_COUNTY_DAIRY_SHARE"] = merged["COUNTY"].map(aim_county["AVERAGE_CATTLE_DAIRY"] / cn)
    merged["AIM_COUNTY_COW_PROXY"] = merged["COUNTY"].map(
        (aim_county["AVERAGE_CATTLE_BEEF"] / cn) * (aim_county["AVERAGE_CATTLE_AGE_36MTH_PLUS"] / cn)
    )
    status = {
        v: np.where(merged[v].isna(), "BLANK", np.where(merged[v].eq(0), "ZERO", "POSITIVE"))
        for v in VARIABLES
    }
    return CensusFrame(year, merged, state.loc[year], status)


# ------------------------------------------------------------------ priors


def _share(num: pd.Series, den: pd.Series) -> np.ndarray:
    num = num.astype(float)
    den = den.astype(float)
    return np.where((den > 0) & num.notna() & den.notna(), num / den, np.nan)


def _cow_proxy_scale(f: pd.DataFrame) -> float:
    """Scale the AIM beef x 36+ month proxy to other-cow share units."""

    ratio = _share(f["S"], f["T"]) / np.where(f["AIM_COW_PROXY"] > 0, f["AIM_COW_PROXY"], np.nan)
    scale = float(np.nanmedian(ratio))
    if not np.isfinite(scale) or scale <= 0:
        raise AssertionError("cannot scale AIM cow proxy")
    return scale


def prior_candidates(cf: CensusFrame, v: str) -> dict[str, np.ndarray]:
    """Every named prior for variable v as a share (D, S) or a count (T, SH)."""

    f = cf.frame
    out: dict[str, np.ndarray] = {}
    hist = [y for y in (2000, 2010, 2020) if y != cf.year]
    if v in ("D", "S"):
        for y in hist:
            out[f"CENSUS_{y}"] = _share(f[f"{v}_{y}"], f[f"T_{y}"])
        published = f.loc[f[v].notna() & f["T"].gt(0)]
        out["NATIONAL"] = np.full(len(f), float(published[v].sum() / published["T"].sum()))
        if cf.year == 2020:
            if v == "D":
                out["AIM_LOCAL"] = f["AIM_DAIRY_SHARE"].to_numpy(float)
                out["AIM_COUNTY"] = f["AIM_COUNTY_DAIRY_SHARE"].to_numpy(float)
            else:
                k = _cow_proxy_scale(f)
                out["AIM_LOCAL"] = f["AIM_COW_PROXY"].to_numpy(float) * k
                out["AIM_COUNTY"] = f["AIM_COUNTY_COW_PROXY"].to_numpy(float) * k
            a, h = out["AIM_LOCAL"], out["CENSUS_2010"]
            w = BLEND_WEIGHT_2010
            out["BLEND_2010_AIM"] = np.where(~np.isnan(a) & ~np.isnan(h), w * h + (1 - w) * a, np.nan)
    elif v == "T":
        for y in hist:
            out[f"CENSUS_{y}"] = f[f"T_{y}"].to_numpy(float)
        if cf.year == 2020:
            out["AIM_LOCAL"] = f["AIM_N"].to_numpy(float)
    elif v == "SH":
        for y in hist:
            out[f"CENSUS_{y}"] = f[f"SH_{y}"].to_numpy(float)
    return out


def chained_prior(cf: CensusFrame, v: str, chain: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """First available prior in the chain for each ED, with its source label."""

    candidates = prior_candidates(cf, v)
    n = len(cf.frame)
    value = np.full(n, np.nan)
    source = np.full(n, "NONE", dtype=object)
    for name in chain:
        cand = candidates[name]
        take = np.isnan(value) & ~np.isnan(cand)
        value[take] = cand[take]
        source[take] = name
    return value, source


def prior_weight(cf: CensusFrame, v: str, value: np.ndarray, totals: np.ndarray) -> np.ndarray:
    """Convert a prior into an allocation weight (shares x ED total cattle)."""

    w = np.nan_to_num(value, nan=0.0)
    if v in ("D", "S"):
        w = w * np.nan_to_num(totals, nan=0.0)
    return np.clip(w, 0.0, None)


# ------------------------------------------------------------------ allocation


def hamilton(weights: np.ndarray, target: int) -> np.ndarray:
    weights = np.asarray(weights, dtype=float)
    if target == 0:
        return np.zeros(len(weights), dtype=np.int64)
    if weights.sum() <= 0:
        raise ValueError("positive target with zero allocation weight")
    scaled = weights / weights.sum() * target
    base = np.floor(scaled).astype(np.int64)
    remainder = int(target - base.sum())
    if remainder:
        base[np.argsort(-(scaled - base), kind="stable")[:remainder]] += 1
    return base


def capped_hamilton(weights: np.ndarray, capacity: np.ndarray, target: int) -> tuple[np.ndarray, int]:
    """Hamilton allocation with per-cell integer capacity; returns (alloc, unallocated)."""

    w = np.asarray(weights, dtype=float).copy()
    cap = np.floor(np.asarray(capacity, dtype=float)).astype(np.int64)
    out = np.zeros(len(w), dtype=np.int64)
    remaining = int(target)
    active = (cap > 0) & (w > 0)
    if remaining > int(cap[active].sum()):
        # Evidence-less cells with capacity may absorb what evidenced cells cannot.
        active = cap > 0
        w = np.where(w > 0, w, 1e-9)
    while remaining > 0:
        idx = np.flatnonzero(active)
        if len(idx) == 0:
            break
        proposal = hamilton(w[idx], remaining)
        accepted = np.minimum(proposal, cap[idx] - out[idx])
        if accepted.sum() == 0:
            break
        out[idx] += accepted
        remaining -= int(accepted.sum())
        active[idx] = out[idx] < cap[idx]
    return out, remaining


def shrunk_weights(weights: np.ndarray, lam: float) -> np.ndarray:
    """Normalised prior weights shrunk toward an equal split."""

    w = np.clip(np.asarray(weights, dtype=float), 0.0, None)
    n = len(w)
    if n == 0:
        return w
    equal = np.full(n, 1.0 / n)
    if w.sum() <= 0:
        return equal
    return lam * w / w.sum() + (1.0 - lam) * equal


@dataclass
class Reconciled:
    values: pd.DataFrame
    cells: pd.DataFrame
    units: pd.DataFrame
    cow_cap_share: float


def reconcile(
    cf: CensusFrame,
    county_totals: pd.DataFrame,
    variant: str = "joint",
    shrinkage: dict[str, float] | None = None,
) -> Reconciled:
    """Fill blank cells of one census year inside exact county totals.

    ``county_totals`` holds the census county totals (columns T, D, S, SH).
    ``shrinkage`` gives lambda per variable, normally from ``select_shrinkage``;
    without it the prior is used unshrunk (lambda 1).
    """

    f = cf.frame
    spec = PRIOR_SPECS[variant][cf.year]
    values = f[list(VARIABLES)].copy()
    sources = {v: np.full(len(f), "", dtype=object) for v in VARIABLES}
    over_cap = {v: np.zeros(len(f), dtype=bool) for v in VARIABLES}
    unit_rows = []
    shrinkage = {v: 1.0 for v in VARIABLES} | dict(shrinkage or {})
    counties = f["COUNTY"].to_numpy()
    if set(counties) != set(county_totals.index):
        raise AssertionError(f"{cf.year}: census county table and AVA42 counties differ")
    for v in VARIABLES:
        if int(county_totals[v].sum()) != int(cf.state[v]):
            raise AssertionError(f"{cf.year} {v}: county totals do not sum to the State total")

    def fill(v: str, capacity=None, hard_capacity=None, floor=None):
        blank = values[v].isna().to_numpy()
        published = f[v].groupby(counties).sum(min_count=1).fillna(0).astype(np.int64)
        hidden = county_totals[v] - published.reindex(county_totals.index).fillna(0).astype(np.int64)
        prior, src = chained_prior(cf, v, spec[v])
        weight = prior_weight(cf, v, prior, values["T"].to_numpy(float))
        lam = float(shrinkage[v])
        if lam == 0.0:
            src = np.full(len(f), "EQUAL_SPLIT", dtype=object)
        cap = np.full(len(f), 1e15) if capacity is None else np.floor(capacity)
        hard = cap if hard_capacity is None else np.floor(hard_capacity)
        filled = np.zeros(len(f), dtype=np.int64)
        for county, target in hidden.items():
            idx = np.flatnonzero(blank & (counties == county))
            if target < 0:
                raise AssertionError(f"{cf.year} {v} {county}: published EDs exceed the county total")
            if len(idx) == 0:
                if target:
                    raise AssertionError(f"{cf.year} {v} {county}: hidden animals but no blank cell")
                continue
            base = np.zeros(len(idx), dtype=np.int64)
            remaining = int(target)
            if floor is not None:
                base = np.minimum(floor[idx].astype(np.int64), remaining)
                remaining -= int(base.sum())
            w = shrunk_weights(weight[idx], lam)
            alloc, left = capped_hamilton(w, cap[idx] - base, remaining)
            above_cap = 0
            if left:
                # The exact county total wins over the plausibility cap.
                extra, left = capped_hamilton(w, hard[idx] - base - alloc, left)
                alloc += extra
                above_cap = int(extra.sum())
            if left:
                raise AssertionError(f"{cf.year} {v} {county}: hidden total exceeds the blank cells' cattle")
            filled[idx] = base + alloc
            over_cap[v][idx] = (base + alloc) > cap[idx]
            unit_rows.append(
                {
                    "YEAR": cf.year,
                    "VARIABLE": MODEL_COLUMNS[v],
                    "COUNTY": county,
                    "SHRINKAGE_LAMBDA": lam,
                    "CENSUS_COUNTY_TOTAL": int(county_totals.at[county, v]),
                    "PUBLISHED_SUM": int(published.get(county, 0)),
                    "HIDDEN_TOTAL": int(target),
                    "BLANK_CELLS": int(len(idx)),
                    "FILLED": int((base + alloc).sum()),
                    "FILLED_ABOVE_COW_CAP": above_cap,
                    "FILLED_OUTSIDE_MODEL": int((base + alloc)[~f["IN_MODEL"].to_numpy()[idx]].sum()),
                }
            )
        values.loc[blank, v] = filled[blank]
        sources[v][blank] = src[blank]

    # 1 total cattle, never below the ED's published cows
    floor = (f["D"].fillna(0) + f["S"].fillna(0)).to_numpy()
    fill("T", floor=floor)
    totals = values["T"].to_numpy(float)
    # cow-share cap from published EDs of this census year
    pub = f.loc[f["T"].ge(COW_CAP_MIN_CATTLE) & f["D"].notna() & f["S"].notna()]
    cap_share = float(((pub["D"] + pub["S"]) / pub["T"]).quantile(COW_CAP_QUANTILE))
    s_pub = f["S"].fillna(0).to_numpy()
    # 2 dairy cows
    hard_d = np.clip(totals - s_pub, 0, None)
    fill("D", capacity=np.minimum(np.clip(cap_share * totals - s_pub, 0, None), hard_d), hard_capacity=hard_d)
    # 3 other cows
    dairy = values["D"].to_numpy(float)
    hard_s = np.clip(totals - dairy, 0, None)
    fill("S", capacity=np.minimum(np.clip(cap_share * totals - dairy, 0, None), hard_s), hard_capacity=hard_s)
    # 4 sheep
    fill("SH")

    values = values.astype(np.int64)
    values[RESIDUAL_COLUMN] = values["T"] - values["D"] - values["S"]
    if (values[RESIDUAL_COLUMN] < 0).any():
        raise AssertionError(f"{cf.year}: negative other cattle after reconciliation")
    for v in VARIABLES:
        published = cf.status[v] != "BLANK"
        if not (values.loc[published, v].to_numpy() == f.loc[published, v].to_numpy()).all():
            raise AssertionError(f"{cf.year} {v}: a published cell changed")
        if not values[v].groupby(counties).sum().reindex(county_totals.index).eq(county_totals[v]).all():
            raise AssertionError(f"{cf.year} {v}: county totals not reproduced")

    cells = []
    for v in VARIABLES:
        blank = cf.status[v] == "BLANK"
        flag = over_cap[v][blank]
        cells.append(
            pd.DataFrame(
                {
                    "YEAR": cf.year,
                    "KEY": f.index[blank],
                    "ED_NAME": f["ED_NAME"].to_numpy()[blank],
                    "COUNTY": f["COUNTY"].to_numpy()[blank],
                    "IN_MODEL": f["IN_MODEL"].to_numpy()[blank],
                    "VARIABLE": MODEL_COLUMNS[v],
                    "FILLED_VALUE": values[v].to_numpy()[blank],
                    "SOURCE": sources[v][blank],
                    "ABOVE_COW_CAP": flag,
                }
            )
        )
    return Reconciled(values, pd.concat(cells, ignore_index=True), pd.DataFrame(unit_rows), cap_share)


# ------------------------------------------------------------------ hidden-cell test


def hidden_cell_test(
    cf: CensusFrame,
    unit_cols: dict[str, str | None],
    chains: dict[str, tuple[str, ...]],
    repetitions: int = TEST_REPETITIONS,
    seed: int = TEST_SEED,
    fallback_only: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hide small published cells, predict them, score the error.

    In every unit (county, region or State) as many small published cells are
    hidden as the unit really has blank cells (at least two). Their known total
    is allocated back over them by every named prior (unshrunk), by an equal
    split, and by the frozen chain at every lambda in SHRINKAGE_GRID.
    DISPLACED_PCT is the share of hidden animals placed in the wrong ED.
    ``unit_cols`` maps each variable to its control unit column (None = State).

    Returns (scores, per-source error of the frozen chain by lambda). With
    ``fallback_only`` the test cells are restricted to EDs without the first
    prior of the chain, i.e. the population on which the fallback order is used.
    """

    f = cf.frame
    rng = np.random.default_rng(seed)
    rows, by_source = [], []
    for v in VARIABLES:
        unit_col = unit_cols.get(v)
        units = f[unit_col] if unit_col else pd.Series("STATE", index=f.index)
        cand = prior_candidates(cf, v)
        frozen_value, frozen_src = chained_prior(cf, v, chains[v])
        methods = [(name, 1.0) for name in cand] + [("EQUAL_SPLIT", 0.0)]
        methods += [("FROZEN_CHAIN", lam) for lam in SHRINKAGE_GRID]
        published = f[v].gt(0) & (f["T"].notna() if v != "SH" else True)
        if fallback_only:
            if chains[v][0] not in cand:
                continue
            published &= np.isnan(cand[chains[v][0]])
        blanks_per_unit = units[f[v].isna()].value_counts()
        values = f[v].to_numpy(float)
        cattle = f["T"].to_numpy(float)
        for q in TEST_SIZE_QUANTILES:
            threshold = f.loc[published, v].quantile(q)
            small = f.index[published & f[v].le(threshold)]
            stats = {m: [0.0, 0.0, [], []] for m in methods}
            src_err: dict[tuple[str, float], list[float]] = {}
            for _ in range(repetitions):
                for unit, idx in pd.Series(small, index=small).groupby(units.loc[small]):
                    pool = idx.to_numpy()
                    h = int(min(max(blanks_per_unit.get(unit, 0), 2), len(pool)))
                    if h < 2:
                        continue
                    pos = f.index.get_indexer(rng.choice(pool, h, replace=False))
                    obs = values[pos]
                    total = int(obs.sum())
                    for name, lam in methods:
                        raw = frozen_value[pos] if name in ("FROZEN_CHAIN", "EQUAL_SPLIT") else cand[name][pos]
                        w = np.nan_to_num(raw, nan=0.0) * (cattle[pos] if v in ("D", "S") else 1.0)
                        if lam == 1.0 and w.sum() <= 0:
                            continue
                        pred = hamilton(shrunk_weights(w, lam), total)
                        s = stats[(name, lam)]
                        s[0] += 0.5 * np.abs(pred - obs).sum()
                        s[1] += total
                        s[2].extend(pred)
                        s[3].extend(obs)
                        if name == "FROZEN_CHAIN":
                            labels = frozen_src[pos] if lam > 0 else np.full(len(pos), "EQUAL_SPLIT", dtype=object)
                            for label in np.unique(labels):
                                m = labels == label
                                e = src_err.setdefault((label, lam), [0.0, 0.0])
                                e[0] += np.abs(pred[m] - obs[m]).sum()
                                e[1] += obs[m].sum()
            label_q = f"smallest {q:.3f} of published cells"
            population = "WITHOUT_" + chains[v][0] if fallback_only else "ALL"
            for (name, lam), (err, tot, pred, obs) in stats.items():
                if tot <= 0:
                    continue
                rows.append(
                    {
                        "YEAR": cf.year,
                        "VARIABLE": MODEL_COLUMNS[v],
                        "PRIOR": name,
                        "LAMBDA": lam,
                        "TEST_CELLS": label_q,
                        "POPULATION": population,
                        "N_SCORED": len(obs),
                        "DISPLACED_PCT": round(100 * err / tot, 2),
                        "SPEARMAN": round(float(spearmanr(pred, obs).statistic), 3),
                    }
                )
            for (label, lam), (err, tot) in src_err.items():
                by_source.append(
                    {
                        "YEAR": cf.year,
                        "VARIABLE": MODEL_COLUMNS[v],
                        "SOURCE": label,
                        "LAMBDA": lam,
                        "TEST_CELLS": label_q,
                        # weighted absolute error of the cells that used this source
                        "TEST_ERROR_PCT": round(100 * err / tot, 2) if tot else np.nan,
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(by_source)


def select_shrinkage(scores: pd.DataFrame) -> pd.Series:
    """Lambda per (year, variable): lowest mean DISPLACED_PCT of the frozen chain.

    Ties go to the larger lambda (more weight on ED evidence).
    """

    chain = scores.loc[scores["PRIOR"].eq("FROZEN_CHAIN") & scores["POPULATION"].eq("ALL")]
    mean = chain.groupby(["YEAR", "VARIABLE", "LAMBDA"])["DISPLACED_PCT"].mean().round(2).reset_index()
    mean = mean.sort_values(["YEAR", "VARIABLE", "DISPLACED_PCT", "LAMBDA"], ascending=[True, True, True, False])
    return mean.groupby(["YEAR", "VARIABLE"])["LAMBDA"].first()


def source_error_lookup(by_source: pd.DataFrame, shrinkage: pd.Series) -> pd.Series:
    """Mean error of each (year, variable, source) across test sizes at the selected lambda."""

    chosen = by_source.merge(shrinkage.rename("SELECTED").reset_index(), on=["YEAR", "VARIABLE"])
    chosen = chosen.loc[chosen["LAMBDA"].eq(chosen["SELECTED"])]
    return chosen.groupby(["YEAR", "VARIABLE", "SOURCE"])["TEST_ERROR_PCT"].mean().round(1)


def confidence_class(error_pct: float) -> str:
    if not np.isfinite(error_pct):
        return "UNTESTED"
    for limit, label in CONFIDENCE_BANDS:
        if error_pct <= limit:
            return label
    return "LOW"


def attach_error_flags(cells: pd.DataFrame, lookup: pd.Series) -> pd.DataFrame:
    keys = list(zip(cells["YEAR"], cells["VARIABLE"], cells["SOURCE"]))
    cells = cells.copy()
    cells["TEST_ERROR_PCT"] = [lookup.get(k, np.nan) for k in keys]
    cells["CONFIDENCE_CLASS"] = cells["TEST_ERROR_PCT"].map(confidence_class)
    return cells


# ------------------------------------------------------------------ temporal holdout


def temporal_holdout(
    census: dict[int, pd.DataFrame],
    model_keys: set[str],
    weights: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """2010 within-county shares applied to 2020 county totals, published cells only.

    Tests the persistence assumption used for non-census years. Only EDs with
    published values in both censuses are scored. ``weights`` (KEY, UNIT,
    WEIGHT) adds an aggregated comparison, e.g. WFD catchments.
    """

    rows = []
    for v in VARIABLES:
        a = census[2010][v]
        b = census[2020][v]
        keep = a.notna() & b.notna() & a.index.isin(model_keys)
        t = pd.DataFrame({"COUNTY": census[2020]["COUNTY"], "Y10": a, "Y20": b}).loc[keep]
        c20 = t.groupby("COUNTY")["Y20"].transform("sum")
        c10 = t.groupby("COUNTY")["Y10"].transform("sum")
        t["PRED"] = np.where(c10 > 0, t["Y10"] / c10 * c20, np.nan)
        t = t.dropna(subset=["PRED"])

        def score(pred, obs):
            return (
                round(float(spearmanr(pred, obs).statistic), 3),
                round(float(50 * np.abs(pred - obs).sum() / obs.sum()), 2),
            )

        rho, disp = score(t["PRED"], t["Y20"])
        row = {"VARIABLE": MODEL_COLUMNS[v], "EDS_SCORED": int(len(t)), "ED_SPEARMAN": rho, "ED_DISPLACED_PCT": disp}
        if weights is not None:
            m = t.join(weights.set_index("KEY"), how="inner")
            g = m.assign(P=m["PRED"] * m["WEIGHT"], O=m["Y20"] * m["WEIGHT"]).groupby("UNIT")[["P", "O"]].sum()
            row["UNIT_SPEARMAN"], row["UNIT_DISPLACED_PCT"] = score(g["P"], g["O"])
        rows.append(row)
    return pd.DataFrame(rows)
