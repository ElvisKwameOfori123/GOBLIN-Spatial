#!/usr/bin/env python
"""One-time audit for a frozen AIM-to-CSO ED alias crosswalk.

The production cattle code must not depend on runtime geometry. This script is
only for deriving a transparent alias table from the repository's frozen ED
boundary file, after which the resulting text crosswalk is committed.
"""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GPKG = ROOT / "data/inputs/spatial/SC2_ED_Boundaries_Frozen.gpkg"
ED = ROOT / "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv"
AIM = ROOT / "data/inputs/baseline/02_DAFM_AIM_ED_Cattle_Profile_2020.csv"


def norm_county(value) -> str:
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def norm_name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(?:RURAL|URBAN)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


def main() -> None:
    gdf = gpd.read_file(GPKG)
    print("BOUNDARY_COLUMNS")
    print("|".join(map(str, gdf.columns)))
    print("BOUNDARY_ROWS", len(gdf))

    ed = pd.read_csv(ED, dtype={"CSOED": str})
    aim = pd.read_csv(AIM)
    aim = aim.loc[
        ~aim["ELECTORAL_DIVISION"].astype(str).str.contains(
            r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
        )
    ].copy()
    aim["County"] = aim["COUNTY"].map(norm_county)
    aim["_AIM_KEY"] = aim["ELECTORAL_DIVISION"].map(norm_name)

    # Identify likely frozen boundary fields without hard-coding case.
    cols = {str(c).upper(): c for c in gdf.columns}
    cso_col = next((cols[k] for k in ("CSOED", "EDID", "GEOGID") if k in cols), None)
    ed_col = next((cols[k] for k in ("EDNAME", "ED_NAME", "NAME") if k in cols), None)
    prop_col = next((cols[k] for k in ("PROPNAME", "PROP_NAME", "ENGLISHNAME", "ENGLISH_NAME") if k in cols), None)
    county_col = next((cols[k] for k in ("COUNTYNAME", "COUNTY", "COUNTY_NAME") if k in cols), None)
    print("SELECTED_FIELDS", cso_col, ed_col, prop_col, county_col)

    if cso_col is None or county_col is None:
        raise AssertionError("boundary file lacks stable ED/county identifiers")
    if prop_col is None:
        raise AssertionError("boundary file lacks the planned PROPNAME/English alias field")

    boundary = pd.DataFrame({
        "CSOED": gdf[cso_col].astype(str).str.replace(r"\\.0$", "", regex=True),
        "County": gdf[county_col].map(norm_county),
        "BOUNDARY_EDNAME": gdf[ed_col].astype(str) if ed_col is not None else "",
        "BOUNDARY_PROPNAME": gdf[prop_col].astype(str),
    })

    def canon(value: str) -> str:
        parts = []
        for token in str(value).split("/"):
            token = token.strip()
            if not token:
                continue
            try:
                parts.append(str(int(float(token))))
            except ValueError:
                parts.append(token)
        return "/".join(
            sorted(parts, key=lambda x: int(x) if x.isdigit() else x)
        )

    boundary["CSOED"] = boundary["CSOED"].map(canon)
    boundary = boundary.set_index("CSOED", drop=False)
    ed["CSOED"] = ed["CSOED"].astype(str).map(canon)

    aim_by_base = {}
    for _, row in aim.iterrows():
        key = (row["County"], row["_AIM_KEY"])
        aim_by_base.setdefault(key, []).append(str(row["ELECTORAL_DIVISION"]))

    direct = []
    alias = []
    unmatched = []

    for _, row in ed.iterrows():
        county = norm_county(row["County"])
        model_names = [
            part.strip() for part in str(row["ED"]).split("/") if part.strip()
        ]
        model_keys = {norm_name(name) for name in model_names if norm_name(name)}

        direct_names = []
        for key in sorted(model_keys):
            direct_names.extend(aim_by_base.get((county, key), []))

        # Gather frozen boundary aliases for every constituent code in a grouped
        # model ED, not only for one-to-one CSOED rows.
        alias_candidates = []
        for constituent in str(row["CSOED"]).split("/"):
            ckey = canon(constituent)
            if ckey not in boundary.index:
                continue
            b = boundary.loc[ckey]
            if isinstance(b, pd.DataFrame):
                boundary_rows = [x for _, x in b.iterrows()]
            else:
                boundary_rows = [b]
            for b_row in boundary_rows:
                for field in ("BOUNDARY_EDNAME", "BOUNDARY_PROPNAME"):
                    value = str(b_row[field]).strip()
                    key = norm_name(value)
                    if value and key and key not in model_keys:
                        alias_candidates.append((field, value, key, ckey))

        alias_names = []
        alias_sources = []
        seen_names = set()
        for field, value, key, constituent in alias_candidates:
            for aim_name in aim_by_base.get((county, key), []):
                if aim_name in direct_names or aim_name in seen_names:
                    continue
                seen_names.add(aim_name)
                alias_names.append(aim_name)
                alias_sources.append(
                    f"{constituent}:{field}:{value}"
                )

        matched_names = list(dict.fromkeys(direct_names + alias_names))
        if direct_names:
            direct.append(row["CSOED"])

        if alias_names:
            alias.append({
                "CSOED": row["CSOED"],
                "County": county,
                "CSO_ED": row["ED"],
                "AIM_NAMES": "|".join(alias_names),
                "BOUNDARY_SOURCES": "|".join(alias_sources),
            })

        if not matched_names:
            unmatched.append({
                "CSOED": row["CSOED"],
                "County": county,
                "CSO_ED": row["ED"],
            })

    matched_ids = set(direct) | {x["CSOED"] for x in alias}
    print("DIRECT_MATCH_EDS", len(set(direct)))
    print("ALIAS_MATCH_EDS", len({x["CSOED"] for x in alias}))
    print("TOTAL_WITH_ALIAS", len(matched_ids))
    print("UNMATCHED_EDS", len(unmatched))
    print("ALIAS_ROWS_BEGIN")
    if alias:
        print(pd.DataFrame(alias).to_csv(index=False).strip())
    print("ALIAS_ROWS_END")
    print("UNMATCHED_ROWS_BEGIN")
    if unmatched:
        print(pd.DataFrame(unmatched).to_csv(index=False).strip())
    print("UNMATCHED_ROWS_END")


if __name__ == "__main__":
    main()
