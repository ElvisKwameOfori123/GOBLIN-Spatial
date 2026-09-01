"""Safe runner for the final manuscript package.

The final reporting map table is intentionally compact.  The manuscript maps
need a few additional downstream comparison variables (baseline SO, signed
change from PRORATA and baseline grassland) that already exist in the frozen
``transition_conditions`` table.  This runner supplies that full downstream
scientific table to the manuscript cartographic layer without modifying any
model result.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.map_reporting import resolve_geometry_path
from goblin_spatial import manuscript_package as mp


def build_package(
    results_dir: str | Path,
    *,
    output_dir: str | Path,
    sensitivity_summary: str | Path | None = None,
    config_path: str | Path = "configs/ireland_2015_2025.yaml",
    geometry: str | Path | None = None,
) -> dict[str, Path]:
    results = Path(results_dir).resolve()
    db = results / "GOBLIN_Spatial_Final_Results.sqlite"
    if not db.exists():
        raise FileNotFoundError(db)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tables = mp._read_sqlite(db)
    required = {
        "transition_conditions", "land_release_summary", "opportunity_mobilisation",
        "persistence", "rewetting_summary", "shared_pool_summary",
    }
    missing = sorted(required - set(tables))
    if missing:
        raise ValueError(f"final results database missing manuscript tables: {missing}")

    # Manuscript mapping needs the complete downstream ED table.  This table is
    # authoritative reporting output and contains no geometry or model mutation.
    tables["map_data"] = tables["transition_conditions"].copy()

    sensitivity = None
    if sensitivity_summary is not None and Path(sensitivity_summary).exists():
        sensitivity = pd.read_csv(sensitivity_summary)
    diagnostics = mp.build_diagnostics(tables, sensitivity)

    diag_dir = out / "diagnostics"
    diag_dir.mkdir(exist_ok=True)
    for name, frame in diagnostics.items():
        frame.to_csv(diag_dir / f"{name}.csv", index=False)

    cfg = load_config(Path(config_path))
    geometry_path = resolve_geometry_path(config_path=config_path, geometry=geometry)
    figure_files, callouts = mp.build_figures(
        tables,
        diagnostics,
        project_root=cfg.project_root,
        output_dir=out / "figures",
        geometry_path=geometry_path,
    )
    for name, frame in callouts.items():
        frame.to_csv(diag_dir / f"{name}.csv", index=False)

    key_results = out / "manuscript_key_results.txt"
    mp._write_key_results(diagnostics, tables, key_results)
    manifest = pd.DataFrame([
        {"FILE": str(p.relative_to(out)), "FORMAT": p.suffix.lstrip("."), "VERSION": mp.VERSION}
        for p in figure_files
    ])
    manifest_path = out / "manuscript_figure_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    return {"output_dir": out, "key_results": key_results, "manifest": manifest_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build final manuscript diagnostics and Figures 2-7")
    parser.add_argument("results_dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sensitivity-summary", default=None)
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument("--geometry", default=None)
    args = parser.parse_args(argv)
    outputs = build_package(
        args.results_dir,
        output_dir=args.output_dir,
        sensitivity_summary=args.sensitivity_summary,
        config_path=args.config,
        geometry=args.geometry,
    )
    for key, value in outputs.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
