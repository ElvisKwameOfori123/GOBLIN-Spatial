"""Machine-readable column dictionary for the historical baseline release.

Every column of the public ED-year, county, national, catchment and livestock
panel tables is described here with its unit and basis. ``describe_table``
returns one row per column; ``undescribed_columns`` lists anything a table
carries that this dictionary does not yet explain (tests keep it empty for the
public tables).

Definitions follow the code that produces each column (cattle/annual_panel,
cattle/annual_age_sex, cattle/cohorts, sheep/annual_panel, sheep/cohorts,
land/panel, se/panel, standard_output/valuation, synthesis/historical,
aggregation/catchments).
"""

from __future__ import annotations

import re

import pandas as pd

YEAR_BASIS = (
    "2020: published CSO Census of Agriculture ED value, unchanged. "
    "Other years: reconstructed under the annual higher-level CSO control."
)

# column -> (unit, description)
_EXACT: dict[str, tuple[str, str]] = {
    # identifiers
    "YEAR": ("year", "Calendar year, 2015-2025."),
    "CSOED": ("code", "Model Electoral Division key (2,857 units; 31 are composite CSO codes)."),
    "CSOED_RAW": ("code", "CSO ED code as published, including composite codes such as 08045/08046."),
    "EDID": ("code", "ED identifier as published in the 2020 Census of Agriculture ED table."),
    "ED": ("name", "Electoral Division name."),
    "EDNAME": ("name", "Electoral Division name from the ED boundary set."),
    "ELECTORAL_DIVISIONS": ("label", "CSO label: ED name, county and code."),
    "County": ("name", "County (26)."),
    "COUNTYNAME": ("name", "County name from the ED boundary set."),
    "Region": ("name", "CSO detailed region (7) used for AAA09 sheep controls."),
    "NUTS2": ("name", "NUTS2 region."),
    "AQA06_REGION": ("name", "CSO AQA06 region used as the annual land-use control."),
    "FADN_REGION": ("code", "Historic Standard Output region: 381 Border, Midland and Western; 382 Southern and Eastern."),
    "FADN_REGION_LABEL": ("name", "Label of FADN_REGION."),
    "GEOGRAPHY": ("name", "Reporting geography of the row (national table)."),
    "WFD_CATCHMENT_ID": ("code", "Official Water Framework Directive catchment identifier (46)."),
    "WFD_CATCHMENT": ("name", "Official WFD catchment name (46)."),
    "COLM_CATCHMENT": ("name", "Catchment in the 37-unit system of GOBLIN-Proj catchment_data_api (Upper and Lower Shannon merged); derived from the WFD result."),
    # provenance and method flags
    "PROVENANCE": ("flag", "Cattle provenance: CSO_ED_2020_PUBLISHED_UNCHANGED (2020), AAA10_COUNTY_CONTROL_ED_2010_2020_PATH (2015-2019), AAA10_COUNTY_CONTROL_ED_2020_PATTERN (2021-2025)."),
    "CATTLE_PROVENANCE": ("flag", "Cattle provenance; see PROVENANCE."),
    "SHEEP_DATA_STATUS": ("flag", "Sheep provenance: CSO_ED_2020_PUBLISHED_UNCHANGED (2020), AAA09_REGION_CONTROL_ED_2010_2020_PATH (2015-2019), AAA09_REGION_CONTROL_ED_2020_REFERENCE_PATTERN (2021-2025)."),
    "SHEEP_PROVENANCE": ("flag", "Sheep provenance; see SHEEP_DATA_STATUS."),
    "AGE_SEX_PRIOR": ("flag", "Prior used to split OTHER_CATTLE into the seven AAA10 age-sex groups (production: dafm_log_odds)."),
    "AGE_SEX_AIM_MATCHED": ("flag", "True where the ED matched a DAFM/AIM 2020 ED age-profile row."),
    "AGE_SEX_DAFM_Q_LOCAL": ("share", "DAFM/AIM 2020 ED share of under-24-month stock aged under 12 months (composition only)."),
    "AGE_SEX_DAFM_Q_COUNTY": ("share", "Same share for the county; the ED signal is used relative to it."),
    # CSO cattle
    "TOTAL_CATTLE": ("head", "Total cattle. " + YEAR_BASIS + " Control: AAA10 county (June)."),
    "DAIRY_COW": ("head", "Dairy cows. " + YEAR_BASIS + " Control: AAA10 county (June)."),
    "OTHER_COW": ("head", "Other (suckler) cows. " + YEAR_BASIS + " Control: AAA10 county (June)."),
    "OTHER_CATTLE": ("head", "Other cattle = TOTAL_CATTLE - DAIRY_COW - OTHER_COW."),
    "BULLS": ("head", "Bulls (CSO AAA10 age-sex group), part of OTHER_CATTLE. Estimated within the ED's OTHER_CATTLE; county group totals from AAA10."),
    "CATTLE_MALE_UNDER_1": ("head", "Male cattle under 1 year (AAA10 group), part of OTHER_CATTLE."),
    "CATTLE_FEMALE_UNDER_1": ("head", "Female cattle under 1 year (AAA10 group), part of OTHER_CATTLE."),
    "CATTLE_MALE_1_2": ("head", "Male cattle 1-2 years (AAA10 group), part of OTHER_CATTLE."),
    "CATTLE_FEMALE_1_2": ("head", "Female cattle 1-2 years (AAA10 group), part of OTHER_CATTLE."),
    "CATTLE_MALE_2_PLUS": ("head", "Male cattle 2 years and over, excluding bulls (AAA10 group), part of OTHER_CATTLE."),
    "CATTLE_FEMALE_2_PLUS": ("head", "Female cattle 2 years and over, excluding cows (AAA10 group), part of OTHER_CATTLE."),
    # CSO sheep
    "TOTAL_SHEEP": ("head", "Total sheep. " + YEAR_BASIS + " Control: AAA09 detailed region (June)."),
    "EWES_2_PLUS": ("head", "Ewes 2 years and over (AAA09 class), allocated within ED TOTAL_SHEEP."),
    "EWES_UNDER_2": ("head", "Ewes under 2 years (AAA09 class), allocated within ED TOTAL_SHEEP."),
    "RAMS": ("head", "Rams (AAA09 class), allocated within ED TOTAL_SHEEP."),
    "OTHER_SHEEP": ("head", "Other sheep (AAA09 class), allocated within ED TOTAL_SHEEP."),
    "EWES": ("head", "EWES_2_PLUS + EWES_UNDER_2."),
    "BREEDING_SHEEP": ("head", "EWES + RAMS."),
    # GOBLIN cattle cohorts (non-pattern)
    "dairy_cows": ("head", "GOBLIN cohort: dairy cows (= DAIRY_COW)."),
    "suckler_cows": ("head", "GOBLIN cohort: suckler cows (= OTHER_COW)."),
    "bulls": ("head", "GOBLIN cohort: bulls (= CSO BULLS)."),
    "GOBLIN_21_CATTLE_COHORT_TOTAL": ("head", "Sum of the 21 GOBLIN cattle cohorts (= TOTAL_CATTLE)."),
    "GOBLIN_10_SHEEP_COHORT_TOTAL": ("head", "Sum of the 10 GOBLIN sheep cohorts (= TOTAL_SHEEP)."),
    # GOBLIN sheep cohorts
    "Lowland ewes": ("head", "GOBLIN sheep cohort: lowland-system breeding ewes (lowland and lowland-cross breed types, DAFM)."),
    "Upland ewes": ("head", "GOBLIN sheep cohort: upland-system breeding ewes (mountain and mountain-cross breed types, DAFM)."),
    "Lowland lamb_less_1_yr": ("head", "GOBLIN sheep cohort: lowland other sheep, lambs under 1 year."),
    "Lowland male_less_1_yr": ("head", "GOBLIN sheep cohort: lowland other sheep, males under 1 year."),
    "Lowland lamb_more_1_yr": ("head", "GOBLIN sheep cohort: lowland other sheep over 1 year (residual)."),
    "Lowland ram": ("head", "GOBLIN sheep cohort: lowland rams."),
    "Upland lamb_less_1_yr": ("head", "GOBLIN sheep cohort: upland other sheep, lambs under 1 year."),
    "Upland male_less_1_yr": ("head", "GOBLIN sheep cohort: upland other sheep, males under 1 year."),
    "Upland lamb_more_1_yr": ("head", "GOBLIN sheep cohort: upland other sheep over 1 year (residual)."),
    "Upland ram": ("head", "GOBLIN sheep cohort: upland rams."),
    # land
    "AREA_FARMED": ("ha", "Area farmed = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA. " + YEAR_BASIS + " Control: AQA06 regional land-use index."),
    "ALL_GRASSLAND": ("ha", "Grassland (pasture, hay, silage, rough grazing in use). " + YEAR_BASIS + " Control: AQA06 regional index."),
    "TOTAL_CEREALS": ("ha", "Cereals. " + YEAR_BASIS + " Control: AQA06 regional index."),
    "OTHER_CROPS_HA": ("ha", "Other crops and remaining agricultural area after reconciliation."),
    # farm structure
    "AGRICULTURAL_HOLDINGS": ("holdings", "Agricultural holdings. 2020: published ED value. Other years: CSO FSS/Census controls (2013, 2016, 2020, 2023) interpolated linearly, 2023 held to 2025."),
    "AVERAGE_SIZE_OF_HOLDINGS": ("ha", "Average holding size (published definition in 2020; may differ slightly from AREA_FARMED / AGRICULTURAL_HOLDINGS). Aggregates: area / holdings."),
    "AVERAGE_AGE_OF_HOLDER": ("years", "Mean age of holder. 2020: published ED value. Other years: CSO FSS/Census controls interpolated linearly."),
    "MEDIAN_AGE_OF_HOLDER": ("years", "Median age of holder (ED only; not aggregated)."),
    # Standard Output (fixed 2020 coefficients, IFS SOC 2020)
    "SO_DAIRY_COWS_2020_EUR": ("EUR", "Standard Output of dairy cows, fixed 2020 IFS coefficients by FADN region."),
    "SO_SUCKLER_COWS_2020_EUR": ("EUR", "Standard Output of suckler cows, fixed 2020 coefficients."),
    "SO_BULLS_2020_EUR": ("EUR", "Standard Output of bulls, fixed 2020 coefficients."),
    "SO_FOLLOWERS_2020_EUR": ("EUR", "Standard Output of the 18 pre-adult cattle cohorts (same coefficient across DxD/DxB/BxB within an age-sex class)."),
    "SO_SHEEP_2020_EUR": ("EUR", "Standard Output of the 10 sheep cohorts, fixed 2020 coefficients."),
    "SO_LIVESTOCK_2020_EUR": ("EUR", "Livestock Standard Output = dairy + suckler + bulls + followers + sheep."),
    "SO_CEREALS_2020_EUR": ("EUR", "Cereals Standard Output = TOTAL_CEREALS x fixed 2020 coefficient."),
    "SO_OTHER_CROPS_2020_EUR": ("EUR", "Other-crops Standard Output = OTHER_CROPS_HA x fixed 2020 coefficient."),
    "SO_OTHER_CROPS_CONSERVATIVE_2020_EUR": ("EUR", "Other-crops Standard Output with the conservative (sensitivity) coefficient."),
    "SO_OTHER_CROPS_IMPUTED_HA": ("ha", "Other-crops area valued (= OTHER_CROPS_HA)."),
    "SO_COVERED_TOTAL_2020_EUR": ("EUR", "Covered Standard Output = livestock + cereals + other crops. A production-value indicator, not income or profit."),
    "SO_COVERED_TOTAL_CONSERVATIVE_2020_EUR": ("EUR", "As SO_COVERED_TOTAL_2020_EUR with the conservative other-crops coefficient."),
    "SO_COVERED_PER_HOLDING_2020_EUR": ("EUR per holding", "SO_COVERED_TOTAL_2020_EUR / AGRICULTURAL_HOLDINGS (blank where no holdings)."),
    "SO_COVERED_PER_HOLDING_CONSERVATIVE_2020_EUR": ("EUR per holding", "Conservative covered Standard Output per holding."),
    # derived signature metrics (synthesis/historical)
    "ADULT_COWS": ("head", "dairy_cows + suckler_cows."),
    "DXD_FOLLOWERS": ("head", "Sum of the 6 DxD pre-adult cohorts."),
    "DXB_FOLLOWERS": ("head", "Sum of the 6 DxB pre-adult cohorts."),
    "BXB_FOLLOWERS": ("head", "Sum of the 6 BxB pre-adult cohorts."),
    "FOLLOWER_TOTAL": ("head", "DXD_FOLLOWERS + DXB_FOLLOWERS + BXB_FOLLOWERS."),
    "UPLAND_SHEEP": ("head", "Sum of the 5 upland sheep cohorts."),
    "DAIRY_SHARE_ADULT_PCT": ("%", "100 x dairy_cows / ADULT_COWS."),
    "DXD_SHARE_FOLLOWERS_PCT": ("%", "100 x DXD_FOLLOWERS / FOLLOWER_TOTAL."),
    "DXB_SHARE_FOLLOWERS_PCT": ("%", "100 x DXB_FOLLOWERS / FOLLOWER_TOTAL."),
    "BXB_SHARE_FOLLOWERS_PCT": ("%", "100 x BXB_FOLLOWERS / FOLLOWER_TOTAL."),
    "FOLLOWER_TO_ADULT_RATIO": ("ratio", "FOLLOWER_TOTAL / ADULT_COWS."),
    "CATTLE_PER_FARMED_HA": ("head per ha", "TOTAL_CATTLE / AREA_FARMED."),
    "SO_PER_FARMED_HA": ("EUR per ha", "SO_COVERED_TOTAL_2020_EUR / AREA_FARMED."),
    "UPLAND_SHARE_SHEEP_PCT": ("%", "100 x UPLAND_SHEEP / TOTAL_SHEEP."),
    # multiscale signature tables
    "GEOGRAPHY_TYPE": ("label", "ED, WFD_CATCHMENT, COUNTY, COLM_CATCHMENT or NATIONAL."),
    "GEOGRAPHY_ID": ("code", "CSOED for EDs, WFD_CATCHMENT_ID, county name, Colm catchment name, or IE."),
    "GEOGRAPHY_NAME": ("name", "Name of the geography unit."),
    "COUNTY": ("name", "County of the ED (ED and county rows only)."),
    "SIGNATURE": ("label", "Name of the signature ratio."),
    "NUMERATOR_COLUMN": ("label", "Column the signature's numerator is taken from."),
    "DENOMINATOR_COLUMN": ("label", "Column the signature's denominator is taken from."),
    "NUMERATOR": ("as column", "Numerator value; sum it across units to re-aggregate."),
    "DENOMINATOR": ("as column", "Denominator value; sum it across units to re-aggregate."),
    "SCALE": ("factor", "Multiplier applied to numerator / denominator (100 for percentages)."),
    "VALUE": ("as signature", "Signature value = NUMERATOR / DENOMINATOR x SCALE; blank where DENOMINATOR is zero."),
    # parent-follower relationship tables
    "COHORT": ("label", "Follower cohort (18 DxD/DxB/BxB age-sex cohorts, or bulls)."),
    "ADULT_ORIGIN": ("label", "Parent population: DAIRY (DxD, DxB), SUCKLER (BxB) or ADULT_COWS (bulls)."),
    "BASE_ORIGIN_ADULTS": ("head", "Parent cows in the ED in the signature year."),
    "BASE_COHORT_HEAD": ("head", "Follower cohort head in the ED in the signature year."),
    "ED_COHORT_PER_ADULT_RATIO": ("ratio", "BASE_COHORT_HEAD / BASE_ORIGIN_ADULTS (0 where the ED has no parent cows)."),
    "COUNTY_ORIGIN_ADULT_TOTAL": ("head", "Parent cows in the ED's county."),
    "COUNTY_COHORT_TOTAL": ("head", "Follower cohort head in the ED's county."),
    "ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO": ("ratio", "For COUNTY_RECEIVER cells: follower head / county parent cows."),
    "ORPHAN_SHARE_OF_COUNTY_COHORT": ("share", "For COUNTY_RECEIVER cells: follower head / county follower head."),
    "COHORT_SPATIAL_ROLE": ("label", "LOCAL_ED (parents in the ED), COUNTY_RECEIVER (no parents in the ED, parents in the county), NATIONAL_ORPHAN (none in the county) or NONE (no followers). This is a support classification, not an animal-movement or origin claim."),
    "ORIGIN_GROUP": ("label", "DxD, DxB, BxB or bulls."),
    "PARENT": ("label", "Parent population of ORIGIN_GROUP."),
    "FOLLOWER_HEAD": ("head", "Follower head of ORIGIN_GROUP in the unit (catchments: area-weighted)."),
    "LOCAL_ED_HEAD": ("head", "Follower head in LOCAL_ED cells."),
    "COUNTY_RECEIVER_HEAD": ("head", "Follower head in COUNTY_RECEIVER cells."),
    "NATIONAL_ORPHAN_HEAD": ("head", "Follower head in NATIONAL_ORPHAN cells."),
    "LOCAL_ED_PCT": ("%", "100 x LOCAL_ED_HEAD / FOLLOWER_HEAD."),
    "COUNTY_RECEIVER_PCT": ("%", "100 x COUNTY_RECEIVER_HEAD / FOLLOWER_HEAD."),
    "NATIONAL_ORPHAN_PCT": ("%", "100 x NATIONAL_ORPHAN_HEAD / FOLLOWER_HEAD."),
    # livestock-signature perturbation tables
    "ARM": ("label", "DAIRY_PARENT (dairy cows, DxD and DxB followers), SUCKLER_PARENT (suckler cows, BxB followers), or PRO_RATA (all 21 cohorts; supplementary reference). Each is a 30% national cut shared pro rata across EDs."),
    "METHOD": ("label", "SIGNATURE: follower change follows the ED's own parent relationship, the county's where the ED has no parents, national as fallback; follower geography remains fixed. HEADCOUNT: national followers-per-cow coefficients applied to each ED's cow change, so follower change is attributed to adult-cow geography. UNIFORM: PRO_RATA only."),
    "BASE_CATTLE": ("head", "Baseline cattle."),
    "BASE_LU": ("LU", "Baseline cattle livestock units (fixed schedule of the CSO age-sex groups)."),
    "BASE_CATTLE_SO_2020_EUR": ("EUR", "Baseline cattle Standard Output, fixed IFS 2020 coefficients."),
    "CHANGE_ADULT_COWS": ("head", "Change in dairy + suckler cows (identical in both methods)."),
    "CHANGE_FOLLOWERS": ("head", "Change in the arm's linked follower cohorts (fractional head)."),
    "CHANGE_FOLLOWERS_LOCAL_ED": ("head", "SIGNATURE only: follower change in cells whose parents are in the ED."),
    "CHANGE_FOLLOWERS_COUNTY_RECEIVER": ("head", "SIGNATURE only: follower change in cells with no parents in the ED, driven by the county's parent change."),
    "CHANGE_FOLLOWERS_NATIONAL_ORPHAN": ("head", "SIGNATURE only: follower change driven by the national parent change (no parents in the county)."),
    "CHANGE_CATTLE": ("head", "Change in cattle = adult change + follower change."),
    "CHANGE_LU": ("LU", "Change in cattle livestock units."),
    "CHANGE_CATTLE_SO_2020_EUR": ("EUR", "Change in cattle Standard Output."),
    "CHANGE_CATTLE_PCT": ("%", "100 x CHANGE_CATTLE / BASE_CATTLE."),
    "CHANGE_LU_PCT": ("%", "100 x CHANGE_LU / BASE_LU."),
    "CHANGE_CATTLE_SO_2020_EUR_PCT": ("%", "100 x CHANGE_CATTLE_SO_2020_EUR / BASE_CATTLE_SO_2020_EUR."),
    "PARENT_COWS_PRESENT": ("flag", "True where the ED has the arm's parent cows in the year."),
    "SIGNATURE_CHANGE_FOLLOWERS": ("head", "Follower change, SIGNATURE method."),
    "HEADCOUNT_CHANGE_FOLLOWERS": ("head", "Follower change, HEADCOUNT method."),
    "DIFFERENCE_FOLLOWERS": ("head", "SIGNATURE minus HEADCOUNT follower change (sums to zero nationally)."),
    "SIGNATURE_CHANGE_CATTLE": ("head", "Cattle change, SIGNATURE method."),
    "HEADCOUNT_CHANGE_CATTLE": ("head", "Cattle change, HEADCOUNT method."),
    "DIFFERENCE_CATTLE": ("head", "SIGNATURE minus HEADCOUNT cattle change (sums to zero nationally)."),
    "SIGNATURE_CHANGE_LU": ("LU", "LU change, SIGNATURE method."),
    "HEADCOUNT_CHANGE_LU": ("LU", "LU change, HEADCOUNT method."),
    "DIFFERENCE_LU": ("LU", "SIGNATURE minus HEADCOUNT LU change (sums to zero nationally)."),
    "SIGNATURE_CHANGE_CATTLE_SO_2020_EUR": ("EUR", "Cattle SO change, SIGNATURE method."),
    "HEADCOUNT_CHANGE_CATTLE_SO_2020_EUR": ("EUR", "Cattle SO change, HEADCOUNT method."),
    "DIFFERENCE_CATTLE_SO_2020_EUR": ("EUR", "SIGNATURE minus HEADCOUNT cattle SO change (does not sum to zero: SO coefficients differ by region)."),
    "QUANTITY": ("label", "FOLLOWERS, CATTLE, LU or CATTLE_SO_2020_EUR."),
    "NATIONAL_CHANGE": ("as quantity", "National change, SIGNATURE method."),
    "HEADCOUNT_NATIONAL_CHANGE": ("as quantity", "National change, HEADCOUNT method."),
    "NATIONAL_METHOD_DIFFERENCE": ("as quantity", "SIGNATURE minus HEADCOUNT national change: zero for head and LU; non-zero for SO because coefficients differ by region."),
    "CONSERVED_NATIONALLY": ("flag", "True where both methods give the same national change, so the half-sum is a transfer and is decomposed."),
    "ED_TOTAL_DISPLACEMENT": ("as quantity", "1/2 x sum over EDs of |SIGNATURE - HEADCOUNT|: the quantity the headcount method places in different EDs (for SO: gross ED difference)."),
    "ED_RECEIVER_COMPONENT": ("as quantity", "Part of ED_TOTAL_DISPLACEMENT from followers standing in EDs without the arm's parent cows, which the headcount method cannot place."),
    "ED_RATIO_COMPONENT": ("as quantity", "ED_TOTAL_DISPLACEMENT minus ED_RECEIVER_COMPONENT (never negative): displacement among EDs with parent cows, from follower-per-cow ratios differing from national."),
    "ED_PURE_RATIO_DISPLACEMENT": ("as quantity", "Displacement among EDs with parent cows if parent-less EDs did not exist (national coefficient re-based on those EDs): the cleanest measure of ED-signature information."),
    "RECEIVER_SHARE_OF_ED_DISPLACEMENT_PCT": ("%", "100 x ED_RECEIVER_COMPONENT / ED_TOTAL_DISPLACEMENT."),
    "ED_DISPLACEMENT_PCT_OF_NATIONAL_CHANGE": ("%", "100 x ED_TOTAL_DISPLACEMENT / |NATIONAL_CHANGE|."),
    "WFD_TOTAL_DISPLACEMENT": ("as quantity", "Same half-sum after aggregating ED differences to the 46 WFD catchments (differences inside a catchment cancel)."),
    "WFD_DISPLACEMENT_PCT_OF_NATIONAL_CHANGE": ("%", "100 x WFD_TOTAL_DISPLACEMENT / |NATIONAL_CHANGE|."),
    "COUNTY_TOTAL_DISPLACEMENT": ("as quantity", "Same half-sum after aggregating ED differences to counties."),
    "PARENTLESS_EDS_WITH_FOLLOWERS": ("EDs", "EDs holding the arm's followers but none of its parent cows (inflated in 2020 by published zero dairy cells)."),
}

