# Using the historical baseline outputs

This is the guide for someone who wants to use the GOBLIN-Spatial 2015-2025 historical baseline without reading the code.

## Build it

```bash
pip install -e ".[geo,reporting,query]"
goblin-spatial fetch-data --verify-only
python scripts/build_historical_release.py
```

The release script runs, in order: the core build, historical validation, cattle diagnostics, the county/catchment/national views, a cross-product coherence audit, and the release bundle. It stops at the first failure. A full run takes about three minutes.

Everything a user needs is then in one folder:

```text
reporting/report_data/historical/
├── historical_results.sqlite     every table, one file (R, QGIS, DB Browser, Excel via ODBC)
├── historical_results.duckdb     the same tables for DuckDB
├── <table>.csv / <table>.parquet one pair per table
└── historical_results_manifest.json   model commit, source checksums, table list
```

CSV and Parquet are the canonical files; the two databases are query copies of the same tables.

## Which table

| Table | Rows | Use it for |
|---|---|---|
| `cso13_ed_year` | 31,427 | The CSO statistical structure: 9 cattle groups (dairy cows, other cows, bulls, male/female under 1, 1-2, 2+) and 4 sheep classes, with land and farm structure. No genetic or breed assumptions. |
| `goblin31_ed_year` | 31,427 | 21 GOBLIN cattle cohorts (DxD, DxB, BxB by age and sex) and 10 sheep cohorts (upland/lowland). The 13 CSO groups are kept as `CSO_` columns. |
| `ed_year` | 31,427 | Everything, wide: CSO groups, cohorts, sheep breed types, land, farm structure, Standard Output and derived ratios. |
| `county_year` | 286 | 26 counties x 11 years. |
| `wfd_catchment_year` | 506 | 46 official WFD catchments x 11 years. |
| `colm_catchment_year` | 407 | 37 GOBLIN-Proj catchments x 11 years. |
| `national_year` | 11 | Ireland. |
| `validation_summary` | | Headline validation results. |
| `baseline_coherence_audit` | | Every cross-product identity, re-derived. All rows must be `PASS`. |
| `validation_detail_*` | | The diagnostics behind the validation summary. |
| `livestock_signature`, `livestock_signature_long` | | Full cohort signatures for 2020 and 2025 at ED, WFD catchment, county, Colm catchment and national scale (see below). |
| `wfd_signature_spread` | | Catchment accounting value paired with denominator-weighted P10, P50 and P90 of intersecting ED signatures. |
| `parent_follower_relationship_*` | | ED parent-follower relationships and their shares by geography. |
| `_columns` | | Unit and meaning of every column in every public table. |
| `_readme` | | The points in this guide, inside the database. |

`YEAR` and `CSOED` key every ED table. Aggregate tables are exact sums of EDs: ED, county, WFD catchment, Colm catchment and national totals always agree. County and catchment are alternative geographies, not a nested hierarchy.

## Livestock signatures (ED and WFD catchment first)

The two primary geographies are the **ED**, for fine-scale spatial pattern, and the **WFD catchment**, as an environmental reporting geography. County, Colm catchment and national rows are provided for context.

| Table | What it holds |
|---|---|
| `livestock_signature` | For 2020 and 2025 and every geography unit: the full 21-cohort cattle state (dairy cows, suckler cows, bulls, and DxD/DxB/BxB by age and sex), adult and follower totals, sheep and upland sheep, farmed area, grassland, covered SO, and the signature ratios. Filter `GEOGRAPHY_TYPE` to `ED` or `WFD_CATCHMENT`. |
| `livestock_signature_long` | Each signature ratio with its numerator, denominator and scale. Re-aggregate by summing numerators and denominators, never by averaging `VALUE`. |
| `wfd_signature_spread` | For each catchment, year and signature: the accounting value plus denominator-weighted ED P10, P50, P90 and P90-P10 spread. All intersecting EDs enter with their fractional crosswalk weight. |
| `parent_follower_relationship_ed` | One row per ED, follower cohort and signature year: parent population (dairy cows for DxD and DxB, suckler cows for BxB, all cows for bulls), parent head, follower head, follower-per-parent ratio, and relationship class. |
| `parent_follower_relationship_shares` | For each ED, WFD catchment, county, Colm catchment and Ireland: follower head by origin group split into `LOCAL_PARENT`, `COUNTY_PARENT_SUPPORT` and `NATIONAL_PARENT_SUPPORT`. The class is an ED property; aggregate rows only say how much of their follower stock sits in each class. |
| `parent_follower_relationship_by_year` | National shares by class for every year 2015-2025. |

