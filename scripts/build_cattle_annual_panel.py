"""Build the CSO-only annual ED cattle panel and its age-sex split, 2015-2025.

Usage: python scripts/build_cattle_annual_panel.py
"""

from __future__ import annotations

from pathlib import Path

from goblin_spatial.cattle.annual_age_sex import build_annual_age_sex_panel, lsu_check_2020
from goblin_spatial.cattle.annual_panel import build_annual_ed_panel
from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS, add_cattle_cohorts
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
    age_sex = build_annual_age_sex_panel(cfg, panel)
    age_sex.to_csv(OUT / "cattle_annual_ed_age_sex_2015_2025.csv", index=False)
    print("2020 LSU check:", lsu_check_2020(cfg, age_sex))

    cohorts = add_cattle_cohorts(age_sex, cfg)
    cohorts.to_csv(OUT / "cattle_annual_ed_21_cohorts_2015_2025.csv", index=False)

    y2020 = cohorts.loc[cohorts["YEAR"] == 2020]
    young_containers = [
        "CATTLE_MALE_UNDER_1",
        "CATTLE_FEMALE_UNDER_1",
        "CATTLE_MALE_1_2",
        "CATTLE_FEMALE_1_2",
    ]
    dxd_young = [CONTAINERS[c]["DxD"] for c in young_containers]
    dxb_young = [CONTAINERS[c]["DxB"] for c in young_containers]

    zero_dairy = y2020["DAIRY_COW"].eq(0)
    suckler_only = zero_dairy & y2020["OTHER_COW"].gt(0)
    dxd_total = float(y2020[dxd_young].to_numpy().sum())
    dxb_total = float(y2020[dxb_young].to_numpy().sum())
    dxd_no_dairy = (
        float(y2020.loc[zero_dairy, dxd_young].to_numpy().sum()) / dxd_total
        if dxd_total > 0
        else float("nan")
    )
    dxb_suckler_only = (
        float(y2020.loc[suckler_only, dxb_young].to_numpy().sum()) / dxb_total
        if dxb_total > 0
        else float("nan")
    )
    print(
        "2020 genetics movement:",
        {
            "DxD_young_in_zero_dairy_EDs": dxd_no_dairy,
            "DxB_young_in_suckler_only_EDs": dxb_suckler_only,
        },
    )
    print(
        f"Wrote {len(panel):,} rows for annual panel, age-sex and "
        f"{len(FINAL_21_COHORTS)}-cohort cattle outputs to {OUT}"
    )


if __name__ == "__main__":
    main()
