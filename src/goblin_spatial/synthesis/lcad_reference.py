"""LCAD 2.02 feedstock reference utilities.

This module exposes a small, read-only bridge between GOBLIN-Spatial and
agricultural feedstock characteristics extracted from the LCAD 2.02 workbook.

It does not reproduce the LCAD process model and is not used by the historical
baseline pipeline. It only converts an already-estimated dry-matter resource
quantity into transparent technical reference quantities.

Source
------
Martinez-Arce, A., O'Flaherty, V., & Styles, D. (2026).
Critical evaluation of prospective biorefinery configurations to deliver a
circular, climate neutral economy. Resources, Conservation and Recycling,
231, 108907. https://doi.org/10.1016/j.resconrec.2026.108907

Workbook: LCAD 2.02 - LCI tool of AD biorefineries.xlsx
Version 2.02 (March 2026).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_REFERENCE_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "inputs"
    / "reference"
    / "lcad_feedstock_characteristics.csv"
)


def load_lcad_feedstock_reference(path: str | Path | None = None) -> pd.DataFrame:
    """Load the frozen LCAD feedstock reference table."""
    reference_path = Path(path) if path is not None else DEFAULT_REFERENCE_PATH
    df = pd.read_csv(reference_path)
    required = {
        "feedstock",
        "methane_yield_m3_ch4_per_t_dm",
        "dm_fraction",
        "total_n_kg_per_t_dm",
        "p2o5_kg_per_t_dm",
        "k2o_kg_per_t_dm",
        "total_carbon_kg_per_t_dm",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"LCAD reference table missing columns: {sorted(missing)}")
    return df


def feedstock_record(
    feedstock: str,
    reference: pd.DataFrame | None = None,
) -> pd.Series:
    """Return exactly one LCAD reference record by feedstock name."""
    ref = load_lcad_feedstock_reference() if reference is None else reference
    key = feedstock.strip().casefold()
    matched = ref.loc[ref["feedstock"].astype(str).str.casefold() == key]
    if len(matched) != 1:
        raise KeyError(
            f"Expected one LCAD feedstock named {feedstock!r}; found {len(matched)}."
        )
    return matched.iloc[0]


def technical_potential_from_dm(
    feedstock: str,
    dry_matter_t: float,
    reference: pd.DataFrame | None = None,
) -> dict[str, float | str]:
    """Convert a feedstock dry-matter quantity into LCAD reference potentials.

    Parameters
    ----------
    feedstock:
        Feedstock name in the frozen LCAD reference table.
    dry_matter_t:
        Feedstock dry matter in tonnes. This quantity must be estimated outside
        this module. For manure, no housing, collection or recoverability
        fraction is inferred here.

    Returns
    -------
    dict
        Technical reference quantities. These are not realised AD outputs.
    """
    if dry_matter_t < 0:
        raise ValueError("dry_matter_t must be non-negative")

    r = feedstock_record(feedstock, reference)
    dm = float(dry_matter_t)
    dm_fraction = float(r["dm_fraction"])

    return {
        "feedstock": str(r["feedstock"]),
        "dry_matter_t": dm,
        "fresh_matter_t": dm / dm_fraction if dm_fraction > 0 else float("nan"),
        "methane_potential_m3_ch4": dm
        * float(r["methane_yield_m3_ch4_per_t_dm"]),
        "total_n_kg": dm * float(r["total_n_kg_per_t_dm"]),
        "p2o5_kg": dm * float(r["p2o5_kg_per_t_dm"]),
        "k2o_kg": dm * float(r["k2o_kg_per_t_dm"]),
        "total_carbon_kg": dm * float(r["total_carbon_kg_per_t_dm"]),
    }


def add_lcad_reference_potentials(
    resources: pd.DataFrame,
    *,
    feedstock_col: str = "feedstock",
    dry_matter_col: str = "dry_matter_t",
    reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach LCAD technical reference quantities to a resource table.

    The input table must already contain the spatially estimated feedstock
    quantity in tonnes of dry matter. This function does not estimate manure
    recoverability, crop residue availability, collection losses, transport
    radii, plant capacity or adoption.
    """
    if feedstock_col not in resources or dry_matter_col not in resources:
        raise KeyError(
            f"resources must contain {feedstock_col!r} and {dry_matter_col!r}"
        )

    ref = load_lcad_feedstock_reference() if reference is None else reference
    cols = [
        "feedstock",
        "methane_yield_m3_ch4_per_t_dm",
        "dm_fraction",
        "total_n_kg_per_t_dm",
        "p2o5_kg_per_t_dm",
        "k2o_kg_per_t_dm",
        "total_carbon_kg_per_t_dm",
    ]
    lookup = ref[cols].copy()

    out = resources.copy()
    if feedstock_col != "feedstock":
        lookup = lookup.rename(columns={"feedstock": feedstock_col})

    out = out.merge(lookup, on=feedstock_col, how="left", validate="many_to_one")
    if out["methane_yield_m3_ch4_per_t_dm"].isna().any():
        missing = sorted(
            out.loc[
                out["methane_yield_m3_ch4_per_t_dm"].isna(), feedstock_col
            ]
            .astype(str)
            .unique()
        )
        raise KeyError(f"Unknown LCAD feedstock(s): {missing}")

    dm = out[dry_matter_col].astype(float)
    if (dm < 0).any():
        raise ValueError(f"{dry_matter_col} must be non-negative")

    out["fresh_matter_t"] = dm / out["dm_fraction"]
    out["methane_potential_m3_ch4"] = (
        dm * out["methane_yield_m3_ch4_per_t_dm"]
    )
    out["total_n_kg"] = dm * out["total_n_kg_per_t_dm"]
    out["p2o5_kg"] = dm * out["p2o5_kg_per_t_dm"]
    out["k2o_kg"] = dm * out["k2o_kg_per_t_dm"]
    out["total_carbon_kg"] = dm * out["total_carbon_kg_per_t_dm"]
    return out
