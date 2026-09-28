import numpy as np
import pandas as pd

from goblin_spatial.validation.baseline_metrics import agreement, bootstrap_ci, continuity


def test_perfect_agreement():
    o = np.array([0.0, 1.0, 5.0, 10.0, 20.0])
    m = agreement(o, o)
    assert m["N"] == 5
    assert m["RMSE"] == 0.0 and m["BIAS"] == 0.0
    assert np.isclose(m["LIN_CCC"], 1.0)
    assert np.isclose(m["NSE"], 1.0)
    assert m["ZERO_AGREEMENT"] == 1.0


def test_ccc_penalises_offset_but_pearson_does_not():
    o = np.arange(1.0, 11.0)
    m = agreement(o, o + 5.0)
    assert np.isclose(m["PEARSON_R"], 1.0)
    assert m["LIN_CCC"] < 0.6
    assert np.isclose(m["BIAS"], 5.0)
    assert m["NSE"] < 0.0


def test_skill_against_baseline():
    o = np.array([1.0, 2.0, 3.0, 4.0])
    p = o + 0.5
    b = np.full(4, o.mean())
    m = agreement(o, p, baseline=b)
    rmse_b = np.sqrt(np.mean((b - o) ** 2))
    assert np.isclose(m["SKILL_VS_BASELINE"], 1 - 0.5 / rmse_b)


def test_nonfinite_dropped_and_small_n():
    m = agreement([1.0, np.nan, 3.0, 4.0], [1.0, 2.0, np.nan, 4.0])
    assert m["N"] == 2 and "RMSE" not in m


def test_bootstrap_ci_brackets_point_estimate():
    rng = np.random.default_rng(1)
    o = rng.gamma(2.0, 50.0, 300)
    p = o * rng.normal(1.0, 0.1, 300)
    lo, hi = bootstrap_ci(o, p, "LIN_CCC", n_boot=200)
    point = agreement(o, p)["LIN_CCC"]
    assert lo <= point <= hi


def test_continuity_identical_years():
    panel = pd.DataFrame(
        [{"CSOED": e, "YEAR": y, "X": float(e)} for e in range(1, 6) for y in range(2015, 2026)]
    )
    c = continuity(panel, ["X"])
    assert len(c) == 10
    assert np.allclose(c["SPEARMAN_RHO"], 1.0)


def test_cluster_bootstrap_ci_brackets_point_estimate():
    rng = np.random.default_rng(7)
    clusters = np.repeat(np.arange(12), 20)
    o = rng.gamma(2.0, 40.0, len(clusters))
    p = o * rng.normal(1.0, 0.08, len(clusters))
    lo, hi = bootstrap_ci(o, p, "LIN_CCC", clusters=clusters, n_boot=250)
    point = agreement(o, p)["LIN_CCC"]
    assert lo <= point <= hi
