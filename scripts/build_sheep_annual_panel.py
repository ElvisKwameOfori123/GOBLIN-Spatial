"""Build the final CSO sheep panel and the derived 10-cohort sheep layer.

The CSO panel is built first and remains the statistical baseline. The
10-cohort layer is then derived from it without changing any CSO sheep
control. National GOBLIN/COHORTS calibration remains a later, separate stage.

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

    print(
        f"Wrote {len(panel):,} CSO-controlled sheep ED-year rows and audit log to {OUT}"
    )

    cohorts = add_sheep_cohorts(panel, cfg)
    cohorts.to_csv(OUT / "sheep_annual_ed_10_cohorts_2015_2025.csv", index=False)
    print(
        f"Wrote {len(cohorts):,} ED-year rows with the 10 derived sheep cohorts"
    )


if __name__ == "__main__":
    main()
