"""Build the CSO-controlled annual ED sheep panel and 10 GOBLIN sheep cohorts, 2015-2025.

Usage: python scripts/build_sheep_annual_panel.py
"""

from __future__ import annotations

from pathlib import Path

from goblin_spatial.config import load_config
from goblin_spatial.sheep import add_sheep_cohorts
from goblin_spatial.sheep.annual_panel import build_annual_sheep_panel

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/sheep"


def main() -> None:
    cfg = load_config(CONFIG)
    panel, log = build_annual_sheep_panel(cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT / "sheep_annual_ed_panel_2015_2025.csv", index=False)
    log.to_csv(OUT / "sheep_annual_ed_panel_log.csv", index=False)

    audit = log.loc[log["RECORD_TYPE"] == "2020_SOURCE_DISCREPANCY"]
    print(audit[["Region", "ED_PUBLISHED_TOTAL", "AAA09_TOTAL", "DIFFERENCE",
                 "N_ELIGIBLE", "MAX_SEED", "MAX_SEED_SHARE_OF_GAP"]].to_string(index=False))
    print(panel.groupby("YEAR")["TOTAL_SHEEP"].sum().to_string())

    cohorts = add_sheep_cohorts(panel, cfg)
    cohorts.to_csv(OUT / "sheep_annual_ed_10_cohorts_2015_2025.csv", index=False)
    print(f"Wrote {len(panel):,} ED-year rows to {OUT}")


if __name__ == "__main__":
    main()
