"""Build the two canonical merged annual ED livestock panels, 2015-2025.

  CSO_13_Cohort_Annual_Panel_2015_2025      9 CSO cattle + 4 CSO sheep groups
  GOBLIN_31_Cohort_Annual_Panel_2015_2025   21 cattle + 10 sheep cohorts (+ CSO_ controls)

CSVs go to the config paths outputs.cso_13_cohort_panel and
outputs.goblin_31_cohort_panel; a workbook and SQLite copy go to
data/processed/livestock/.
Usage: python scripts/build_livestock_panels.py
"""

from __future__ import annotations

from pathlib import Path

from goblin_spatial.config import load_config
from goblin_spatial.export.livestock_panels import (
    export_sqlite,
    export_workbook,
    project_enriched_livestock_panels,
    run_checks,
)
from goblin_spatial.pipeline import build as build_historical_core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/livestock"


def main() -> None:
    cfg = load_config(CONFIG)
    master = build_historical_core(cfg)
    panel13, panel31 = project_enriched_livestock_panels(master)
    checks = run_checks(panel13, panel31, cfg)
    print(checks.to_string(index=False))
    export_workbook(panel13, panel31, checks, OUT / "CSO_13_and_GOBLIN_31_Cohort_Annual_Panels_2015_2025.xlsx")
    export_sqlite(panel13, panel31, checks, OUT / "CSO_13_and_GOBLIN_31_Cohort_Annual_Panels_2015_2025.sqlite")
    print(panel13.groupby("YEAR")[["TOTAL_CATTLE", "TOTAL_SHEEP"]].sum().to_string())


if __name__ == "__main__":
    main()
