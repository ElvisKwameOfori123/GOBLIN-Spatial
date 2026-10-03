#!/usr/bin/env python
"""Build Paper 1 Figure 2: historical cattle structural turnover, 2015-2025.

Panel (a): national total cattle, dairy cows and suckler cows indexed to 2015 = 100.
Panel (b): national follower-origin composition (DxD, DxB, BxB) in 2015, 2020 and 2025.

The figure is derived directly from the released GOBLIN 31-cohort historical panel.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import BXB_COHORTS, DXB_COHORTS, DXD_COHORTS
from goblin_spatial.config import load_config


def _configured_output(cfg, key: str, default: str) -> Path:
    raw = cfg.raw.get("outputs", {}).get(key, default)
    path = Path(raw)
    return path if path.is_absolute() else cfg.project_root / path


def build_national_series(master: pd.DataFrame) -> pd.DataFrame:
    required = {
        "YEAR",
        "TOTAL_CATTLE",
        "DAIRY_COW",
        "OTHER_COW",
        *DXD_COHORTS,
        *DXB_COHORTS,
        *BXB_COHORTS,
    }
    missing = sorted(required - set(master.columns))
    if missing:
        raise ValueError(f"historical master missing required columns: {missing}")

    work = master.copy()
    work["YEAR"] = pd.to_numeric(work["YEAR"], errors="raise").astype(int)
    numeric = [column for column in required if column != "YEAR"]
    work[numeric] = work[numeric].apply(pd.to_numeric, errors="raise")

    national = work.groupby("YEAR", as_index=False, sort=True)[
        ["TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW", *DXD_COHORTS, *DXB_COHORTS, *BXB_COHORTS]
    ].sum()

    national["DxD"] = national[list(DXD_COHORTS)].sum(axis=1)
    national["DxB"] = national[list(DXB_COHORTS)].sum(axis=1)
    national["BxB"] = national[list(BXB_COHORTS)].sum(axis=1)
    national["FOLLOWER_ORIGIN_TOTAL"] = national[["DxD", "DxB", "BxB"]].sum(axis=1)

    for origin in ("DxD", "DxB", "BxB"):
        national[f"{origin}_SHARE_PCT"] = np.where(
            national["FOLLOWER_ORIGIN_TOTAL"] > 0,
            national[origin] / national["FOLLOWER_ORIGIN_TOTAL"] * 100.0,
            np.nan,
        )

    base = national.loc[national["YEAR"] == 2015]
    if len(base) != 1:
        raise AssertionError("expected exactly one 2015 national row")
    for column in ("TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW"):
        denominator = float(base.iloc[0][column])
        if denominator <= 0:
            raise AssertionError(f"2015 {column} is not positive")
        national[f"{column}_INDEX_2015"] = national[column] / denominator * 100.0

    return national


def draw_figure(national: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))

    # Panel (a): indexed national cattle structure.
    ax = axes[0]
    ax.plot(national["YEAR"], national["TOTAL_CATTLE_INDEX_2015"], marker="o", label="Total cattle")
    ax.plot(national["YEAR"], national["DAIRY_COW_INDEX_2015"], marker="o", label="Dairy cows")
    ax.plot(national["YEAR"], national["OTHER_COW_INDEX_2015"], marker="o", label="Suckler cows")
    ax.axhline(100.0, linewidth=0.8, linestyle="--")
    ax.set_xlabel("Year")
    ax.set_ylabel("Index (2015 = 100)")
    ax.set_title("(a) National cattle structure")
    ax.set_xticks([2015, 2020, 2025])
    ax.legend(frameon=False)

    # Panel (b): follower-origin composition at the three anchor years.
    anchor = national.loc[national["YEAR"].isin([2015, 2020, 2025])].copy()
    if anchor["YEAR"].tolist() != [2015, 2020, 2025]:
        raise AssertionError("national series must contain 2015, 2020 and 2025")

    ax = axes[1]
    x = np.arange(len(anchor))
    bottom = np.zeros(len(anchor), dtype=float)
    for origin, label in (("DxD", "DxD"), ("DxB", "DxB"), ("BxB", "BxB")):
        values = anchor[f"{origin}_SHARE_PCT"].to_numpy(dtype=float)
        ax.bar(x, values, bottom=bottom, label=label)
        bottom += values

    ax.set_xticks(x, anchor["YEAR"].astype(str))
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of lineage-assigned followers (%)")
    ax.set_title("(b) Follower-origin composition")
    ax.legend(frameon=False)

    fig.suptitle("Historical structural turnover in the Irish cattle population, 2015-2025", y=1.02)
    fig.tight_layout()

    png = output_dir / "figure2_historical_structural_turnover.png"
    pdf = output_dir / "figure2_historical_structural_turnover.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)


def write_source_table(national: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    keep = [
        "YEAR",
        "TOTAL_CATTLE",
        "DAIRY_COW",
        "OTHER_COW",
        "TOTAL_CATTLE_INDEX_2015",
        "DAIRY_COW_INDEX_2015",
        "OTHER_COW_INDEX_2015",
        "DxD",
        "DxB",
        "BxB",
        "DxD_SHARE_PCT",
        "DxB_SHARE_PCT",
        "BxB_SHARE_PCT",
    ]
    national[keep].to_csv(output_dir / "figure2_historical_structural_turnover_data.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Paper 1 historical-turnover figure.")
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    parser.add_argument("--output-dir", default="reporting/paper1/figures")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    master_path = _configured_output(
        cfg,
        "standard_output_master",
        "data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv",
    )
    if not master_path.exists():
        raise FileNotFoundError(
            f"{master_path} does not exist. Run the historical baseline build first."
        )

    master = pd.read_csv(master_path)
    national = build_national_series(master)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = cfg.project_root / output_dir

    draw_figure(national, output_dir)
    write_source_table(national, output_dir)

    anchor = national.loc[national["YEAR"].isin([2015, 2020, 2025]), [
        "YEAR", "TOTAL_CATTLE", "DAIRY_COW", "OTHER_COW", "DxD", "DxB", "BxB",
        "DxD_SHARE_PCT", "DxB_SHARE_PCT", "BxB_SHARE_PCT",
    ]]
    print(anchor.to_string(index=False))
    print(f"Wrote Figure 2 and source data to: {output_dir}")


if __name__ == "__main__":
    main()
