"""CSO-controlled annual ED sheep panel, 2015-2025.

Published 2020 ED sheep are the fine-scale spatial anchor. Unknown years are
reconstructed to the binding CSO AAA09 detailed-region totals, while DAFM
breeding-ewe shares move county weights within each region.

Published
    2020  CSO Census of Agriculture ED TOTAL_SHEEP, returned unchanged,
          including every published zero. The difference between the published
          ED sum and AAA09 2020 is logged as a source difference only and is
          never placed into any ED.

Not published (2015-2019, 2021-2025)
    1. County split within region. Each county starts from its published 2020
       share of regional ED sheep. That share is moved by a DAFM breeding-ewe
       index
           m(c, t) = s_DAFM_ewes(c | r, t) / s_DAFM_ewes(c | r, 2020)
       with DAFM anchors 2015, 2016, 2020, 2022 and 2025 (linear between
       anchors), then renormalised within the region and Hamilton-rounded to
       the AAA09 regional total. DAFM sets direction only; CSO sets the level.

    2. ED split within county. Each ED's share of its county moves linearly
       from its 2010 share to its published 2020 share for 2015-2019,
       lambda = (year - 2010) / 10, and holds the published 2020 share for
       2021-2025. A blank 2010 value takes the published 2020 share. A
       published 2020 zero therefore remains zero from 2021 to 2025.

    3. Classes (ewes 2+, ewes <2, rams, other sheep). AAA09 regional class
       totals, Hamilton-scaled to the regional total, are allocated over EDs
       in proportion to ED TOTAL_SHEEP and integerised without changing any ED
       total. No county class totals are invented. In 2020 the class vector is
       scaled to the published regional ED sum.

Stage boundary: this module ends at CSO-level sheep (ED TOTAL_SHEEP and the
four AAA09 classes). DAFM breed composition, the 10 GOBLIN sheep cohorts and
any GOBLIN/COHORTS calibration are later, separate stages.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_panel import _integerise_keep_zeros
from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate
from goblin_spatial.sheep.panel import (
    ED_CLASS_COLS,
    IDENTIFIER_CANDIDATES,
    REGION_SOURCE_COLS,
    _load_workbook,
    _normalise_county,
)

YEARS = tuple(range(2015, 2026))
KNOWN_YEAR = 2020
DAFM_EWE_ANCHORS = (2015, 2016, 2020, 2022, 2025)
PROVENANCE_KNOWN = "CSO_ED_2020_PUBLISHED_UNCHANGED"
PROVENANCE_PATH = "AAA09_REGION_CONTROL_ED_2010_2020_PATH"
PROVENANCE_HELD = "AAA09_REGION_CONTROL_ED_2020_PATTERN"
OUTPUT_CLASS_COLS = (*ED_CLASS_COLS, "EWES", "BREEDING_SHEEP")


# ---------------------------------------------------------------- loading


def _load_ed_2020(path, crosswalk: pd.DataFrame, expected_eds: int) -> pd.DataFrame:
    ed = pd.read_csv(path)
    required = ["CSOED", "County", "TOTAL_SHEEP", "TOTAL_CATTLE", "ALL_GRASSLAND"]
    missing = [column for column in required if column not in ed.columns]
    if missing:
        raise ValueError(f"2020 ED data missing columns: {missing}")
    ed["CSOED"] = ed["CSOED"].astype(str)
    ed["County"] = ed["County"].map(_normalise_county)
    for column in ("TOTAL_SHEEP", "TOTAL_CATTLE"):
        values = pd.to_numeric(ed[column], errors="raise")
        if values.isna().any() or (values < 0).any() or (values % 1 != 0).any():
            raise ValueError(f"2020 ED {column} must be non-negative integers")
        ed[column] = values.astype(np.int64)
    ed["ALL_GRASSLAND"] = pd.to_numeric(ed["ALL_GRASSLAND"], errors="raise").astype(float)
    if len(ed) != expected_eds or ed["CSOED"].duplicated().any():
        raise AssertionError(f"expected {expected_eds:,} unique 2020 EDs")
    ed["_ED_KEY"] = ed["CSOED"].map(canonical_ed_key)
    if ed["_ED_KEY"].duplicated().any():
        raise AssertionError("duplicate canonical ED key in 2020 ED data")
    ed = ed.merge(crosswalk, on="County", how="left", validate="many_to_one")
    if ed[["Region", "NUTS2"]].isna().any().any():
        raise AssertionError("county without AAA09 region mapping")
    return ed.sort_values(["County", "CSOED"], kind="stable").reset_index(drop=True)


def _attach_2010(ed: pd.DataFrame, path) -> pd.DataFrame:
    """Attach 2010 ED TOTAL_SHEEP, keeping published blanks as NaN."""

    e10 = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "TOTAL_SHEEP" not in e10.columns or "CSOED" not in e10.columns:
        raise ValueError("2010 ED data missing CSOED or TOTAL_SHEEP")
    e10["_ED_KEY"] = e10["CSOED"].map(canonical_ed_key)
    if e10["_ED_KEY"].duplicated().any():
        raise AssertionError("duplicate canonical ED key in 2010 ED data")
    text = e10["TOTAL_SHEEP"].astype(str).str.strip()
    values = pd.to_numeric(text.mask(text.eq("")), errors="raise")
    if (values.dropna() < 0).any():
        raise ValueError("negative 2010 TOTAL_SHEEP")
    source = pd.Series(values.to_numpy(dtype=float), index=e10["_ED_KEY"])
    missing = sorted(set(ed["_ED_KEY"]) - set(source.index))
    if missing:
        raise AssertionError(f"2010 ED data missing {len(missing)} EDs of the 2020 frame")
    out = ed.copy()
    out["TOTAL_SHEEP_2010"] = out["_ED_KEY"].map(source).astype(float)
    return out


def _dafm_ewe_shares(county_path, breed_path, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """DAFM December breeding-ewe county shares within AAA09 region by anchor year.

    2015, 2020, 2022, 2025 from the DAFM county census file; 2016 from the
    breed-anchor file (EWES totals, identical to the county file where both
    report a year).
    """

    county = pd.read_csv(county_path)
    required_county = {"YEAR", "County", "EWES"}
    missing_county = sorted(required_county - set(county.columns))
    if missing_county:
        raise ValueError(f"DAFM sheep county pattern missing columns: {missing_county}")
    county["YEAR"] = pd.to_numeric(county["YEAR"], errors="raise").astype(int)
    county["County"] = county["County"].map(_normalise_county)
    county["EWES"] = pd.to_numeric(county["EWES"], errors="raise").astype(float)
    if not np.isfinite(county["EWES"]).all() or (county["EWES"] <= 0).any():
        raise ValueError("DAFM sheep county pattern has non-positive or non-finite EWES")
    if county[["YEAR", "County"]].duplicated().any():
        raise AssertionError("duplicate DAFM sheep county-year rows")
    ewes = county[["YEAR", "County", "EWES"]].copy()

    breed = pd.read_csv(breed_path, encoding="utf-8-sig")
    required_breed = {"YEAR", "CATEGORY", "County", "TOTAL_DAFM"}
    missing_breed = sorted(required_breed - set(breed.columns))
    if missing_breed:
        raise ValueError(f"DAFM sheep breed anchors missing columns: {missing_breed}")
    breed["YEAR"] = pd.to_numeric(breed["YEAR"], errors="raise").astype(int)
    breed["County"] = breed["County"].map(_normalise_county)
    breed["TOTAL_DAFM"] = pd.to_numeric(
        breed["TOTAL_DAFM"], errors="raise"
    ).astype(float)
    breed = breed.loc[
        breed["CATEGORY"].astype(str).str.upper() == "EWES",
        ["YEAR", "County", "TOTAL_DAFM"],
    ]
    if not np.isfinite(breed["TOTAL_DAFM"]).all() or (breed["TOTAL_DAFM"] <= 0).any():
        raise ValueError("DAFM sheep ewe breed anchors are non-positive or non-finite")
    if breed[["YEAR", "County"]].duplicated().any():
        raise AssertionError("duplicate DAFM ewe breed-anchor county-year rows")
    breed = breed.rename(columns={"TOTAL_DAFM": "EWES"})

    both = ewes.merge(breed, on=["YEAR", "County"], suffixes=("", "_BREED"))
    if not both.empty and (both["EWES"] != both["EWES_BREED"]).any():
        raise AssertionError("DAFM county and breed-anchor ewe totals disagree")
    ewes = pd.concat([ewes, breed.loc[~breed["YEAR"].isin(ewes["YEAR"])]], ignore_index=True)

    ewes = ewes.loc[ewes["YEAR"].isin(DAFM_EWE_ANCHORS)]
    for year in DAFM_EWE_ANCHORS:
        counties = set(ewes.loc[ewes["YEAR"] == year, "County"])
        if counties != set(crosswalk["County"]):
            raise AssertionError(f"DAFM ewes {year}: county coverage differs from the crosswalk")
    if (ewes["EWES"] <= 0).any():
        raise AssertionError("DAFM county ewes must be positive")

    ewes = ewes.merge(crosswalk[["County", "Region"]], on="County", validate="many_to_one")
    ewes["SHARE"] = ewes["EWES"] / ewes.groupby(["YEAR", "Region"])["EWES"].transform("sum")
    return ewes.pivot_table(index="County", columns="YEAR", values="SHARE").loc[:, list(DAFM_EWE_ANCHORS)]


def _ewe_index(shares: pd.DataFrame, year: int) -> pd.Series:
    """m(c, t): DAFM ewe share at t (linear between anchors) over its 2020 share."""

    anchors = list(shares.columns)
    if year in anchors:
        s_t = shares[year]
    else:
        lo = max(a for a in anchors if a < year)
        hi = min(a for a in anchors if a > year)
        w = (year - lo) / (hi - lo)
        s_t = (1.0 - w) * shares[lo] + w * shares[hi]
    return s_t / shares[KNOWN_YEAR]


# ----------------------------------------------------------------- shares


def _ed_shares(ed: pd.DataFrame, published_2020: pd.Series) -> pd.DataFrame:
    """Within-county ED shares: 2010 (blank rule) and published 2020."""

    s2010 = pd.Series(0.0, index=ed.index)
    s2020 = pd.Series(0.0, index=ed.index)
    for _, idx in ed.groupby("County").groups.items():
        r20 = published_2020.loc[idx]
        if r20.sum() <= 0:
            raise AssertionError("county with no published 2020 sheep")
        c20 = r20 / r20.sum()
        s2020.loc[idx] = c20
        t10 = ed.loc[idx, "TOTAL_SHEEP_2010"]
        blank = t10.isna()
        published = t10.loc[~blank]
        if published.sum() <= 0:
            s2010.loc[idx] = c20
            continue
        s2010.loc[t10.index[blank]] = c20.loc[t10.index[blank]]
        remaining = max(0.0, 1.0 - float(c20.loc[t10.index[blank]].sum()))
        s2010.loc[published.index] = published / published.sum() * remaining
    return pd.DataFrame({"SHARE_2010": s2010, "SHARE_2020": s2020})


def _region_class_targets(region: pd.DataFrame, year: int, region_name: str, total: int) -> tuple[np.ndarray, int]:
    row = region.loc[(region["Year"] == year) & (region["Region"] == region_name)].iloc[0]
    raw = np.array([row[f"{c}__HEAD"] for c in REGION_SOURCE_COLS], dtype=float)
    rounding = int(raw.sum()) - int(row["Total sheep__HEAD"])
    return hamilton_allocate(raw, int(total)), rounding


# ------------------------------------------------------------------ build


def build_annual_sheep_panel(config: SpatialConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (panel, log) for 2015-2025 under the published-2020 support rule."""

    crosswalk, region = _load_workbook(config.files["cso_sheep_workbook"])
    ed = _load_ed_2020(config.files["cso_ed_2020"], crosswalk, config.expected_eds)
    ed = _attach_2010(ed, config.files["cso_ed_2010"])
    dafm = _dafm_ewe_shares(
        config.files["dafm_sheep_county_pattern"],
        config.files["sheep_breed_anchors"],
        crosswalk,
    )

    published_2020 = ed["TOTAL_SHEEP"].astype(float)
    shares = _ed_shares(ed, published_2020)

    county_published = ed.groupby("County")["TOTAL_SHEEP"].sum().astype(float)
    county_region = crosswalk.set_index("County")["Region"]

    identifiers = [c for c in IDENTIFIER_CANDIDATES if c in ed.columns]
    frames, log_rows = [], []
    for year in YEARS:
        frame = ed[identifiers + ["Region", "NUTS2"]].copy()
        frame.insert(0, "YEAR", year)
        totals = np.zeros(len(ed), dtype=np.int64)

        if year == KNOWN_YEAR:
            totals = ed["TOTAL_SHEEP"].to_numpy(dtype=np.int64)
            frame["SHEEP_DATA_STATUS"] = PROVENANCE_KNOWN
        else:
            m = _ewe_index(dafm, year)
            weight = (year - 2010) / 10.0 if year < KNOWN_YEAR else 1.0
            ed_share = (1.0 - weight) * shares["SHARE_2010"] + weight * shares["SHARE_2020"]
            for region_name in sorted(county_region.unique()):
                counties = sorted(county_region.index[county_region == region_name])
                published_share = county_published.loc[counties] / county_published.loc[counties].sum()
                moved = published_share * m.loc[counties]
                moved = moved / moved.sum()
                target = int(region.loc[(region["Year"] == year) & (region["Region"] == region_name), "Total sheep__HEAD"].iloc[0])
                county_totals = hamilton_allocate(moved.to_numpy(dtype=float), target)
                for county_name, county_total in zip(counties, county_totals):
                    idx = np.asarray(ed.index[ed["County"] == county_name])
                    totals[idx] = hamilton_allocate(ed_share.loc[idx].to_numpy(dtype=float), int(county_total))
                    log_rows.append(
                        {
                            "RECORD_TYPE": "COUNTY_SPLIT",
                            "YEAR": year,
                            "Region": region_name,
                            "County": county_name,
                            "CSO2020_PUBLISHED_COUNTY_SHARE": float(published_share.loc[county_name]),
                            "DAFM_EWE_INDEX": float(m.loc[county_name]),
                            "COUNTY_SHARE": float(moved.loc[county_name]),
                            "COUNTY_TOTAL": int(county_total),
                        }
                    )
            frame["SHEEP_DATA_STATUS"] = PROVENANCE_PATH if year < KNOWN_YEAR else PROVENANCE_HELD

        frame["TOTAL_SHEEP"] = totals
        classes = np.zeros((len(ed), len(ED_CLASS_COLS)), dtype=np.int64)
        for region_name, idx in ed.groupby("Region").groups.items():
            idx = np.asarray(idx)
            rows = totals[idx]
            cols, rounding = _region_class_targets(region, year, region_name, int(rows.sum()))
            fitted = rows[:, None].astype(float) * (cols / max(cols.sum(), 1))[None, :]
            classes[idx] = _integerise_keep_zeros(fitted, rows, cols)
            log_rows.append(
                {
                    "RECORD_TYPE": "REGION_CLASSES",
                    "YEAR": year,
                    "Region": region_name,
                    "REGION_TOTAL": int(rows.sum()),
                    "AAA09_CLASS_SUM_MINUS_TOTAL_HEAD": rounding,
                    **{f"TARGET_{c}": int(v) for c, v in zip(ED_CLASS_COLS, cols)},
                }
            )
        for j, column in enumerate(ED_CLASS_COLS):
            frame[column] = classes[:, j]
        frame["EWES"] = frame["EWES_2_PLUS"] + frame["EWES_UNDER_2"]
        frame["BREEDING_SHEEP"] = frame["EWES"] + frame["RAMS"]
        frames.append(frame)

    panel = pd.concat(frames, ignore_index=True)
    panel = panel[[c for c in panel.columns if c != "SHEEP_DATA_STATUS"] + ["SHEEP_DATA_STATUS"]]
    _validate(panel, ed, region, config.expected_eds)

    source_rows = []
    for region_name, idx in ed.groupby("Region").groups.items():
        observed = int(ed.loc[idx, "TOTAL_SHEEP"].sum())
        aaa09 = int(
            region.loc[
                (region["Year"] == KNOWN_YEAR) & (region["Region"] == region_name),
                "Total sheep__HEAD",
            ].iloc[0]
        )
        source_rows.append(
            {
                "RECORD_TYPE": "2020_SOURCE_DIFFERENCE",
                "YEAR": KNOWN_YEAR,
                "Region": region_name,
                "ED_PUBLISHED_TOTAL": observed,
                "AAA09_TOTAL": aaa09,
                "DIFFERENCE": observed - aaa09,
                "N_EDS_POSITIVE": int(ed.loc[idx, "TOTAL_SHEEP"].gt(0).sum()),
                "N_EDS_ZERO": int(ed.loc[idx, "TOTAL_SHEEP"].eq(0).sum()),
            }
        )
    log = pd.concat(
        [pd.DataFrame(log_rows), pd.DataFrame(source_rows)],
        ignore_index=True,
        sort=False,
    )
    return panel.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True), log


