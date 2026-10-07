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
    "WFD_CATCHMENT_LABEL": ("label", "Catchment identifier plus name, used where names repeat (for example Shannon units)."),
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
    "UNDER1_FOLLOWERS": ("head", "Sum of DxD, DxB and BxB male and female calf cohorts aged under one year."),
    "UPLAND_SHEEP": ("head", "Sum of the 5 upland sheep cohorts."),
    "DAIRY_SHARE_ADULT_PCT": ("%", "100 x dairy_cows / ADULT_COWS."),
    "DXD_SHARE_FOLLOWERS_PCT": ("%", "100 x DXD_FOLLOWERS / FOLLOWER_TOTAL."),
    "DXB_SHARE_FOLLOWERS_PCT": ("%", "100 x DXB_FOLLOWERS / FOLLOWER_TOTAL."),
    "BXB_SHARE_FOLLOWERS_PCT": ("%", "100 x BXB_FOLLOWERS / FOLLOWER_TOTAL."),
    "UNDER1_SHARE_FOLLOWERS_PCT": ("%", "100 x UNDER1_FOLLOWERS / FOLLOWER_TOTAL."),
    "FOLLOWER_TO_ADULT_RATIO": ("ratio", "FOLLOWER_TOTAL / ADULT_COWS."),
    "CATTLE_PER_FARMED_HA": ("head per ha", "TOTAL_CATTLE / AREA_FARMED."),
    "SHEEP_PER_FARMED_HA": ("head per ha", "TOTAL_SHEEP / AREA_FARMED."),
    "GRASSLAND_SHARE_FARMED_PCT": ("%", "100 x ALL_GRASSLAND / AREA_FARMED."),
    "CEREAL_SHARE_FARMED_PCT": ("%", "100 x TOTAL_CEREALS / AREA_FARMED."),
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
    "CATCHMENT_VALUE": ("as signature", "Catchment signature recomputed from fractionally aggregated ED numerators and denominators."),
    "ED_WEIGHTED_P10": ("as signature", "Denominator-weighted 10th percentile of intersecting ED signature values inside the catchment."),
    "ED_WEIGHTED_P50": ("as signature", "Denominator-weighted median of intersecting ED signature values inside the catchment."),
    "ED_WEIGHTED_P90": ("as signature", "Denominator-weighted 90th percentile of intersecting ED signature values inside the catchment."),
    "ED_WEIGHTED_P90_P10": ("as signature", "Within-catchment spread: ED_WEIGHTED_P90 - ED_WEIGHTED_P10."),
    "INTERSECTING_EDS": ("EDs", "Number of EDs contributing positive denominator weight to the catchment signature distribution."),
    "DISTRIBUTION_DENOMINATOR": ("as denominator", "Sum of each ED signature denominator multiplied by its ED-catchment area weight."),
    "STRADDLING_EDS": ("EDs", "Number of EDs intersecting more than one WFD catchment."),
    "TOTAL_EDS": ("EDs", "Number of EDs in the model universe for the comparison year."),
    "FOLLOWER_TO_ADULT_RATIO_FRACTIONAL": ("ratio", "Followers per adult cow after fractional ED-to-catchment allocation."),
    "FOLLOWER_TO_ADULT_RATIO_MAJORITY": ("ratio", "Followers per adult cow after assigning each ED wholly to its largest-area catchment."),
    "FOLLOWER_TO_ADULT_ABS_DIFF": ("ratio", "Absolute difference between majority and fractional followers-per-adult-cow."),

    # parent-follower relationship tables
    "COHORT": ("label", "Follower cohort (18 DxD/DxB/BxB age-sex cohorts, or bulls)."),
    "ADULT_ORIGIN": ("label", "Parent population: DAIRY (DxD, DxB), SUCKLER (BxB) or ADULT_COWS (bulls)."),
    "BASE_ORIGIN_ADULTS": ("head", "Parent cows in the ED in the signature year."),
    "BASE_COHORT_HEAD": ("head", "Follower cohort head in the ED in the signature year."),
    "ED_COHORT_PER_ADULT_RATIO": ("ratio", "BASE_COHORT_HEAD / BASE_ORIGIN_ADULTS (0 where the ED has no parent cows)."),
    "COUNTY_ORIGIN_ADULT_TOTAL": ("head", "Parent cows in the ED's county."),
    "COUNTY_COHORT_TOTAL": ("head", "Follower cohort head in the ED's county."),
    "ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO": ("ratio", "For county-parent-support cells: follower head / county parent cows; legacy column name retained for compatibility."),
    "ORPHAN_SHARE_OF_COUNTY_COHORT": ("share", "For county-parent-support cells: follower head / county follower head; legacy column name retained for compatibility."),
    "COHORT_SPATIAL_ROLE": ("label", "Parent-support class: LOCAL_PARENT, COUNTY_PARENT_SUPPORT, NATIONAL_PARENT_SUPPORT or NONE. This is not an animal-movement or origin claim."),
    "COHORT_SPATIAL_ROLE_LEGACY": ("label", "Legacy internal support label retained for compatibility: LOCAL_ED, COUNTY_RECEIVER, NATIONAL_ORPHAN or NONE."),
    "ORIGIN_GROUP": ("label", "DxD, DxB, BxB or bulls."),
    "PARENT": ("label", "Parent population of ORIGIN_GROUP."),
    "FOLLOWER_HEAD": ("head", "Follower head of ORIGIN_GROUP in the unit (catchments: area-weighted)."),
    "LOCAL_PARENT_HEAD": ("head", "Follower head in EDs where corresponding parent cows are present locally."),
    "COUNTY_PARENT_SUPPORT_HEAD": ("head", "Follower head in EDs where corresponding parent cows are absent locally but present elsewhere in the county."),
    "NATIONAL_PARENT_SUPPORT_HEAD": ("head", "Follower head in EDs whose county has no corresponding parent cows."),
    "LOCAL_PARENT_PCT": ("%", "100 x LOCAL_PARENT_HEAD / FOLLOWER_HEAD."),
    "COUNTY_PARENT_SUPPORT_PCT": ("%", "100 x COUNTY_PARENT_SUPPORT_HEAD / FOLLOWER_HEAD."),
    "NATIONAL_PARENT_SUPPORT_PCT": ("%", "100 x NATIONAL_PARENT_SUPPORT_HEAD / FOLLOWER_HEAD."),
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
    if column.endswith("_FRACTIONAL"):
        return "head", "Catchment total under fractional ED-to-catchment allocation."
    if column.endswith("_MAJORITY"):
        return "head", "Catchment total under whole-ED majority-area assignment."
    if column.endswith("_ABS_DIFF_PCT"):
        return "%", "Absolute majority-versus-fractional catchment difference as a percentage of the fractional value."
    if column.endswith("_DIFF"):
        return "head", "Majority minus fractional catchment total."
    if column.startswith("STRADDLING_") and column.endswith("_SHARE_PCT"):
        return "%", "Share of the national quantity located in EDs intersecting more than one WFD catchment."
    if column.startswith("STRADDLING_"):
        return "head", "National quantity located in EDs intersecting more than one WFD catchment."
    if column.startswith("MEDIAN_") and column.endswith("_ABS_DIFF_PCT"):
        return "%", "Median absolute catchment difference between majority and fractional allocation."
    if column.startswith("MAX_") and column.endswith("_ABS_DIFF_PCT"):
        return "%", "Maximum absolute catchment difference between majority and fractional allocation."
    if column.startswith("MEDIAN_FOLLOWER_TO_ADULT_ABS_DIFF"):
        return "ratio", "Median absolute catchment difference in followers per adult cow."
    if column.startswith("MAX_FOLLOWER_TO_ADULT_ABS_DIFF"):
        return "ratio", "Maximum absolute catchment difference in followers per adult cow."
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
