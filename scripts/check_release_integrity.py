#!/usr/bin/env python
"""Independent regression checks on the completed historical release.

These checks deliberately recompute identities from released tables rather than
calling the functions that produced them. CI runs this script after rebuilding
the release. The expected contract is 42/42 checks passing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import CONTAINERS, FINAL_21_COHORTS
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "reporting/report_data/historical"
CROSSWALK = ROOT / "data/processed/ed_wfd_catchment_crosswalk.csv"


def _read(name: str) -> pd.DataFrame:
    return pd.read_parquet(BUNDLE / f"{name}.parquet")


def _close(a, b, atol=1e-6) -> bool:
    aa = np.asarray(a, dtype=float)
    bb = np.asarray(b, dtype=float)
    return np.allclose(aa, bb, rtol=0, atol=atol, equal_nan=True)


def main() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, bool(ok)))
        if not ok:
            raise AssertionError(f"release integrity check failed: {name}")

    ed = _read("ed_year")
    county = _read("county_year")
    national = _read("national_year")
    wfd = _read("wfd_catchment_year")
    cso13 = _read("cso13_ed_year")
    g31 = _read("goblin31_ed_year")
    sig_long = _read("livestock_signature_long")
    spread = _read("wfd_signature_spread")
    audit = _read("baseline_coherence_audit")
    xw = pd.read_csv(CROSSWALK, dtype={"CSOED": str, "WFD_CATCHMENT_ID": str})

    ed["CSOED"] = ed["CSOED"].astype(str)
    cso13["CSOED"] = cso13["CSOED"].astype(str)
    g31["CSOED"] = g31["CSOED"].astype(str)

    # 1-9: ED panel integrity.
    check("01 ED row count", len(ed) == 2857 * 11)
    check("02 unique ED-year keys", not ed[["YEAR", "CSOED"]].duplicated().any())
    check("03 year coverage", set(ed["YEAR"].astype(int)) == set(range(2015, 2026)))
    check("04 complete ED coverage each year", ed.groupby("YEAR")["CSOED"].nunique().eq(2857).all())
    animal_cols = ["TOTAL_CATTLE", "TOTAL_SHEEP", "dairy_cows", "suckler_cows", *FINAL_21_COHORTS, *GOBLIN_SHEEP_10]
    animal = ed[animal_cols].apply(pd.to_numeric, errors="raise")
    check("05 no negative animal counts", (animal >= 0).all().all())
    check("06 animal counts are integer-valued", np.allclose(animal.to_numpy(), np.rint(animal.to_numpy()), rtol=0, atol=1e-9))
    land_error = ed["ALL_GRASSLAND"] + ed["TOTAL_CEREALS"] + ed["OTHER_CROPS_HA"] - ed["AREA_FARMED"]
    check("07 land identity", float(land_error.abs().max()) <= 1e-6)
    check("08 holdings non-negative", (pd.to_numeric(ed["AGRICULTURAL_HOLDINGS"], errors="raise") >= 0).all())
    check("09 Standard Output non-negative", (pd.to_numeric(ed["SO_COVERED_TOTAL_2020_EUR"], errors="raise") >= 0).all())

    # 10-24: CSO13 versus GOBLIN31 biological identities.
    check("10 CSO13 row count", len(cso13) == len(ed))
    check("11 GOBLIN31 row count", len(g31) == len(ed))
    keys_ed = set(zip(ed["YEAR"].astype(int), ed["CSOED"]))
    check("12 CSO13 keys match ED panel", set(zip(cso13["YEAR"].astype(int), cso13["CSOED"])) == keys_ed)
    check("13 GOBLIN31 keys match ED panel", set(zip(g31["YEAR"].astype(int), g31["CSOED"])) == keys_ed)
    check("14 21 cattle cohorts close to CSO total cattle", _close(g31[list(FINAL_21_COHORTS)].sum(axis=1), g31["CSO_TOTAL_CATTLE"]))
    check("15 10 sheep cohorts close to CSO total sheep", _close(g31[list(GOBLIN_SHEEP_10)].sum(axis=1), g31["CSO_TOTAL_SHEEP"]))
    check("16 dairy cohort equals CSO dairy cows", _close(g31["dairy_cows"], g31["CSO_DAIRY_COW"]))
    check("17 suckler cohort equals CSO other cows", _close(g31["suckler_cows"], g31["CSO_OTHER_COW"]))
    check("18 bull cohort equals CSO bulls", _close(g31["bulls"], g31["CSO_BULLS"]))
    expected_groups = [
        "CATTLE_MALE_UNDER_1",
        "CATTLE_FEMALE_UNDER_1",
        "CATTLE_MALE_1_2",
        "CATTLE_FEMALE_1_2",
        "CATTLE_MALE_2_PLUS",
        "CATTLE_FEMALE_2_PLUS",
    ]
    for number, group in enumerate(expected_groups, start=19):
        cohorts = list(CONTAINERS[group].values())
        check(
            f"{number:02d} {group} closes across origins",
            _close(g31[cohorts].sum(axis=1), g31[f"CSO_{group}"]),
        )

    # 25-32: ED aggregation independently reproduces county and national views.
    additive = ["TOTAL_CATTLE", "TOTAL_SHEEP", "AREA_FARMED", "SO_COVERED_TOTAL_2020_EUR"]
    county_ed = ed.groupby(["YEAR", "County"], as_index=False)[additive].sum().sort_values(["YEAR", "County"]).reset_index(drop=True)
    county_ref = county[["YEAR", "County", *additive]].sort_values(["YEAR", "County"]).reset_index(drop=True)
    for number, col in enumerate(additive, start=25):
        check(f"{number:02d} county {col} aggregation", _close(county_ed[col], county_ref[col]))
    nat_ed = ed.groupby("YEAR", as_index=False)[additive].sum().sort_values("YEAR").reset_index(drop=True)
    nat_ref = national[["YEAR", *additive]].sort_values("YEAR").reset_index(drop=True)
    for number, col in enumerate(additive, start=29):
        check(f"{number:02d} national {col} aggregation", _close(nat_ed[col], nat_ref[col]))

    # 33-36: independently re-aggregate EDs through the frozen WFD crosswalk
    # and reproduce the released 46-catchment table.
    xw_for_join = xw[["CSOED", "WFD_CATCHMENT_ID", "ED_CATCHMENT_WEIGHT"]].copy()
    weighted = ed[["YEAR", "CSOED", *additive]].merge(
        xw_for_join, on="CSOED", how="inner", validate="many_to_many"
    )
    for col in additive:
        weighted[col] = pd.to_numeric(weighted[col], errors="raise").astype(float) * pd.to_numeric(
            weighted["ED_CATCHMENT_WEIGHT"], errors="raise"
        ).astype(float)
    reagg = (
        weighted.groupby(["YEAR", "WFD_CATCHMENT_ID"], as_index=False)[additive]
        .sum()
        .sort_values(["YEAR", "WFD_CATCHMENT_ID"])
        .reset_index(drop=True)
    )
    wfd_ref = (
        wfd[["YEAR", "WFD_CATCHMENT_ID", *additive]]
        .assign(WFD_CATCHMENT_ID=lambda d: d["WFD_CATCHMENT_ID"].astype(str))
        .sort_values(["YEAR", "WFD_CATCHMENT_ID"])
        .reset_index(drop=True)
    )
    for number, col in enumerate(additive, start=33):
        check(f"{number:02d} WFD {col} crosswalk reaggregation", _close(reagg[col], wfd_ref[col], atol=1e-4))

    # 37-39: crosswalk contract.
    weight_sum = xw.groupby("CSOED")["ED_CATCHMENT_WEIGHT"].sum()
    check("37 crosswalk weights sum to one per ED", _close(weight_sum, np.ones(len(weight_sum)), atol=1e-9))
    check("38 crosswalk covers all model EDs", set(weight_sum.index.astype(str)) == set(ed["CSOED"].unique()))
    check("39 crosswalk contains 46 WFD catchments", xw["WFD_CATCHMENT_ID"].nunique() == 46)

    # 40-41: released signature algebra.
    defined = pd.to_numeric(sig_long["DENOMINATOR"], errors="coerce") > 0
    expected = (
        pd.to_numeric(sig_long.loc[defined, "NUMERATOR"], errors="raise")
        / pd.to_numeric(sig_long.loc[defined, "DENOMINATOR"], errors="raise")
        * pd.to_numeric(sig_long.loc[defined, "SCALE"], errors="raise")
    )
    check("40 every released signature recomputes", _close(expected, sig_long.loc[defined, "VALUE"], atol=1e-9))
    check(
        "41 catchment spread accounting value is finite where defined",
        spread.loc[spread["DISTRIBUTION_DENOMINATOR"] > 0, "CATCHMENT_VALUE"].notna().all(),
    )

    # 42: built-in cross-product coherence audit remains fully green.
    check("42 built-in coherence audit 47/47", len(audit) == 47 and audit["PASS"].astype(bool).all())

    if len(checks) != 42:
        raise AssertionError(f"expected 42 independent checks, constructed {len(checks)}")
    print("Independent historical-release integrity: 42/42 PASS")
    for name, _ in checks:
        print(f"  PASS {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
