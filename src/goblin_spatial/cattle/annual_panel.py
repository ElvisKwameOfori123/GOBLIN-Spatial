"""CSO-only annual ED cattle panel, 2015-2025.

One rule: where the ED truth is known it is kept; where it is not known,
ED values are reconstructed and every county closes exactly.

Known truth
    2020  CSO Census of Agriculture ED publication. Every published ED value
          (dairy cows, other cows, other cattle, total cattle) is returned
          unchanged. No reconciliation is applied to 2020.

Unknown years (2015-2019, 2021-2025)
    County controls are the CSO AAA10 June totals for dairy cows, other cows,
    total cattle and other cattle = total - dairy - other cows. ED values are
    reconstructed from the two ED censuses:

    1. ED size. Each ED's share of county total cattle moves linearly from its
       2010 share to its 2020 share (lambda = (year - 2010) / 10) for
       2015-2019 and is held at the 2020 share for 2021-2025. EDs with cattle
       in 2010 but none in 2020 therefore fade to zero by 2020. A blank 2010
       total keeps its 2020 share. ED totals are Hamilton-rounded to the
       AAA10 county total.

    2. ED mix. Each ED's dairy / other-cow / other-cattle proportions move
       linearly from the 2010 mix to the 2020 mix on the same path. Published
       2010 cells are used as published; where some are blank but the 2010
       total is published, the remaining block is split over the blank cells
       in the ED's 2020 proportions (county proportions if the ED has none).

    3. 2020 reference mix for the unknown years. The published 2020 ED sums
       fall short of AAA10 2020 for dairy and other cows (the animals sit in
       other cattle). To stop later years placing a county's whole cow
       shortfall on the few EDs published with cows, each cow class's 2020
       county shortfall is seeded, for the reference mix only, into the
       other cattle of eligible EDs published with zero of that class:
       cattle present, cows of some class present, and not a published 2010
       zero for that class; in proportion to the ED's other cattle. The
       published 2020 values themselves are never changed.

    4. Joint county calibration. For each county and year, the ED x
       (dairy, other cows, other cattle) table starts from ED total x ED mix
       and is fitted by IPF so every ED keeps its total and every county
       column equals AAA10. The result is integerised (largest remainder plus
       augmenting paths) without changing any margin and without filling a
       zero cell. A component that is zero in both censuses stays zero.

Only CSO data are used: the 2010 ED census (AVA42), the 2020 ED census and
AAA10 county cattle 2015-2025.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.cattle.panel import (
    _load_aaa10,
    _load_cso_ed_2010,
    _normalise_county,
)
from goblin_spatial.config import SpatialConfig
from goblin_spatial.reconciliation import hamilton_allocate, ipf_reconcile

YEARS = tuple(range(2015, 2026))
KNOWN_YEAR = 2020
COMPONENTS = ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE")
COLUMNS = (*COMPONENTS, "TOTAL_CATTLE")
PROVENANCE_KNOWN = "CSO_ED_2020_PUBLISHED_UNCHANGED"
PROVENANCE_PATH = "AAA10_COUNTY_CONTROL_ED_2010_2020_PATH"
PROVENANCE_HELD = "AAA10_COUNTY_CONTROL_ED_2020_PATTERN"
SUPPORT_EPSILON = 1.0e-6


def _load_ed_2020(path) -> pd.DataFrame:
    ed = pd.read_csv(path)
    required = ["CSOED", "County", "ED", *COLUMNS]
    missing = [column for column in required if column not in ed.columns]
    if missing:
        raise ValueError(f"2020 ED cattle data missing columns: {missing}")
    ed["CSOED"] = ed["CSOED"].astype(str)
    ed["County"] = ed["County"].map(_normalise_county)
    for column in COLUMNS:
        values = pd.to_numeric(ed[column], errors="raise")
        if values.isna().any() or (values < 0).any():
            raise ValueError(f"2020 ED cattle data invalid in {column}")
        ed[column] = values.astype(np.int64)
    if ed["CSOED"].duplicated().any():
        raise AssertionError("duplicate CSOED in 2020 ED cattle data")
    identity = ed["DAIRY_COW"] + ed["OTHER_COW"] + ed["OTHER_CATTLE"] - ed["TOTAL_CATTLE"]
    if int(identity.abs().max()) != 0:
        raise AssertionError("published 2020 ED identity D + S + O = T does not close")
    ed["_ED_KEY"] = ed["CSOED"].map(canonical_ed_key)
    if ed["_ED_KEY"].duplicated().any():
        raise AssertionError("duplicate canonical ED key in 2020 ED cattle data")
    return ed.sort_values(["County", "CSOED"], kind="stable").reset_index(drop=True)


def _county_controls(county: pd.DataFrame, year: int) -> pd.DataFrame:
    frame = county.loc[county["Year"] == year].copy()
    if frame.empty:
        raise AssertionError(f"{year}: no AAA10 county controls")
    if frame["County"].duplicated().any():
        duplicates = sorted(frame.loc[frame["County"].duplicated(False), "County"].unique())
        raise AssertionError(f"{year}: duplicate AAA10 county controls: {duplicates}")
    frame = frame.set_index("County")
    controls = pd.DataFrame(
        {
            "DAIRY_COW": frame["Dairy cows__HEAD"].astype(np.int64),
            "OTHER_COW": frame["Other cows__HEAD"].astype(np.int64),
            "TOTAL_CATTLE": frame["Total cattle__HEAD"].astype(np.int64),
        }
    )
    controls["OTHER_CATTLE"] = (
        controls["TOTAL_CATTLE"] - controls["DAIRY_COW"] - controls["OTHER_COW"]
    )
    if (controls < 0).any().any():
        raise AssertionError(f"{year}: negative AAA10 county control")
    return controls


def _attach_2010(ed: pd.DataFrame, ed_2010: pd.DataFrame) -> pd.DataFrame:
    if ed_2010["_ED_KEY"].duplicated().any():
        raise AssertionError("duplicate canonical ED key in 2010 ED cattle data")
    source = ed_2010.set_index("_ED_KEY")
    missing = sorted(set(ed["_ED_KEY"]) - set(source.index))
    if missing:
        raise AssertionError(f"2010 ED data missing {len(missing)} EDs of the 2020 frame")
    out = ed.copy()
    for column in COLUMNS:
        out[f"{column}_2010"] = out["_ED_KEY"].map(source[column]).astype(float)
    return out


def _check_2010_consistency(ed: pd.DataFrame) -> None:
    """Fail on internally inconsistent published 2010 ED cattle rows."""

    d, s, o, t = (ed[f"{c}_2010"] for c in COLUMNS)
    full = d.notna() & s.notna() & o.notna() & t.notna()
    if ((d + s + o - t).abs()[full] > 0).any():
        raise AssertionError("published 2010 ED rows with D + S + O != T")
    parts = d.fillna(0) + s.fillna(0) + o.fillna(0)
    if (t.eq(0) & parts.gt(0)).any():
        raise AssertionError("published 2010 ED has positive cattle components with zero total")
    if (t.notna() & (parts > t)).any():
        raise AssertionError("published 2010 ED components exceed the 2010 total")


def _size_shares(ed: pd.DataFrame) -> pd.DataFrame:
    """Within-county shares of total cattle in 2010 and 2020 (blank rule)."""

    s2010 = pd.Series(0.0, index=ed.index)
    s2020 = pd.Series(0.0, index=ed.index)
    for _, idx in ed.groupby("County").groups.items():
        t20 = ed.loc[idx, "TOTAL_CATTLE"].astype(float)
        if t20.sum() <= 0:
            raise AssertionError("county with no published 2020 cattle")
        c20 = t20 / t20.sum()
        s2020.loc[idx] = c20

        t10 = ed.loc[idx, "TOTAL_CATTLE_2010"]
        blank = t10.isna()
        published = t10.loc[~blank]
        if published.sum() <= 0:
            s2010.loc[idx] = c20
            continue
        s2010.loc[t10.index[blank]] = c20.loc[t10.index[blank]]
        remaining = max(0.0, 1.0 - float(c20.loc[t10.index[blank]].sum()))
        s2010.loc[published.index] = published / published.sum() * remaining

    shares = pd.DataFrame({"SIZE_2010": s2010, "SIZE_2020": s2020})
    if (shares < -1e-12).any().any():
        raise AssertionError("negative ED total-cattle share")
    for column in shares.columns:
        closure = shares.assign(County=ed["County"]).groupby("County")[column].sum()
        if float((closure - 1.0).abs().max()) > 1e-9:
            raise AssertionError(f"{column}: within-county ED shares do not sum to one")
    return shares


def _reference_mix_2020(
    ed: pd.DataFrame, controls_2020: pd.DataFrame, apply_seed: bool = True
) -> pd.DataFrame:
    """2020 mix used only to guide unknown years (published values untouched)."""

    counts = ed[list(COMPONENTS)].astype(float).copy()
    seeded = pd.Series(0.0, index=ed.index)
    seeded_by_component = pd.DataFrame(
        0.0, index=ed.index, columns=("DAIRY_COW", "OTHER_COW")
    )
    for county_name, idx in ed.groupby("County").groups.items():
        for component in ("DAIRY_COW", "OTHER_COW"):
            shortfall = float(controls_2020.loc[county_name, component]) - float(
                ed.loc[idx, component].sum()
            )
            if shortfall <= 0 or not apply_seed:
                continue
            published = ed.loc[idx, component]
            cows_present = (ed.loc[idx, "DAIRY_COW"] + ed.loc[idx, "OTHER_COW"]) > 0
            zero_2010 = ed.loc[idx, f"{component}_2010"].eq(0.0)
            eligible = (
                published.eq(0)
                & ed.loc[idx, "TOTAL_CATTLE"].gt(0)
                & cows_present
                & ~zero_2010
            )
            room = (counts.loc[idx, "OTHER_CATTLE"]).where(eligible, 0.0).clip(lower=0.0)
            if room.sum() <= 0:
                continue
            seed = np.minimum(room, shortfall * room / room.sum())
            counts.loc[idx, component] += seed
            counts.loc[idx, "OTHER_CATTLE"] -= seed
            seeded.loc[idx] += seed
            seeded_by_component.loc[idx, component] += seed

    total = counts.sum(axis=1)
    mix = counts.div(total.where(total > 0), axis=0)
    mix["SEEDED_HEAD_2020_REFERENCE"] = seeded
    mix["SEEDED_DAIRY_COW_2020_REFERENCE"] = seeded_by_component["DAIRY_COW"]
    mix["SEEDED_OTHER_COW_2020_REFERENCE"] = seeded_by_component["OTHER_COW"]
    return mix


def _mix_2010(ed: pd.DataFrame, mix_2020: pd.DataFrame) -> pd.DataFrame:
    """2010 mix from published 2010 cells.

    Published 2010 components are used as published (zeros stay zero). If some
    components are blank but the 2010 total is published, the remaining block
    (total minus published components) is split over the blank components in
    the ED's own 2020 reference proportions, or the county's if the ED has none.
    If the 2010 total is blank, the ED's 2020 reference mix is used.
    """

    comp = list(COMPONENTS)
    values = ed[[f"{c}_2010" for c in comp]].to_numpy(dtype=float)
    total = ed["TOTAL_CATTLE_2010"].to_numpy(dtype=float)
    ref = mix_2020[comp].to_numpy(dtype=float)

    county_ref = {}
    for county_name, idx in ed.groupby("County").groups.items():
        block = np.nan_to_num(ref[np.asarray(idx)]) * ed.loc[idx, "TOTAL_CATTLE"].to_numpy(dtype=float)[:, None]
        county_ref[county_name] = block.sum(axis=0) / max(block.sum(), 1.0)

    out = np.full(values.shape, np.nan)
    for i in range(len(ed)):
        t = total[i]
        if np.isnan(t) or t <= 0:
            out[i] = ref[i]
            continue
        blank = np.isnan(values[i])
        row = np.where(blank, 0.0, values[i])
        if blank.any():
            remaining = max(0.0, t - row.sum())
            weights = ref[i] if np.isfinite(ref[i]).all() and ref[i][blank].sum() > 0 else county_ref[ed.at[i, "County"]]
            w = np.where(blank, weights, 0.0)
            if w.sum() <= 0:
                w = blank.astype(float)
            row = row + remaining * w / w.sum()
        out[i] = row / max(row.sum(), 1e-12)
    return pd.DataFrame(out, index=ed.index, columns=comp).clip(lower=0.0)


def _blend(a: pd.DataFrame, b: pd.DataFrame, weight_b: float) -> pd.DataFrame:
    left = a[list(COMPONENTS)].fillna(b[list(COMPONENTS)])
    right = b[list(COMPONENTS)].fillna(a[list(COMPONENTS)])
    out = (1.0 - weight_b) * left + weight_b * right
    total = out.sum(axis=1)
    return out.div(total.where(total > 0), axis=0).fillna(0.0)


def _integerise_keep_zeros(fitted: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """Exact integerisation of an IPF result that never fills a zero cell.

    Largest-remainder rounding restricted to cells with positive fitted value,
    so a structural zero in the prior stays zero after rounding.
    """

    rows = np.asarray(rows, dtype=np.int64)
    cols = np.asarray(cols, dtype=np.int64)
    support = fitted > 0
    allocation = np.floor(fitted + 1e-9).astype(np.int64)
    row_need = rows - allocation.sum(axis=1)
    col_need = cols - allocation.sum(axis=0)
    if (row_need < 0).any() or (col_need < 0).any():
        raise AssertionError("negative residual during integerisation")
    fraction = fitted - allocation
    upper = np.where(support, np.ceil(fitted - 1e-9), 0).astype(np.int64)

    # 1. largest remainders first
    while int(row_need.sum()) > 0:
        eligible = (allocation < upper) & (row_need > 0)[:, None] & (col_need > 0)[None, :]
        if not eligible.any():
            break
        score = np.where(eligible, fraction, -np.inf)
        i, j = np.unravel_index(int(np.argmax(score)), score.shape)
        allocation[i, j] += 1
        fraction[i, j] -= 1.0
        row_need[i] -= 1
        col_need[j] -= 1

    # 2. augmenting paths for any remainder (row -> add -> col -> remove -> row ...)
    lower = np.floor(fitted + 1e-9).astype(np.int64)
    n_rows, n_cols = fitted.shape
    while int(row_need.sum()) > 0:
        start = int(np.where(row_need > 0)[0][0])
        parent_col, parent_row = {}, {start: None}
        queue, end = [start], None
        while queue and end is None:
            r = queue.pop(0)
            for c in range(n_cols):
                if c in parent_col or allocation[r, c] >= upper[r, c]:
                    continue
                parent_col[c] = r
                if col_need[c] > 0:
                    end = c
                    break
                for k in range(n_rows):
                    if k not in parent_row and allocation[k, c] > lower[k, c]:
                        parent_row[k] = c
                        queue.append(k)
        if end is None:
            raise RuntimeError("integerisation has no supported residual path")
        c = end
        while True:
            r = parent_col[c]
            allocation[r, c] += 1
            back = parent_row[r]
            if back is None:
                break
            allocation[r, back] -= 1
            c = back
        row_need[start] -= 1
        col_need[end] -= 1
    if not (np.array_equal(allocation.sum(axis=1), rows) and np.array_equal(allocation.sum(axis=0), cols)):
        raise AssertionError("integerisation margins failed")
    if (allocation[~support] != 0).any():
        raise AssertionError("integerisation filled a structural zero")
    return allocation


def _calibrate_county(
    row_totals: np.ndarray,
    mix: np.ndarray,
    col_targets: np.ndarray,
    possible: np.ndarray,
    label: str = "county calibration",
) -> tuple[np.ndarray, int]:
    """IPF + exact integerisation; returns allocation and fallback level used."""

    prior = row_totals[:, None].astype(float) * mix
    # Level 0: the prior as built. Level 1: tiny support added only to cells
    # allowed by the census evidence. No level ever opens a structural zero.
    attempts = (
        prior,
        prior + SUPPORT_EPSILON * row_totals[:, None] * possible,
    )
    for level, candidate in enumerate(attempts):
        try:
            fitted = ipf_reconcile(candidate, row_totals, col_targets)
        except (ValueError, RuntimeError):
            continue
        return _integerise_keep_zeros(fitted, row_totals, col_targets), level
    raise RuntimeError(
        f"{label}: calibration infeasible without relaxing a structural zero"
    )


def build_annual_ed_panel(
    config: SpatialConfig, seed_reference_mix: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (panel, calibration_log) for 2015-2025.

    ``seed_reference_mix=False`` is the sensitivity that guides the unknown
    years with the published 2020 composition only (no cow-shortfall seeding).
    """

    county = _load_aaa10(config.files["cso_cattle_county"])
    ed = _load_ed_2020(config.files["cso_ed_2020"])
    ed = _attach_2010(ed, _load_cso_ed_2010(config.files["cso_ed_2010"]))

    sizes = _size_shares(ed)
    _check_2010_consistency(ed)
    controls_2020 = _county_controls(county, KNOWN_YEAR)
    mix20 = _reference_mix_2020(ed, controls_2020, apply_seed=seed_reference_mix)
    mix10 = _mix_2010(ed, mix20)

    # a component zero in both censuses (published zero, not seeded) stays zero
    possible = pd.DataFrame(index=ed.index)
    for component in COMPONENTS:
        was_2010 = ed[f"{component}_2010"].isna() | ed[f"{component}_2010"].gt(0)
        possible[component] = (mix20[component].fillna(0) > 0) | (was_2010 & mix10[component].gt(0))
    possible = possible.to_numpy(dtype=float)

    frames = []
    log_rows = []
    for year in YEARS:
        frame = ed[["CSOED", "County", "ED"]].copy()
        frame.insert(0, "YEAR", year)

        if year == KNOWN_YEAR:
            for column in COLUMNS:
                frame[column] = ed[column].to_numpy(dtype=np.int64)
            frame["PROVENANCE"] = PROVENANCE_KNOWN
            frames.append(frame)
            continue

        weight = (year - 2010) / 10.0 if year < KNOWN_YEAR else 1.0
        size = (1.0 - weight) * sizes["SIZE_2010"] + weight * sizes["SIZE_2020"]
        mix = _blend(mix10, mix20, weight) if year < KNOWN_YEAR else mix20[list(COMPONENTS)].fillna(0.0)
        controls = _county_controls(county, year)

        values = np.zeros((len(ed), len(COMPONENTS)), dtype=np.int64)
        for county_name, idx in ed.groupby("County").groups.items():
            idx = np.asarray(idx)
            target = controls.loc[county_name]
            rows = hamilton_allocate(size.loc[idx].to_numpy(dtype=float), int(target["TOTAL_CATTLE"]))
            cols = np.array([int(target[c]) for c in COMPONENTS], dtype=np.int64)
            m = mix.loc[idx, list(COMPONENTS)].to_numpy(dtype=float, copy=True)
            empty = (m.sum(axis=1) <= 0) & (rows > 0)
            if empty.any():
                # ED with cattle on the path but no usable mix in either census:
                # county mix, restricted to components not published zero.
                county_mix = cols / max(1, cols.sum())
                allowed = possible[idx][empty] * county_mix[None, :]
                none = allowed.sum(axis=1) <= 0
                if none.any():
                    bad = idx[empty][none]
                    bad_eds = ed.loc[bad, "CSOED"].astype(str).tolist()
                    raise RuntimeError(
                        f"{county_name} {year}: cattle-bearing EDs have no "
                        f"census-supported composition: {bad_eds}"
                    )
                m[empty] = allowed / allowed.sum(axis=1, keepdims=True)
            allocation, level = _calibrate_county(
                rows, m, cols, possible[idx], label=f"{county_name} {year}"
            )
            values[idx] = allocation
            log_rows.append(
                {
                    "RECORD_TYPE": "CALIBRATION",
                    "YEAR": year,
                    "County": county_name,
                    "SUPPORT_FALLBACK_LEVEL": level,
                    "SEED_REFERENCE_MIX": bool(seed_reference_mix),
                }
            )

        for j, component in enumerate(COMPONENTS):
            frame[component] = values[:, j]
        frame["TOTAL_CATTLE"] = values.sum(axis=1)
        frame["PROVENANCE"] = PROVENANCE_PATH if year < KNOWN_YEAR else PROVENANCE_HELD
        frames.append(frame)

    panel = pd.concat(frames, ignore_index=True)
    _validate(panel, ed, county, expected_eds=config.expected_eds)

    audit_rows = []
    for county_name, idx in ed.groupby("County").groups.items():
        observed = ed.loc[idx, list(COLUMNS)].sum()
        target = controls_2020.loc[county_name, list(COLUMNS)]
        audit = {
            "RECORD_TYPE": "2020_SOURCE_DISCREPANCY",
            "YEAR": KNOWN_YEAR,
            "County": county_name,
            "SUPPORT_FALLBACK_LEVEL": np.nan,
            "SEED_REFERENCE_MIX": bool(seed_reference_mix),
            "REFERENCE_SEEDED_DAIRY_COW": float(
                mix20.loc[idx, "SEEDED_DAIRY_COW_2020_REFERENCE"].sum()
            ),
            "REFERENCE_SEEDED_OTHER_COW": float(
                mix20.loc[idx, "SEEDED_OTHER_COW_2020_REFERENCE"].sum()
            ),
        }
        audit["REFERENCE_SEEDED_TOTAL"] = (
            audit["REFERENCE_SEEDED_DAIRY_COW"]
            + audit["REFERENCE_SEEDED_OTHER_COW"]
        )
        for column in COLUMNS:
            audit[f"ED_{column}"] = int(observed[column])
            audit[f"AAA10_{column}"] = int(target[column])
            audit[f"DIFF_{column}"] = int(observed[column] - target[column])
        audit_rows.append(audit)

    log = pd.concat(
        [pd.DataFrame(log_rows), pd.DataFrame(audit_rows)],
        ignore_index=True,
        sort=False,
    )
    shortfall = 0.0
    for county_name, idx in ed.groupby("County").groups.items():
        for component in ("DAIRY_COW", "OTHER_COW"):
            shortfall += max(
                0.0,
                float(controls_2020.loc[county_name, component])
                - float(ed.loc[idx, component].sum()),
            )
    log.attrs["cow_shortfall_2020"] = shortfall
    log.attrs["seeded_head_2020_reference"] = float(mix20["SEEDED_HEAD_2020_REFERENCE"].sum())
    log.attrs["unseeded_head_2020_reference"] = shortfall - log.attrs["seeded_head_2020_reference"]
    return panel, log


