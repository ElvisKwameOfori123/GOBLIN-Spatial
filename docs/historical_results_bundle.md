# Historical results bundle

The historical model paper uses one canonical result bundle built downstream of the
validated 2015-2025 ED baseline.

Build it after the baseline, historical validation diagnostics and WFD catchment
bridge have been created:

```bash
python scripts/build_historical_results_bundle.py
```

The default output is:

```text
reporting/report_data/historical/
├── ed_year.parquet
├── county_year.parquet
├── wfd_catchment_year.parquet
├── national_year.parquet
├── validation_summary.parquet
├── anchor_reconciliation_2020.parquet
├── so_change_2015_2025.parquet
├── signature_ranges_2020.parquet
├── information_geography_2020.parquet
├── concentration_2020.parquet
├── matched_pairs_2020.parquet
├── stable_ed_sensitivity.parquet
├── multiscale_example_2020.parquet
├── multiscale_county_selection_scores_2020.parquet
├── historical_results.duckdb
└── historical_results_manifest.json
```

CSV companions are written beside every Parquet file.

## Authority

The authoritative scientific state remains:

```text
data/processed/08_GOBLIN_Spatial_Standard_Output_2015_2025.csv
```

The historical result bundle is a derived synthesis/query layer. It never modifies
livestock, land, Standard Output, cohort allocation or catchment allocation.

## Reporting geographies

The same reconstructed system is available at:

```text
Ireland
ED
county
official WFD catchment
```

County and WFD catchment are alternative reporting geographies, not a nested
hierarchy. Signature ratios are calculated after additive populations are
aggregated; ED percentages are never averaged to create a higher-level
signature. Average holding size is recomputed from aggregate farmed area and
holdings, while average holder age is holdings-weighted. Median holder age is
retained only at ED level because ED medians cannot be validly aggregated.

## Main paper checks

The bundle materialises the checks required for the model paper:

- 2020 raw-ED to annual-control reconciliation for total cattle, dairy cows and
  other/suckler cows;
- complete 2015-2025 fixed-coefficient Standard Output change decomposition;
- held-out, external-source, applied and temporal validation summaries;
- 2020 multiscale signature ranges;
- information-geography statistics;
- land-normalised concentration summaries;
- within-county matched ED contrasts using a common farmed-area denominator;
- stable-cattle ED sensitivity at ±2.5%, ±5% and ±10%;
- a pre-specified multiscale illustration chosen by maximum adult-cow-weighted
  within-county dairy-share heterogeneity.

## SQL access

`historical_results.duckdb` contains a query copy of every table. The
CSV/Parquet files remain the canonical reporting products.

Example:

```sql
SELECT YEAR, TOTAL_CATTLE, dairy_cows, suckler_cows,
       DXB_SHARE_FOLLOWERS_PCT, SO_COVERED_TOTAL_2020_EUR
FROM national_year
ORDER BY YEAR;
```

Example local place query:

```sql
SELECT County, EDNAME, TOTAL_CATTLE,
       DAIRY_SHARE_ADULT_PCT, DXB_SHARE_FOLLOWERS_PCT,
       FOLLOWER_TO_ADULT_RATIO, SO_PER_FARMED_HA
FROM ed_year
WHERE YEAR = 2020
ORDER BY TOTAL_CATTLE DESC;
```

A publication workbook can later be generated from these frozen tables without
rerunning the scientific model.
