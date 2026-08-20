from __future__ import annotations

import numpy as np
import pandas as pd

from goblin_spatial.sheep.drift import (
    ANCHOR_YEARS,
    MODEL_YEARS,
    build_annual_dafm_county_drift,
    drifted_county_weights,
)


IRISH_COUNTIES = [
    "Carlow",
    "Cavan",
    "Clare",
    "Cork",
    "Donegal",
    "Dublin",
    "Galway",
    "Kerry",
    "Kildare",
    "Kilkenny",
    "Laois",
    "Leitrim",
    "Limerick",
    "Longford",
    "Louth",
    "Mayo",
    "Meath",
    "Monaghan",
    "Offaly",
    "Roscommon",
    "Sligo",
    "Tipperary",
    "Waterford",
    "Westmeath",
    "Wexford",
    "Wicklow",
]


def _synthetic_anchors() -> pd.DataFrame:
    rows = []
    for year in ANCHOR_YEARS:
        for i, county in enumerate(IRISH_COUNTIES):
            # Positive counts with deliberately changing county distribution.
            rows.append(
                {
                    "YEAR": year,
                    "County": county,
                    "TOTAL": 1000 + 20 * i + (year - 2015) * (i + 1),
                }
            )
    return pd.DataFrame(rows)


def test_dafm_drift_preserves_observed_anchor_shares_and_2020_identity() -> None:
    anchors = _synthetic_anchors()
    drift = build_annual_dafm_county_drift(anchors)

    assert tuple(sorted(drift["YEAR"].unique())) == MODEL_YEARS
    assert len(drift) == 26 * len(MODEL_YEARS)
    assert np.allclose(
        drift.groupby("YEAR")["DAFM_COUNTY_SHARE"].sum().to_numpy(),
        1.0,
        atol=1e-12,
        rtol=0.0,
    )
    assert np.array_equal(
        drift.loc[drift["YEAR"] == 2020, "DAFM_DRIFT_FACTOR"].to_numpy(),
        np.ones(26),
    )

    observed = anchors.pivot(index="County", columns="YEAR", values="TOTAL")
    observed = observed.div(observed.sum(axis=0), axis=1)
    for year in ANCHOR_YEARS:
        model = (
            drift.loc[drift["YEAR"] == year]
            .set_index("County")["DAFM_COUNTY_SHARE"]
            .sort_index()
        )
        expected = observed[year].sort_index()
        assert np.array_equal(model.to_numpy(), expected.to_numpy())


def test_intermediate_dafm_shares_are_linear_and_renormalised() -> None:
    anchors = _synthetic_anchors()
    drift = build_annual_dafm_county_drift(anchors)
    shares = anchors.pivot(index="County", columns="YEAR", values="TOTAL")
    shares = shares.div(shares.sum(axis=0), axis=1)

    alpha = (2018 - 2015) / (2020 - 2015)
    expected = shares[2015] + alpha * (shares[2020] - shares[2015])
    expected = expected / expected.sum()
    actual = (
        drift.loc[drift["YEAR"] == 2018]
        .set_index("County")["DAFM_COUNTY_SHARE"]
        .reindex(expected.index)
    )
    assert np.allclose(actual.to_numpy(), expected.to_numpy(), atol=1e-15, rtol=0.0)


def test_drifted_county_weights_leave_2020_anchor_untouched() -> None:
    anchors = _synthetic_anchors()
    drift = build_annual_dafm_county_drift(anchors)
    county_anchor = pd.DataFrame(
        {
            "County": IRISH_COUNTIES[:6],
            "Region": ["R1", "R1", "R1", "R2", "R2", "R2"],
            "TOTAL_SHEEP_2020_RECONCILED": [100, 200, 300, 400, 500, 600],
        }
    )

    weights_2020 = drifted_county_weights(
        county_anchor, drift, year=2020, region="R1"
    )
    assert np.array_equal(weights_2020, np.array([100.0, 200.0, 300.0]))

    weights_2025 = drifted_county_weights(
        county_anchor, drift, year=2025, region="R1"
    )
    assert np.all(weights_2025 > 0)
    assert not np.array_equal(weights_2025, weights_2020)
