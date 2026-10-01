#!/usr/bin/env python
"""Rebuild the production 2020 CSO ED baseline with reconciled dairy cows.

Standalone provenance utility only. It is not imported by GOBLIN-Spatial.

Rule
----
* Keep the existing 2,857-row production frame, row order and all non-target
  columns unchanged.
* Preserve TOTAL_CATTLE and OTHER_COW exactly.
* Preserve published positive 2020 dairy values and published numeric zeros.
* Reconstruct only raw 2020 BLANK dairy cells.
* Prior hierarchy for a blank cell:
    1. local 2020 DAFM/AIM dairy-type share;
    2. positive 2010 AVA42 dairy share;
    3. positive 2000 AVA42 share only when 2010 is blank;
    4. county 2020 AIM dairy-type share.
* Close each county exactly to the 2020 CSO AAA10 dairy control.
* Derive OTHER_CATTLE after dairy reconciliation:
      OTHER_CATTLE = TOTAL_CATTLE - OTHER_COW - DAIRY_COW

The output has the same schema and row order as the existing production file,
so after review it can replace data/inputs/baseline/
01_CSO_ED_Agricultural_Baseline_2020.csv without adding runtime logic.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


def canonical_ed_key(value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("ED code must not be blank")
    parts = [int(float(x.strip())) for x in text.split("/") if x.strip()]
    if not parts:
        raise ValueError(f"invalid ED code: {value!r}")
    return "/".join(str(x) for x in sorted(parts))


def normalise_county(value: object) -> str:
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def normalise_ed_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).upper())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(?:RURAL|URBAN)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


def split_ava42_label(label: str) -> tuple[str, str, str]:
    if label == "State":
        return "STATE", "State", "State"
    csoed = label.rsplit(",", 1)[-1].strip()
    ed = label.rsplit(", Co.", 1)[0].strip()
    match = re.search(r",\s*Co\.([^,]+),\s*[^,]+$", label)
    county = match.group(1).strip() if match else ""
    return csoed, ed, county


def load_ava42(path: Path) -> dict[int, pd.DataFrame]:
    src = pd.read_excel(path, sheet_name="Unpivoted", dtype=str)
    required = {"Census Year", "Electoral Division", "Type of Livestock", "VALUE"}
    missing = required - set(src.columns)
    if missing:
        raise ValueError(f"AVA42 missing columns: {sorted(missing)}")

    years: dict[int, pd.DataFrame] = {}
    for year in (2000, 2010, 2020):
        df = src.loc[src["Census Year"].astype(str).str.strip().eq(str(year))].copy()
        parsed = df["Electoral Division"].map(split_ava42_label)
        df["CSOED_RAW"] = parsed.map(lambda x: x[0])
        df["ED_RAW"] = parsed.map(lambda x: x[1])
        df["COUNTY_RAW"] = parsed.map(lambda x: x[2])
        df = df.loc[df["CSOED_RAW"].ne("STATE")]

        wide = (
            df.pivot_table(
                index=["CSOED_RAW", "ED_RAW", "COUNTY_RAW"],
                columns="Type of Livestock",
                values="VALUE",
                aggfunc="first",
                dropna=False,
            )
            .reset_index()
        )
        wide["ED_KEY"] = wide["CSOED_RAW"].map(canonical_ed_key)
        for col in ("Total cattle", "Dairy cows", "Other cows"):
            if col not in wide.columns:
                wide[col] = np.nan
            wide[col] = pd.to_numeric(
                wide[col].replace(r"^\s*$", np.nan, regex=True), errors="coerce"
            )
        wide["DAIRY_STATUS"] = np.where(
            wide["Dairy cows"].isna(),
            "BLANK",
            np.where(wide["Dairy cows"].eq(0), "ZERO", "POSITIVE"),
        )
        if wide["ED_KEY"].duplicated().any():
            raise ValueError(f"AVA42 {year} has duplicate canonical ED keys")
        years[year] = wide.set_index("ED_KEY", drop=False)
    return years


def load_aim(path: Path) -> tuple[pd.DataFrame, pd.Series]:
    aim = pd.read_csv(path)
    required = {
        "COUNTY", "ELECTORAL_DIVISION",
        "AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY",
    }
    missing = required - set(aim.columns)
    if missing:
        raise ValueError(f"AIM missing columns: {sorted(missing)}")

    aim["CountyKey"] = aim["COUNTY"].map(normalise_county)
    aim["EDNameKey"] = aim["ELECTORAL_DIVISION"].map(normalise_ed_name)
    for col in ("AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"):
        aim[col] = pd.to_numeric(aim[col], errors="raise")

    low_herd = aim["ELECTORAL_DIVISION"].astype(str).str.contains(
        r"DED\s*<\s*5\s*HERDS", case=False, regex=True, na=False
    )

    county = aim.groupby("CountyKey")[["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"]].sum()
    county_share = (
        county["AVERAGE_CATTLE_DAIRY"] / county["AVERAGE_NUMBER_CATTLE"]
    ).fillna(0.0)

    local = (
        aim.loc[~low_herd]
        .groupby(["CountyKey", "EDNameKey"], as_index=False)[
            ["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY"]
        ]
        .sum()
    )
    local["AIM_DAIRY_SHARE"] = np.where(
        local["AVERAGE_NUMBER_CATTLE"].gt(0),
        local["AVERAGE_CATTLE_DAIRY"] / local["AVERAGE_NUMBER_CATTLE"],
        0.0,
    )
    return local, county_share


def load_aaa10_2020(path: Path) -> pd.Series:
    aaa = pd.read_csv(path)
    aaa = aaa.loc[pd.to_numeric(aaa["Year"], errors="coerce").eq(2020)].copy()
    aaa = aaa.loc[aaa["UNIT"].eq("000 Head")].copy()
    aaa["CountyKey"] = aaa["Region and County"].map(normalise_county)
    aaa["DAIRY_TARGET"] = np.rint(
        pd.to_numeric(aaa["Dairy cows"], errors="raise") * 1000.0
    ).astype(int)
    if aaa["CountyKey"].duplicated().any():
        raise ValueError("AAA10 2020 contains duplicate county rows")
    return aaa.set_index("CountyKey")["DAIRY_TARGET"]


def hamilton(values: np.ndarray, target: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if target == 0:
        return np.zeros(len(values), dtype=int)
    if values.sum() <= 0:
        raise ValueError("positive target with zero allocation support")
    scaled = values / values.sum() * target
    base = np.floor(scaled).astype(int)
    remainder = int(target - base.sum())
    if remainder:
        order = np.argsort(-(scaled - base), kind="stable")
        base[order[:remainder]] += 1
    return base


def cap_safe_hamilton(support: np.ndarray, capacity: np.ndarray, target: int) -> np.ndarray:
    support = np.asarray(support, dtype=float)
    capacity = np.floor(np.asarray(capacity, dtype=float)).astype(int)
    if target == 0:
        return np.zeros(len(support), dtype=int)
    if capacity.sum() < target:
        raise ValueError(f"insufficient ED capacity: {capacity.sum()} < {target}")

    out = np.zeros(len(support), dtype=int)
    active = capacity > 0
    remaining = int(target)
    while remaining > 0:
        idx = np.flatnonzero(active)
        if len(idx) == 0:
            raise ValueError("no active EDs remain before target closure")
        weights = support[idx]
        if weights.sum() <= 0:
            raise ValueError("remaining candidate EDs have zero prior support")
        proposal = hamilton(weights, remaining)
        avail = capacity[idx] - out[idx]
        accepted = np.minimum(proposal, avail)
        if accepted.sum() == 0:
            raise ValueError("allocation stalled under capacity constraints")
        out[idx] += accepted
        remaining -= int(accepted.sum())
        active[idx] = out[idx] < capacity[idx]
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-2020", required=True, type=Path)
    p.add_argument("--ava42", required=True, type=Path)
    p.add_argument("--aim", required=True, type=Path)
    p.add_argument("--aaa10", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--audit", required=True, type=Path)
    p.add_argument("--expected-rows", type=int, default=2857)
    args = p.parse_args()

    base = pd.read_csv(args.baseline_2020, dtype={"CSOED": str})
    original = base.copy(deep=True)
    if len(base) != args.expected_rows:
        raise ValueError(f"row count {len(base)} != expected {args.expected_rows}")

    required = {"CSOED", "ED", "County", "DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"}
    missing = required - set(base.columns)
    if missing:
        raise ValueError(f"production baseline missing: {sorted(missing)}")

    base["ED_KEY"] = base["CSOED"].map(canonical_ed_key)
    if base["ED_KEY"].duplicated().any():
        raise ValueError("duplicate production ED keys")
    for col in ("TOTAL_CATTLE", "OTHER_COW"):
        base[col] = pd.to_numeric(base[col], errors="raise")

    census = load_ava42(args.ava42)
    c00, c10, c20 = census[2000], census[2010], census[2020]
    if set(base["ED_KEY"]) - set(c20.index):
        raise ValueError("some production ED keys are absent from AVA42 2020")

    base["DAIRY_RAW_2020"] = base["ED_KEY"].map(c20["Dairy cows"])
    base["DAIRY_STATUS_RAW_2020"] = base["ED_KEY"].map(c20["DAIRY_STATUS"])
    base["D2010"] = base["ED_KEY"].map(c10["Dairy cows"])
    base["S2010"] = base["ED_KEY"].map(c10["DAIRY_STATUS"])
    base["T2010"] = base["ED_KEY"].map(c10["Total cattle"])
    base["D2000"] = base["ED_KEY"].map(c00["Dairy cows"])
    base["S2000"] = base["ED_KEY"].map(c00["DAIRY_STATUS"])
    base["T2000"] = base["ED_KEY"].map(c00["Total cattle"])

    local, county_share = load_aim(args.aim)
    local = local.rename(columns={"CountyKey": "_CountyKey", "EDNameKey": "_EDNameKey"})
    base["_CountyKey"] = base["County"].map(normalise_county)
    base["_EDNameKey"] = base["ED"].map(normalise_ed_name)
    base = base.merge(
        local[["_CountyKey", "_EDNameKey", "AIM_DAIRY_SHARE"]],
        on=["_CountyKey", "_EDNameKey"], how="left", validate="many_to_one", sort=False,
    )
    target = load_aaa10_2020(args.aaa10)

    base["DAIRY_COW_RECONCILED"] = base["DAIRY_RAW_2020"]
    base["DAIRY_COW_RECOVERED"] = 0
    base["RECON_METHOD"] = np.where(
        base["DAIRY_STATUS_RAW_2020"].eq("POSITIVE"), "PUBLISHED_POSITIVE",
        np.where(base["DAIRY_STATUS_RAW_2020"].eq("ZERO"), "PUBLISHED_ZERO", ""),
    )
    base["PRIOR_SHARE"] = np.nan
    base["PRIOR_SOURCE"] = ""
    blank = base["DAIRY_STATUS_RAW_2020"].eq("BLANK")
    capacity = base["TOTAL_CATTLE"] - base["OTHER_COW"]
    if (capacity < 0).any():
        raise ValueError("OTHER_COW exceeds TOTAL_CATTLE")

    use = blank & base["AIM_DAIRY_SHARE"].notna()
    base.loc[use, "PRIOR_SHARE"] = base.loc[use, "AIM_DAIRY_SHARE"]
    base.loc[use, "PRIOR_SOURCE"] = "AIM_LOCAL"

    use = blank & base["PRIOR_SHARE"].isna() & base["S2010"].eq("POSITIVE") & base["T2010"].gt(0)
    base.loc[use, "PRIOR_SHARE"] = base.loc[use, "D2010"] / base.loc[use, "T2010"]
    base.loc[use, "PRIOR_SOURCE"] = "HISTORY_2010"

    use = blank & base["PRIOR_SHARE"].isna() & base["S2010"].eq("BLANK") & base["S2000"].eq("POSITIVE") & base["T2000"].gt(0)
    base.loc[use, "PRIOR_SHARE"] = base.loc[use, "D2000"] / base.loc[use, "T2000"]
    base.loc[use, "PRIOR_SOURCE"] = "HISTORY_2000"

    use = blank & base["PRIOR_SHARE"].isna()
    base.loc[use, "PRIOR_SHARE"] = base.loc[use, "_CountyKey"].map(county_share)
    base.loc[use, "PRIOR_SOURCE"] = "AIM_COUNTY_FALLBACK"
    base["PRIOR_SCORE"] = base["PRIOR_SHARE"] * base["TOTAL_CATTLE"]

    audit_rows = []
    for county, idx in base.groupby("_CountyKey", sort=True).groups.items():
        idx = list(idx)
        county_target = int(target.loc[county])
        published = int(round(base.loc[idx, "DAIRY_RAW_2020"].fillna(0).sum()))
        gap = county_target - published
        if gap < 0:
            raise ValueError(f"{county}: published dairy exceeds county target")

        cand = base.index[
            base.index.isin(idx)
            & base["DAIRY_STATUS_RAW_2020"].eq("BLANK")
            & base["PRIOR_SCORE"].gt(0)
            & capacity.gt(0)
        ]
        support = base.loc[cand, "PRIOR_SCORE"].to_numpy(float)
        cap = capacity.loc[cand].to_numpy(float)
        if gap:
            alloc = cap_safe_hamilton(support, cap, gap)
            base.loc[cand, "DAIRY_COW_RECONCILED"] = alloc
            base.loc[cand, "DAIRY_COW_RECOVERED"] = alloc
            base.loc[cand, "RECON_METHOD"] = base.loc[cand, "PRIOR_SOURCE"]

        final = int(round(base.loc[idx, "DAIRY_COW_RECONCILED"].fillna(0).sum()))
        if final != county_target:
            raise AssertionError(f"{county}: dairy closure failed {final} != {county_target}")
        audit_rows.append({
            "County": county,
            "AAA10_DAIRY_TARGET": county_target,
            "PUBLISHED_ED_DAIRY": published,
            "DAIRY_RECOVERED": gap,
            "FINAL_DAIRY": final,
            "CANDIDATE_EDS": len(cand),
            "SUM_PRIOR_SUPPORT": float(support.sum()),
            "ALLOCATION_FACTOR": float(gap / support.sum()) if support.sum() else 0.0,
        })

    remaining = blank & base["DAIRY_COW_RECONCILED"].isna()
    base.loc[remaining, "DAIRY_COW_RECONCILED"] = 0
    base.loc[remaining, "RECON_METHOD"] = "RECONSTRUCTED_ZERO"
    base["DAIRY_COW_RECONCILED"] = np.rint(base["DAIRY_COW_RECONCILED"]).astype(int)
    base["OTHER_CATTLE_RECONCILED"] = base["TOTAL_CATTLE"] - base["OTHER_COW"] - base["DAIRY_COW_RECONCILED"]
    if (base["OTHER_CATTLE_RECONCILED"] < 0).any():
        raise AssertionError("negative OTHER_CATTLE after reconciliation")

    output = original.copy(deep=True)
    output["DAIRY_COW"] = base["DAIRY_COW_RECONCILED"].to_numpy()
    output["OTHER_CATTLE"] = base["OTHER_CATTLE_RECONCILED"].to_numpy()

    if list(output.columns) != list(original.columns) or len(output) != len(original):
        raise AssertionError("production contract changed")
    if not output["CSOED"].astype(str).equals(original["CSOED"].astype(str)):
        raise AssertionError("CSOED order changed")
    for col in original.columns:
        if col not in {"DAIRY_COW", "OTHER_CATTLE"} and not output[col].equals(original[col]):
            raise AssertionError(f"unexpected change to {col}")

    d = pd.to_numeric(output["DAIRY_COW"], errors="raise")
    s = pd.to_numeric(output["OTHER_COW"], errors="raise")
    o = pd.to_numeric(output["OTHER_CATTLE"], errors="raise")
    t = pd.to_numeric(output["TOTAL_CATTLE"], errors="raise")
    if not (d + s + o).equals(t):
        raise AssertionError("ED cattle identity failed")

    county_check = pd.DataFrame({"County": output["County"].map(normalise_county), "Dairy": d}).groupby("County")["Dairy"].sum().astype(int)
    if not county_check.equals(target.reindex(county_check.index).astype(int)):
        raise AssertionError("county dairy closure failed on production frame")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.out, index=False)
    pd.DataFrame(audit_rows).to_csv(args.audit, index=False)
    print(f"Wrote {args.out}")
    print(f"Rows: {len(output):,}")
    print(f"National dairy: {int(d.sum()):,}")
    print("Changed columns: DAIRY_COW, OTHER_CATTLE only")


if __name__ == "__main__":
    main()
