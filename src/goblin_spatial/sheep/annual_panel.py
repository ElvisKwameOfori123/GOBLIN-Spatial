"""CSO-controlled annual ED sheep panel, 2015-2025.

Same rule as the cattle panel: where the ED truth is known it is kept; where
it is not known, ED values are reconstructed and every binding CSO control
closes exactly. For sheep the binding annual control is the AAA09 detailed
region (seven regions), not the county.

Known truth
    2020  CSO Census of Agriculture ED TOTAL_SHEEP, returned unchanged,
          including every published zero. The published ED sum is below AAA09
          2020 (259,807 head nationally); that gap is written to the log and
          never repaired inside the 2020 panel.

Unknown years (2015-2019, 2021-2025)
    1. 2020 region-consistent sheep reference distribution. Guides the
       unknown years only. Each region's AAA09 2020 minus published ED sum is
       spread over EDs published with zero sheep that were positive in 2010,
       or blank in 2010 with cattle in 2020. EDs zero in both censuses are
       excluded. Weights: the 2010 sheep count where positive; where 2010 is
       blank, ED grassland x the region's density in EDs with published sheep
       x a national small-flock factor (2010 sheep per ha in the 2010-positive
       candidates over the density of EDs with published sheep), so both
       weight types sit on the same scale. This is not an estimate of observed
       2020 sheep. The published 2020 LSU is not used here; it stays a
       held-out check.

    2. County split within region. The county's share of its region in the
       2020 reference distribution (published county sheep plus the reference
       sheep of its EDs) is moved by a DAFM breeding-ewe index
           m(c, t) = s_DAFM_ewes(c | r, t) / s_DAFM_ewes(c | r, 2020)
       with DAFM anchors 2015, 2016, 2020, 2022, 2025 (linear in the share
       between anchors), then renormalised inside the region and
       Hamilton-rounded to the AAA09 regional total. DAFM sets direction
       only; CSO sets the level. County and ED use the same 2020 reference,
       so a county's total carries the reference sheep its EDs carry. (With
       published county shares instead, published-sheep EDs in Limerick fall
       to 0.46x from 2020 to 2021 while the Mid-West grows 1.02x; the
       reference county shares are also closer to DAFM 2020 county levels,
       which production never uses.)

    3. ED split within county. Each ED's share of its county moves linearly
       from its 2010 share to its 2020 reference share (lambda = (t-2010)/10)
       for 2015-2019 and holds the 2020 reference share for 2021-2025. A
       blank 2010 value takes the 2020 reference share. A zero in both
       censuses stays zero.

    4. Classes (ewes 2+, ewes <2, rams, other sheep). AAA09 regional class
       totals, Hamilton-scaled to the regional total (AAA09 is published in
       thousands to one decimal and its classes do not always add to the
       published total), are allocated over all EDs of the region in
       proportion to ED TOTAL_SHEEP and integerised without changing any ED
       total. No county class totals are invented. In 2020 the class vector
       is scaled to the published regional ED sum.

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
PROVENANCE_HELD = "AAA09_REGION_CONTROL_ED_2020_REFERENCE_PATTERN"
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
    county["County"] = county["County"].map(_normalise_county)
    ewes = county[["YEAR", "County", "EWES"]].copy()

    breed = pd.read_csv(breed_path, encoding="utf-8-sig")
    breed["County"] = breed["County"].map(_normalise_county)
    breed = breed.loc[breed["CATEGORY"].astype(str).str.upper() == "EWES", ["YEAR", "County", "TOTAL_DAFM"]]
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


# ---------------------------------------------------------- reference 2020


def _reference_2020(ed: pd.DataFrame, region: pd.DataFrame, apply_seed: bool = True) -> tuple[pd.Series, list[dict]]:
    """2020 region-consistent sheep reference distribution (unknown years only)."""

    published = ed["TOTAL_SHEEP"].astype(float)
    reference = published.copy()
    s10 = ed["TOTAL_SHEEP_2010"]
    positive_2010 = s10.gt(0)
    blank_2010 = s10.isna()
    eligible = published.eq(0) & (positive_2010 | (blank_2010 & ed["TOTAL_CATTLE"].gt(0)))

    # One density scale for 2010-blank candidates. The regional density of EDs
    # with published sheep overstates small-flock EDs, so it is scaled by a
    # national small-flock factor: 2010 sheep per ha in the 2010-positive
    # candidates over the density of EDs with published sheep. Both weight
    # types are then on the scale of the EDs that faded from the 2020 census.
    has_all = published.gt(0)
    faded = eligible & positive_2010
    sheep_density_national = float(published[has_all].sum() / ed.loc[has_all, "ALL_GRASSLAND"].sum())
    faded_density_national = float(s10[faded].sum() / ed.loc[faded, "ALL_GRASSLAND"].sum())
    small_flock_factor = faded_density_national / sheep_density_national

    audit = []
    for region_name, idx in ed.groupby("Region").groups.items():
        idx = np.asarray(idx)
        aaa09 = int(region.loc[(region["Year"] == KNOWN_YEAR) & (region["Region"] == region_name), "Total sheep__HEAD"].iloc[0])
        observed = int(ed.loc[idx, "TOTAL_SHEEP"].sum())
        gap = aaa09 - observed
        if gap < 0:
            raise AssertionError(
                f"{region_name}: published 2020 ED sheep exceed AAA09 regional total"
            )

        has = ed.loc[idx, "TOTAL_SHEEP"].gt(0)
        grassland_support = float(
            ed.loc[idx[has.to_numpy()], "ALL_GRASSLAND"].sum()
        )
        if observed > 0 and grassland_support <= 0:
            raise AssertionError(
                f"{region_name}: positive published sheep but no positive grassland support"
            )
        density = (observed / grassland_support if grassland_support > 0 else 0.0) * small_flock_factor

        weight = pd.Series(0.0, index=idx)
        el = eligible.loc[idx]
        weight[el & positive_2010.loc[idx]] = s10.loc[idx][el & positive_2010.loc[idx]]
        blank_el = el & blank_2010.loc[idx]
        weight[blank_el] = ed.loc[idx, "ALL_GRASSLAND"][blank_el] * density

        seed = pd.Series(0.0, index=idx)
        scale = np.nan
        if apply_seed and gap > 0 and weight.sum() > 0:
            scale = gap / float(weight.sum())
            seed = weight * scale
            reference.loc[idx] += seed

        seeded = seed[seed > 0].sort_values(ascending=False)
        cum = seeded.cumsum() / seeded.sum() if len(seeded) else seeded
        county_pub = ed.loc[idx].groupby("County")["TOTAL_SHEEP"].transform("sum")
        audit.append(
            {
                "RECORD_TYPE": "2020_SOURCE_DISCREPANCY",
                "YEAR": KNOWN_YEAR,
                "Region": region_name,
                "SEED_REFERENCE": bool(apply_seed),
                "ED_PUBLISHED_TOTAL": observed,
                "AAA09_TOTAL": aaa09,
                "DIFFERENCE": observed - aaa09,
                "REFERENCE_SEEDED_TOTAL": float(seed.sum()),
                "UNSEEDED_RESIDUAL": float(max(gap, 0) - seed.sum()),
                "N_ZERO_EDS_2020": int(ed.loc[idx, "TOTAL_SHEEP"].eq(0).sum()),
                "N_ELIGIBLE": int(el.sum()),
                "N_ELIGIBLE_2010_POSITIVE": int((el & positive_2010.loc[idx]).sum()),
                "N_ELIGIBLE_2010_BLANK": int(blank_el.sum()),
                "BLANK_CANDIDATE_SHEEP_PER_HA": density,
                "SMALL_FLOCK_FACTOR": small_flock_factor,
                "SEED_SCALE_ON_WEIGHTS": scale,
                "MAX_SEED": float(seed.max()) if len(seed) else 0.0,
                "MAX_SEED_SHARE_OF_GAP": float(seed.max() / gap) if gap > 0 and seed.sum() > 0 else 0.0,
                "MAX_SEED_SHARE_OF_COUNTY_PUBLISHED": float((seed / county_pub.clip(lower=1)).max()),
                "P95_SEED": float(seeded.quantile(0.95)) if len(seeded) else 0.0,
                "P99_SEED": float(seeded.quantile(0.99)) if len(seeded) else 0.0,
                "N_EDS_FOR_50PCT": int((cum < 0.5).sum() + 1) if len(seeded) else 0,
                "N_EDS_FOR_75PCT": int((cum < 0.75).sum() + 1) if len(seeded) else 0,
                "N_EDS_FOR_90PCT": int((cum < 0.9).sum() + 1) if len(seeded) else 0,
            }
        )
    if apply_seed:
        for region_name, idx in ed.groupby("Region").groups.items():
            target = int(
                region.loc[
                    (region["Year"] == KNOWN_YEAR)
                    & (region["Region"] == region_name),
                    "Total sheep__HEAD",
                ].iloc[0]
            )
            if not np.isclose(float(reference.loc[idx].sum()), target, atol=1e-6):
                raise AssertionError(
                    f"{region_name}: 2020 reference distribution does not close to AAA09"
                )

    return reference, audit


# ----------------------------------------------------------------- shares


def _ed_shares(ed: pd.DataFrame, reference: pd.Series) -> pd.DataFrame:
    """Within-county ED shares: 2010 (blank rule) and 2020 reference."""

    s2010 = pd.Series(0.0, index=ed.index)
    s2020 = pd.Series(0.0, index=ed.index)
    for _, idx in ed.groupby("County").groups.items():
        r20 = reference.loc[idx]
        if r20.sum() <= 0:
            raise AssertionError("county with no 2020 sheep reference")
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


def build_annual_sheep_panel(config: SpatialConfig, seed_reference: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (panel, log) for 2015-2025.

    ``seed_reference=False`` is the sensitivity that guides the unknown years
    with the published 2020 ED sheep only.
    """

    crosswalk, region = _load_workbook(config.files["cso_sheep_workbook"])
    ed = _load_ed_2020(config.files["cso_ed_2020"], crosswalk, config.expected_eds)
    ed = _attach_2010(ed, config.files["cso_ed_2010"])
    dafm = _dafm_ewe_shares(
        config.files["dafm_sheep_county_pattern"],
        config.files["sheep_breed_anchors"],
        crosswalk,
    )

    reference, audit = _reference_2020(ed, region, apply_seed=seed_reference)
    shares = _ed_shares(ed, reference)

    # County and ED use the same 2020 reference so each county total carries
    # the reference sheep of its own EDs.
    county_published = ed.groupby("County")["TOTAL_SHEEP"].sum().astype(float)
    county_reference = reference.groupby(ed["County"]).sum()
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
                base = county_reference.loc[counties] / county_reference.loc[counties].sum()
                published_share = county_published.loc[counties] / county_published.loc[counties].sum()
                moved = base * m.loc[counties]
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
                            "SEED_REFERENCE": bool(seed_reference),
                            "CSO2020_PUBLISHED_COUNTY_SHARE": float(published_share.loc[county_name]),
                            "CSO2020_REFERENCE_COUNTY_SHARE": float(base.loc[county_name]),
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
                    "SEED_REFERENCE": bool(seed_reference),
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

    seeded = reference - ed["TOTAL_SHEEP"]
    reference_rows = pd.DataFrame(
        {
            "RECORD_TYPE": "REFERENCE_2020",
            "YEAR": KNOWN_YEAR,
            "Region": ed["Region"],
            "County": ed["County"],
            "CSOED": ed["CSOED"],
            "SEED_REFERENCE": bool(seed_reference),
            "ED_PUBLISHED_TOTAL": ed["TOTAL_SHEEP"],
            "REFERENCE_SEED": seeded,
            "REFERENCE_2020": reference,
        }
    ).loc[seeded > 0]
    log = pd.concat(
        [pd.DataFrame(log_rows), pd.DataFrame(audit), reference_rows], ignore_index=True, sort=False
    )
    return panel.sort_values(["YEAR", "CSOED"], kind="stable").reset_index(drop=True), log


def _validate(panel: pd.DataFrame, ed: pd.DataFrame, region: pd.DataFrame, expected_eds: int) -> None:
    if len(panel) != expected_eds * len(YEARS) or panel[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("sheep panel must hold every ED once per year")
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
        if year == KNOWN_YEAR:
            continue
        sums = panel.loc[panel["YEAR"] == year].groupby("Region")["TOTAL_SHEEP"].sum()
        target = region.loc[region["Year"] == year].set_index("Region")["Total sheep__HEAD"]
        if not (sums == target.loc[sums.index]).all():
            raise AssertionError(f"{year}: regional sheep totals do not match AAA09")

    zero_both = ed.loc[ed["TOTAL_SHEEP"].eq(0) & ed["TOTAL_SHEEP_2010"].eq(0), "CSOED"]
    if int(panel.loc[panel["CSOED"].isin(zero_both), "TOTAL_SHEEP"].sum()) != 0:
        raise AssertionError("an ED with zero sheep in both censuses received sheep")