Relationship classes: `LOCAL_PARENT` means the follower's corresponding parent cows are in the same ED; `COUNTY_PARENT_SUPPORT` means the ED has followers but the corresponding parent cows occur only elsewhere in the county; `NATIONAL_PARENT_SUPPORT` is the final support level where the county has no corresponding parents.

**Relationship support classes are not movement classes.** They describe only the finest spatial scale at which the parent-follower relationship is supported. The former internal codes are retained in `COHORT_SPATIAL_ROLE_LEGACY` for compatibility.

## Reading catchment results

Catchments have two complementary representations. The accounting value is
computed by transferring additive ED quantities with the full frozen
ED-catchment area crosswalk, summing the numerator and denominator and
recalculating the ratio. The within-catchment structural distribution retains
the intersecting ED signature values and weights each by its denominator
multiplied by the same fractional crosswalk weight. This yields P10, P50 and
P90 values without treating ED percentages as additive.

A majority-inside threshold may be used in a figure to display uncluttered ED
polygons inside a named catchment, but it is a display rule only. It is not
used for the published catchment totals or the `wfd_signature_spread` table.

## Reading the numbers correctly

**2020 is the local census anchor.** 2020 ED values for cattle, sheep, land and holdings are the Census of Agriculture values, with confidentiality-suppressed livestock cells prepared in Stage 00. Reconstructed cattle years close exactly to AAA10 county controls and reconstructed sheep years close exactly to AAA09 regional controls. Land is different: the 2020 census level is retained and surrounding years follow the AQA06 regional change index, so the model is not forced to equal the absolute AQA06 land level. `PROVENANCE` (cattle) and `SHEEP_DATA_STATUS` (sheep) label every ED row; in the two livestock panels they are `CATTLE_PROVENANCE` and `SHEEP_PROVENANCE`.

**2020 and the annual controls.** Model-universe 2020 ED sums sit slightly below the annual controls: census animals in the 552 EDs outside the model universe are reported, not moved in (8,744 cattle, 1,723 dairy cows, 4,518 sheep), and AAA10 and AAA09 are rounded to 100 head. The remaining 2020 step in ED time series is therefore about 0.1% nationally. Before Stage 00 (release v1.1) suppressed cells were stored as zero and 2020 dairy cows sat 187,716 head below AAA10 and sheep 259,807 head below AAA09.

**The 2021-2022 land dip is in the CSO data.** Area farmed falls about 3.9% in 2021-2022 and recovers in 2023 because the AQA06 June series does; the model follows the regional change index. Because 2020 census land is the level anchor, absolute model land totals need not equal AQA06 levels.

**Within an ED, some splits are modelled.** Age-sex groups within other cattle, sheep classes within total sheep, DxD/DxB/BxB genetics and sheep breed types are estimates constrained to the observed or controlled totals. The GOBLIN genetic margins use national COHORTS ratios on AAA10 cow numbers in every year; they are not observed at ED level.

**Standard Output is a production-value indicator** at fixed 2020 IFS coefficients by historic region (381 BMW, 382 S&E). It is not income, profit, welfare or land value. Within an age-sex class, DxD, DxB and BxB carry the same coefficient.

**Ratios are computed after aggregation.** Aggregate-table percentages and per-hectare values are recomputed from summed quantities, never averaged across EDs. Median holder age exists only at ED level.

## Examples

SQLite, from the command line or any client:

