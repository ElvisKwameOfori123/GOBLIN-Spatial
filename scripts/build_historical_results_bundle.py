#!/usr/bin/env python
"""Build the historical GOBLIN-Spatial release bundle.

The ED x year baseline remains authoritative. This script materialises the
manuscript tables, the two canonical livestock panels (CSO 13 groups, GOBLIN 31
cohorts), every reporting geography and the validation tables as CSV and
Parquet, plus two query copies of the same tables: DuckDB and SQLite. Each copy
carries a `_columns` dictionary (unit and meaning of every column) and a
`_readme` table.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.export.column_dictionary import describe_table, sqlite_safe_names
from goblin_spatial.export.livestock_panels import README as LIVESTOCK_README
from goblin_spatial.synthesis.historical import build_historical_result_tables
from goblin_spatial.synthesis.signatures import (
    build_livestock_signature,
    build_relationship_by_year,
    build_relationship_ed,
    build_relationship_shares,
    build_signature_long,
    build_wfd_signature_spread,
    build_wfd_fractional_vs_majority,
)
from goblin_spatial.validation.coherence import output_paths

# Tables whose every column must be described in the column dictionary.
PUBLIC_TABLES = (
    "livestock_signature",
    "livestock_signature_long",
    "wfd_signature_spread",
    "wfd_fractional_vs_majority",
    "wfd_fractional_vs_majority_summary",
    "parent_follower_relationship_ed",
    "parent_follower_relationship_shares",
    "parent_follower_relationship_by_year",
    "cso13_ed_year",
    "goblin31_ed_year",
    "ed_year",
    "county_year",
    "national_year",
    "wfd_catchment_year",
    "colm_catchment_year",
)

BUNDLE_README = [
    ("What this is", "GOBLIN-Spatial historical baseline for Ireland: livestock, land, farm structure and Standard Output for 2,857 Electoral Divisions (EDs), every year 2015-2025 (31,427 ED-years), with county, WFD catchment, Colm catchment and national tables that sum exactly from the EDs."),
    ("Start here", "cso13_ed_year: CSO groups only (9 cattle, 4 sheep) with land and farm structure. goblin31_ed_year: 21 cattle + 10 sheep GOBLIN cohorts with the CSO groups kept as CSO_ columns. ed_year: everything wide, including Standard Output and derived signature metrics."),
    ("Keys", "YEAR x CSOED identifies every ED-year row. County, WFD_CATCHMENT_ID, COLM_CATCHMENT and YEAR key the aggregate tables."),
    ("Evidence rule", "2020 ED values are the CSO Census of Agriculture values: published cells unchanged, suppressed livestock cells filled before the model runs (Stage 00) so that census county and State totals hold exactly. Reconstructed cattle years close exactly to AAA10 county controls and sheep years to AAA09 regional controls. Land retains the 2020 census level and follows AQA06 regional change indices rather than being rescaled to absolute AQA06 levels. PROVENANCE and SHEEP_DATA_STATUS label every livestock row; data/inputs/baseline/census_reconciliation/filled_cells.csv lists every filled census cell with its prior source and measured hidden-cell error."),
    ("2020 source difference", "Model-universe 2020 ED sums sit slightly below the annual controls: census animals in EDs outside the 2,857-ED model universe are reported, not moved into it (cattle 8,744, dairy cows 1,723, sheep 4,518 head), and AAA10/AAA09 are rounded to 100 head."),
    ("2021-2022 land dip", "Area farmed falls about 3.9% in 2021-2022 and recovers in 2023. This is in the CSO AQA06 June series itself; the model follows the AQA06 regional index exactly."),
    ("Columns", "_columns gives the unit and meaning of every column in every public table."),
    ("Livestock signatures", "livestock_signature holds, for 2020 and 2025, the full 21-cohort cattle state plus adult/follower totals, livestock density, land composition and production-intensity ratios for every ED and WFD catchment (the two primary geographies), and for county, Colm catchment and Ireland. Aggregates sum populations and land first, then derive ratios. livestock_signature_long gives each ratio with its numerator and denominator."),
    ("Catchment structure", "wfd_signature_spread pairs each catchment-level signature with the denominator-weighted P10, P50 and P90 of intersecting ED signatures. Catchment values use the full fractional ED-catchment crosswalk; the ED spread describes within-catchment heterogeneity and does not replace the accounting value."),
    ("Catchment allocation sensitivity", "wfd_fractional_vs_majority compares the production fractional allocation with a whole-ED majority-area assignment for 2020 and 2025. The summary table reports straddling-ED livestock shares and median/maximum catchment differences. Majority assignment is a sensitivity benchmark, not an alternative production result."),
    ("Parent-follower relationships", "parent_follower_relationship_ed: for each ED, follower cohort and signature year, the parent population, follower-per-parent ratio and parent-support class. parent_follower_relationship_shares reports how much follower stock each ED/WFD/county/national unit holds in each class."),
    ("Relationship support classes", "LOCAL_PARENT means corresponding parent cows occur in the ED; COUNTY_PARENT_SUPPORT means parents are absent locally but occur elsewhere in the county; NATIONAL_PARENT_SUPPORT is the final support level where the county has no corresponding parents. Legacy internal labels are retained in COHORT_SPATIAL_ROLE_LEGACY for compatibility. These are support classifications, not movement or origin claims."),
    ("Validation", "validation_summary is the headline table; validation_detail_* are the underlying diagnostics; baseline_coherence_audit re-derives every cross-product identity (must be all PASS)."),
    ("Standard Output", "Fixed 2020 IFS coefficients by historic FADN region. A production-value indicator, not income, profit or welfare."),
    ("SQLite names", "SQLite ignores case in column names. In the SQLite copy only, GOBLIN cohort columns that clash with a CSO column differing only in case get the suffix _goblin (e.g. bulls -> bulls_goblin). _columns records SQLITE_COLUMN_NAME."),
    *[(f"Livestock: {item}", text) for item, text in LIVESTOCK_README if item not in ("Checks", "Purpose")],
]



def _configured_output(cfg, key: str, default: str) -> Path:
    raw = cfg.raw.get("outputs", {}).get(key, default)
    path = Path(raw)
    return path if path.is_absolute() else cfg.project_root / path


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument(
        "--output-root",
        default="reporting/report_data/historical",
    )
    parser.add_argument(
        "--allow-audit-failures",
        action="store_true",
        help="bundle despite failed coherence checks (robustness variants only)",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    root = cfg.project_root
    master_path = _configured_output(
        cfg,
        "standard_output_master",
        "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
    )
    wfd_path = root / "data/processed/goblin_spatial_wfd_catchment_2015_2025.csv"
    crosswalk_path = root / "data/processed/ed_wfd_catchment_crosswalk.csv"
    validation_dir = root / "data/processed/validation/historical"

    required = [master_path, wfd_path, crosswalk_path, validation_dir / "historical_validation_overview.csv"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Historical result bundle requires completed baseline, validation and "
            f"catchment outputs. Missing: {missing}"
        )

    master = pd.read_csv(master_path, low_memory=False)
    wfd = pd.read_csv(wfd_path, low_memory=False)
    crosswalk = pd.read_csv(crosswalk_path, dtype={"CSOED": str}, low_memory=False)

    tables = build_historical_result_tables(
        master,
        wfd,
        crosswalk,
        ed_anchor_path=root / cfg.files["cso_ed_2020"],
        cattle_control_path=root / cfg.files["cso_cattle_county"],
        validation_dir=validation_dir,
    )

    # Canonical livestock panels, the Colm reporting geography, and validation
    # detail tables, so the bundle is self-contained.
    paths = output_paths(cfg)
    tables["cso13_ed_year"] = pd.read_csv(paths["cso13"], dtype={"CSOED": str}, low_memory=False)
    tables["goblin31_ed_year"] = pd.read_csv(paths["goblin31"], dtype={"CSOED": str}, low_memory=False)
    tables["colm_catchment_year"] = pd.read_csv(paths["colm"], low_memory=False)
    audit_path = validation_dir / "baseline_coherence_audit.csv"
    if not audit_path.exists():
        raise FileNotFoundError(
            f"{audit_path} missing: run scripts/audit_historical_baseline.py first"
        )
    audit = pd.read_csv(audit_path)
    if not audit["PASS"].all() and not args.allow_audit_failures:
        failed = audit.loc[~audit["PASS"], "CHECK"].tolist()
        raise AssertionError(f"baseline coherence audit has failures: {failed}")
    tables["baseline_coherence_audit"] = audit
    for path in sorted(validation_dir.glob("*.csv")):
        if path.name in {"baseline_coherence_audit.csv", "historical_validation_overview.csv"}:
            continue
        tables[f"validation_detail_{path.stem}"] = pd.read_csv(path, low_memory=False)

    # Livestock signatures (2020, 2025) at ED, WFD catchment, county, Colm
    # catchment and national scale, plus within-catchment ED distributions and
    # ED parent-follower relationships. All derived; nothing is rebuilt.
    signature = build_livestock_signature(
        tables["ed_year"], tables["county_year"], tables["wfd_catchment_year"],
        tables["colm_catchment_year"], tables["national_year"],
    )
    relationship = build_relationship_ed(master, cfg)
    tables["livestock_signature"] = signature
    signature_long = build_signature_long(signature)
    tables["livestock_signature_long"] = signature_long
    tables["wfd_signature_spread"] = build_wfd_signature_spread(signature_long, crosswalk)
    wfd_compare, wfd_compare_summary = build_wfd_fractional_vs_majority(
        tables["ed_year"], crosswalk
    )
    tables["wfd_fractional_vs_majority"] = wfd_compare
    tables["wfd_fractional_vs_majority_summary"] = wfd_compare_summary
    tables["parent_follower_relationship_ed"] = relationship
    tables["parent_follower_relationship_shares"] = build_relationship_shares(relationship, crosswalk)
    tables["parent_follower_relationship_by_year"] = build_relationship_by_year(master, cfg)

    # The wide ED table must carry the authoritative values unchanged.
    check = tables["ed_year"].copy()
    check["CSOED"] = check["CSOED"].astype(str)
    reference = master.copy()
    reference["CSOED"] = reference["CSOED"].astype(str)
    joined = check.merge(reference, on=["YEAR", "CSOED"], suffixes=("", "__master"))
    if len(joined) != len(reference):
        raise AssertionError("ed_year does not cover the authoritative master rows")
    for column in reference.columns:
        if column in ("YEAR", "CSOED") or column not in check.columns:
            continue
        left, right = joined[column], joined[f"{column}__master"]
        same = (
            (left.astype(float) - right.astype(float)).abs().max() < 1e-6
            if left.dtype.kind in "if" and right.dtype.kind in "if"
            else left.astype(str).equals(right.astype(str))
        )
        if not same:
            raise AssertionError(f"ed_year.{column} differs from the authoritative master")

    dictionary = pd.concat(
        [describe_table(name, frame) for name, frame in tables.items()], ignore_index=True
    )
    public = dictionary["TABLE_NAME"].isin(PUBLIC_TABLES)
    undescribed = dictionary.loc[public & dictionary["DESCRIPTION"].eq(""), ["TABLE_NAME", "COLUMN_NAME"]]
    if not undescribed.empty:
        raise AssertionError(f"public columns without a dictionary entry: {undescribed.values.tolist()}")
    dictionary.loc[~public & dictionary["DESCRIPTION"].eq(""), "DESCRIPTION"] = (
        "Validation or manuscript diagnostic column; see docs/validation.md and docs/historical_results_bundle.md."
    )
    sqlite_rename = {name: sqlite_safe_names(list(frame.columns)) for name, frame in tables.items()}
    dictionary["SQLITE_COLUMN_NAME"] = [
        sqlite_rename[t].get(c, c) for t, c in zip(dictionary["TABLE_NAME"], dictionary["COLUMN_NAME"])
    ]
    readme = pd.DataFrame(BUNDLE_README, columns=["ITEM", "DESCRIPTION"])
    extras = {"_columns": dictionary, "_readme": readme}

    out = Path(args.output_root)
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    table_meta: dict[str, dict[str, object]] = {}
    for name, frame in {**tables, **extras}.items():
        csv_path = out / f"{name}.csv"
        parquet_path = out / f"{name}.parquet"
        frame.to_csv(csv_path, index=False)
        frame.to_parquet(parquet_path, index=False)
        table_meta[name] = {
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "csv": str(csv_path.relative_to(root)),
            "parquet": str(parquet_path.relative_to(root)),
            "csv_sha256": _sha(csv_path),
            "parquet_sha256": _sha(parquet_path),
        }

    # Optional SQL query copy. Parquet/CSV remain the canonical reporting files.
    db_path = out / "historical_results.duckdb"
    try:
        import duckdb
    except ImportError:
        duckdb = None

    if duckdb is not None:
        if db_path.exists():
            db_path.unlink()
        con = duckdb.connect(str(db_path))
        try:
            for name, frame in {**tables, **extras}.items():
                con.register("_frame", frame)
                con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM _frame')
                con.unregister("_frame")
            con.execute(
                "CREATE TABLE _bundle_metadata AS SELECT ? AS model_commit, ? AS note",
                [
                    _git_commit(root),
                    "Query copy only; CSV/Parquet are canonical reporting data.",
                ],
            )
        finally:
            con.close()

    # SQLite copy of the same tables, for users without DuckDB (R, QGIS,
    # DB Browser, Excel via ODBC). Column clashes that differ only in case are
    # renamed as recorded in _columns.SQLITE_COLUMN_NAME.
    import sqlite3

    sqlite_path = out / "historical_results.sqlite"
    if sqlite_path.exists():
        sqlite_path.unlink()
    with sqlite3.connect(sqlite_path) as con:
        for name, frame in {**tables, **extras}.items():
            frame.rename(columns=sqlite_rename.get(name, {})).to_sql(name, con, index=False)
            if {"YEAR", "CSOED"} <= set(frame.columns):
                con.execute(f'CREATE INDEX "ix_{name}_year_ed" ON "{name}" (YEAR, CSOED)')
        pd.DataFrame(
            [{"model_commit": _git_commit(root), "note": "Query copy only; CSV/Parquet are canonical reporting data."}]
        ).to_sql("_bundle_metadata", con, index=False)

    sources = {
        str(master_path.relative_to(root)): _sha(master_path),
        str(wfd_path.relative_to(root)): _sha(wfd_path),
        str(crosswalk_path.relative_to(root)): _sha(crosswalk_path),
        str((validation_dir / "historical_validation_overview.csv").relative_to(root)): _sha(
            validation_dir / "historical_validation_overview.csv"
        ),
    }
    manifest = {
        "bundle": "GOBLIN_SPATIAL_HISTORICAL_RESULTS",
        "version": "1.1",
        "model_commit": _git_commit(root),
        "authoritative_state": str(master_path.relative_to(root)),
        "reporting_boundary": (
            "Derived manuscript/query data only. Does not alter baseline science."
        ),
        "sources": sources,
        "tables": table_meta,
        "duckdb": str(db_path.relative_to(root)) if db_path.exists() else None,
        "sqlite": str(sqlite_path.relative_to(root)),
    }
    (out / "historical_results_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Historical result bundle:", out)
    print("Tables:", ", ".join(sorted(tables)))
    print("\nAnchor reconciliation:")
    print(tables["anchor_reconciliation_2020"].to_string(index=False))
    print("\nSO decomposition:")
    print(tables["so_change_2015_2025"].to_string(index=False))
    print("\nStable-ED sensitivity:")
    print(tables["stable_ed_sensitivity"].to_string(index=False))
    print("\nMultiscale example:")
    print(tables["multiscale_example_2020"].to_string(index=False))
    print("\nTop matched pairs:")
    print(tables["matched_pairs_2020"].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
