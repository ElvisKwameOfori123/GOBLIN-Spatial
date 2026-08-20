"""DAFM county sheep-share drift used by the final sheep reconstruction.

DAFM is used only as relative spatial information. CSO AAA09 remains the
population authority. For county c and year t, the model uses

    delta[c,t] = s[c,t] / s[c,2020]

where s is the county share of the DAFM national flock. Observed DAFM anchors
are retained, intermediate county shares are linearly interpolated and
renormalised, and the resulting drift factors reweight the reconciled 2020 CSO
county anchors inside each AAA09 detailed region.

This module deliberately contains no ED allocation logic. It prepares the
county-year relative weights consumed by the regional -> county -> ED sheep
hierarchy.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


MODEL_YEARS = tuple(range(2015, 2026))
ANCHOR_YEARS = (2015, 2020, 2022, 2025)


def _normalise_county(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("Co.", "").replace("County", "")
    return " ".join(text.split()).title()


def load_dafm_county_sheep_anchors(path: str | Path) -> pd.DataFrame:
    """Load and validate the frozen DAFM county sheep-total anchors.

    The canonical frozen file contains ``YEAR``, ``County`` and ``TOTAL``.
    Counts are used to calculate county shares only. Their national level is
    never substituted for the AAA09 sheep population.
    """

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    frame = pd.read_csv(source)
    frame.columns = [str(column).strip().lstrip("\ufeff") for column in frame.columns]
    required = {"YEAR", "County", "TOTAL"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"DAFM county sheep anchors missing columns: {missing}")

    frame = frame[["YEAR", "County", "TOTAL"]].copy()
    frame["YEAR"] = pd.to_numeric(frame["YEAR"], errors="raise").astype(int)
    frame["County"] = frame["County"].map(_normalise_county)
    frame["TOTAL"] = pd.to_numeric(frame["TOTAL"], errors="raise")

    if frame["County"].eq("").any():
        raise ValueError("DAFM county sheep anchors contain a blank county")
    if frame["TOTAL"].isna().any() or (frame["TOTAL"] < 0).any():
        raise ValueError("DAFM county sheep anchors contain invalid totals")
    if frame[["YEAR", "County"]].duplicated().any():
        raise AssertionError("duplicate DAFM YEAR-County sheep anchor")
    if tuple(sorted(frame["YEAR"].unique())) != ANCHOR_YEARS:
        raise AssertionError(
            f"DAFM county sheep anchor years must be exactly {ANCHOR_YEARS}"
        )

    counties = sorted(frame["County"].unique())
    if len(counties) != 26:
        raise AssertionError(f"expected 26 DAFM counties; found {len(counties)}")
    expected_rows = len(ANCHOR_YEARS) * len(counties)
    if len(frame) != expected_rows:
        raise AssertionError(
            f"expected {expected_rows} DAFM county-year anchors; found {len(frame)}"
        )

    coverage = frame.groupby("YEAR")["County"].nunique()
    if not (coverage == 26).all():
        raise AssertionError("every DAFM anchor year must contain all 26 counties")
    if (frame.groupby("YEAR")["TOTAL"].sum() <= 0).any():
        raise AssertionError("DAFM national sheep total must be positive in every anchor year")

    return frame.sort_values(["YEAR", "County"], kind="stable").reset_index(drop=True)


def _interpolation_bounds(year: int) -> tuple[int, int, float, str]:
    year = int(year)
    if year not in MODEL_YEARS:
        raise ValueError(f"year outside sheep drift model window: {year}")
    if year in ANCHOR_YEARS:
        return year, year, 0.0, "OBSERVED_DAFM"

    for start, end in zip(ANCHOR_YEARS[:-1], ANCHOR_YEARS[1:]):
        if start < year < end:
            alpha = (year - start) / (end - start)
            return start, end, float(alpha), f"INTERPOLATED_DAFM_{start}_{end}"
    raise AssertionError(f"no DAFM interpolation interval for {year}")


def build_annual_dafm_county_drift(anchors: pd.DataFrame) -> pd.DataFrame:
    """Return annual county shares and 2020-relative DAFM drift factors.

    Linear interpolation is performed on county shares, not animal counts.
    Interpolated shares are renormalised to one each year. Consequently the
    operator captures movement in the county distribution while remaining
    independent of differences in national population level between DAFM and
    CSO AAA09.
    """

    required = {"YEAR", "County", "TOTAL"}
    missing = sorted(required - set(anchors.columns))
    if missing:
        raise ValueError(f"DAFM anchor table missing columns: {missing}")

    source = anchors.copy()
    source["YEAR"] = pd.to_numeric(source["YEAR"], errors="raise").astype(int)
    source["County"] = source["County"].map(_normalise_county)
    source["TOTAL"] = pd.to_numeric(source["TOTAL"], errors="raise")
    if source[["YEAR", "County"]].duplicated().any():
        raise AssertionError("duplicate DAFM YEAR-County sheep anchor")

    pivot = source.pivot(index="County", columns="YEAR", values="TOTAL")
    if tuple(sorted(int(value) for value in pivot.columns)) != ANCHOR_YEARS:
        raise AssertionError("DAFM drift input does not contain the four required anchor years")
    if len(pivot) != 26 or pivot.isna().any().any():
        raise AssertionError("DAFM drift input must contain all 26 counties at every anchor")

    anchor_shares = pivot.div(pivot.sum(axis=0), axis=1)
    if (anchor_shares[2020] <= 0).any():
        bad = anchor_shares.index[anchor_shares[2020] <= 0].tolist()
        raise ValueError(f"2020 DAFM share is zero for counties: {bad}")

    rows: list[dict[str, object]] = []
    for year in MODEL_YEARS:
        start, end, alpha, status = _interpolation_bounds(year)
        if start == end:
            shares = anchor_shares[start].astype(float).copy()
        else:
            shares = (
                anchor_shares[start].astype(float)
                + alpha * (anchor_shares[end].astype(float) - anchor_shares[start].astype(float))
            )
            total = float(shares.sum())
            if total <= 0:
                raise AssertionError(f"interpolated DAFM shares sum to zero in {year}")
            shares = shares / total

        if (shares < -1e-12).any():
            raise AssertionError(f"negative interpolated DAFM county share in {year}")
        shares = shares.clip(lower=0.0)
        shares = shares / float(shares.sum())

        for county, share in shares.items():
            share_2020 = float(anchor_shares.loc[county, 2020])
            drift = float(share) / share_2020
            rows.append(
                {
                    "YEAR": int(year),
                    "County": str(county),
                    "DAFM_COUNTY_SHARE": float(share),
                    "DAFM_2020_COUNTY_SHARE": share_2020,
                    "DAFM_DRIFT_FACTOR": drift,
                    "SOURCE_STATUS": status,
                    "ANCHOR_START_YEAR": int(start),
                    "ANCHOR_END_YEAR": int(end),
                }
            )

    annual = pd.DataFrame(rows).sort_values(["YEAR", "County"], kind="stable")
    annual = annual.reset_index(drop=True)

    share_closure = annual.groupby("YEAR")["DAFM_COUNTY_SHARE"].sum()
    if not np.allclose(share_closure.to_numpy(dtype=float), 1.0, atol=1e-12, rtol=0.0):
        raise AssertionError("annual DAFM county shares do not close to one")

    drift_2020 = annual.loc[annual["YEAR"] == 2020, "DAFM_DRIFT_FACTOR"].to_numpy(dtype=float)
    if not np.allclose(drift_2020, 1.0, atol=0.0, rtol=0.0):
        raise AssertionError("2020 DAFM drift factors must equal one exactly")

    for year in ANCHOR_YEARS:
        observed = annual.loc[annual["YEAR"] == year].set_index("County")["DAFM_COUNTY_SHARE"]
        target = anchor_shares[year].sort_index()
        observed = observed.reindex(target.index)
        if not np.allclose(observed.to_numpy(), target.to_numpy(), atol=1e-15, rtol=0.0):
            raise AssertionError(f"observed DAFM share anchor changed in {year}")

    return annual


def drifted_county_weights(
    county_anchor: pd.DataFrame,
    annual_drift: pd.DataFrame,
    *,
    year: int,
    region: str,
) -> np.ndarray:
    """Reweight reconciled 2020 county anchors by DAFM relative movement.

    Returned values are continuous weights for Hamilton allocation to the
    authoritative AAA09 regional total. In 2020 they are exactly the reconciled
    CSO county anchor weights because every DAFM drift factor equals one.
    """

    required_anchor = {"County", "Region", "TOTAL_SHEEP_2020_RECONCILED"}
    missing = sorted(required_anchor - set(county_anchor.columns))
    if missing:
        raise ValueError(f"county sheep anchor missing columns: {missing}")

    counties = (
        county_anchor.loc[county_anchor["Region"] == region]
        .sort_values("County", kind="stable")
        .reset_index(drop=True)
    )
    if counties.empty:
        raise ValueError(f"no county sheep anchors for region {region!r}")

    drift = annual_drift.loc[annual_drift["YEAR"] == int(year), ["County", "DAFM_DRIFT_FACTOR"]].copy()
    if drift["County"].duplicated().any():
        raise AssertionError(f"duplicate DAFM drift county in {year}")
    joined = counties[["County", "TOTAL_SHEEP_2020_RECONCILED"]].merge(
        drift,
        on="County",
        how="left",
        validate="one_to_one",
    )
    if joined["DAFM_DRIFT_FACTOR"].isna().any():
        missing_counties = joined.loc[joined["DAFM_DRIFT_FACTOR"].isna(), "County"].tolist()
        raise AssertionError(f"missing DAFM drift factors for counties: {missing_counties}")

    base = pd.to_numeric(joined["TOTAL_SHEEP_2020_RECONCILED"], errors="raise").to_numpy(dtype=float)
    factor = pd.to_numeric(joined["DAFM_DRIFT_FACTOR"], errors="raise").to_numpy(dtype=float)
    weights = base * factor
    if (~np.isfinite(weights)).any() or (weights < 0).any() or float(weights.sum()) <= 0:
        raise AssertionError(f"invalid drifted county sheep weights for {region} {year}")

    if int(year) == 2020 and not np.array_equal(weights, base):
        raise AssertionError("DAFM drift changed the reconciled 2020 county sheep anchor")
    return weights