def _validate(
    panel: pd.DataFrame,
    ed: pd.DataFrame,
    county: pd.DataFrame,
    expected_eds: int,
) -> None:
    expected_rows = expected_eds * len(YEARS)
    if len(panel) != expected_rows:
        raise AssertionError(f"expected {expected_rows:,} ED-year rows, found {len(panel):,}")
    if panel[["YEAR", "CSOED"]].duplicated().any():
        raise AssertionError("duplicate YEAR x CSOED rows in annual panel")
    if set(panel["YEAR"].unique()) != set(YEARS):
        raise AssertionError("annual panel years are not exactly 2015-2025")
    coverage = panel.groupby("YEAR")["CSOED"].nunique()
    if not coverage.eq(expected_eds).all():
        raise AssertionError("ED coverage is incomplete in one or more years")
    if panel["CSOED"].nunique() != expected_eds:
        raise AssertionError("annual panel ED universe differs from the expected frame")
    if not all(np.issubdtype(panel[column].dtype, np.integer) for column in COLUMNS):
        raise AssertionError("annual cattle counts must be integer-valued")
    if (panel[list(COLUMNS)] < 0).any().any():
        raise AssertionError("negative cattle value in annual panel")
    identity = panel[list(COMPONENTS)].sum(axis=1) - panel["TOTAL_CATTLE"]
    if int(identity.abs().max()) != 0:
        raise AssertionError("D + S + O = T fails in annual panel")

    known = panel.loc[panel["YEAR"] == KNOWN_YEAR].set_index("CSOED")[list(COLUMNS)]
    published = ed.set_index("CSOED")[list(COLUMNS)]
    if set(known.index) != set(published.index):
        raise AssertionError("2020 ED universe differs from the published census")
    if not known.loc[published.index].equals(published):
        raise AssertionError("2020 published ED values were changed")

    for year in YEARS:
        if year == KNOWN_YEAR:
            continue
        sums = panel.loc[panel["YEAR"] == year].groupby("County")[list(COLUMNS)].sum()
        target = _county_controls(county, year)
        if not sums.equals(target.loc[sums.index, list(COLUMNS)]):
            raise AssertionError(f"{year}: county totals do not match AAA10")
