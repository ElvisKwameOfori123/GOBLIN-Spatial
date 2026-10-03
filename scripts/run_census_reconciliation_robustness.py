"""Robustness of headline results to the Stage 00 census reconciliation.

Builds the full historical release three times from different prepared census
inputs and compares the headline results:

A  v1.1 production inputs: 2020 dairy cows reconciled alone (git e8a1f3e);
   other suppressed 2020 cells and all suppressed 2010 cells left blank/zero
B  Stage 00, joint reconciliation of 2010 and 2020 (committed inputs)
C  Stage 00 with contemporary AIM evidence first in the 2020 prior chains

    python scripts/run_census_reconciliation_robustness.py

Each variant is built in a temporary copy of the working tree, so the
repository's own outputs are untouched. Writes
data/inputs/baseline/census_reconciliation/robustness_variants.csv (one row
per metric and variant, with the A-C range) and
robustness_signature_agreement.csv (rank agreement of ED and WFD signatures
against variant B).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goblin_spatial.preparation.stage00 import Stage00Paths, prepare  # noqa: E402

BASELINE_A = "e8a1f3e"
INPUTS = (
    "data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv",
    "data/inputs/baseline/CSO_ED2010.csv",
)
OUT = ROOT / "data/inputs/baseline/census_reconciliation"
IGNORE = shutil.ignore_patterns(".git", "reporting", "processed", "interim", "__pycache__", "*.egg-info")
SIGNATURES = (
    "DAIRY_SHARE_ADULT_PCT",
    "DXD_SHARE_FOLLOWERS_PCT",
    "DXB_SHARE_FOLLOWERS_PCT",
    "BXB_SHARE_FOLLOWERS_PCT",
    "FOLLOWER_TO_ADULT_RATIO",
    "CATTLE_PER_FARMED_HA",
)


def _variant_inputs(variant: str) -> dict[str, bytes]:
    if variant == "A":
        return {
            path: subprocess.run(
                ["git", "show", f"{BASELINE_A}:{path}"], cwd=ROOT, check=True, capture_output=True
            ).stdout
            for path in INPUTS
        }
    if variant == "B":
        return {path: (ROOT / path).read_bytes() for path in INPUTS}
    result = prepare(Stage00Paths.default(ROOT), variant="aim_first")
    return {path: result.files[str(ROOT / path)] for path in INPUTS}


def _build(variant: str, workdir: Path) -> Path:
    tree = workdir / variant
    shutil.copytree(ROOT, tree, ignore=IGNORE)
    for path, payload in _variant_inputs(variant).items():
        (tree / path).write_bytes(payload)
    env = {**os.environ, "PYTHONPATH": str(tree / "src")}
    subprocess.run(
        [sys.executable, "scripts/build_historical_release.py", "--skip-stage00-check", "--no-audit-stop"],
        cwd=tree,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return tree / "reporting/report_data/historical/historical_results.duckdb"


def _metrics(db: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    con = duckdb.connect(str(db), read_only=True)
    rows = []

    def add(group, metric, value):
        rows.append({"GROUP": group, "METRIC": metric, "VALUE": float(value)})

    audit = con.sql("select * from baseline_coherence_audit").df()
    add("coherence audit", "failed checks", int((~audit["PASS"].astype(bool)).sum()))
    print(f"  {db.parent.parent.parent.parent.name}: failed audit checks: " + "; ".join(audit.loc[~audit["PASS"].astype(bool), "CHECK"]), flush=True)
    disp = con.sql("select * from utility_displacement where QUANTITY = 'FOLLOWERS'").df()
    for _, r in disp.iterrows():
        tag = f"{r['ARM']} {int(r['YEAR'])}"
        add("utility displacement", f"{tag} ED displacement % of national change", r["ED_DISPLACEMENT_PCT_OF_NATIONAL_CHANGE"])
        add("utility displacement", f"{tag} WFD displacement % of national change", r["WFD_DISPLACEMENT_PCT_OF_NATIONAL_CHANGE"])
        add("utility displacement", f"{tag} receiver share of ED displacement %", r["RECEIVER_SHARE_OF_ED_DISPLACEMENT_PCT"])
        add("utility displacement", f"{tag} parentless EDs with followers", r["PARENTLESS_EDS_WITH_FOLLOWERS"])
    conc = con.sql("select * from concentration_2020").df()
    for _, r in conc.iterrows():
        add("concentration 2020", f"top-decile ED share of {r['POPULATION']} %", r["POPULATION_SHARE_PCT"])
    pairs = con.sql("select * from matched_pairs_2020").df()
    add("matched pairs 2020", "number of pairs", len(pairs))
    add("matched pairs 2020", "median dairy-share gap pp", (pairs["DAIRY_SHARE_A_PCT"] - pairs["DAIRY_SHARE_B_PCT"]).abs().median())
    rb = con.sql("select * from information_geography_2020").df()
    for _, r in rb.iterrows():
        add("between-county share R_B 2020", r["METRIC"], r["BETWEEN_COUNTY_SHARE_RB"])
    flows = con.sql("select * from parent_follower_relationship_by_year where YEAR = 2020").df()
    for _, r in flows.iterrows():
        add("parent-follower 2020", f"{r['ORIGIN_GROUP']} local-ED share %", r["LOCAL_ED_PCT"])
    signatures = {
        geo: con.sql(
            f"select GEOGRAPHY_ID, {', '.join(SIGNATURES)} from livestock_signature "
            f"where YEAR = 2020 and GEOGRAPHY_TYPE = '{geo}'"
        ).df().set_index("GEOGRAPHY_ID")
        for geo in ("ED", "WFD_CATCHMENT")
    }
    con.close()
    return pd.DataFrame(rows), signatures


def main() -> int:
    tables, signatures = {}, {}
    with tempfile.TemporaryDirectory(prefix="goblin_robustness_") as tmp:
        for variant in ("A", "B", "C"):
            print(f"building variant {variant}", flush=True)
            tables[variant], signatures[variant] = _metrics(_build(variant, Path(tmp)))

    wide = tables["B"].rename(columns={"VALUE": "B_JOINT"})
    wide.insert(2, "A_DAIRY_ONLY", tables["A"]["VALUE"].to_numpy())
    wide["C_AIM_FIRST"] = tables["C"]["VALUE"].to_numpy()
    span = wide[["A_DAIRY_ONLY", "B_JOINT", "C_AIM_FIRST"]]
    wide["RANGE_MIN"] = span.min(axis=1)
    wide["RANGE_MAX"] = span.max(axis=1)
    wide["MAX_ABS_DIFF_FROM_B"] = span.sub(wide["B_JOINT"], axis=0).abs().max(axis=1)
    wide = wide.round(4)
    wide.to_csv(OUT / "robustness_variants.csv", index=False, lineterminator="\n")

    agreement = []
    for geo in ("ED", "WFD_CATCHMENT"):
        base = signatures["B"][geo]
        for variant in ("A", "C"):
            other = signatures[variant][geo].reindex(base.index)
            for metric in SIGNATURES:
                ok = base[metric].notna() & other[metric].notna()
                diff = (other.loc[ok, metric] - base.loc[ok, metric]).abs()
                agreement.append(
                    {
                        "GEOGRAPHY": geo,
                        "VARIANT_VS_B": variant,
                        "METRIC": metric,
                        "N": int(ok.sum()),
                        "SPEARMAN": round(float(spearmanr(base.loc[ok, metric], other.loc[ok, metric]).statistic), 4),
                        "MEDIAN_ABS_DIFF": round(float(diff.median()), 4),
                        "P95_ABS_DIFF": round(float(np.percentile(diff, 95)), 4),
                        "MAX_ABS_DIFF": round(float(diff.max()), 4),
                    }
                )
    pd.DataFrame(agreement).to_csv(OUT / "robustness_signature_agreement.csv", index=False, lineterminator="\n")
    print(wide.to_string(index=False))
    print(pd.DataFrame(agreement).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
