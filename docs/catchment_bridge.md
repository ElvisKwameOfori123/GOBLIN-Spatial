# Catchment bridge

This is a downstream aggregation layer for the validated GOBLIN-Spatial historical baseline. It does not change the ED reconstruction, livestock cohorts, Standard Output, SC1, SC2 or SC3.

## Purpose

The same 2015-2025 system can be viewed at four reporting scales:

```text
                 -> county
ED (authority)  -> official WFD catchment
                 -> Ireland
```

County and WFD catchment are parallel derived views of the authoritative ED x
year master, not a nested spatial hierarchy.

## Catchment geography

The authoritative hydrological geography is the Environmental Protection Agency Water Framework Directive Catchments polygon dataset.

Dataset landing page:

https://data.gov.ie/dataset/water-framework-directive-water-catchments

The repository contains a frozen copy of the 46-feature EPA WFD catchment
geometry at:

```text
data/inputs/spatial/WFD_Catchments_Frozen.gpkg
```

Its SHA-256 is pinned in both `data_manifest.yaml` and the adjacent
`WFD_Catchments_Frozen.gpkg.sha256` sidecar. The frozen layer uses
`CATCHMENTI` as the catchment identifier, `NAME` as the catchment name and
EPSG:2157 geometry.

The bridge preserves those **46 official WFD catchments** as the primary hydrological output.

A second compatibility output collapses the detailed Upper Shannon and Lower Shannon units to the 37-name catchment system used by Colm Duffy's `GOBLIN-Proj/catchment_data_api`. The 37-unit table is therefore derived from the official WFD result and is not the spatial authority.

## Frozen input contract

Normal production builds are offline with respect to catchment geography.
`scripts/build_catchment_baseline.py` requires the frozen GeoPackage and its
checksum sidecar, verifies the SHA-256 before reading the layer, and fails if
either file is absent or altered. It does not query a live spatial service.

A different catchment file can still be supplied explicitly with
`--catchment-geometry`, but it must have a matching SHA-256 sidecar supplied
with `--catchment-checksum` (or located at
`<catchment-geometry>.sha256`). This prevents silent changes in the
ED-to-catchment weights.

## Method

A static ED-to-catchment overlay is calculated once. If an ED intersects more than one catchment, its additive quantities are distributed using the fraction of intersected ED area:

```text
ED_CATCHMENT_WEIGHT = ED/catchment intersection area / total mapped intersection area for that ED
```

Weights are normalised to sum to exactly 1 within each model ED. This guarantees national closure for additive variables.

A small number of offshore or otherwise uncovered ED polygons may not intersect the WFD catchment polygon layer. These are assigned deterministically to the nearest official WFD catchment in projected coordinates. Such rows are explicitly flagged as `nearest_catchment_fallback`, retain zero polygon coverage and record the nearest-distance value, so they can be audited separately rather than silently absorbed.

The first implementation is deliberately area-weighted. A later agricultural-land or LPIS-weighted crosswalk can replace these weights without changing the aggregation architecture.

## Outputs

Running:

```bash
pip install -e '.[geo]'
python scripts/build_catchment_baseline.py
```

writes:

```text
data/processed/ed_wfd_catchment_crosswalk.csv
data/processed/goblin_spatial_wfd_catchment_2015_2025.csv
data/processed/goblin_spatial_colm_catchment_2015_2025.csv
data/processed/goblin_spatial_county_2015_2025.csv
data/processed/goblin_spatial_national_2015_2025.csv
data/processed/catchment_closure_diagnostics.csv
```

### Primary WFD output

`goblin_spatial_wfd_catchment_2015_2025.csv` preserves the official WFD catchment identifier and name. It is the preferred dataset for future hydrological and water-quality analysis.

### Colm compatibility output

`goblin_spatial_colm_catchment_2015_2025.csv` aggregates the official WFD result into the 37-name system used by `catchment_data_api`. It exists for comparison and integration with the existing GOBLIN catchment package.

The county, catchment and national outputs carry both livestock representations
already present in the ED master: the CSO-controlled groups/totals and the full
31 GOBLIN cohorts. They also carry additive agricultural land, holdings and
fixed-2020 Standard Output components.

Farm-structure averages are not summed. At county, WFD catchment, 37-catchment
compatibility and national scales:

```text
AVERAGE_SIZE_OF_HOLDINGS = AREA_FARMED / AGRICULTURAL_HOLDINGS
```

and `AVERAGE_AGE_OF_HOLDER` is weighted by represented agricultural holdings.
For catchments, those holdings follow the same fractional ED-to-catchment area
weights used by the rest of the bridge. `MEDIAN_AGE_OF_HOLDER` remains ED-only
because a valid higher-level median cannot be recovered from ED medians.

## Accounting rule

For every year and every additive variable:

```text
sum(ED) = sum(county) = sum(46 WFD catchments) = sum(37 Colm catchments) = Ireland
```

The build fails if any derived geography does not reproduce the ED national totals within numerical tolerance.

## Relationship to earlier Irish catchment work

EPA catchment-characterisation and Pollution Impact Potential work has already combined Electoral Division agricultural statistics with WFD hydrological units, soils and agricultural land information. The bridge follows that established spatial logic but supplies a richer GOBLIN-Spatial livestock source layer.

CSO has also published national statistics by WFD catchment using direct geocoded assignment. GOBLIN-Spatial does not have public herd coordinates, so polygon intersection from the ED baseline is the appropriate reproducible approach.

## Relationship to catchment_data_api

Colm's catchment package estimates catchment cohort populations from catchment dairy/suckler/sheep totals using national GOBLIN cohort coefficients. GOBLIN-Spatial now contains reconstructed cohort populations directly at ED level for 2015-2025. The bridge therefore aggregates those spatially explicit ED cohorts to official WFD catchments rather than re-estimating them from national ratios.

The existing package remains useful for 2020 comparison and later integration with catchment land-cover, soil and environmental data.

## Interpretation

These are derived catchment representations of the GOBLIN-Spatial ED baseline. Where an ED crosses a catchment boundary, animal numbers are fractionally allocated because individual herd coordinates are not available in the public baseline. They should not be interpreted as observed animal locations within the intersected part of an ED.