```sql
-- national cattle, sheep and farmed area by year
SELECT YEAR, SUM(TOTAL_CATTLE) AS cattle, SUM(TOTAL_SHEEP) AS sheep, SUM(AREA_FARMED) AS ha
FROM cso13_ed_year GROUP BY YEAR ORDER BY YEAR;

-- WFD catchments: catchment value and ED heterogeneity (2020)
SELECT WFD_CATCHMENT, CATCHMENT_VALUE,
       ED_WEIGHTED_P10, ED_WEIGHTED_P50, ED_WEIGHTED_P90
FROM wfd_signature_spread
WHERE YEAR = 2020 AND SIGNATURE = 'FOLLOWER_TO_ADULT_RATIO'
ORDER BY ED_WEIGHTED_P90_P10 DESC;

-- WFD catchment agricultural context
SELECT WFD_CATCHMENT, CATTLE_PER_FARMED_HA, SHEEP_PER_FARMED_HA,
       GRASSLAND_SHARE_FARMED_PCT, CEREAL_SHARE_FARMED_PCT
FROM livestock_signature
WHERE GEOGRAPHY_TYPE = 'WFD_CATCHMENT' AND YEAR = 2020;

-- ED signatures for mapping (2025)
SELECT GEOGRAPHY_ID AS CSOED, DAIRY_SHARE_ADULT_PCT, DXB_SHARE_FOLLOWERS_PCT, FOLLOWER_TO_ADULT_RATIO
FROM livestock_signature WHERE GEOGRAPHY_TYPE = 'ED' AND YEAR = 2025;

-- what a column means
SELECT COLUMN_NAME, UNIT, DESCRIPTION FROM _columns
WHERE TABLE_NAME = 'goblin31_ed_year' AND COLUMN_NAME LIKE 'DxB%';
```

Python:

```python
import pandas as pd, sqlite3
con = sqlite3.connect("reporting/report_data/historical/historical_results.sqlite")
eds_2020 = pd.read_sql("SELECT * FROM goblin31_ed_year WHERE YEAR = 2020", con)
# or, without a database:
panel = pd.read_parquet("reporting/report_data/historical/goblin31_ed_year.parquet")
```

R:

```r
library(DBI)
con <- dbConnect(RSQLite::SQLite(), "reporting/report_data/historical/historical_results.sqlite")
county <- dbGetQuery(con, "SELECT * FROM county_year WHERE YEAR = 2025")
```

**SQLite column names.** SQLite ignores case in column names, so in the SQLite copy of `ed_year` the GOBLIN cohort `bulls` is stored as `bulls_goblin` (the CSO group `BULLS` keeps its name). `_columns.SQLITE_COLUMN_NAME` records this. CSV, Parquet and DuckDB keep the original names.

## Checking a build

`baseline_coherence_audit` re-derives, from the output files and the public inputs, that:

- every ED product shares one YEAR x CSOED backbone (2,857 EDs x 11 years);
- the 13 CSO groups add up, 2020 equals the prepared census input and keeps every published AVA42 cell, and other years equal AAA10 and AAA09;
- the 31 cohorts reproduce the CSO groups exactly;
- later products change no earlier value;
- land accounts close and follow AQA06;
- Standard Output recomputes from head counts and coefficients;
- every aggregate table is the sum of EDs;
- counts, land, holdings, holder age and provenance are complete.

CI rebuilds the release on every change and fails if any check fails.

See also: `docs/data_dictionary.md` (variable definitions), `docs/historical_results_bundle.md` (manuscript tables), `docs/validation.md` (validation design), `docs/methodology.md` (method).


**Farm holdings after 2023.** The holding count reaches the 2023 Farm Structure Survey control and is held at that latest observed value through 2025. Report observed/reconstructed change in holdings through 2023 rather than interpreting 2024-2025 as new survey observations.

**Cattle cohort input step.** The visible 2016-2017 drop in national DxD follower share is inherited from the COHORTS relationship input: the DxD-to-dairy-cow coefficient falls between those years. It should be attributed to the biological input series rather than interpreted as an ED allocation artefact.

**County sheep reporting.** Manuscript county sheep quantities should be taken from the released tables, which are controlled to the AAA09 regional/State series used by the model, rather than from auxiliary workbook layouts that do not reproduce those totals.
