"""SC1 transition, exposure and distributional diagnostics.

These metrics are reporting outputs only. They never feed back into cattle
allocation, cohort propagation or released-land spatialisation.

Standard Output (SO) remains a fixed-2020 production-value exposure measure,
not profit, income or welfare. Some EDs can gain SO or cattle locally when
endpoint composition shifts even while the national pathway contracts.
Distributional loss/reduction metrics therefore use positive-part quantities
and report gains/expansion separately rather than forcing signed values into
non-negative concentration statistics.

The parent GOBLIN released-land control and the independent pasture-DM land
balance are also reported separately. The DM balance is signed: positive values
mean an ED has lower implied livestock grassland requirement, while negative
values mean additional grassland would be required under the diagnostic.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise KeyError(column)
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    if (~np.isfinite(values)).any():
        raise ValueError(f"{column} must be finite")
    return values


def gini(values: np.ndarray | pd.Series) -> float:
    """Return the standard Gini coefficient for finite non-negative values."""

    x = np.asarray(values, dtype=float)
    if x.ndim != 1:
        raise ValueError("gini requires a one-dimensional vector")
    if (~np.isfinite(x)).any() or (x < -1e-12).any():
        raise ValueError("gini requires finite non-negative values")
    x = np.maximum(x, 0.0)
    n = len(x)
    total = float(x.sum())
    if n == 0 or total <= 1e-15:
        return 0.0
    ordered = np.sort(x)
    ranks = np.arange(1, n + 1, dtype=float)
    value = float(np.sum((2.0 * ranks - n - 1.0) * ordered) / (n * total))
    return float(np.clip(value, 0.0, 1.0))


def _top_share(values: np.ndarray, fraction: float) -> float:
    x = np.maximum(np.asarray(values, dtype=float), 0.0)
    if not 0.0 < float(fraction) <= 1.0:
        raise ValueError("fraction must lie in (0, 1]")
    total = float(x.sum())
    if len(x) == 0 or total <= 1e-15:
        return 0.0
    count = max(1, int(math.ceil(len(x) * float(fraction))))
    return float(np.sort(x)[-count:].sum() / total)


def _units_to_reach_share(values: np.ndarray, share: float) -> int:
    x = np.maximum(np.asarray(values, dtype=float), 0.0)
    if not 0.0 < float(share) <= 1.0:
        raise ValueError("share must lie in (0, 1]")
    total = float(x.sum())
    if len(x) == 0 or total <= 1e-15:
        return 0
    ordered = np.sort(x)[::-1]
    threshold = total * float(share)
    return int(np.searchsorted(np.cumsum(ordered), threshold, side="left") + 1)


def add_sc1_ed_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach transparent ED-level SC1 exposure/intensity reporting columns."""

    out = frame.copy()

    if "SO_LIVESTOCK_EXPOSURE_2020_EUR" in out.columns:
        exposure = _numeric(out, "SO_LIVESTOCK_EXPOSURE_2020_EUR")
        out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"] = np.maximum(exposure, 0.0)
        out["SO_LIVESTOCK_GAIN_2020_EUR"] = np.maximum(-exposure, 0.0)

    if "CUMULATIVE_REDUCTION_TOTAL_CATTLE" in out.columns:
        # Endpoint state defines this signed quantity as baseline minus scenario.
        # A negative value is therefore a legitimate local expansion, not an
        # invalid national-pathway result. Keep reduction and expansion as
        # separate non-negative reporting quantities.
        signed_reduction = _numeric(out, "CUMULATIVE_REDUCTION_TOTAL_CATTLE")
        out["TOTAL_CATTLE_REDUCTION_HEAD"] = np.maximum(signed_reduction, 0.0)
        out["TOTAL_CATTLE_EXPANSION_HEAD"] = np.maximum(-signed_reduction, 0.0)

    if "AGRICULTURAL_HOLDINGS" in out.columns:
        holdings = pd.to_numeric(
            out["AGRICULTURAL_HOLDINGS"], errors="coerce"
        ).to_numpy(dtype=float)
        valid_holdings = np.isfinite(holdings) & (holdings > 0)
        if "SO_LIVESTOCK_GROSS_LOSS_2020_EUR" in out.columns:
            gross_loss = out["SO_LIVESTOCK_GROSS_LOSS_2020_EUR"].to_numpy(
                dtype=float
            )
            out["SO_LIVESTOCK_GROSS_LOSS_PER_HOLDING_2020_EUR"] = np.divide(
                gross_loss,
                holdings,
                out=np.full(len(out), np.nan, dtype=float),
                where=valid_holdings,
            )
        if "TOTAL_CATTLE_REDUCTION_HEAD" in out.columns:
            cattle = out["TOTAL_CATTLE_REDUCTION_HEAD"].to_numpy(dtype=float)
            out["TOTAL_CATTLE_REDUCTION_PER_HOLDING"] = np.divide(
                cattle,
                holdings,
                out=np.full(len(out), np.nan, dtype=float),
                where=valid_holdings,
            )
        if "TOTAL_CATTLE_EXPANSION_HEAD" in out.columns:
            cattle = out["TOTAL_CATTLE_EXPANSION_HEAD"].to_numpy(dtype=float)
            out["TOTAL_CATTLE_EXPANSION_PER_HOLDING"] = np.divide(
                cattle,
                holdings,
                out=np.full(len(out), np.nan, dtype=float),
                where=valid_holdings,
            )

    if "GOBLIN_RELEASED_GRASSLAND_HA" in out.columns:
        released = _numeric(out, "GOBLIN_RELEASED_GRASSLAND_HA")
        if (released < -1e-9).any():
            raise ValueError("SC1 released grassland cannot be negative")
        released = np.maximum(released, 0.0)
        if "ALL_GRASSLAND" in out.columns:
            grass = _numeric(out, "ALL_GRASSLAND")
            if (grass < -1e-9).any():
                raise ValueError("ALL_GRASSLAND cannot be negative")
            out["GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE"] = np.divide(
                100.0 * released,
                grass,
                out=np.zeros(len(out), dtype=float),
                where=grass > 0,
            )

    dm_columns = {
        "SIGNED_GRASSLAND_BALANCE_HA",
        "POTENTIAL_SPARED_GRASSLAND_HA",
        "ADDITIONAL_GRASSLAND_REQUIRED_HA",
    }
    if dm_columns.issubset(out.columns):
        signed = _numeric(out, "SIGNED_GRASSLAND_BALANCE_HA")
        spared = _numeric(out, "POTENTIAL_SPARED_GRASSLAND_HA")
        additional = _numeric(out, "ADDITIONAL_GRASSLAND_REQUIRED_HA")
        if (spared < -1e-9).any() or (additional < -1e-9).any():
            raise ValueError("DM grassland positive-part diagnostics cannot be negative")
        spared = np.maximum(spared, 0.0)
        additional = np.maximum(additional, 0.0)
        if not np.allclose(signed, spared - additional, atol=1e-8):
            raise ValueError("DM grassland diagnostic identity does not close")
        out["DM_DIAGNOSTIC_SPATIAL_MOVEMENT_HA"] = spared + additional

        if "ALL_GRASSLAND" in out.columns:
            grass = _numeric(out, "ALL_GRASSLAND")
            out["DM_DIAGNOSTIC_POTENTIAL_RELEASE_PCT_OF_BASE"] = np.divide(
                100.0 * spared,
                grass,
                out=np.zeros(len(out), dtype=float),
                where=grass > 0,
            )
            out["DM_DIAGNOSTIC_ADDITIONAL_REQUIRED_PCT_OF_BASE"] = np.divide(
                100.0 * additional,
                grass,
                out=np.zeros(len(out), dtype=float),
                where=grass > 0,
            )

    share_columns = {
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR": "SO_GROSS_LOSS_SHARE_NATIONAL",
        "TOTAL_CATTLE_REDUCTION_HEAD": "TOTAL_CATTLE_REDUCTION_SHARE_NATIONAL",
        "TOTAL_CATTLE_EXPANSION_HEAD": "TOTAL_CATTLE_EXPANSION_SHARE_NATIONAL",
        "GOBLIN_RELEASED_GRASSLAND_HA": "RELEASED_GRASSLAND_SHARE_NATIONAL",
        "POTENTIAL_SPARED_GRASSLAND_HA": "DM_POTENTIAL_RELEASE_SHARE_NATIONAL",
        "ADDITIONAL_GRASSLAND_REQUIRED_HA": "DM_ADDITIONAL_REQUIRED_SHARE_NATIONAL",
        "DM_DIAGNOSTIC_SPATIAL_MOVEMENT_HA": "DM_SPATIAL_MOVEMENT_SHARE_NATIONAL",
    }
    for source, destination in share_columns.items():
        if source not in out.columns:
            continue
        values = pd.to_numeric(out[source], errors="raise").to_numpy(dtype=float)
        values = np.maximum(values, 0.0)
        total = float(values.sum())
        out[destination] = (
            values / total if total > 1e-15 else np.zeros(len(out))
        )

    return out


