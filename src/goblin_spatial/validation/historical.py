"""Transparent validation diagnostics for the historical GOBLIN-Spatial baseline.

These routines distinguish three things that should not be conflated:

1. accounting verification: identities and controlling totals close;
2. external/applied validation: comparison with evidence not mechanically
   imposed by the reconstruction;
3. reconstruction diagnostics: holdout and temporal-stability checks.

No arbitrary composite validation score is created here.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

from goblin_spatial.baseline.signatures import BXB_COHORTS, DXB_COHORTS, DXD_COHORTS, FOLLOWER_COHORTS


ACHILL_VARIABLE_MAP = {
    "DAIRY_COW": "Dairy cows total",
    "OTHER_COW": "Other cows total",
    "TOTAL_CATTLE": "Cattle total",
    "TOTAL_SHEEP": "Sheep total",
}

ACHILL_LAND_VARIABLE_MAP = {
    "AGRICULTURAL_HOLDINGS": "Holdings total",
    "AVERAGE_SIZE_OF_HOLDINGS": "Average holding size",
    "AREA_FARMED": "Area farmed total ha",
    "TOTAL_CEREALS": "Cereals total ha",
    "ALL_GRASSLAND": "Grassland total ha",
}


def _normalise_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower().replace("co.", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalise_county(value: object) -> str:
    text = _normalise_text(value).replace("county ", "")
    return text.title()


def _normalise_csoed(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text


def _load_achill_ed_crosswalk(benchmark_path: str | Path) -> pd.DataFrame:
    path = Path(benchmark_path).with_name("ED_Name_Crosswalk.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"Achill ED identifier crosswalk is required beside the benchmark: {path}"
        )
    crosswalk = pd.read_csv(path, dtype={"MODEL_CSOED": str})
    required = {"Electoral Division", "GOBLIN ED label", "MODEL_CSOED"}
    missing = sorted(required - set(crosswalk.columns))
    if missing:
        raise ValueError(f"Achill ED crosswalk missing columns: {missing}")
    if crosswalk["Electoral Division"].duplicated().any():
        raise AssertionError("Achill ED crosswalk contains duplicate survey labels")
    if crosswalk["MODEL_CSOED"].map(_normalise_csoed).duplicated().any():
        raise AssertionError("Achill ED crosswalk contains duplicate model CSOED identifiers")
    return crosswalk


def spearman_rank(observed: pd.Series, predicted: pd.Series) -> float:
    """Return Spearman's rho without requiring scipy."""
    x = pd.to_numeric(observed, errors="raise").astype(float)
    y = pd.to_numeric(predicted, errors="raise").astype(float)
    if len(x) != len(y):
        raise ValueError("observed and predicted series must have equal length")
    if len(x) < 2:
        return float("nan")
    if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
        return float("nan")
    return float(x.rank(method="average").corr(y.rank(method="average")))


def error_summary(
    frame: pd.DataFrame,
    *,
    observed: str,
    predicted: str,
    group: str | None = None,
) -> pd.DataFrame:
    """Summarise transparent error diagnostics."""
    work = frame.copy()
    obs = pd.to_numeric(work[observed], errors="raise").astype(float)
    pred = pd.to_numeric(work[predicted], errors="raise").astype(float)
    work["_ABS"] = (pred - obs).abs()
    work["_SQ"] = (pred - obs) ** 2
    work["_ERR"] = pred - obs
    work["_APE"] = np.where(obs != 0, work["_ABS"] / obs.abs() * 100.0, np.nan)

    def summarise(part: pd.DataFrame) -> dict[str, float | int]:
        o = pd.to_numeric(part[observed], errors="raise").astype(float)
        p = pd.to_numeric(part[predicted], errors="raise").astype(float)
        return {
            "N": int(len(part)),
            "OBSERVED_TOTAL": float(o.sum()),
            "PREDICTED_TOTAL": float(p.sum()),
            "BIAS": float((p - o).mean()),
            "MAE": float((p - o).abs().mean()),
            "RMSE": float(np.sqrt(((p - o) ** 2).mean())),
            "MAPE_PCT": float(np.nanmean(np.where(o != 0, (p - o).abs() / o.abs() * 100.0, np.nan))),
            "SPEARMAN_RHO": spearman_rank(o, p),
        }

    if group is None:
        return pd.DataFrame([summarise(work)])

    rows = []
    for key, part in work.groupby(group, sort=True):
        row = {group: key}
        row.update(summarise(part))
        rows.append(row)
    return pd.DataFrame(rows)