_GEN = {"DxD": "dairy dam x dairy sire", "DxB": "dairy dam x beef sire", "BxB": "beef dam x beef sire"}
_STAGE = {
    "calves_m": "male calves under 1 year (AAA10 CATTLE_MALE_UNDER_1)",
    "calves_f": "female calves under 1 year (AAA10 CATTLE_FEMALE_UNDER_1)",
    "heifers_less_2_yr": "heifers 1-2 years (AAA10 CATTLE_FEMALE_1_2)",
    "steers_less_2_yr": "males 1-2 years (AAA10 CATTLE_MALE_1_2)",
    "heifers_more_2_yr": "heifers 2 years and over (AAA10 CATTLE_FEMALE_2_PLUS)",
    "steers_more_2_yr": "males 2 years and over (AAA10 CATTLE_MALE_2_PLUS)",
}
_BREED = {
    "MOUNTAIN": "mountain breed type",
    "MOUNTAIN_CROSS": "mountain-cross breed type",
    "LOWLAND": "lowland breed type",
    "LOWLAND_CROSS": "lowland-cross breed type",
    "MOUNTAIN_TYPE": "mountain-type (mountain + mountain-cross)",
    "LOWLAND_TYPE": "lowland-type (lowland + lowland-cross)",
}
_SHEEP_CLASS = {
    "EWES": "ewes",
    "RAMS": "rams",
    "OTHER": "other sheep",
    "OTHER_SHEEP": "other sheep",
    "EWES_2_PLUS": "ewes 2 years and over",
    "EWES_UNDER_2": "ewes under 2 years",
}
_COHORT_RE = re.compile(r"^(DxD|DxB|BxB)_(" + "|".join(_STAGE) + r")$")
_BREED_RE = re.compile(
    r"^(EWES_2_PLUS|EWES_UNDER_2|OTHER_SHEEP|EWES|RAMS|OTHER)_"
    r"(MOUNTAIN_CROSS|LOWLAND_CROSS|MOUNTAIN_TYPE|LOWLAND_TYPE|MOUNTAIN|LOWLAND)$"
)


