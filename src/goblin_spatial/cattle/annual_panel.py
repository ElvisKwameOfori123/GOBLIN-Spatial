"""CSO-only annual ED cattle panel, 2015-2025.

One rule: where the ED value is published it is kept; where it is not,
ED values are allocated pro rata and every county control closes exactly.

Published
    2020  CSO Census of Agriculture ED publication. Every published ED value
          (dairy cows, other cows, other cattle, total cattle) is returned
          unchanged, including every published zero.

Not published (2015-2019, 2021-2025)
    County controls are the CSO AAA10 June totals for dairy cows, other cows
    and total cattle; other cattle = total - dairy - other cows. Each of the
    three components is allocated separately:

    ED share of the county component
        2021-2025  the ED's published 2020 share of the county's published
                   2020 component. A component published as zero stays zero.
        2015-2019  (1 - lambda) x 2010 share + lambda x published 2020 share,
                   lambda = (year - 2010) / 10. EDs active in 2010 move to the
                   published 2020 pattern by 2020. A component zero in both
                   censuses stays zero. A blank 2010 total keeps its 2020
                   share; blank 2010 components inside a published 2010 total
                   are split in the ED's published 2020 proportions (county
                   proportions if the ED has none).

    The county component control is shared pro rata to these shares and
    Hamilton-rounded, so each county component closes exactly. Total cattle
    is the sum of the three components.

The published 2020 ED sums differ from AAA10 2020. The difference is written
to the log as a source difference only; no cause is assigned and it is not
placed into any ED.

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
from goblin_spatial.reconciliation import hamilton_allocate

YEARS = tuple(range(2015, 2026))
KNOWN_YEAR = 2020
COMPONENTS = ("DAIRY_COW", "OTHER_COW", "OTHER_CATTLE")
COLUMNS = (*COMPONENTS, "TOTAL_CATTLE")
PROVENANCE_KNOWN = "CSO_ED_2020_PUBLISHED_UNCHANGED"
PROVENANCE_PATH = "AAA10_COUNTY_CONTROL_ED_2010_2020_PATH"
PROVENANCE_HELD = "AAA10_COUNTY_CONTROL_ED_2020_PATTERN"


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


def _mix_2010(ed: pd.DataFrame, mix_2020: pd.DataFrame) -> pd.DataFrame:
    """2010 mix from published 2010 cells.

    Published 2010 components are used as published (zeros stay zero). If some
    components are blank but the 2010 total is published, the remaining block
    (total minus published components) is split over the blank components in
    the ED's own published 2020 proportions, or the county's if the ED has none.
    If the 2010 total is blank, the ED's published 2020 mix is used.
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


def _published_mix_2020(ed: pd.DataFrame) -> pd.DataFrame:
    """Published 2020 ED component proportions (NaN where the ED has no cattle)."""

    counts = ed[list(COMPONENTS)].astype(float)
    total = counts.sum(axis=1)
    return counts.div(total.where(total > 0), axis=0)


