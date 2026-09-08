"""Finalize publication reporting outputs without changing model science.

This script is deliberately downstream of the completed eight-run publication
pack. It does not invoke Baseline, SC1, SC2, SC3, or the feasible-geography
solver. It materialises the complete reporting layer needed for publication:

* Parquet-first canonical derived tables;
* post-SC3 flexibility and cross-scenario robustness tables;
* map-ready and figure-ready extracts keyed by CSOED;
* a standalone DuckDB query database materialised from Parquet;
* a compact query catalogue, example SQL, and validation manifest.

Parquet remains the canonical reporting datastore. DuckDB is a convenience
query layer and is never used as a scientific input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


EXPECTED_RUNS = 8
EXPECTED_EDS = 2857
USES = (
    "AD_GRASS",
    "BIOREFINERY_GRASS",
    "WILLOW",
    "ADDITIONAL_TILLAGE",
    "FOREST",
    "REWETTING",
)
PRODUCTIVE_USES = USES[:-1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, dtype={"CSOED": str})


def write_pair(frame: pd.DataFrame, base: Path) -> dict[str, object]:
    base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = base.with_suffix(".csv")
    parquet_path = base.with_suffix(".parquet")
    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False, engine="pyarrow")
    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "csv": str(csv_path),
        "parquet": str(parquet_path),
        "parquet_sha256": sha256(parquet_path),
    }


def require_unique(frame: pd.DataFrame, keys: Iterable[str], label: str) -> None:
    keys = list(keys)
    missing = [key for key in keys if key not in frame.columns]
    if missing:
        raise AssertionError(f"{label} missing uniqueness keys: {missing}")
    if frame.duplicated(keys).any():
        raise AssertionError(f"{label} contains duplicate keys: {keys}")


def validate_national_accounting(inventory: pd.DataFrame) -> None:
    if len(inventory) != EXPECTED_RUNS:
        raise AssertionError(f"publication inventory has {len(inventory)} runs; expected 8")
    require_unique(inventory, ["RUN_ID"], "publication inventory")
    if set(inventory["N_EDS"].astype(int)) != {EXPECTED_EDS}:
        raise AssertionError("publication inventory does not contain 2,857 EDs in every run")

    for use in USES:
        target = pd.to_numeric(inventory[f"{use}_TARGET_HA"], errors="raise")
        realised = pd.to_numeric(inventory[f"{use}_REALISED_HA"], errors="raise")
        unmet = pd.to_numeric(inventory[f"{use}_UNMET_HA"], errors="raise")
        if ((target - realised - unmet).abs() > 1e-5).any():
            raise AssertionError(f"Target = Realised + Unmet fails for {use}")
        if ((target < -1e-7) | (realised < -1e-7) | (unmet < -1e-7)).any():
            raise AssertionError(f"negative national SC3 quantity for {use}")

    released = pd.to_numeric(inventory["TOTAL_RELEASED_HA"], errors="raise")
    allocated = pd.to_numeric(inventory["TOTAL_ALLOCATED_HA"], errors="raise")
    residual = pd.to_numeric(inventory["RESIDUAL_RELEASED_HA"], errors="raise")
    if ((released - allocated - residual).abs() > 1e-5).any():
        raise AssertionError("Released = Allocated + Residual fails")

    for scenario, block in inventory.groupby("SCENARIO_ID", sort=False):
        if block["TOTAL_RELEASED_HA"].max() - block["TOTAL_RELEASED_HA"].min() > 1e-5:
            raise AssertionError(f"released land varies across allocation rules for {scenario}")


def build_flex_allocations(principal_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for run_dir in sorted(path for path in principal_root.iterdir() if path.is_dir()):
        source = run_dir / "sc3_flexibility_allocations.csv"
        if source.exists():
            frames.append(read_csv(source))
    if len(frames) != EXPECTED_RUNS:
        raise AssertionError(
            f"found flexibility allocation files for {len(frames)} runs; expected 8"
        )
    out = pd.concat(frames, ignore_index=True, sort=False)
    required = {"RUN_ID", "SCENARIO_ID", "ALLOCATION_RULE", "SOLUTION_ID", "CSOED", "USE", "ALLOCATED_HA"}
    missing = sorted(required - set(out.columns))
    if missing:
        raise AssertionError(f"flexibility allocations missing columns: {missing}")
    return out


def build_sc2_response_long(sc2: pd.DataFrame) -> pd.DataFrame:
    id_candidates = [
        "RUN_ID",
        "REPORT_SCENARIO_ID",
        "REPORT_ALLOCATION_RULE",
        "REPORT_BASELINE_YEAR",
        "REPORT_TARGET_YEAR",
        "CSOED",
        "County",
        "GOBLIN_RELEASED_GRASSLAND_HA",
    ]
    ids = [column for column in id_candidates if column in sc2.columns]
    frames: list[pd.DataFrame] = []
    for use in PRODUCTIVE_USES:
        column = f"COLM_DIRECT_{use}_ELIGIBLE_HA"
        if column not in sc2.columns:
            raise AssertionError(f"SC2 reporting data missing {column}")
        part = sc2[ids + [column]].copy()
        part.insert(len(ids), "USE", use)
        part = part.rename(columns={column: "ELIGIBLE_HA"})
        frames.append(part)
    return pd.concat(frames, ignore_index=True, sort=False)


def build_sc3_allocation_long(sc3: pd.DataFrame) -> pd.DataFrame:
    ids = [
        column
        for column in (
            "RUN_ID",
            "REPORT_SCENARIO_ID",
            "REPORT_ALLOCATION_RULE",
            "REPORT_BASELINE_YEAR",
            "REPORT_TARGET_YEAR",
            "CSOED",
            "County",
            "GOBLIN_RELEASED_GRASSLAND_HA",
            "SC3_TOTAL_ALLOCATED_HA",
            "SC3_RESIDUAL_RELEASED_HA",
        )
        if column in sc3.columns
    ]
    frames: list[pd.DataFrame] = []
    for use in USES:
        column = f"SC3_{use}_ALLOCATED_HA"
        if column not in sc3.columns:
            raise AssertionError(f"SC3 reporting data missing {column}")
        part = sc3[ids + [column]].copy()
        part.insert(len(ids), "USE", use)
        part = part.rename(columns={column: "ALLOCATED_HA"})
        frames.append(part)
    return pd.concat(frames, ignore_index=True, sort=False)


def selected_sc1_incidence(comparison: pd.DataFrame) -> pd.DataFrame:
    candidates = [
        "RUN_ID",
        "REPORT_SCENARIO_ID",
        "REPORT_ALLOCATION_RULE",
        "CSOED",
        "County",
        "TOTAL_CATTLE_REDUCTION_HEAD",
        "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
        "GOBLIN_RELEASED_GRASSLAND_HA",
        "GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE",
        "SIGNED_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_HEAD",
        "PROTECTION_RELIEF_TOTAL_CATTLE_REDUCTION_HEAD",
        "DISPLACED_BURDEN_TOTAL_CATTLE_REDUCTION_HEAD",
        "SIGNED_DIFFERENCE_FROM_PRORATA_TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
        "PROTECTION_RELIEF_TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
        "DISPLACED_BURDEN_TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
        "SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "SIGNED_DIFFERENCE_FROM_PRORATA_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
        "PROTECTION_RELIEF_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
        "DISPLACED_BURDEN_SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
        "SIGNED_DIFFERENCE_FROM_PRORATA_GOBLIN_RELEASED_GRASSLAND_HA",
        "PROTECTION_RELIEF_GOBLIN_RELEASED_GRASSLAND_HA",
        "DISPLACED_BURDEN_GOBLIN_RELEASED_GRASSLAND_HA",
    ]
    columns = [column for column in candidates if column in comparison.columns]
    return comparison[columns].copy()


def build_fig02(sc1_national: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    # National endpoints are invariant across allocation rules within a pathway.
    # Use PRORATA only to avoid repeating the same national values four times.
    sc1 = sc1_national.loc[
        sc1_national["REPORT_ALLOCATION_RULE"].astype(str) == "PRORATA"
    ].copy()
    inv = inventory.loc[inventory["ALLOCATION_RULE"].astype(str) == "PRORATA"].copy()
    keep_sc1 = [
        column
        for column in (
            "REPORT_SCENARIO_ID",
            "BASE_TOTAL_CATTLE",
            "SCENARIO_TOTAL_CATTLE",
            "BASE_DAIRY_COWS",
            "SCENARIO_DAIRY_COWS",
            "BASE_SUCKLER_COWS",
            "SCENARIO_SUCKLER_COWS",
            "GOBLIN_RELEASED_GRASSLAND_HA",
        )
        if column in sc1.columns
    ]
    out = sc1[keep_sc1].rename(columns={"REPORT_SCENARIO_ID": "SCENARIO_ID"})
    target_columns = ["SCENARIO_ID"] + [f"{use}_TARGET_HA" for use in USES]
    out = out.merge(inv[target_columns], on="SCENARIO_ID", how="left", validate="one_to_one")
    return out


def build_duckdb(
    database_path: Path,
    tables: dict[str, Path],
) -> None:
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Final publication query pack requires DuckDB. Install with: "
            "pip install 'goblin-spatial[query]'"
        ) from exc

    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()
    con = duckdb.connect(str(database_path))
    try:
        for table_name, parquet_path in tables.items():
            safe_name = table_name.replace("/", "__").replace("-", "_")
            escaped = str(parquet_path.resolve()).replace("'", "''")
            con.execute(
                f'CREATE TABLE "{safe_name}" AS SELECT * FROM read_parquet(\'{escaped}\')'
            )
        con.execute(
            "CREATE TABLE _metadata AS SELECT "
            "'Parquet is the canonical reporting datastore; DuckDB is a query convenience.' AS note"
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--principal-root", default="data/processed/principal")
    parser.add_argument("--report-data-root", default="reporting/report_data")
    parser.add_argument("--publication-root", default="reporting/publication")
    parser.add_argument("--figure-data-root", default="reporting/figure_data")
    parser.add_argument("--map-data-root", default="reporting/map_data")
    parser.add_argument("--query-root", default="reporting/query")
    args = parser.parse_args()

    principal_root = Path(args.principal_root)
    report_root = Path(args.report_data_root)
    publication_root = Path(args.publication_root)
    figure_root = Path(args.figure_data_root)
    map_root = Path(args.map_data_root)
    query_root = Path(args.query_root)

    publication_manifest = json.loads(
        (publication_root / "publication_pack_manifest.json").read_text(encoding="utf-8")
    )
    report_manifest = json.loads(
        (report_root / "report_data_manifest.json").read_text(encoding="utf-8")
    )
    if int(publication_manifest["RUN_COUNT"]) != EXPECTED_RUNS:
        raise AssertionError("publication manifest is not the complete eight-run pack")
    if int(report_manifest["RUN_COUNT"]) != EXPECTED_RUNS:
        raise AssertionError("report-data manifest is not the complete eight-run pack")

    inventory = read_csv(publication_root / "publication_run_inventory.csv")
    national_long = read_csv(publication_root / "sc3_crossrun_national_long.csv")
    feasibility = read_csv(publication_root / "sc3_feasibility_sensitivity.csv")
    flex_summary = read_csv(publication_root / "sc3_flexibility_ed_all_runs.csv")
    flex_crossrun = read_csv(publication_root / "sc3_crossrun_flexibility_robustness.csv")
    flex_diag = read_csv(publication_root / "sc3_flexibility_diagnostics_all_runs.csv")
    validate_national_accounting(inventory)

    sc1_national = read_csv(report_root / "sc1/national_metrics.csv")
    sc1_comparison = read_csv(report_root / "sc1/comparison_ed.csv")
    sc1_robust = read_csv(report_root / "sc1/robust_exposure.csv")
    sc2 = read_csv(report_root / "sc2/ed_context.csv")
    sc3 = read_csv(report_root / "sc3/ed_results.csv")

    if len(sc1_robust) != EXPECTED_EDS:
        raise AssertionError("SC1 robust exposure does not contain 2,857 EDs")
    if len(sc2) != EXPECTED_RUNS * EXPECTED_EDS:
        raise AssertionError("SC2 report data does not contain 8 x 2,857 ED rows")
    if len(sc3) != EXPECTED_RUNS * EXPECTED_EDS:
        raise AssertionError("SC3 report data does not contain 8 x 2,857 ED rows")
    if len(flex_summary) != EXPECTED_RUNS * EXPECTED_EDS * len(USES):
        raise AssertionError("post-SC3 flexibility summary has unexpected row count")
    if len(flex_crossrun) != EXPECTED_EDS * len(USES):
        raise AssertionError("cross-run flexibility robustness has unexpected row count")

    require_unique(sc1_robust, ["CSOED"], "SC1 robust exposure")
    require_unique(
        flex_summary,
        ["RUN_ID", "CSOED", "USE"],
        "post-SC3 flexibility summary",
    )
    require_unique(flex_crossrun, ["CSOED", "USE"], "cross-run flexibility robustness")

    # Every publication run requested 8 alternatives and retained the reference.
    if not (pd.to_numeric(flex_diag["REQUESTED_ALTERNATIVES"], errors="raise") == 8).all():
        raise AssertionError("unexpected flexibility alternative count")
    if not (pd.to_numeric(flex_diag["TOTAL_SOLUTIONS_WITH_REFERENCE"], errors="raise") == 9).all():
        raise AssertionError("not every run contains 8 alternatives plus the reference")
    if not flex_diag["PER_USE_NATIONAL_REALISED_VECTOR_FIXED"].astype(bool).all():
        raise AssertionError("flexibility analysis did not preserve the per-use realised vector")

    registry: dict[str, dict[str, object]] = {}

    # Canonical derived Parquet tables.
    registry["publication/run_inventory"] = write_pair(
        inventory, report_root / "publication/run_inventory"
    )
    registry["sc3/crossrun_national_long"] = write_pair(
        national_long, report_root / "sc3/crossrun_national_long"
    )
    registry["sc3/feasibility_sensitivity"] = write_pair(
        feasibility, report_root / "sc3/feasibility_sensitivity"
    )
    registry["flexibility/ed_summary_all_runs"] = write_pair(
        flex_summary, report_root / "flexibility/ed_summary_all_runs"
    )
    registry["flexibility/diagnostics"] = write_pair(
        flex_diag, report_root / "flexibility/diagnostics"
    )
    registry["robustness/sc3_crossrun_flexibility"] = write_pair(
        flex_crossrun, report_root / "robustness/sc3_crossrun_flexibility"
    )

    flex_alloc = build_flex_allocations(principal_root)
    registry["flexibility/allocations"] = write_pair(
        flex_alloc, report_root / "flexibility/allocations"
    )

    # Map-ready tables. Geometry remains frozen separately and joins on CSOED.
    map_sc1 = selected_sc1_incidence(sc1_comparison)
    map_sc2 = build_sc2_response_long(sc2)
    map_sc3 = build_sc3_allocation_long(sc3)
    map_tables = {
        "sc1_transition_incidence": map_sc1,
        "sc1_robust_exposure": sc1_robust,
        "sc2_response_potential": map_sc2,
        "sc3_allocations": map_sc3,
        "sc3_spatial_flexibility": flex_summary,
        "sc3_crossrun_robustness": flex_crossrun,
    }
    for name, frame in map_tables.items():
        registry[f"map_data/{name}"] = write_pair(frame, map_root / name)

    # Figure-ready source tables. These are data extracts, not rendered figures.
    fig02 = build_fig02(sc1_national, inventory)
    figure_tables = {
        "fig02_national_pathway_pressures": fig02,
        "fig03_transition_incidence_redistribution": map_sc1,
        "fig04_robust_exposure": sc1_robust,
        "fig05_response_potential": map_sc2,
        "fig06_sc3_feasibility": national_long,
        "fig07_spatial_flexibility": flex_summary,
    }
    for name, frame in figure_tables.items():
        registry[f"figure_data/{name}"] = write_pair(frame, figure_root / name)

    # Build compact query catalogue.
    catalogue_rows: list[dict[str, object]] = []
    duck_tables: dict[str, Path] = {}
    for logical_name, record in sorted(registry.items()):
        parquet_path = Path(str(record["parquet"]))
        catalogue_rows.append(
            {
                "TABLE_NAME": logical_name.replace("/", "__"),
                "LOGICAL_NAME": logical_name,
                "PARQUET_PATH": str(parquet_path),
                "ROWS": int(record["rows"]),
                "COLUMNS": int(record["columns"]),
                "PARQUET_SHA256": str(record["parquet_sha256"]),
            }
        )
        duck_tables[logical_name] = parquet_path
    catalogue = pd.DataFrame(catalogue_rows)
    registry["query/catalogue"] = write_pair(catalogue, query_root / "query_catalogue")

    database_path = query_root / "goblin_spatial_results.duckdb"
    build_duckdb(database_path, duck_tables)

    examples = """-- GOBLIN-Spatial publication query examples\n-- Parquet is canonical; this DuckDB database is a convenience query layer.\n\n-- National SC3 feasibility by pathway, allocation rule and use\nSELECT SCENARIO_ID, ALLOCATION_RULE, USE, TARGET_HA, REALISED_HA, UNMET_HA\nFROM sc3__crossrun_national_long\nORDER BY SCENARIO_ID, ALLOCATION_RULE, USE;\n\n-- Robust SC1 exposure hotspots\nSELECT *\nFROM map_data__sc1_robust_exposure\nORDER BY ROBUST_MIN_CATTLE_REDUCTION_PCT DESC\nLIMIT 50;\n\n-- Places where a use is positive in every sampled feasible geography and every run\nSELECT CSOED, USE, N_RUNS, MIN_POSITIVE_FREQUENCY_SAMPLED\nFROM robustness__sc3_crossrun_flexibility\nWHERE PERSISTENT_ROBUST_POSITIVE_SAMPLED_ALL_RUNS = TRUE\nORDER BY USE, CSOED;\n\n-- Map-ready SC3 allocation for one pathway and implementation rule\nSELECT *\nFROM map_data__sc3_allocations\nWHERE REPORT_SCENARIO_ID = 'BE_SG'\n  AND REPORT_ALLOCATION_RULE = 'PRORATA';\n"""
    query_root.mkdir(parents=True, exist_ok=True)
    (query_root / "examples.sql").write_text(examples, encoding="utf-8")

    productive_unmet = {
        use: int((pd.to_numeric(inventory[f"{use}_UNMET_HA"], errors="raise") > 1e-6).sum())
        for use in PRODUCTIVE_USES
    }
    rewetting_unmet_runs = int(
        (pd.to_numeric(inventory["REWETTING_UNMET_HA"], errors="raise") > 1e-6).sum()
    )

    final_manifest = {
        "FINAL_REPORTING_VERSION": "1.0",
        "SOURCE_PUBLICATION_PACK_VERSION": publication_manifest.get("PUBLICATION_PACK_VERSION"),
        "MODEL_COMMIT": publication_manifest.get("MODEL_COMMIT"),
        "RUN_COUNT": EXPECTED_RUNS,
        "EXPECTED_EDS": EXPECTED_EDS,
        "PARQUET_CANONICAL": True,
        "DUCKDB_QUERY_LAYER": str(database_path),
        "DUCKDB_IS_SCIENTIFIC_AUTHORITY": False,
        "MAP_JOIN_KEY": "CSOED",
        "FLEXIBILITY_SOLUTIONS_PER_RUN": 9,
        "FLEXIBILITY_INTERPRETATION": "SAMPLED_NOT_COMPLETE_FEASIBLE_ENVELOPE",
        "PRODUCTIVE_USE_RUNS_WITH_UNMET": productive_unmet,
        "REWETTING_RUNS_WITH_UNMET": rewetting_unmet_runs,
        "TABLES": registry,
        "VALIDATION": {
            "NATIONAL_TARGET_IDENTITIES": "PASS",
            "RELEASED_EQUALS_ALLOCATED_PLUS_RESIDUAL": "PASS",
            "EIGHT_RUN_ENSEMBLE": "PASS",
            "ED_UNIVERSE_2857": "PASS",
            "SC1_ROBUST_EXPOSURE_UNIQUE_CSOED": "PASS",
            "POST_SC3_SAME_OUTCOME_VECTOR_FIXED": "PASS",
            "POST_SC3_EIGHT_UNIQUE_ALTERNATIVES_PLUS_REFERENCE": "PASS",
        },
        "SCIENTIFIC_BOUNDARY": (
            "DOWNSTREAM_REPORTING_ONLY; FROZEN_MODEL_RESULTS_ARE_NOT_RECALCULATED_OR_REPRIORITISED"
        ),
    }
    manifest_path = query_root / "final_reporting_manifest.json"
    manifest_path.write_text(
        json.dumps(final_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Final reporting pack complete.")
    print(f"Parquet catalogue: {query_root / 'query_catalogue.parquet'}")
    print(f"DuckDB query database: {database_path}")
    print(f"Figure-ready data: {figure_root}")
    print(f"Map-ready data: {map_root}")
    print(f"Validation manifest: {manifest_path}")


if __name__ == "__main__":
    main()
