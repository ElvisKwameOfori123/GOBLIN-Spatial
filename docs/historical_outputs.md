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
| `parent_follower_relationship_*` | | ED parent-follower relationships and their shares by geography. |
| `utility_perturbation_*` | | The controlled 10% dairy / suckler / pro-rata test. |
| `_columns` | | Unit and meaning of every column in every public table. |
| `_readme` | | The points in this guide, inside the database. |

`YEAR` and `CSOED` key every ED table. Aggregate tables are exact sums of EDs: ED, county, WFD catchment, Colm catchment and national totals always agree. County and catchment are alternative geographies, not a nested hierarchy.

## Livestock signatures (ED and WFD catchment first)

The two primary geographies are the **ED**, for spatial pattern, and the **WFD catchment**, for water-framework work. County, Colm catchment and national rows are provided for context.

| Table | What it holds |
|---|---|
| `livestock_signature` | For 2020 and 2025 and every geography unit: the full 21-cohort cattle state (dairy cows, suckler cows, bulls, and DxD/DxB/BxB by age and sex), adult and follower totals, sheep and upland sheep, farmed area, grassland, covered SO, and the signature ratios. Filter `GEOGRAPHY_TYPE` to `ED` or `WFD_CATCHMENT`. |
| `livestock_signature_long` | Each signature ratio with its numerator, denominator and scale. Re-aggregate by summing numerators and denominators, never by averaging `VALUE`. |
| `parent_follower_relationship_ed` | One row per ED, follower cohort and signature year: parent population (dairy cows for DxD and DxB, suckler cows for BxB, all cows for bulls), parent head, follower head, follower-per-parent ratio, and relationship class. |
| `parent_follower_relationship_shares` | For each ED, WFD catchment, county, Colm catchment and Ireland: follower head by origin group split into `LOCAL_ED`, `COUNTY_RECEIVER` and `NATIONAL_ORPHAN`. The class is an ED property; aggregate rows only say how much of their follower stock sits in each class. |
| `parent_follower_relationship_by_year` | National shares by class for every year 2015-2025. |

Relationship classes: `LOCAL_ED` means the follower's parent cows are in the same ED; `COUNTY_RECEIVER` means the ED has followers but none of their parent cows, which the county does have; `NATIONAL_ORPHAN` is the final fallback (no parent cows in the county) and does not occur in 2020 or 2025.

**Read 2020 relationship classes with care.** About 26% of dairy-origin followers are `COUNTY_RECEIVER` in 2020, against 4-6% in every other year. The published 2020 Census reports zero dairy cows in 931 EDs that hold dairy cows in 2019 and 2021, so their followers lose their local parents only in 2020. 2025 (or an adjacent reconstructed year) gives the more consistent receiver structure.

## The 10% utility test

`utility_perturbation_ed`, `utility_perturbation_aggregate` and `utility_perturbation_national` hold a controlled test on the frozen 2020 and 2025 baselines. It is not a scenario or a forecast, and nothing is rebuilt.

| Arm | Reduced by 10% | Unchanged |
|---|---|---|
| `DAIRY_PARENT` | dairy cows, all DxD and DxB followers | suckler cows, BxB, bulls, sheep |
| `SUCKLER_PARENT` | suckler cows, all BxB followers | dairy cows, DxD, DxB, bulls, sheep |
| `PRO_RATA` | all 21 cattle cohorts | sheep |

Each follower cohort changes by the proportion its parents change, through its ED relationship class: the ED's own parents (`LOCAL_ED`), the county's (`COUNTY_RECEIVER`) or the nation's (`NATIONAL_ORPHAN`). Followers stay where the baseline places them. With a uniform 10% cut every targeted cohort falls by exactly 10%, so the national effect of a parent arm is 10% times that system's share of cattle. The information is spatial: where the change lands. Livestock units use one fixed schedule and Standard Output the fixed IFS 2020 coefficients, so changes come only from composition. Head counts stay fractional so the arms are the exact stated transformation.

`utility_perturbation_aggregate` gives the same changes by WFD catchment (area-weighted), county, Colm catchment and Ireland.

## Reading the numbers correctly

**2020 is the observed year.** 2020 ED values for cattle (dairy cows, other cows, other cattle, total), sheep, land and holdings are the published CSO Census of Agriculture 2020 values, unchanged. Every other year is reconstructed and sums exactly to an annual CSO control: AAA10 county cattle, AAA09 regional sheep, AQA06 regional land (all June). `PROVENANCE` (cattle) and `SHEEP_DATA_STATUS` (sheep) label every ED row; in the two livestock panels they are `CATTLE_PROVENANCE` and `SHEEP_PROVENANCE`.

**Expect a step at 2020.** The published 2020 ED sums fall below the June controls: dairy cows by 187,716 head (12%), sheep by 259,807 head (4.7%). This is a difference between two CSO sources with different reference dates and coverage, not a modelled event. Mark 2020 in time-series figures rather than smoothing it.

**The 2021-2022 land dip is in the CSO data.** Area farmed falls about 3.9% in 2021-2022 and recovers in 2023 because the AQA06 June series does; the model follows each AQA06 regional index exactly.

**Within an ED, some splits are modelled.** Age-sex groups within other cattle, sheep classes within total sheep, DxD/DxB/BxB genetics and sheep breed types are estimates constrained to the observed or controlled totals. The GOBLIN genetic margins use national COHORTS ratios on AAA10 cow numbers in every year; they are not observed at ED level.

**Standard Output is a production-value indicator** at fixed 2020 IFS coefficients by historic region (381 BMW, 382 S&E). It is not income, profit, welfare or land value. Within an age-sex class, DxD, DxB and BxB carry the same coefficient.

**Ratios are computed after aggregation.** Aggregate-table percentages and per-hectare values are recomputed from summed quantities, never averaged across EDs. Median holder age exists only at ED level.

## Examples

SQLite, from the command line or any client:

```sql
-- national cattle, sheep and farmed area by year
SELECT YEAR, SUM(TOTAL_CATTLE) AS cattle, SUM(TOTAL_SHEEP) AS sheep, SUM(AREA_FARMED) AS ha
FROM cso13_ed_year GROUP BY YEAR ORDER BY YEAR;

-- WFD catchments: where would a 10% dairy-parent cut remove most grazing LU? (2025)
SELECT GEOGRAPHY_ID, CHANGE_LU, CHANGE_LU_PCT FROM utility_perturbation_aggregate
WHERE GEOGRAPHY_TYPE = 'WFD_CATCHMENT' AND ARM = 'DAIRY_PARENT' AND YEAR = 2025
ORDER BY CHANGE_LU LIMIT 10;

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
- the 13 CSO groups add up, 2020 equals the published values, and other years equal AAA10 and AAA09;
- the 31 cohorts reproduce the CSO groups exactly;
- later products change no earlier value;
- land accounts close and follow AQA06;
- Standard Output recomputes from head counts and coefficients;
- every aggregate table is the sum of EDs;
- counts, land, holdings, holder age and provenance are complete.

CI rebuilds the release on every change and fails if any check fails.

See also: `docs/data_dictionary.md` (variable definitions), `docs/historical_results_bundle.md` (manuscript tables), `docs/validation.md` (validation design), `docs/methodology.md` (method).
