"""Build the CSO-only annual ED cattle panel 2015-2025 and write it to disk.

Usage: python scripts/build_cattle_annual_panel.py
"""

from __future__ import annotations

from pathlib import Path

from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ireland_2015_2025.yaml"
OUT = ROOT / "data/processed/cattle"


def main() -> None:
    cfg = load_config(CONFIG)
    panel, log = build_annual_ed_panel(cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT / "cattle_annual_ed_panel_2015_2025.csv", index=False)
    log.to_csv(OUT / "cattle_annual_ed_panel_calibration_log.csv", index=False)
    totals = panel.groupby("YEAR")[["DAIRY_COW", "OTHER_COW", "OTHER_CATTLE", "TOTAL_CATTLE"]].sum()
    print(totals.to_string())
    print(f"Wrote {len(panel):,} rows to {OUT}")


if __name__ == "__main__":
    main()