def _validate(panel: pd.DataFrame, ed: pd.DataFrame, region: pd.DataFrame, expected_eds: int) -> None:
    if len(panel) != expected_eds * len(YEARS):
        raise AssertionError("sheep panel row count is incomplete")
    if panel[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR-CSOED sheep rows")
    if panel["CSOED"].nunique() != expected_eds:
        raise AssertionError("sheep ED coverage changed")
    if set(panel["YEAR"].unique()) != set(YEARS):
        raise AssertionError("sheep years are not exactly 2015-2025")

    columns = ["TOTAL_SHEEP", *OUTPUT_CLASS_COLS]
    if not all(np.issubdtype(panel[c].dtype, np.integer) for c in columns):
        raise AssertionError("sheep counts must be integer-valued")
    if (panel[columns] < 0).any().any():
        raise AssertionError("negative sheep value")
    if not (panel[list(ED_CLASS_COLS)].sum(axis=1) == panel["TOTAL_SHEEP"]).all():
        raise AssertionError("sheep classes do not sum to TOTAL_SHEEP")

    known = panel.loc[panel["YEAR"] == KNOWN_YEAR].set_index("CSOED")["TOTAL_SHEEP"]
    published = ed.set_index("CSOED")["TOTAL_SHEEP"]
    if not known.loc[published.index].equals(published):
        raise AssertionError("2020 published ED sheep were changed")

    for year in YEARS:
        yearly = panel.loc[panel["YEAR"] == year]
        totals = yearly.groupby("Region")["TOTAL_SHEEP"].sum()
        if year != KNOWN_YEAR:
            target = region.loc[
                region["Year"] == year
            ].set_index("Region")["Total sheep__HEAD"]
            if not (totals == target.loc[totals.index]).all():
                raise AssertionError(
                    f"{year}: regional sheep totals do not match AAA09"
                )

        class_sums = yearly.groupby("Region")[list(ED_CLASS_COLS)].sum()
        for region_name in class_sums.index:
            targets, _ = _region_class_targets(
                region,
                year,
                region_name,
                int(totals.loc[region_name]),
            )
            if not np.array_equal(
                class_sums.loc[region_name].to_numpy(dtype=np.int64),
                targets,
            ):
                raise AssertionError(
                    f"{year} {region_name}: regional sheep classes do not close"
                )

    published_zero = ed.loc[ed["TOTAL_SHEEP"].eq(0), "CSOED"]
    later = panel.loc[panel["YEAR"] > KNOWN_YEAR]
    if int(later.loc[later["CSOED"].isin(published_zero), "TOTAL_SHEEP"].sum()) != 0:
        raise AssertionError("a sheep value published as zero in 2020 became positive after 2020")

    zero_both = ed.loc[
        ed["TOTAL_SHEEP"].eq(0) & ed["TOTAL_SHEEP_2010"].eq(0),
        "CSOED",
    ]
    if int(panel.loc[panel["CSOED"].isin(zero_both), "TOTAL_SHEEP"].sum()) != 0:
        raise AssertionError("an ED with zero sheep in both censuses received sheep")