def validate_dafm_sheep_counties(
    master: pd.DataFrame,
    validation_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare reconstructed county sheep totals with the DAFM county pattern.

    The model's sheep population remains controlled by CSO/AAA09, but the DAFM
    breeding-ewe geography also informs relative county weighting in the
    reconstruction. This is therefore a pattern-fidelity diagnostic, not
    independent validation.
    """
    required = {"YEAR", "County", "TOTAL_SHEEP"}
    missing = sorted(required - set(master.columns))
    if missing:
        raise ValueError(f"historical master missing columns for DAFM validation: {missing}")

    observed = pd.read_csv(validation_path)
    required_obs = {"YEAR", "County", "TOTAL"}
    missing_obs = sorted(required_obs - set(observed.columns))
    if missing_obs:
        raise ValueError(f"DAFM sheep validation file missing columns: {missing_obs}")

    observed = observed[["YEAR", "County", "TOTAL"]].copy()
    observed["YEAR"] = pd.to_numeric(observed["YEAR"], errors="raise").astype(int)
    observed["County"] = observed["County"].map(_normalise_county)
    observed["DAFM_TOTAL_SHEEP"] = pd.to_numeric(observed["TOTAL"], errors="raise").astype(float)
    observed = observed.drop(columns="TOTAL")

    model = master[["YEAR", "County", "TOTAL_SHEEP"]].copy()
    model["YEAR"] = pd.to_numeric(model["YEAR"], errors="raise").astype(int)
    model["County"] = model["County"].map(_normalise_county)
    model["TOTAL_SHEEP"] = pd.to_numeric(model["TOTAL_SHEEP"], errors="raise").astype(float)
    model = (
        model.groupby(["YEAR", "County"], as_index=False, sort=True)["TOTAL_SHEEP"]
        .sum()
        .rename(columns={"TOTAL_SHEEP": "MODEL_TOTAL_SHEEP"})
    )

    years = sorted(set(model["YEAR"]) & set(observed["YEAR"]))
    diagnostics = observed.loc[observed["YEAR"].isin(years)].merge(
        model.loc[model["YEAR"].isin(years)],
        on=["YEAR", "County"],
        how="inner",
        validate="one_to_one",
    )
    diagnostics["ERROR"] = diagnostics["MODEL_TOTAL_SHEEP"] - diagnostics["DAFM_TOTAL_SHEEP"]
    diagnostics["ABS_ERROR"] = diagnostics["ERROR"].abs()
    diagnostics["PCT_ERROR"] = np.where(
        diagnostics["DAFM_TOTAL_SHEEP"] != 0,
        diagnostics["ERROR"] / diagnostics["DAFM_TOTAL_SHEEP"] * 100.0,
        np.nan,
    )

    summary = error_summary(
        diagnostics,
        observed="DAFM_TOTAL_SHEEP",
        predicted="MODEL_TOTAL_SHEEP",
        group="YEAR",
    )
    summary.insert(0, "VALIDATION", "DAFM_COUNTY_SHEEP")
    return diagnostics.sort_values(["YEAR", "County"]).reset_index(drop=True), summary


def sheep_anchor_holdout(
    anchor_path: str | Path,
    *,
    holdout_year: int = 2022,
    start_year: int = 2020,
    end_year: int = 2025,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Omit one DAFM sheep-composition anchor and interpolate it from neighbours.

    This is a genuine holdout of composition, not a closure test.
    """
    if not start_year < holdout_year < end_year:
        raise ValueError("holdout year must lie strictly between start and end years")

    anchors = pd.read_csv(anchor_path)
    required = {
        "YEAR",
        "CATEGORY",
        "County",
        "TOTAL_DAFM",
        "MOUNTAIN_COUNT",
        "MOUNTAIN_CROSS_COUNT",
        "LOWLAND_COUNT",
        "LOWLAND_CROSS_COUNT",
    }
    missing = sorted(required - set(anchors.columns))
    if missing:
        raise ValueError(f"sheep anchor file missing columns: {missing}")

    anchors = anchors.copy()
    anchors["YEAR"] = pd.to_numeric(anchors["YEAR"], errors="raise").astype(int)
    anchors["CATEGORY"] = anchors["CATEGORY"].astype(str).str.strip().str.upper()
    anchors["County"] = anchors["County"].map(_normalise_county)

    breeds = ("MOUNTAIN", "MOUNTAIN_CROSS", "LOWLAND", "LOWLAND_CROSS")
    for breed in breeds:
        anchors[f"{breed}_COUNT"] = pd.to_numeric(
            anchors[f"{breed}_COUNT"], errors="raise"
        ).astype(float)

    totals = anchors[[f"{b}_COUNT" for b in breeds]].sum(axis=1)
    if (totals <= 0).any():
        raise AssertionError("sheep composition anchor contains a non-positive total")
    for breed in breeds:
        anchors[f"{breed}_SHARE"] = anchors[f"{breed}_COUNT"] / totals

    key = ["County", "CATEGORY"]
    start = anchors.loc[anchors["YEAR"] == start_year, [*key, *[f"{b}_SHARE" for b in breeds]]]
    end = anchors.loc[anchors["YEAR"] == end_year, [*key, *[f"{b}_SHARE" for b in breeds]]]
    observed = anchors.loc[
        anchors["YEAR"] == holdout_year,
        [*key, *[f"{b}_SHARE" for b in breeds]],
    ]

    start = start.rename(columns={f"{b}_SHARE": f"{b}_START" for b in breeds})
    end = end.rename(columns={f"{b}_SHARE": f"{b}_END" for b in breeds})
    observed = observed.rename(columns={f"{b}_SHARE": f"{b}_OBSERVED" for b in breeds})

    merged = start.merge(end, on=key, validate="one_to_one").merge(
        observed, on=key, validate="one_to_one"
    )
    alpha = (holdout_year - start_year) / (end_year - start_year)

    rows = []
    for breed in breeds:
        predicted = (
            merged[f"{breed}_START"]
            + alpha * (merged[f"{breed}_END"] - merged[f"{breed}_START"])
        )
        part = merged[key].copy()
        part["HOLDOUT_YEAR"] = holdout_year
        part["BREED_GROUP"] = breed
        part["OBSERVED_SHARE"] = merged[f"{breed}_OBSERVED"].astype(float)
        part["PREDICTED_SHARE"] = predicted.astype(float)
        part["ERROR_PP"] = (part["PREDICTED_SHARE"] - part["OBSERVED_SHARE"]) * 100.0
        part["ABS_ERROR_PP"] = part["ERROR_PP"].abs()
        rows.append(part)

    diagnostics = pd.concat(rows, ignore_index=True)
    summary = error_summary(
        diagnostics,
        observed="OBSERVED_SHARE",
        predicted="PREDICTED_SHARE",
        group="BREED_GROUP",
    )
    summary.insert(0, "VALIDATION", f"SHEEP_COMPOSITION_HOLDOUT_{holdout_year}")
    # Convert share-scale error summaries to percentage points for readability.
    for column in ("BIAS", "MAE", "RMSE"):
        summary[f"{column}_PP"] = summary[column] * 100.0
    return diagnostics.sort_values(["BREED_GROUP", "County", "CATEGORY"]).reset_index(drop=True), summary


def _find_ed_name_column(master: pd.DataFrame) -> str:
    # The external Achill survey uses the Census of Agriculture ED labels.
    # Prefer the source `ED` field before harmonised/reporting aliases such as
    # EDNAME, which can contain Irish-language or later boundary labels.
    for candidate in ("ED", "EDNAME", "ELECTORAL_DIVISIONS"):
        if candidate in master.columns:
            return candidate
    raise ValueError("historical master has no recognised ED-name column")


def validate_achill_benchmark(
    master: pd.DataFrame,
    benchmark_path: str | Path,
    *,
    county: str = "Mayo",
    year: int = 2020,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare 2020 GOBLIN-Spatial broad livestock geography with Achill North.

    The Achill survey uses Census of Agriculture 2020, so this is an external
    applied implementation benchmark rather than fully independent population
    validation.
    """
    benchmark = pd.read_csv(benchmark_path)
    required_benchmark = {
        "Electoral Division",
        "Overlap fraction",
        *ACHILL_VARIABLE_MAP.values(),
        "Cattle corrected",
        "Sheep corrected",
    }
    missing = sorted(required_benchmark - set(benchmark.columns))
    if missing:
        raise ValueError(f"Achill benchmark missing columns: {missing}")

    name_col = _find_ed_name_column(master)
    required_master = {"YEAR", "County", "CSOED", name_col, *ACHILL_VARIABLE_MAP}
    missing_master = sorted(required_master - set(master.columns))
    if missing_master:
        raise ValueError(f"historical master missing Achill comparison columns: {missing_master}")

    years = pd.to_numeric(master["YEAR"], errors="raise").astype(int)
    model = master.loc[years == year, list(required_master)].copy()
    model = model.loc[
        model["County"].map(_normalise_county) == _normalise_county(county)
    ].copy()
    model["_CSOED_KEY"] = model["CSOED"].map(_normalise_csoed)

    bench = benchmark.copy()
    crosswalk = _load_achill_ed_crosswalk(benchmark_path)
    bench = bench.merge(
        crosswalk[["Electoral Division", "GOBLIN ED label", "MODEL_CSOED"]],
        on="Electoral Division",
        how="left",
        validate="one_to_one",
    )
    if bench["MODEL_CSOED"].isna().any():
        missing_names = bench.loc[
            bench["MODEL_CSOED"].isna(), "Electoral Division"
        ].tolist()
        raise AssertionError(f"Achill crosswalk missing benchmark EDs: {missing_names}")
    bench["_CSOED_KEY"] = bench["MODEL_CSOED"].map(_normalise_csoed)

    model = model.loc[
        model["_CSOED_KEY"].isin(set(bench["_CSOED_KEY"]))
    ].copy()
    if model["_CSOED_KEY"].duplicated().any():
        dup = model.loc[
            model["_CSOED_KEY"].duplicated(keep=False), [name_col, "CSOED"]
        ].to_dict("records")
        raise AssertionError(f"duplicate model CSOED values in {county}: {dup}")

    keep_model = ["_CSOED_KEY", "CSOED", name_col, *ACHILL_VARIABLE_MAP]
    merged = bench.merge(
        model[keep_model],
        on="_CSOED_KEY",
        how="left",
        validate="one_to_one",
    )
    if merged[name_col].isna().any():
        missing_names = merged.loc[merged[name_col].isna(), "Electoral Division"].tolist()
        raise AssertionError(f"Achill EDs not matched to GOBLIN-Spatial {county} baseline: {missing_names}")

    diagnostics = []
    summary_rows = []
    for model_column, benchmark_column in ACHILL_VARIABLE_MAP.items():
        part = merged[
            ["Electoral Division", benchmark_column, model_column]
        ].copy()
        part["VARIABLE"] = model_column
        part = part.rename(
            columns={
                benchmark_column: "BENCHMARK_VALUE",
                model_column: "MODEL_VALUE",
            }
        )
        part["ERROR"] = pd.to_numeric(part["MODEL_VALUE"], errors="raise") - pd.to_numeric(
            part["BENCHMARK_VALUE"], errors="raise"
        )
        diagnostics.append(part)

        stats = error_summary(
            part,
            observed="BENCHMARK_VALUE",
            predicted="MODEL_VALUE",
        ).iloc[0].to_dict()
        stats["VALIDATION"] = "ACHILL_ED_2020"
        stats["VARIABLE"] = model_column
        summary_rows.append(stats)

    animal_diagnostics = pd.concat(diagnostics, ignore_index=True)
    summary = pd.DataFrame(summary_rows)[
        ["VALIDATION", "VARIABLE", "N", "OBSERVED_TOTAL", "PREDICTED_TOTAL", "BIAS", "MAE", "RMSE", "MAPE_PCT", "SPEARMAN_RHO"]
    ]

    spatial = merged[
        [
            "Electoral Division",
            "Overlap fraction",
            "Cattle total",
            "Cattle corrected",
            "Sheep total",
            "Sheep corrected",
        ]
    ].copy()
    overlap = pd.to_numeric(spatial["Overlap fraction"], errors="coerce")
    spatial["CATTLE_AREA_CALC"] = pd.to_numeric(spatial["Cattle total"], errors="raise") * overlap
    spatial["SHEEP_AREA_CALC"] = pd.to_numeric(spatial["Sheep total"], errors="raise") * overlap
    spatial["CATTLE_AREA_ERROR"] = (
        pd.to_numeric(spatial["Cattle corrected"], errors="raise") - spatial["CATTLE_AREA_CALC"]
    )
    spatial["SHEEP_AREA_ERROR"] = (
        pd.to_numeric(spatial["Sheep corrected"], errors="raise") - spatial["SHEEP_AREA_CALC"]
    )

    return (
        animal_diagnostics.sort_values(["VARIABLE", "Electoral Division"]).reset_index(drop=True),
        summary.reset_index(drop=True),
        spatial.reset_index(drop=True),
    )


def validate_achill_land_benchmark(
    master: pd.DataFrame,
    benchmark_path: str | Path,
    *,
    county: str = "Mayo",
    year: int = 2020,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare broad 2020 land/farm structure with the Achill North benchmark.

    Like the livestock comparison, this is a reproducibility/application test
    because both sources ultimately use Census of Agriculture 2020.
    """
    benchmark = pd.read_csv(benchmark_path)
    required_benchmark = {"Electoral Division", *ACHILL_LAND_VARIABLE_MAP.values()}
    missing = sorted(required_benchmark - set(benchmark.columns))
    if missing:
        raise ValueError(f"Achill land benchmark missing columns: {missing}")

    name_col = _find_ed_name_column(master)
    required_master = {
        "YEAR",
        "County",
        "CSOED",
        name_col,
        *ACHILL_LAND_VARIABLE_MAP,
    }
    missing_master = sorted(required_master - set(master.columns))
    if missing_master:
        raise ValueError(
            f"historical master missing Achill land comparison columns: {missing_master}"
        )

    years = pd.to_numeric(master["YEAR"], errors="raise").astype(int)
    model = master.loc[years == year, list(required_master)].copy()
    model = model.loc[
        model["County"].map(_normalise_county) == _normalise_county(county)
    ].copy()
    model["_CSOED_KEY"] = model["CSOED"].map(_normalise_csoed)

    bench = benchmark.copy()
    crosswalk = _load_achill_ed_crosswalk(benchmark_path)
    bench = bench.merge(
        crosswalk[["Electoral Division", "GOBLIN ED label", "MODEL_CSOED"]],
        on="Electoral Division",
        how="left",
        validate="one_to_one",
    )
    if bench["MODEL_CSOED"].isna().any():
        missing_names = bench.loc[
            bench["MODEL_CSOED"].isna(), "Electoral Division"
        ].tolist()
        raise AssertionError(
            f"Achill land crosswalk missing benchmark EDs: {missing_names}"
        )
    bench["_CSOED_KEY"] = bench["MODEL_CSOED"].map(_normalise_csoed)

    model = model.loc[
        model["_CSOED_KEY"].isin(set(bench["_CSOED_KEY"]))
    ].copy()
    if model["_CSOED_KEY"].duplicated().any():
        dup = model.loc[
            model["_CSOED_KEY"].duplicated(keep=False), [name_col, "CSOED"]
        ].to_dict("records")
        raise AssertionError(f"duplicate model CSOED values in {county}: {dup}")

    merged = bench.merge(
        model[
            ["_CSOED_KEY", "CSOED", name_col, *ACHILL_LAND_VARIABLE_MAP]
        ],
        on="_CSOED_KEY",
        how="left",
        validate="one_to_one",
    )
    if merged[name_col].isna().any():
        missing_names = merged.loc[
            merged[name_col].isna(), "Electoral Division"
        ].tolist()
        raise AssertionError(
            f"Achill land EDs not matched to GOBLIN-Spatial {county} baseline: {missing_names}"
        )

    diagnostics = []
    summary_rows = []
    for model_column, benchmark_column in ACHILL_LAND_VARIABLE_MAP.items():
        part = merged[["Electoral Division", benchmark_column, model_column]].copy()
        part["VARIABLE"] = model_column
        part = part.rename(
            columns={
                benchmark_column: "BENCHMARK_VALUE",
                model_column: "MODEL_VALUE",
            }
        )
        part["ERROR"] = (
            pd.to_numeric(part["MODEL_VALUE"], errors="raise")
            - pd.to_numeric(part["BENCHMARK_VALUE"], errors="raise")
        )
        diagnostics.append(part)

        stats = error_summary(
            part,
            observed="BENCHMARK_VALUE",
            predicted="MODEL_VALUE",
        ).iloc[0].to_dict()
        stats["VALIDATION"] = "ACHILL_ED_LAND_2020"
        stats["VARIABLE"] = model_column
        summary_rows.append(stats)

    diagnostic_frame = pd.concat(diagnostics, ignore_index=True)
    summary = pd.DataFrame(summary_rows)[
        [
            "VALIDATION",
            "VARIABLE",
            "N",
            "OBSERVED_TOTAL",
            "PREDICTED_TOTAL",
            "BIAS",
            "MAE",
            "RMSE",
            "MAPE_PCT",
            "SPEARMAN_RHO",
        ]
    ]
    return (
        diagnostic_frame.sort_values(
            ["VARIABLE", "Electoral Division"]
        ).reset_index(drop=True),
        summary.reset_index(drop=True),
    )


def add_signature_indicators(master: pd.DataFrame) -> pd.DataFrame:
    """Add transparent ED livestock-system signature indicators."""
    required = {
        "YEAR",
        "CSOED",
        "DAIRY_COW",
        "OTHER_COW",
        "TOTAL_CATTLE",
        "TOTAL_SHEEP",
        *DXD_COHORTS,
        *DXB_COHORTS,
        *BXB_COHORTS,
        *FOLLOWER_COHORTS,
    }
    missing = sorted(required - set(master.columns))
    if missing:
        raise ValueError(f"historical master missing signature columns: {missing}")

    out = master.copy()
    dairy = pd.to_numeric(out["DAIRY_COW"], errors="raise").astype(float)
    suckler = pd.to_numeric(out["OTHER_COW"], errors="raise").astype(float)
    adults = dairy + suckler
    followers = out[list(FOLLOWER_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    dxd = out[list(DXD_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    dxb = out[list(DXB_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    bxb = out[list(BXB_COHORTS)].apply(pd.to_numeric, errors="raise").sum(axis=1)
    origin_total = dxd + dxb + bxb

    out["SIG_DAIRY_SHARE_ADULT_COWS"] = np.where(adults > 0, dairy / adults, np.nan)
    out["SIG_FOLLOWERS_PER_ADULT_COW"] = np.where(adults > 0, followers / adults, np.nan)
    out["SIG_DXD_SHARE_ORIGIN_FOLLOWERS"] = np.where(origin_total > 0, dxd / origin_total, np.nan)
    out["SIG_DXB_SHARE_ORIGIN_FOLLOWERS"] = np.where(origin_total > 0, dxb / origin_total, np.nan)
    out["SIG_BXB_SHARE_ORIGIN_FOLLOWERS"] = np.where(origin_total > 0, bxb / origin_total, np.nan)
    return out


def temporal_rank_stability(
    master: pd.DataFrame,
    columns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Measure adjacent-year stability of ED rankings.

    This is a reconstruction diagnostic, not independent validation. It is
    useful for detecting accidental year-to-year spatial discontinuities.
    """
    work = add_signature_indicators(master)
    if columns is None:
        columns = (
            "TOTAL_CATTLE",
            "TOTAL_SHEEP",
            "SIG_DAIRY_SHARE_ADULT_COWS",
            "SIG_FOLLOWERS_PER_ADULT_COW",
            "SIG_DXD_SHARE_ORIGIN_FOLLOWERS",
            "SIG_DXB_SHARE_ORIGIN_FOLLOWERS",
            "SIG_BXB_SHARE_ORIGIN_FOLLOWERS",
        )

    years = sorted(pd.to_numeric(work["YEAR"], errors="raise").astype(int).unique())
    rows = []
    for previous, current in zip(years[:-1], years[1:]):
        left = work.loc[
            pd.to_numeric(work["YEAR"], errors="raise").astype(int) == previous,
            ["CSOED", *columns],
        ].copy()
        right = work.loc[
            pd.to_numeric(work["YEAR"], errors="raise").astype(int) == current,
            ["CSOED", *columns],
        ].copy()
        merged = left.merge(right, on="CSOED", validate="one_to_one", suffixes=("_PREV", "_CURR"))
        for column in columns:
            pair = merged[[f"{column}_PREV", f"{column}_CURR"]].dropna()
            rows.append(
                {
                    "YEAR_FROM": previous,
                    "YEAR_TO": current,
                    "INDICATOR": column,
                    "N_ED": int(len(pair)),
                    "SPEARMAN_RHO": spearman_rank(pair.iloc[:, 0], pair.iloc[:, 1]),
                }
            )
    return pd.DataFrame(rows)
