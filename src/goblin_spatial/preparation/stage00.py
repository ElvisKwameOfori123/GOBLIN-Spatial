"""Stage 00 orchestration: raw CSO census tables -> prepared model inputs.

Reads the raw AVA42 ED livestock table and the exact Census of Agriculture
county totals, reconciles the 2010 and 2020 census years with
``census_suppression``, and writes

* the prepared 2020 ED baseline (model universe, 2,857 EDs) and
* the prepared 2010 ED census (all 3,409 EDs),

changing only the livestock columns. All non-livestock fields are preserved
exactly, and the row order, encoding, quoting and line endings of the existing
files (which act as templates) round-trip unchanged. The audit tables of the
reconciliation are written next to them. AAA10 and AAA09 are read only to
check the census county totals against them.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import census_suppression as cs

LIVESTOCK_COLUMNS = ("DAIRY_COW", "OTHER_COW", "TOTAL_CATTLE", "OTHER_CATTLE", "TOTAL_SHEEP")
UNIT_COLUMNS = {v: "COUNTY" for v in cs.VARIABLES}
YEARS = (2010, 2020)


@dataclass(frozen=True)
class Stage00Paths:
    ava42: Path
    census_county: Path
    aim: Path
    aaa10: Path
    aaa09: Path
    ed_2020: Path
    ed_2010: Path
    ed_geometry: Path
    wfd_geometry: Path
    audit_dir: Path

    @classmethod
    def default(cls, root: str | Path = ".") -> "Stage00Paths":
        root = Path(root)
        base = root / "data" / "inputs" / "baseline"
        spatial = root / "data" / "inputs" / "spatial"
        return cls(
            ava42=base / "00_CSO_AVA42_Livestock_ED_2000_2010_2020.csv",
            census_county=base / "00_CSO_Census_County_Livestock_2010_2020.csv",
            aim=base / "02_DAFM_AIM_ED_Cattle_Profile_2020.csv",
            aaa10=base / "01_CSO_AAA10_Cattle_County_2015_2025.csv",
            aaa09=base / "03_CSO_AAA09_Sheep_County_Region_2015_2025.xlsx",
            ed_2020=base / "01_CSO_ED_Agricultural_Baseline_2020.csv",
            ed_2010=base / "CSO_ED2010.csv",
            ed_geometry=spatial / "ED_Boundaries_Frozen.gpkg",
            wfd_geometry=spatial / "WFD_Catchments_Frozen.gpkg",
            audit_dir=base / "census_reconciliation",
        )


# ------------------------------------------------------------------ format-preserving CSV


@dataclass
class CsvTemplate:
    bom: bool
    newline: str
    header: list[str]
    rows: list[list[str]]

    @classmethod
    def read(cls, path: Path) -> "CsvTemplate":
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        newline = "\r\n" if "\r\n" in text else "\n"
        records = list(csv.reader(io.StringIO(text, newline="")))
        template = cls(bom, newline, records[0], records[1:])
        if template.render() != raw:
            raise AssertionError(f"{path} does not round-trip through the CSV writer; refusing to edit it")
        return template

    def render(self) -> bytes:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator=self.newline, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(self.header)
        writer.writerows(self.rows)
        return (("﻿" if self.bom else "") + buffer.getvalue()).encode("utf-8")

    def with_livestock(self, keys: list[str], values: pd.DataFrame) -> "CsvTemplate":
        """Copy of the template with livestock fields replaced row by row."""

        position = {c: self.header.index(c) for c in LIVESTOCK_COLUMNS}
        rows = []
        for key, row in zip(keys, self.rows):
            new = list(row)
            for column, i in position.items():
                new[i] = str(int(values.at[key, column]))
            rows.append(new)
        return CsvTemplate(self.bom, self.newline, list(self.header), rows)


def _keys(template: CsvTemplate) -> list[str]:
    i = template.header.index("CSOED")
    keys = [cs.canonical_key(r[i]) for r in template.rows]
    if len(set(keys)) != len(keys):
        raise AssertionError("duplicate canonical ED key in template")
    return keys


def _model_values(values: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=values.index)
    for v, column in cs.MODEL_COLUMNS.items():
        out[column] = values[v]
    out[cs.RESIDUAL_COLUMN] = values[cs.RESIDUAL_COLUMN]
    return out


# ------------------------------------------------------------------ spatial summaries


def ed_wfd_weights(paths: Stage00Paths, csoed: list[str]) -> pd.DataFrame:
    """Area weights of every census ED over the 46 frozen WFD catchments.

    ``csoed`` are the ED codes as written in the census file (the geometry
    layer is matched on the model's own CSOED canonicalisation).
    """

    import geopandas as gpd

    from ..aggregation.catchments import EXPECTED_WFD_CATCHMENTS, build_ed_catchment_crosswalk

    expected = (paths.wfd_geometry.with_name(paths.wfd_geometry.name + ".sha256")).read_text().split()[0]
    actual = hashlib.sha256(paths.wfd_geometry.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("frozen WFD catchment geometry checksum mismatch")
    eds = gpd.read_file(paths.ed_geometry)
    catchments = gpd.read_file(paths.wfd_geometry)
    crosswalk = build_ed_catchment_crosswalk(
        pd.DataFrame({"CSOED": csoed}),
        eds,
        catchments,
        expected_wfd_catchments=EXPECTED_WFD_CATCHMENTS,
    )
    return pd.DataFrame(
        {
            "KEY": crosswalk["CSOED"].map(cs.canonical_key),
            "UNIT": crosswalk["WFD_CATCHMENT"],
            "WEIGHT": crosswalk["ED_CATCHMENT_WEIGHT"],
        }
    )


def coverage_outside_model(
    frames: dict[int, cs.CensusFrame],
    results: dict[int, cs.Reconciled],
    weights: pd.DataFrame,
) -> pd.DataFrame:
    """Livestock held in census EDs outside the 2,857-ED model universe."""

    rows = []
    for year, cf in frames.items():
        f = cf.frame
        values = results[year].values
        out = ~f["IN_MODEL"]
        for v in cs.VARIABLES:
            published = f[v].fillna(0).where(out, 0)
            filled = (values[v] - f[v].fillna(0)).where(out, 0)
            total = values[v]
            frame = pd.DataFrame(
                {"COUNTY": f["COUNTY"], "PUB": published, "FILL": filled, "ALL": total}
            )
            levels = {"COUNTY": frame.groupby("COUNTY")[["PUB", "FILL", "ALL"]].sum()}
            w = frame.join(weights.set_index("KEY"), how="inner")
            for c in ("PUB", "FILL", "ALL"):
                w[c] = w[c] * w["WEIGHT"]
            levels["WFD_CATCHMENT"] = w.groupby("UNIT")[["PUB", "FILL", "ALL"]].sum()
            levels["STATE"] = frame[["PUB", "FILL", "ALL"]].sum().to_frame("STATE").T
            for level, table in levels.items():
                for unit, r in table.iterrows():
                    outside = r["PUB"] + r["FILL"]
                    rows.append(
                        {
                            "YEAR": year,
                            "LEVEL": level,
                            "UNIT": unit,
                            "VARIABLE": cs.MODEL_COLUMNS[v],
                            "PUBLISHED_OUTSIDE_MODEL": round(float(r["PUB"]), 1),
                            "FILLED_OUTSIDE_MODEL": round(float(r["FILL"]), 1),
                            "TOTAL_OUTSIDE_MODEL": round(float(outside), 1),
                            "CENSUS_TOTAL": round(float(r["ALL"]), 1),
                            "OUTSIDE_SHARE_PCT": round(100 * outside / r["ALL"], 3) if r["ALL"] else 0.0,
                        }
                    )
    return pd.DataFrame(rows)


def state_closure(frames: dict[int, cs.CensusFrame], results: dict[int, cs.Reconciled]) -> pd.DataFrame:
    rows = []
    for year, cf in frames.items():
        f = cf.frame
        values = results[year].values
        for v in cs.VARIABLES:
            blank = f[v].isna()
            rows.append(
                {
                    "YEAR": year,
                    "VARIABLE": cs.MODEL_COLUMNS[v],
                    "STATE_TOTAL": int(cf.state[v]),
                    "PUBLISHED_SUM": int(f[v].sum()),
                    "BLANK_CELLS": int(blank.sum()),
                    "FILLED_SUM": int(values.loc[blank, v].sum()),
                    "FILLED_IN_MODEL": int(values.loc[blank & f["IN_MODEL"], v].sum()),
                    "FILLED_OUTSIDE_MODEL": int(values.loc[blank & ~f["IN_MODEL"], v].sum()),
                    "RECONCILED_TOTAL": int(values[v].sum()),
                    "MODEL_UNIVERSE_TOTAL": int(values.loc[f["IN_MODEL"], v].sum()),
                    "DIFFERENCE_FROM_STATE": int(values[v].sum() - cf.state[v]),
                }
            )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ county controls


def county_control_checks(
    census: dict[int, pd.DataFrame],
    state: pd.DataFrame,
    county_totals: dict[int, pd.DataFrame],
    paths: Stage00Paths,
) -> pd.DataFrame:
    """Validate the census county totals before they are used as controls.

    Each year: counties sum to the AVA42 State total; every county total is at
    least its published ED sum; the hidden amount is positive exactly where the
    county has blank cells. 2020: the census county totals lie within the 100-head
    rounding of AAA10 (cattle) and AAA09 (sheep regions), an independent check
    of the transcription.
    """

    rows = []
    aaa10 = cs.load_aaa10_2020(paths.aaa10)
    aaa09, county_region = cs.load_aaa09_2020(paths.aaa09)
    for year in YEARS:
        eds = census[year]
        table = county_totals[year]
        for v in cs.VARIABLES:
            if int(table[v].sum()) != int(state.loc[year, v]):
                raise AssertionError(f"{year} {v}: census county totals do not sum to the State total")
            published = eds.groupby("COUNTY")[v].sum()
            blanks = eds.groupby("COUNTY")[v].apply(lambda x: int(x.isna().sum()))
            for county in table.index:
                hidden = int(table.at[county, v] - published.get(county, 0))
                n_blank = int(blanks.get(county, 0))
                if hidden < 0 or (hidden > 0) != (n_blank > 0):
                    raise AssertionError(f"{year} {v} {county}: county total inconsistent with AVA42 blanks")
                row = {
                    "YEAR": year,
                    "VARIABLE": cs.MODEL_COLUMNS[v],
                    "UNIT": county,
                    "CENSUS_TOTAL": int(table.at[county, v]),
                    "PUBLISHED_ED_SUM": int(published.get(county, 0)),
                    "BLANK_CELLS": n_blank,
                    "HIDDEN_TOTAL": hidden,
                    "ANNUAL_CONTROL": None,
                    "CENSUS_MINUS_CONTROL": None,
                }
                if year == 2020 and v in ("T", "D", "S"):
                    row["ANNUAL_CONTROL"] = "AAA10"
                    row["CENSUS_MINUS_CONTROL"] = int(table.at[county, v] - aaa10.at[county, v])
                rows.append(row)
        if year == 2020:
            regional = table["SH"].groupby(county_region.reindex(table.index)).sum()
            for region, value in regional.items():
                rows.append(
                    {
                        "YEAR": year,
                        "VARIABLE": "TOTAL_SHEEP",
                        "UNIT": f"REGION {region}",
                        "CENSUS_TOTAL": int(value),
                        "ANNUAL_CONTROL": "AAA09",
                        "CENSUS_MINUS_CONTROL": int(value - aaa09[region]),
                    }
                )
    checks = pd.DataFrame(rows)
    gaps = pd.to_numeric(checks["CENSUS_MINUS_CONTROL"]).abs()
    if (gaps > 50).any():
        raise AssertionError("census county totals depart from AAA10/AAA09 beyond their rounding")
    return checks


# ------------------------------------------------------------------ main entry


@dataclass
class Stage00Result:
    files: dict[str, bytes]
    shrinkage: pd.Series
    closure: pd.DataFrame


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def prepare(paths: Stage00Paths, variant: str = "joint", repetitions: int = cs.TEST_REPETITIONS) -> Stage00Result:
    """Run Stage 00 and return every output file as bytes (nothing is written)."""

    census, state = cs.load_ava42(paths.ava42)
    aim_local, aim_county = cs.load_aim(paths.aim)
    county_totals = cs.load_census_county(paths.census_county)
    checks = county_control_checks(census, state, county_totals, paths)

    template_2020 = CsvTemplate.read(paths.ed_2020)
    template_2010 = CsvTemplate.read(paths.ed_2010)
    keys_2020 = _keys(template_2020)
    keys_2010 = _keys(template_2010)
    model_keys = set(keys_2020)
    for year in (2000, 2010, 2020):
        if set(census[year].index) != set(keys_2010):
            raise AssertionError(f"AVA42 {year} ED universe differs from the 2010 census file")
    if not model_keys <= set(census[2020].index):
        raise AssertionError("model EDs missing from AVA42")

    frames = {
        2020: cs.build_frame(2020, census, state, aim_local, aim_county, model_keys),
        2010: cs.build_frame(2010, census, state, aim_local, aim_county, model_keys),
    }

    scores, by_source, fallback, results, cells = [], [], [], {}, []
    for year in YEARS:
        cf = frames[year]
        chains = cs.PRIOR_SPECS[variant][year]
        sc, src = cs.hidden_cell_test(cf, UNIT_COLUMNS, chains, repetitions=repetitions)
        fb, _ = cs.hidden_cell_test(
            cf, UNIT_COLUMNS, chains, repetitions=repetitions, fallback_only=True
        )
        scores.append(sc)
        by_source.append(src)
        fallback.append(fb)
    scores = pd.concat(scores + fallback, ignore_index=True)
    by_source = pd.concat(by_source, ignore_index=True)
    shrinkage = cs.select_shrinkage(scores)
    lookup = cs.source_error_lookup(by_source, shrinkage)

    for year in YEARS:
        lam = {v: float(shrinkage.loc[(year, cs.MODEL_COLUMNS[v])]) for v in cs.VARIABLES}
        results[year] = cs.reconcile(frames[year], county_totals[year], variant, shrinkage=lam)
        c = cs.attach_error_flags(results[year].cells, lookup)
        c.insert(c.columns.get_loc("SOURCE") + 1, "SHRINKAGE_LAMBDA", c["VARIABLE"].map(
            {cs.MODEL_COLUMNS[v]: lam[v] for v in cs.VARIABLES}
        ))
        cells.append(c)

    # hard checks -----------------------------------------------------------
    closure = state_closure(frames, results)
    if closure["DIFFERENCE_FROM_STATE"].ne(0).any():
        raise AssertionError("reconciled census does not reproduce the State totals")
    for year in YEARS:
        f, values = frames[year].frame, results[year].values
        for v in cs.VARIABLES:
            pub = f[v].notna()
            if not values.loc[pub, v].eq(f.loc[pub, v]).all():
                raise AssertionError(f"{year} {v}: published cell changed")
        if (values[cs.RESIDUAL_COLUMN] < 0).any():
            raise AssertionError(f"{year}: negative other cattle")

    # prepared model inputs -------------------------------------------------
    model_2020 = _model_values(results[2020].values)
    model_2010 = _model_values(results[2010].values)
    prepared_2020 = template_2020.with_livestock(keys_2020, model_2020)
    prepared_2010 = template_2010.with_livestock(keys_2010, model_2010)
    for before, after in ((template_2020, prepared_2020), (template_2010, prepared_2010)):
        keep = [i for i, c in enumerate(before.header) if c not in LIVESTOCK_COLUMNS]
        for a, b in zip(before.rows, after.rows):
            if [a[i] for i in keep] != [b[i] for i in keep]:
                raise AssertionError("a non-livestock field changed")

    csoed_col = template_2010.header.index("CSOED")
    weights = ed_wfd_weights(paths, [r[csoed_col] for r in template_2010.rows])
    temporal = cs.temporal_holdout(census, model_keys, weights.loc[weights["KEY"].isin(model_keys)])
    coverage = coverage_outside_model(frames, results, weights)
    unit_audit = pd.concat([results[y].units for y in YEARS], ignore_index=True)
    cap = pd.DataFrame(
        {"YEAR": list(YEARS), "COW_CAP_SHARE": [round(results[y].cow_cap_share, 4) for y in YEARS]}
    )
    selection = shrinkage.rename("SHRINKAGE_LAMBDA").reset_index()

    files = {
        str(paths.ed_2020): prepared_2020.render(),
        str(paths.ed_2010): prepared_2010.render(),
        str(paths.audit_dir / "filled_cells.csv"): _csv_bytes(pd.concat(cells, ignore_index=True)),
        str(paths.audit_dir / "state_closure.csv"): _csv_bytes(closure),
        str(paths.audit_dir / "county_closure.csv"): _csv_bytes(unit_audit),
        str(paths.audit_dir / "county_control_checks.csv"): _csv_bytes(checks),
        str(paths.audit_dir / "cow_cap.csv"): _csv_bytes(cap),
        str(paths.audit_dir / "hidden_cell_test.csv"): _csv_bytes(scores),
        str(paths.audit_dir / "hidden_cell_source_error.csv"): _csv_bytes(by_source),
        str(paths.audit_dir / "shrinkage_selection.csv"): _csv_bytes(selection),
        str(paths.audit_dir / "temporal_holdout_2010_2020.csv"): _csv_bytes(temporal),
        str(paths.audit_dir / "coverage_outside_model.csv"): _csv_bytes(coverage),
    }
    return Stage00Result(files, shrinkage, closure)


__all__ = ["LIVESTOCK_COLUMNS", "Stage00Paths", "Stage00Result", "CsvTemplate", "prepare"]
