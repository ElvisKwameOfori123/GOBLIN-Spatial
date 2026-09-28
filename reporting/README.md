# Reporting

The `reporting/` tree is the presentation and query layer for the **validated GOBLIN-Spatial historical baseline**. It organises baseline outputs for inspection, SQL querying, mapping, figures and tables without changing the underlying reconstruction.

The authoritative scientific state remains the validated ED × year baseline under `data/processed/`. Everything in `reporting/` is derived from that frozen state.

---

## Install reporting dependencies

From the repository root:

```bash
pip install -e ".[reporting]"
```

This installs the geospatial, Parquet and plotting dependencies used by the baseline reporting layer.

To include the optional DuckDB/SQL query interface:

```bash
pip install -e ".[reporting,query]"
```

CSV and Parquet remain the canonical reporting products. DuckDB provides a convenient SQL view over the same tables.

---

## Build the historical reporting bundle

After the baseline, validation diagnostics and catchment products have been built:

```bash
python scripts/build_historical_results_bundle.py
```

The bundle is written to:

```text
reporting/report_data/historical/
```

Core tables include:

```text
ed_year
county_year
wfd_catchment_year
national_year
validation_summary
anchor_reconciliation_2020
so_change_2015_2025
signature_ranges_2020
information_geography_2020
concentration_2020
matched_pairs_2020
stable_ed_sensitivity
multiscale_example_2020
multiscale_county_selection_scores_2020
```

CSV and Parquet versions are written for each table, together with a provenance manifest. When the `query` extra is installed, the same bundle is also exposed through:

```text
reporting/report_data/historical/historical_results.duckdb
```

See [`docs/historical_results_bundle.md`](../docs/historical_results_bundle.md) for the full table contract.

---

## Baseline signatures across spatial scales

The historical synthesis carries livestock-system signatures at four reporting scales:

```text
ED
County
WFD catchment
Ireland
```

Signature metrics are calculated from additive livestock populations **after aggregation** at each scale. Higher-level signatures are therefore reconstructed from the underlying populations rather than obtained by averaging ED percentages.

Current signature measures include:

- dairy share of adult cows;
- dairy-bred, dairy-beef-cross and beef-bred shares of follower cattle;
- follower-to-adult ratio;
- cattle per farmed hectare;
- Standard Output per farmed hectare;
- upland-type share of sheep.

The `ed_year`, `county_year`, `wfd_catchment_year` and `national_year` tables provide the main source for ED, county, catchment and national signature analysis through time. `signature_ranges_2020` provides a direct multiscale comparison for the 2020 anchor.

---

## SQL queries

With the `query` extra installed, open the historical database with DuckDB or query it from Python.

Example national time series:

```sql
SELECT
    YEAR,
    TOTAL_CATTLE,
    TOTAL_SHEEP,
    DAIRY_SHARE_ADULT_PCT,
    DXB_SHARE_FOLLOWERS_PCT,
    SO_PER_FARMED_HA
FROM national_year
ORDER BY YEAR;
```

Example ED query:

```sql
SELECT
    YEAR,
    County,
    EDNAME,
    TOTAL_CATTLE,
    TOTAL_SHEEP,
    DAIRY_SHARE_ADULT_PCT,
    FOLLOWER_TO_ADULT_RATIO,
    SO_PER_FARMED_HA
FROM ed_year
WHERE YEAR = 2020
ORDER BY TOTAL_CATTLE DESC;
```

Example WFD catchment query:

```sql
SELECT
    YEAR,
    WFD_CATCHMENT,
    TOTAL_CATTLE,
    TOTAL_SHEEP,
    DAIRY_SHARE_ADULT_PCT,
    UPLAND_SHARE_SHEEP_PCT,
    SO_PER_FARMED_HA
FROM wfd_catchment_year
WHERE YEAR = 2020
ORDER BY TOTAL_CATTLE DESC;
```

These queries read the same frozen reporting tables used for figures and maps.

---

## Maps and GIS

Historical maps should be derived from the frozen reporting tables and the frozen geometries registered in `data_manifest.yaml`.

The main mapping views are:

```text
ED maps
    livestock totals
    cattle and sheep cohorts
    livestock-system signatures
    land and farm structure
    Standard Output

County maps
    regional totals and signatures

WFD catchment maps
    livestock totals
    catchment signatures
    production-value exposure
```

ED mapping uses the frozen ED geometry. WFD mapping uses the frozen 46-catchment geometry and the validated ED-to-catchment bridge.

Map-ready data should remain a presentation derivative of the baseline tables. Geometry joins do not alter livestock, land, Standard Output or signatures.

---

## Figures and tables

The same historical bundle is intended to support publication tables and figure-ready extracts.

Typical baseline reporting products include:

```text
2015-2025 national time series
ED / county / WFD signature comparisons
livestock-system composition maps
cattle and sheep cohort maps
production-value exposure maps
multiscale ED-county-catchment comparisons
validation summaries
matched-place comparisons
```

Publication figures and tables should be generated from frozen report data rather than by recalculating the baseline.

---

## Reporting structure

Directories are created as needed:

```text
reporting/
├── report_data/     # canonical derived baseline reporting tables
├── figure_data/     # figure-ready extracts
├── table_data/      # table-ready extracts
├── figures/         # generated figures
├── maps/            # generated maps
├── tables/          # rendered tables
├── gis/             # GIS-ready exports
├── query/           # query databases and catalogues
└── explorer/        # optional interactive exploration
```

Generated reporting artefacts are generally ignored by Git. Selected outputs can be archived or published separately when required.

Scientific controls and authoritative model inputs remain under `data/`.

---

## Reporting principle

> **The baseline is calculated once; reporting makes it easier to query, compare, map and communicate.**

Reporting may aggregate, reshape, join geometry or format validated outputs for presentation, but it does not change the historical scientific state.
