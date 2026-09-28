"""Build the two merged annual ED livestock panels, 2015-2025.

  annual_livestock_cso_13_groups_2015_2025   9 CSO cattle + 4 CSO sheep groups
  annual_livestock_31_cohorts_2015_2025      21 cattle + 10 sheep cohorts (+ the 13 groups)

Writes CSV, one workbook and one SQLite file to data/processed/livestock/.
Usage: python scripts/build_livestock_panels.py
"""

from __future__ import annotations

from pathlib import Path

from goblin_spatial.config import load_config
from goblin_spatial.export.livestock_panels import (
    NAME_13,
    NAME_31,
    build_livestock_panels,
    export_sqlite,
    export_workbook,
    run_checks,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/livestock"


def main() -> None:
    cfg = load_config(CONFIG)
    panel13, panel31 = build_livestock_panels(cfg)
    checks = run_checks(panel13, panel31, cfg)
    print(checks.to_string(index=False))
    OUT.mkdir(parents=True, exist_ok=True)
    panel13.to_csv(OUT / f"{NAME_13}.csv", index=False)
    panel31.to_csv(OUT / f"{NAME_31}.csv", index=False)
    export_workbook(panel13, panel31, checks, OUT / "annual_livestock_panels_2015_2025.xlsx")
    export_sqlite(panel13, panel31, checks, OUT / "annual_livestock_panels_2015_2025.sqlite")
    print(panel13.groupby("YEAR")[["TOTAL_CATTLE", "TOTAL_SHEEP"]].sum().to_string())
    print(f"Wrote {NAME_13}, {NAME_31} (CSV), workbook and SQLite to {OUT}")


if __name__ == "__main__":
    main()
