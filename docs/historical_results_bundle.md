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
├── signature_ranges_2020.parquet (+ 2025 and unrestricted sensitivity tables)
├── information_geography_2020.parquet (+ 2025 and unrestricted sensitivity tables)
├── concentration_2020.parquet (+ 2025 and unrestricted sensitivity tables)
├── matched_pairs_2020.parquet (+ 2025 and unrestricted sensitivity tables)
├── dairy_2020_discontinuity_eds.parquet
├── stable_ed_change_detail.parquet
├── stable_ed_sensitivity.parquet
├── multiscale_example_2020.parquet
├── multiscale_county_selection_scores_2020.parquet
├── cso13_ed_year.parquet
├── goblin31_ed_year.parquet
├── colm_catchment_year.parquet
├── baseline_coherence_audit.parquet
├── validation_detail_*.parquet
├── livestock_signature.parquet (+ _long)
├── parent_follower_relationship_ed.parquet (+ _shares, _by_year)
├── utility_comparison_ed.parquet (+ _wfd), utility_displacement.parquet
├── utility_perturbation_ed.parquet (+ _aggregate, _national)
├── _columns.parquet
├── _readme.parquet
├── historical_results.duckdb
├── historical_results.sqlite
└── historical_results_manifest.json
```

CSV companions are written beside every Parquet file. The bundle requires
`scripts/audit_historical_baseline.py` to have run and passed; it refuses to
build otherwise, and it checks that `ed_year` carries the authoritative master
values unchanged. `docs/historical_outputs.md` is the user guide.

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
- 2020 and 2025 multiscale signature ranges, with the primary ED distributions excluding the 931 documented 2020-only dairy-zero EDs and unrestricted results retained as sensitivity outputs;
- information-geography statistics for 2020 and 2025 on the same primary admissible ED set, plus unrestricted sensitivity results;
- land-normalised concentration summaries for 2020 and 2025 using the same exclusion, plus unrestricted sensitivity results;
- within-county matched ED contrasts for 2020 and 2025 using the same admissible ED set and a common farmed-area denominator, with unrestricted matches retained as sensitivity outputs;
- stable-cattle ED sensitivity at ±2.5%, ±5% and ±10%, reporting raw compositional change alongside county-centred and national-centred change;
- a pre-specified multiscale illustration chosen by maximum adult-cow-weighted
  within-county dairy-share heterogeneity.

## SQL access

`historical_results.duckdb` and `historical_results.sqlite` each contain a
query copy of every table, plus `_columns` and `_readme`. The CSV/Parquet files
remain the canonical reporting products. SQLite ignores case in column names,
so in its copy the GOBLIN cohort `bulls` in `ed_year` is stored as
`bulls_goblin`; `_columns.SQLITE_COLUMN_NAME` records every such rename.

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


## Cross-sectional dairy-discontinuity sensitivity

The published 2020 Census reports zero dairy cows in 931 EDs that have positive
reconstructed dairy populations in both 2019 and 2021. Because a contrast
algorithm that maximises dairy-orientation differences can select these EDs
systematically, they are excluded from the **primary** matched-pair,
concentration, ED signature-range and information-geography analyses. The same
931 EDs are excluded from the corresponding 2025 primary analyses so that both
years use a common admissible ED set. Unrestricted 2020 and 2025 tables are
released alongside the primary outputs as sensitivity checks.

This exclusion changes only manuscript-facing synthesis tables. It does not
alter the authoritative ED baseline, any county or national control, the WFD
crosswalk, livestock signatures themselves, or the utility perturbation.

## Stable-abundance change relative to broader trends

The stable-ED analysis now reports three versions of 2015-2025 compositional
change: raw ED change, ED change centred on the corresponding county aggregate
change, and ED change centred on national aggregate change. County-centred
change is the primary net-of-trend diagnostic because annual cattle controls
enter at county level. National-centred change is retained as a sensitivity
measure. These are reconstruction diagnostics, not claims of independently
observed annual ED transitions.
