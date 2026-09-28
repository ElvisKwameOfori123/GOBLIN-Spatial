"""Validation metrics and tests for the historical ED baseline (v1.1).

Every test is labelled by the independence of its comparison data:

  INDEPENDENT     comparison data never enter estimation
  PARTLY          the comparison source informs another part of the model
  CONSISTENCY     the comparison source is a model input or a different
                  statistical concept; agreement is reported, not claimed as
                  validation
  DIAGNOSTIC      internal behaviour (e.g. temporal continuity)

Metrics (``agreement``):
  N, observed and predicted totals, bias, MAE, RMSE, NRMSE (RMSE / mean
  observed), R2 (1 - SSE/SST, on the 1:1 line), Pearson r, Pearson r on
  log(1+x), Spearman rho, Lin's concordance correlation coefficient (CCC),
  zero agreement (share of units with the same zero / non-zero status), and
  skill = 1 - RMSE(model) / RMSE(baseline) when a baseline is supplied.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.cattle.annual_age_sex import LSU_COEFFICIENTS, SHEEP_LSU
from goblin_spatial.cattle.ed_keys import canonical_ed_key
from goblin_spatial.cattle.age_sex import _normalise_ed_name
from goblin_spatial.sheep.panel import _normalise_county

YEARS = tuple(range(2015, 2026))


# ------------------------------------------------------------------ metrics


def agreement(observed, predicted, baseline=None) -> dict[str, float]:
    o = np.asarray(observed, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if o.shape != p.shape:
        raise ValueError("observed and predicted must have equal length")
    ok = np.isfinite(o) & np.isfinite(p)
    o, p = o[ok], p[ok]
    n = len(o)
    out: dict[str, float] = {"N": n}
    if n < 3:
        return out
    err = p - o
    rmse = float(np.sqrt(np.mean(err**2)))
    sst = float(np.sum((o - o.mean()) ** 2))
    out.update(
        {
            "OBSERVED_TOTAL": float(o.sum()),
            "PREDICTED_TOTAL": float(p.sum()),
            "BIAS": float(err.mean()),
            "MAE": float(np.abs(err).mean()),
            "RMSE": rmse,
            "NRMSE": rmse / float(o.mean()) if o.mean() != 0 else np.nan,
            "R2_1TO1": 1.0 - float(np.sum(err**2)) / sst if sst > 0 else np.nan,
            "PEARSON_R": _corr(o, p),
            "PEARSON_R_LOG1P": _corr(np.log1p(np.clip(o, 0, None)), np.log1p(np.clip(p, 0, None))),
            "SPEARMAN_RHO": _corr(pd.Series(o).rank().to_numpy(), pd.Series(p).rank().to_numpy()),
            "LIN_CCC": _ccc(o, p),
            "ZERO_AGREEMENT": float(np.mean((o == 0) == (np.round(p, 9) == 0))),
        }
    )
    if baseline is not None:
        b = np.asarray(baseline, dtype=float)[ok]
        rmse_b = float(np.sqrt(np.mean((b - o) ** 2)))
        out["RMSE_BASELINE"] = rmse_b
        out["SKILL_VS_BASELINE"] = 1.0 - rmse / rmse_b if rmse_b > 0 else np.nan
    return out


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _ccc(o: np.ndarray, p: np.ndarray) -> float:
    so, sp = o.var(), p.var()
    cov = float(np.mean((o - o.mean()) * (p - p.mean())))
    denom = so + sp + (o.mean() - p.mean()) ** 2
    return 2.0 * cov / denom if denom > 0 else float("nan")


def bootstrap_ci(observed, predicted, metric: str, n_boot: int = 500, seed: int = 20260928) -> tuple[float, float]:
    """95% percentile interval for one agreement metric, resampling units."""
    o = np.asarray(observed, dtype=float)
    p = np.asarray(predicted, dtype=float)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        i = rng.integers(0, len(o), len(o))
        v = agreement(o[i], p[i]).get(metric, np.nan)
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return (np.nan, np.nan)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def row(test: str, status: str, variable: str, subset: str, observed, predicted, baseline=None,
        baseline_name: str = "", note: str = "", ci_metrics=("LIN_CCC",)) -> dict:
    r = {"TEST": test, "INDEPENDENCE": status, "VARIABLE": variable, "SUBSET": subset,
         "BASELINE": baseline_name, "NOTE": note}
    r.update(agreement(observed, predicted, baseline))
    for m in ci_metrics:
        lo, hi = bootstrap_ci(observed, predicted, m)
        r[f"{m}_CI_LOW"], r[f"{m}_CI_HIGH"] = lo, hi
    return r


# -------------------------------------------------------------------- tests


def lsu_frame(age_sex_2020: pd.DataFrame, published: pd.DataFrame) -> pd.DataFrame:
    """Modelled 2020 LSU (cattle age-sex + 0.1 x sheep) against published ED LSU."""
    x = age_sex_2020.set_index("CSOED")
    pub = published.set_index("CSOED").loc[x.index]
    model = sum(x[c] * w for c, w in LSU_COEFFICIENTS.items()) + SHEEP_LSU * pub["TOTAL_SHEEP"]
    return pd.DataFrame(
        {
            "CSOED": x.index,
            "County": pub["County"].to_numpy(),
            "LSU_PUBLISHED": pub["LSU"].astype(float).to_numpy(),
            "LSU_MODEL": model.to_numpy(dtype=float),
            "TOTAL_CATTLE": pub["TOTAL_CATTLE"].to_numpy(),
            "TOTAL_SHEEP": pub["TOTAL_SHEEP"].to_numpy(),
            "ALL_GRASSLAND": pub["ALL_GRASSLAND"].to_numpy(dtype=float),
        }
    )


def backcast_2020_from_2010(ed2020: pd.DataFrame, ed2010: pd.DataFrame, column: str) -> pd.DataFrame:
    """Blind test of the time rule: 2010 within-county shares x 2020 county totals.

    Scored on EDs whose 2010 value is published (not blank). The county total
    is the published 2020 sum over those EDs, so only the spatial pattern is
    tested. Baselines: equal shares within county, and 2020 grassland shares.
    """
    e10 = ed2010.copy()
    e10["_KEY"] = e10["CSOED"].map(canonical_ed_key)
    text = e10.set_index("_KEY")[column].astype(str).str.strip()
    v10 = pd.to_numeric(text.mask(text.eq("")), errors="coerce")
    f = ed2020[["CSOED", "County", column, "ALL_GRASSLAND"]].copy()
    f["V2010"] = f["CSOED"].map(canonical_ed_key).map(v10)
    f = f.loc[f["V2010"].notna()].copy()
    f["OBSERVED_2020"] = f[column].astype(float)
    parts = []
    for _, g in f.groupby("County"):
        g = g.copy()
        total = g["OBSERVED_2020"].sum()
        s10 = g["V2010"] / g["V2010"].sum() if g["V2010"].sum() > 0 else 1.0 / len(g)
        g["PRED_2010_SHARES"] = total * s10
        g["BASE_EQUAL"] = total / len(g)
        gs = g["ALL_GRASSLAND"].astype(float)
        g["BASE_GRASSLAND"] = total * gs / gs.sum() if gs.sum() > 0 else total / len(g)
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def match_aim_totals(ed2020: pd.DataFrame, aim: pd.DataFrame) -> pd.DataFrame:
    """Census 2020 ED cattle against DAFM/AIM register ED averages (name match)."""
    a = aim.copy()
    a["County"] = a["COUNTY"].map(_normalise_county)
    a["_NAME"] = a["ELECTORAL_DIVISION"].map(_normalise_ed_name)
    a = a.loc[~a["ELECTORAL_DIVISION"].astype(str).str.contains(r"DED\s*<\s*5", case=False, regex=True)]
    agg = a.groupby(["County", "_NAME"])[["AVERAGE_NUMBER_CATTLE", "AVERAGE_CATTLE_DAIRY", "AVERAGE_CATTLE_BEEF"]].sum()
    rows = []
    for _, r in ed2020.iterrows():
        keys = {_normalise_ed_name(p) for p in str(r["ED"]).split("/") if _normalise_ed_name(p)}
        tot = dairy = beef = 0.0
        hit = False
        for k in keys:
            if (r["County"], k) in agg.index:
                v = agg.loc[(r["County"], k)]
                tot += v["AVERAGE_NUMBER_CATTLE"]; dairy += v["AVERAGE_CATTLE_DAIRY"]; beef += v["AVERAGE_CATTLE_BEEF"]
                hit = True
        if hit:
            rows.append({"CSOED": r["CSOED"], "County": r["County"], "CENSUS_TOTAL_CATTLE": r["TOTAL_CATTLE"],
                         "AIM_AVG_CATTLE": tot, "AIM_DAIRY_TYPE": dairy, "AIM_BEEF_TYPE": beef})
    return pd.DataFrame(rows)


def continuity(panel: pd.DataFrame, columns) -> pd.DataFrame:
    w = {c: panel.pivot_table(index="CSOED", columns="YEAR", values=c) for c in columns}
    out = []
    for c, t in w.items():
        for y in YEARS[:-1]:
            out.append({"VARIABLE": c, "FROM": y, "TO": y + 1,
                        "SPEARMAN_RHO": _corr(t[y].rank().to_numpy(), t[y + 1].rank().to_numpy()),
                        "PEARSON_R_LOG1P": _corr(np.log1p(t[y].to_numpy()), np.log1p(t[y + 1].to_numpy()))})
    return pd.DataFrame(out)