def _component_shares(ed: pd.DataFrame, mix10: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Within-county ED shares of each cattle component in 2010 and 2020.

    2020: the published ED component over the published county sum.
    2010: the published 2010 component (blank components completed inside a
    published 2010 total by ``_mix_2010``). An ED whose 2010 total is blank
    keeps its 2020 share; the EDs with a published 2010 total share the rest
    of the county in proportion to their 2010 values. A county with no 2010
    evidence for a component uses its 2020 shares.
    """

    out: dict[str, pd.DataFrame] = {}
    t10 = ed["TOTAL_CATTLE_2010"]
    blank_total = t10.isna()
    c10_all = mix10.fillna(0.0).mul(t10.fillna(0.0), axis=0)
    c10_all.loc[blank_total] = 0.0
    for component in COMPONENTS:
        s2010 = pd.Series(0.0, index=ed.index)
        s2020 = pd.Series(0.0, index=ed.index)
        for county_name, idx in ed.groupby("County").groups.items():
            pub = ed.loc[idx, component].astype(float)
            if pub.sum() <= 0:
                raise AssertionError(
                    f"{county_name}: no published 2020 ED support for {component}"
                )
            c20 = pub / pub.sum()
            s2020.loc[idx] = c20
            blank = blank_total.loc[idx]
            c10 = c10_all.loc[idx, component]
            known = c10.loc[~blank]
            if known.sum() <= 0:
                s2010.loc[idx] = c20
                continue
            s2010.loc[blank.index[blank]] = c20.loc[blank.index[blank]]
            remaining = max(0.0, 1.0 - float(c20.loc[blank.index[blank]].sum()))
            s2010.loc[known.index] = known / known.sum() * remaining
        shares = pd.DataFrame({"SHARE_2010": s2010, "SHARE_2020": s2020})
        if (shares < -1e-12).any().any():
            raise AssertionError(f"{component}: negative ED share")
        for column in shares.columns:
            closure = shares.assign(County=ed["County"]).groupby("County")[column].sum()
            if float((closure - 1.0).abs().max()) > 1e-9:
                raise AssertionError(f"{component} {column}: shares do not sum to one")
        out[component] = shares
    return out


def build_annual_ed_panel(config: SpatialConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (panel, log) for 2015-2025.

    Each cattle component (dairy cows, other cows, other cattle) is allocated
    separately: the county AAA10 control for that component is shared over the
    county's EDs pro rata to the ED's component share and Hamilton-rounded.
    Total cattle is the sum of the three components.
    """

    county = _load_aaa10(config.files["cso_cattle_county"])
    ed = _load_ed_2020(config.files["cso_ed_2020"])
    ed = _attach_2010(ed, _load_cso_ed_2010(config.files["cso_ed_2010"]))
    _check_2010_consistency(ed)

    controls_2020 = _county_controls(county, KNOWN_YEAR)
    mix20 = _published_mix_2020(ed)
    mix10 = _mix_2010(ed, mix20)
    shares = _component_shares(ed, mix10)

    frames = []
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
        controls = _county_controls(county, year)
        for component in COMPONENTS:
            share = (1.0 - weight) * shares[component]["SHARE_2010"] + weight * shares[component]["SHARE_2020"]
            values = np.zeros(len(ed), dtype=np.int64)
            for county_name, idx in ed.groupby("County").groups.items():
                idx = np.asarray(idx)
                values[idx] = hamilton_allocate(
                    share.loc[idx].to_numpy(dtype=float),
                    int(controls.loc[county_name, component]),
                )
            frame[component] = values
        frame["TOTAL_CATTLE"] = frame[list(COMPONENTS)].sum(axis=1).astype(np.int64)
        frame["PROVENANCE"] = PROVENANCE_PATH if year < KNOWN_YEAR else PROVENANCE_HELD
        frames.append(frame)

    panel = pd.concat(frames, ignore_index=True)
    _validate(panel, ed, county, expected_eds=config.expected_eds)

    rows = []
    for county_name, idx in ed.groupby("County").groups.items():
        observed = ed.loc[idx, list(COLUMNS)].sum()
        target = controls_2020.loc[county_name, list(COLUMNS)]
        row = {"RECORD_TYPE": "2020_SOURCE_DIFFERENCE", "YEAR": KNOWN_YEAR, "County": county_name}
        for column in COLUMNS:
            row[f"ED_{column}"] = int(observed[column])
            row[f"AAA10_{column}"] = int(target[column])
            row[f"DIFF_{column}"] = int(observed[column] - target[column])
            row[f"N_EDS_POSITIVE_{column}"] = int((ed.loc[idx, column] > 0).sum())
        rows.append(row)
    log = pd.DataFrame(rows)
    log.attrs["n_eds"] = len(ed)
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

    published_zero = published.eq(0)
    for year in YEARS:
        if year <= KNOWN_YEAR:
            continue
        values = panel.loc[panel["YEAR"] == year].set_index("CSOED")[list(COLUMNS)]
        if (values.loc[published_zero.index][published_zero] > 0).any().any():
            raise AssertionError(f"{year}: a component published as zero in 2020 became positive")
