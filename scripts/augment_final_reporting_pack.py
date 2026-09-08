"""Augment a completed publication artifact without rerunning model science.

This is a reporting-only utility. It operates on an already validated eight-run
publication pack and does not invoke Baseline, SC1, SC2, SC3, or any optimiser.

It performs three final publication tasks:
1. repairs/standardises map-ready SC1 pathway and allocation identifiers;
2. materialises the low/central/high rewetting-proxy sensitivity as reporting data;
3. rebuilds a standalone DuckDB database containing every Parquet reporting table.

Parquet remains the canonical reporting datastore. DuckDB is only a query layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_RUNS = 8
EXPECTED_EDS = 2857
LOW_DRAINED_HA = 90_000.0
CENTRAL_DRAINED_HA = 105_000.0
HIGH_DRAINED_HA = 120_000.0
GRASSLAND_PEAT_HA = 335_000.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_pair(frame: pd.DataFrame, base: Path) -> tuple[Path, Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = base.with_suffix(".csv")
    parquet_path = base.with_suffix(".parquet")
    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False, engine="pyarrow")
    return csv_path, parquet_path


def build_sc1_map(report_root: Path, map_root: Path, figure_root: Path) -> None:
    source = pd.read_parquet(report_root / "sc1/comparison_ed.parquet")
    required = {
        "RUN_ID",
        "SCENARIO_NAME",
        "SCENARIO_ALLOCATION_RULE",
        "CSOED",
        "TOTAL_CATTLE_REDUCTION_HEAD",
        "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE",
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE",
        "GOBLIN_RELEASED_GRASSLAND_HA",
    }
    missing = sorted(required - set(source.columns))
    if missing:
        raise AssertionError(f"SC1 comparison data missing columns: {missing}")

    candidates = [
        "RUN_ID",
        "SCENARIO_NAME",
        "SCENARIO_ALLOCATION_RULE",
        "SCENARIO_BASELINE_YEAR",
        "SCENARIO_TARGET_YEAR",
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
    columns = [column for column in candidates if column in source.columns]
    out = source[columns].copy().rename(
        columns={
            "SCENARIO_NAME": "SCENARIO_ID",
            "SCENARIO_ALLOCATION_RULE": "ALLOCATION_RULE",
            "SCENARIO_BASELINE_YEAR": "BASELINE_YEAR",
            "SCENARIO_TARGET_YEAR": "TARGET_YEAR",
        }
    )
    if len(out) != EXPECTED_RUNS * EXPECTED_EDS:
        raise AssertionError("SC1 map data does not contain 8 x 2,857 ED rows")
    if out.duplicated(["RUN_ID", "CSOED"]).any():
        raise AssertionError("SC1 map data contains duplicate RUN_ID × CSOED keys")
    write_pair(out, map_root / "sc1_transition_incidence")
    write_pair(out, figure_root / "fig03_transition_incidence_redistribution")


def build_rewetting_sensitivity(
    report_root: Path,
    figure_root: Path,
) -> pd.DataFrame:
    sc3 = pd.read_parquet(report_root / "sc3/ed_results.parquet")
    required = {
        "RUN_ID",
        "REPORT_SCENARIO_ID",
        "REPORT_ALLOCATION_RULE",
        "COLM_RELEASED_PEAT_HA",
        "SC3_RESIDUAL_PEAT_HA",
        "SC3_REWETTING_PEAT_HA",
        "SC3_REWETTING_NATIONAL_TARGET_HA",
        "SC3_REWETTING_NATIONAL_REALISED_HA",
        "SC3_REWETTING_NATIONAL_UNMET_HA",
    }
    missing = sorted(required - set(sc3.columns))
    if missing:
        raise AssertionError(f"SC3 data missing rewetting sensitivity columns: {missing}")

    cases = (
        ("LOW", LOW_DRAINED_HA),
        ("CENTRAL", CENTRAL_DRAINED_HA),
        ("HIGH", HIGH_DRAINED_HA),
    )
    rows: list[dict[str, object]] = []
    for run_id, block in sc3.groupby("RUN_ID", sort=False):
        target_values = pd.to_numeric(
            block["SC3_REWETTING_NATIONAL_TARGET_HA"], errors="raise"
        )
        if target_values.max() - target_values.min() > 1e-7:
            raise AssertionError(f"rewetting target varies within {run_id}")
        target = float(target_values.iloc[0])
        released_peat = pd.to_numeric(block["COLM_RELEASED_PEAT_HA"], errors="raise").to_numpy(float)
        pre_rewet_residual = (
            pd.to_numeric(block["SC3_RESIDUAL_PEAT_HA"], errors="raise").to_numpy(float)
            + pd.to_numeric(block["SC3_REWETTING_PEAT_HA"], errors="raise").to_numpy(float)
        )
        scenario = str(block["REPORT_SCENARIO_ID"].iloc[0])
        allocation_rule = str(block["REPORT_ALLOCATION_RULE"].iloc[0])

        for label, drained_ha in cases:
            share = float(drained_ha) / GRASSLAND_PEAT_HA
            capacity = np.minimum(released_peat * share, pre_rewet_residual)
            available = float(np.maximum(capacity, 0.0).sum())
            realised = min(target, available)
            unmet = max(target - realised, 0.0)
            rows.append(
                {
                    "RUN_ID": run_id,
                    "SCENARIO_ID": scenario,
                    "ALLOCATION_RULE": allocation_rule,
                    "SENSITIVITY_CASE": label,
                    "DRAINED_GRASSLAND_PEAT_HA_ASSUMPTION": drained_ha,
                    "MAPPED_GRASSLAND_PEAT_HA_DENOMINATOR": GRASSLAND_PEAT_HA,
                    "DRAINED_SHARE_PROXY": share,
                    "REWETTING_TARGET_HA": target,
                    "AVAILABLE_PROXY_CAPACITY_HA": available,
                    "REALISED_HA": realised,
                    "UNMET_HA": unmet,
                    "REALISED_SHARE": 1.0 if target <= 1e-12 else realised / target,
                    "UNMET_SHARE": 0.0 if target <= 1e-12 else unmet / target,
                }
            )

    out = pd.DataFrame(rows)
    if len(out) != EXPECTED_RUNS * 3:
        raise AssertionError("rewetting sensitivity does not contain 8 runs × 3 cases")

    # Confirm the central case reproduces the completed SC3 run.
    central = out.loc[out["SENSITIVITY_CASE"] == "CENTRAL"].set_index("RUN_ID")
    actual = (
        sc3.groupby("RUN_ID", sort=False)
        .agg(
            REWETTING_REALISED=("SC3_REWETTING_NATIONAL_REALISED_HA", "first"),
            REWETTING_UNMET=("SC3_REWETTING_NATIONAL_UNMET_HA", "first"),
        )
    )
    joined = central.join(actual)
    if ((joined["REALISED_HA"] - joined["REWETTING_REALISED"]).abs() > 1e-5).any():
        raise AssertionError("central proxy sensitivity does not reproduce SC3 realised rewetting")
    if ((joined["UNMET_HA"] - joined["REWETTING_UNMET"]).abs() > 1e-5).any():
        raise AssertionError("central proxy sensitivity does not reproduce SC3 unmet rewetting")

    write_pair(out, report_root / "robustness/rewetting_proxy_sensitivity")
    write_pair(out, figure_root / "fig06b_rewetting_proxy_sensitivity")
    return out


def safe_table_name(path: Path, reporting_root: Path) -> str:
    rel = path.relative_to(reporting_root).with_suffix("")
    name = "__".join(rel.parts)
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    return name


def rebuild_duckdb(reporting_root: Path, query_root: Path) -> pd.DataFrame:
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install query dependencies with: pip install 'goblin-spatial[query]'") from exc

    parquet_paths = sorted(
        path
        for path in reporting_root.rglob("*.parquet")
        if query_root not in path.parents
    )
    if not parquet_paths:
        raise AssertionError("no Parquet reporting tables found")

    database = query_root / "goblin_spatial_results.duckdb"
    query_root.mkdir(parents=True, exist_ok=True)
    if database.exists():
        database.unlink()

    con = duckdb.connect(str(database))
    catalogue_rows: list[dict[str, object]] = []
    try:
        for path in parquet_paths:
            table = safe_table_name(path, reporting_root)
            escaped = str(path.resolve()).replace("'", "''")
            con.execute(
                f'CREATE TABLE "{table}" AS SELECT * FROM read_parquet(\'{escaped}\')'
            )
            rows = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            columns = int(len(con.execute(f'PRAGMA table_info("{table}")').fetchall()))
            catalogue_rows.append(
                {
                    "TABLE_NAME": table,
                    "PARQUET_PATH": str(path),
                    "ROWS": rows,
                    "COLUMNS": columns,
                    "PARQUET_SHA256": sha256(path),
                }
            )
        con.execute(
            "CREATE TABLE _metadata AS SELECT "
            "'Parquet is canonical; DuckDB is a standalone query convenience.' AS note"
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    catalogue = pd.DataFrame(catalogue_rows).sort_values("TABLE_NAME").reset_index(drop=True)
    write_pair(catalogue, query_root / "query_catalogue")
    return catalogue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reporting-root", default="reporting")
    args = parser.parse_args()

    reporting_root = Path(args.reporting_root)
    report_root = reporting_root / "report_data"
    publication_root = reporting_root / "publication"
    map_root = reporting_root / "map_data"
    figure_root = reporting_root / "figure_data"
    query_root = reporting_root / "query"

    pack_manifest = json.loads(
        (publication_root / "publication_pack_manifest.json").read_text(encoding="utf-8")
    )
    if int(pack_manifest["RUN_COUNT"]) != EXPECTED_RUNS:
        raise AssertionError("source publication pack is not the complete eight-run ensemble")

    build_sc1_map(report_root, map_root, figure_root)
    rewet = build_rewetting_sensitivity(report_root, figure_root)
    catalogue = rebuild_duckdb(reporting_root, query_root)

    if (rewet["UNMET_HA"] <= 1e-6).any():
        # This would not be an error scientifically, but for the frozen publication
        # pack it would mean the expected robust restoration constraint changed.
        raise AssertionError("rewetting is not unmet in every low/central/high principal sensitivity case")

    validation = {
        "REPORTING_AUGMENT_VERSION": "1.0",
        "SOURCE_MODEL_COMMIT": pack_manifest.get("MODEL_COMMIT"),
        "RUN_COUNT": EXPECTED_RUNS,
        "EXPECTED_EDS": EXPECTED_EDS,
        "PARQUET_CANONICAL": True,
        "DUCKDB_IS_SCIENTIFIC_AUTHORITY": False,
        "DUCKDB_TABLE_COUNT": int(len(catalogue)),
        "MAP_JOIN_KEY": "CSOED",
        "REWETTING_SENSITIVITY_CASES": ["LOW", "CENTRAL", "HIGH"],
        "REWETTING_UNMET_IN_ALL_24_RUN_CASES": True,
        "SCIENTIFIC_BOUNDARY": "REPORTING_ONLY; NO MODEL OR OPTIMISATION RECALCULATION",
        "VALIDATION": {
            "SC1_MAP_RUN_AND_ED_KEYS": "PASS",
            "CENTRAL_REWETTING_PROXY_REPRODUCES_SC3": "PASS",
            "LOW_CENTRAL_HIGH_REWETTING_SENSITIVITY": "PASS",
            "ALL_REPORTING_PARQUETS_QUERYABLE_IN_DUCKDB": "PASS",
        },
    }
    (query_root / "reporting_augment_manifest.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    examples = """-- Final GOBLIN-Spatial DuckDB examples\n\n-- Discover every available reporting table\nSELECT * FROM query__query_catalogue ORDER BY TABLE_NAME;\n\n-- SC1 robust exposure\nSELECT * FROM report_data__sc1__robust_exposure\nORDER BY ROBUST_MIN_CATTLE_REDUCTION_PCT DESC\nLIMIT 50;\n\n-- SC3 national feasibility\nSELECT SCENARIO_ID, ALLOCATION_RULE, USE, TARGET_HA, REALISED_HA, UNMET_HA\nFROM report_data__sc3__crossrun_national_long\nORDER BY SCENARIO_ID, ALLOCATION_RULE, USE;\n\n-- Map-ready SC3 allocations\nSELECT * FROM map_data__sc3_allocations\nWHERE REPORT_SCENARIO_ID = 'BE_SG'\n  AND REPORT_ALLOCATION_RULE = 'PRORATA';\n\n-- Low / central / high rewetting proxy sensitivity\nSELECT * FROM report_data__robustness__rewetting_proxy_sensitivity\nORDER BY SCENARIO_ID, ALLOCATION_RULE, SENSITIVITY_CASE;\n"""
    (query_root / "examples.sql").write_text(examples, encoding="utf-8")

    print(f"Reporting-only augmentation complete: {len(catalogue)} Parquet tables in DuckDB")
    print("No model science or optimisation was rerun.")


if __name__ == "__main__":
    main()
