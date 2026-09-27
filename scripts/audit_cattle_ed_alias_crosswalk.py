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
        "CSOED": gdf[cso_col].astype(str).str.replace(r"\.0$", "", regex=True),
        "County": gdf[county_col].map(norm_county),
        "BOUNDARY_EDNAME": gdf[ed_col].astype(str) if ed_col is not None else "",
        "BOUNDARY_PROPNAME": gdf[prop_col].astype(str),
    })
    # Canonicalise leading zeroes for numeric ED codes while preserving grouped ids.
    def canon(value: str) -> str:
        parts=[]
        for token in str(value).split("/"):
            token=token.strip()
            if not token:
                continue
            try:
                parts.append(str(int(float(token))))
            except ValueError:
                parts.append(token)
        return "/".join(sorted(parts, key=lambda x: int(x) if x.isdigit() else x))

    boundary["CSOED"] = boundary["CSOED"].map(canon)
    ed["CSOED"] = ed["CSOED"].astype(str).map(canon)
    merged = ed[["CSOED","County","ED"]].merge(
        boundary,
        on="CSOED",
        how="left",
        suffixes=("_CSO","_BOUNDARY"),
        validate="one_to_one",
    )
    merged["County"] = merged["County_CSO"].map(norm_county)
    merged["_ED_KEY"] = merged["ED"].map(norm_name)
    merged["_PROP_KEY"] = merged["BOUNDARY_PROPNAME"].map(norm_name)
    merged["_BOUNDARY_ED_KEY"] = merged["BOUNDARY_EDNAME"].map(norm_name)

    aim_keys = set(zip(aim["County"], aim["_AIM_KEY"]))

    direct = []
    alias = []
    for _, row in merged.iterrows():
        county = row["County"]
        if (county, row["_ED_KEY"]) in aim_keys:
            direct.append(row["CSOED"])
            continue
        candidates = []
        for field, key in (
            ("PROPNAME", row["_PROP_KEY"]),
            ("BOUNDARY_EDNAME", row["_BOUNDARY_ED_KEY"]),
        ):
            if key and key != row["_ED_KEY"] and (county, key) in aim_keys:
                candidates.append((field, key))
        if candidates:
            # Deduplicate aliases that normalise to the same name.
            unique = []
            seen = set()
            for field, key in candidates:
                if key not in seen:
                    unique.append((field,key))
                    seen.add(key)
            alias.append({
                "CSOED": row["CSOED"],
                "County": county,
                "CSO_ED": row["ED"],
                "BOUNDARY_EDNAME": row["BOUNDARY_EDNAME"],
                "BOUNDARY_PROPNAME": row["BOUNDARY_PROPNAME"],
                "MATCH_FIELDS": "+".join(x[0] for x in unique),
                "MATCH_KEYS": "+".join(x[1] for x in unique),
            })

    print("DIRECT_MATCH_EDS", len(direct))
    print("ALIAS_MATCH_EDS", len(alias))
    print("TOTAL_WITH_ALIAS", len(direct)+len(alias))
    print("ALIAS_ROWS_BEGIN")
    if alias:
        print(pd.DataFrame(alias).to_csv(index=False).strip())
    print("ALIAS_ROWS_END")


if __name__ == "__main__":
    main()