def describe(column: str) -> tuple[str, str] | None:
    """Return (unit, description) for a public column, or None if unknown."""

    if column in _EXACT:
        return _EXACT[column]
    if column.startswith("CSO_") and column[4:] in _EXACT:
        unit, text = _EXACT[column[4:]]
        return unit, f"CSO control carried in the GOBLIN 31 panel: {column[4:]}. {text}"
    match = _COHORT_RE.match(column)
    if match:
        gen, stage = match.groups()
        return "head", (
            f"GOBLIN cohort: {gen} ({_GEN[gen]}) {_STAGE[stage]}. Split of the CSO age-sex "
            "group by national COHORTS genetic ratios with a DAFM/AIM ED cattle-type prior; "
            "DxD + DxB + BxB equals the age-sex group exactly."
        )
    match = _BREED_RE.match(column)
    if match:
        cls, breed = match.groups()
        return "head", (
            f"{_SHEEP_CLASS[cls].capitalize()}, {_BREED[breed]}: DAFM breed composition applied "
            "within the ED's AAA09 class total."
        )
    return None


def describe_table(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for position, column in enumerate(frame.columns, start=1):
        found = describe(column)
        unit, text = found if found else ("", "")
        rows.append(
            {
                "TABLE_NAME": table,
                "POSITION": position,
                "COLUMN_NAME": column,
                "DTYPE": str(frame[column].dtype),
                "UNIT": unit,
                "DESCRIPTION": text,
            }
        )
    return pd.DataFrame(rows)


def undescribed_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if describe(column) is None]


def sqlite_safe_names(columns: list[str]) -> dict[str, str]:
    """Renames for columns that differ from an earlier column only in case.

    SQLite treats column names case-insensitively, so the wide ED table's CSO
    ``BULLS`` and GOBLIN ``bulls`` cannot coexist. The later column gets the
    suffix ``_goblin``; every rename is recorded in ``_columns``.
    """

    seen: set[str] = set()
    rename: dict[str, str] = {}
    for column in columns:
        name = column
        if name.lower() in seen:
            name = f"{column}_goblin"
            while name.lower() in seen:
                name += "_"
            rename[column] = name
        seen.add(name.lower())
    return rename