def build_sc1_national_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one-row national SC1 transition/exposure/distribution summary."""

    out = add_sc1_ed_metrics(frame)
    row: dict[str, float | int | str] = {}

    for source, destination in (
        ("PATHWAY_NAME", "SCENARIO_ID"),
        ("SCENARIO_NAME", "SCENARIO_ID"),
    ):
        if source in out.columns:
            row[destination] = str(out[source].iloc[0])
            break
    if "PATHWAY_BASELINE_YEAR" in out.columns:
        row["RUN_START_YEAR"] = int(
            pd.to_numeric(out["PATHWAY_BASELINE_YEAR"], errors="raise").iloc[0]
        )
    elif "SCENARIO_BASELINE_YEAR" in out.columns:
        row["RUN_START_YEAR"] = int(
            pd.to_numeric(out["SCENARIO_BASELINE_YEAR"], errors="raise").iloc[0]
        )
    if "MILESTONE_YEAR" in out.columns:
        row["TARGET_YEAR"] = int(
            pd.to_numeric(out["MILESTONE_YEAR"], errors="raise").iloc[0]
        )
    row["ED_COUNT"] = (
        int(out["CSOED"].nunique()) if "CSOED" in out.columns else int(len(out))
    )

    sum_columns = {
        "BASE_DAIRY_COW": "BASE_DAIRY_COWS",
        "SCENARIO_DAIRY_COW": "SCENARIO_DAIRY_COWS",
        "BASE_OTHER_COW": "BASE_SUCKLER_COWS",
        "SCENARIO_OTHER_COW": "SCENARIO_SUCKLER_COWS",
        "BASE_TOTAL_CATTLE": "BASE_TOTAL_CATTLE",
        "SCENARIO_TOTAL_CATTLE": "SCENARIO_TOTAL_CATTLE",
        # Preserve the historical national field as the signed/net national
        # reduction while adding explicit gross spatial-incidence quantities.
        "CUMULATIVE_REDUCTION_TOTAL_CATTLE": "TOTAL_CATTLE_REDUCTION_HEAD",
        "TOTAL_CATTLE_REDUCTION_HEAD": "GROSS_TOTAL_CATTLE_REDUCTION_HEAD",
        "TOTAL_CATTLE_EXPANSION_HEAD": "GROSS_TOTAL_CATTLE_EXPANSION_HEAD",
        "BASE_SO_LIVESTOCK_2020_EUR": "BASE_SO_LIVESTOCK_2020_EUR",
        "SCENARIO_SO_LIVESTOCK_2020_EUR": "SCENARIO_SO_LIVESTOCK_2020_EUR",
        "SO_LIVESTOCK_EXPOSURE_2020_EUR": "NET_SO_LIVESTOCK_EXPOSURE_2020_EUR",
        "SO_LIVESTOCK_GROSS_LOSS_2020_EUR": "GROSS_SO_LIVESTOCK_LOSS_2020_EUR",
        "SO_LIVESTOCK_GAIN_2020_EUR": "GROSS_SO_LIVESTOCK_GAIN_2020_EUR",
        "GOBLIN_RELEASED_GRASSLAND_HA": "GOBLIN_RELEASED_GRASSLAND_HA",
        "SIGNED_GRASSLAND_BALANCE_HA": "DM_DIAGNOSTIC_NET_LAND_RELEASE_HA",
        "POTENTIAL_SPARED_GRASSLAND_HA": "DM_DIAGNOSTIC_GROSS_POTENTIAL_RELEASE_HA",
        "ADDITIONAL_GRASSLAND_REQUIRED_HA": "DM_DIAGNOSTIC_GROSS_ADDITIONAL_REQUIRED_HA",
        "DM_DIAGNOSTIC_SPATIAL_MOVEMENT_HA": "DM_DIAGNOSTIC_GROSS_SPATIAL_MOVEMENT_HA",
    }
    for column, name in sum_columns.items():
        if column in out.columns:
            row[name] = float(pd.to_numeric(out[column], errors="raise").sum())
    if "CUMULATIVE_REDUCTION_TOTAL_CATTLE" in out.columns:
        row["NET_TOTAL_CATTLE_REDUCTION_HEAD"] = float(
            pd.to_numeric(
                out["CUMULATIVE_REDUCTION_TOTAL_CATTLE"], errors="raise"
            ).sum()
        )

    if {
        "GOBLIN_RELEASED_GRASSLAND_HA",
        "DM_DIAGNOSTIC_NET_LAND_RELEASE_HA",
    }.issubset(row):
        row["GOBLIN_MINUS_DM_DIAGNOSTIC_NET_RELEASE_HA"] = (
            float(row["GOBLIN_RELEASED_GRASSLAND_HA"])
            - float(row["DM_DIAGNOSTIC_NET_LAND_RELEASE_HA"])
        )

    if "DM_DIAGNOSTIC_NET_LAND_RELEASE_HA" in row:
        net = float(row["DM_DIAGNOSTIC_NET_LAND_RELEASE_HA"])
        gross_movement = float(
            row.get("DM_DIAGNOSTIC_GROSS_SPATIAL_MOVEMENT_HA", 0.0)
        )
        row["DM_DIAGNOSTIC_GROSS_MOVEMENT_TO_ABS_NET_RATIO"] = (
            gross_movement / abs(net) if abs(net) > 1e-12 else np.nan
        )

    if "BASE_SO_LIVESTOCK_2020_EUR" in out.columns:
        base_so = np.maximum(_numeric(out, "BASE_SO_LIVESTOCK_2020_EUR"), 0.0)
        scenario_so = np.maximum(
            _numeric(out, "SCENARIO_SO_LIVESTOCK_2020_EUR"), 0.0
        )
        row["GINI_BASE_SO_LIVESTOCK"] = gini(base_so)
        row["GINI_SCENARIO_SO_LIVESTOCK"] = gini(scenario_so)
        row["DELTA_GINI_SO_LIVESTOCK"] = (
            row["GINI_SCENARIO_SO_LIVESTOCK"] - row["GINI_BASE_SO_LIVESTOCK"]
        )

    diagnostic_vectors = {
        "SO_LOSS": "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
        "TOTAL_CATTLE_REDUCTION": "TOTAL_CATTLE_REDUCTION_HEAD",
        "TOTAL_CATTLE_EXPANSION": "TOTAL_CATTLE_EXPANSION_HEAD",
        "ADULT_CATTLE_REDUCTION": "REDUCTION_ADULT_COWS",
        "RELEASED_GRASSLAND": "GOBLIN_RELEASED_GRASSLAND_HA",
        "DM_POTENTIAL_RELEASE": "POTENTIAL_SPARED_GRASSLAND_HA",
        "DM_ADDITIONAL_GRASSLAND": "ADDITIONAL_GRASSLAND_REQUIRED_HA",
        "DM_SPATIAL_MOVEMENT": "DM_DIAGNOSTIC_SPATIAL_MOVEMENT_HA",
    }
    for label, column in diagnostic_vectors.items():
        if column not in out.columns:
            continue
        values = _numeric(out, column)
        if (values < -1e-9).any():
            raise ValueError(
                f"{column} cannot be negative for SC1 distribution metrics"
            )
        values = np.maximum(values, 0.0)
        row[f"GINI_{label}"] = gini(values)
        row[f"TOP_10PCT_ED_SHARE_{label}"] = _top_share(values, 0.10)
        row[f"TOP_20PCT_ED_SHARE_{label}"] = _top_share(values, 0.20)
        row[f"EDS_FOR_50PCT_{label}"] = _units_to_reach_share(values, 0.50)
        row[f"EDS_FOR_80PCT_{label}"] = _units_to_reach_share(values, 0.80)
        row[f"EDS_WITH_POSITIVE_{label}"] = int((values > 1e-12).sum())

    if "SO_LIVESTOCK_EXPOSURE_2020_EUR" in out.columns:
        exposure = _numeric(out, "SO_LIVESTOCK_EXPOSURE_2020_EUR")
        row["EDS_WITH_SO_LOSS"] = int((exposure > 1e-9).sum())
        row["EDS_WITH_SO_GAIN"] = int((exposure < -1e-9).sum())
        row["EDS_WITH_NO_MATERIAL_SO_CHANGE"] = int(
            (np.abs(exposure) <= 1e-9).sum()
        )

    if "ADDITIONAL_GRASSLAND_REQUIRED_HA" in out.columns:
        additional = _numeric(out, "ADDITIONAL_GRASSLAND_REQUIRED_HA")
        additional_mask = additional > 1e-9
        row["EDS_WITH_ADDITIONAL_GRASSLAND_REQUIREMENT"] = int(
            additional_mask.sum()
        )
        if "TOTAL_CATTLE_EXPANSION_HEAD" in out.columns:
            cattle_expansion = _numeric(out, "TOTAL_CATTLE_EXPANSION_HEAD") > 1e-9
            row["EDS_WITH_BOTH_ADDITIONAL_GRASSLAND_AND_CATTLE_EXPANSION"] = int(
                (additional_mask & cattle_expansion).sum()
            )
        if {"BASE_DAIRY_COW", "SCENARIO_DAIRY_COW"}.issubset(out.columns):
            dairy_expansion = (
                _numeric(out, "SCENARIO_DAIRY_COW")
                > _numeric(out, "BASE_DAIRY_COW") + 1e-9
            )
            row["EDS_WITH_BOTH_ADDITIONAL_GRASSLAND_AND_DAIRY_EXPANSION"] = int(
                (additional_mask & dairy_expansion).sum()
            )

    return pd.DataFrame([row])


def build_sc1_county_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate SC1 physical, SO and land-pressure incidence to county level."""

    if "County" not in frame.columns:
        raise ValueError("SC1 county summary requires County")
    out = add_sc1_ed_metrics(frame)
    value_columns = [
        column
        for column in (
            "BASE_DAIRY_COW",
            "SCENARIO_DAIRY_COW",
            "BASE_OTHER_COW",
            "SCENARIO_OTHER_COW",
            "BASE_TOTAL_CATTLE",
            "SCENARIO_TOTAL_CATTLE",
            "TOTAL_CATTLE_REDUCTION_HEAD",
            "TOTAL_CATTLE_EXPANSION_HEAD",
            "BASE_SO_LIVESTOCK_2020_EUR",
            "SCENARIO_SO_LIVESTOCK_2020_EUR",
            "SO_LIVESTOCK_EXPOSURE_2020_EUR",
            "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
            "SO_LIVESTOCK_GAIN_2020_EUR",
            "GOBLIN_RELEASED_GRASSLAND_HA",
            "SIGNED_GRASSLAND_BALANCE_HA",
            "POTENTIAL_SPARED_GRASSLAND_HA",
            "ADDITIONAL_GRASSLAND_REQUIRED_HA",
            "DM_DIAGNOSTIC_SPATIAL_MOVEMENT_HA",
            "AGRICULTURAL_HOLDINGS",
            "ALL_GRASSLAND",
        )
        if column in out.columns
    ]
    summary = out.groupby("County", as_index=False)[value_columns].sum(
        numeric_only=True
    )
    summary["ED_COUNT"] = (
        out.groupby("County")["CSOED"]
        .nunique()
        .reindex(summary["County"])
        .to_numpy()
    )
    if {"BASE_TOTAL_CATTLE", "SCENARIO_TOTAL_CATTLE"}.issubset(summary.columns):
        summary["NET_TOTAL_CATTLE_REDUCTION_HEAD"] = (
            summary["BASE_TOTAL_CATTLE"] - summary["SCENARIO_TOTAL_CATTLE"]
        )
    if {
        "GOBLIN_RELEASED_GRASSLAND_HA",
        "SIGNED_GRASSLAND_BALANCE_HA",
    }.issubset(summary.columns):
        summary["GOBLIN_MINUS_DM_DIAGNOSTIC_NET_RELEASE_HA"] = (
            summary["GOBLIN_RELEASED_GRASSLAND_HA"]
            - summary["SIGNED_GRASSLAND_BALANCE_HA"]
        )

    for source, destination in (
        (
            "SO_LIVESTOCK_GROSS_LOSS_2020_EUR",
            "COUNTY_SHARE_NATIONAL_SO_GROSS_LOSS",
        ),
        (
            "TOTAL_CATTLE_REDUCTION_HEAD",
            "COUNTY_SHARE_NATIONAL_CATTLE_REDUCTION",
        ),
        (
            "TOTAL_CATTLE_EXPANSION_HEAD",
            "COUNTY_SHARE_NATIONAL_CATTLE_EXPANSION",
        ),
        (
            "GOBLIN_RELEASED_GRASSLAND_HA",
            "COUNTY_SHARE_NATIONAL_RELEASED_GRASSLAND",
        ),
        (
            "POTENTIAL_SPARED_GRASSLAND_HA",
            "COUNTY_SHARE_NATIONAL_DM_POTENTIAL_RELEASE",
        ),
        (
            "ADDITIONAL_GRASSLAND_REQUIRED_HA",
            "COUNTY_SHARE_NATIONAL_DM_ADDITIONAL_REQUIRED",
        ),
    ):
        if source not in summary.columns:
            continue
        total = float(summary[source].sum())
        summary[destination] = summary[source] / total if total > 1e-15 else 0.0

    return summary.sort_values("County", kind="stable").reset_index(drop=True)
