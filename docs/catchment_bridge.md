# Catchment bridge

This is a downstream aggregation layer for the validated GOBLIN-Spatial historical baseline. It does not change the ED reconstruction, livestock cohorts, Standard Output, SC1, SC2 or SC3.

## Purpose

The same 2015-2025 livestock system can be viewed at four scales:

```text
ED -> county -> official WFD catchment -> Ireland
```

The ED x year master remains authoritative. County and catchment tables are derived views.

## Catchment geography

The authoritative hydrological geography is the Environmental Protection Agency Water Framework Directive Catchments polygon dataset.

Dataset landing page:

https://data.gov.ie/dataset/water-framework-directive-water-catchments

The public EPA/GSI FeatureServer mirror exposes the WFD Catchments layer as polygon features with:

- layer ID: 2
- catchment identifier field: `CATCHMENTI`
- catchment name field: `NAME`
- spatial reference: EPSG:2157
- 46 catchment features
- GeoJSON query support

The bridge preserves those **46 official WFD catchments** as the primary hydrological output.

A second compatibility output collapses the detailed Upper Shannon and Lower Shannon units to the 37-name catchment system used by Colm Duffy's `GOBLIN-Proj/catchment_data_api`. The 37-unit table is therefore derived from the official WFD result and is not the spatial authority.

## Automatic retrieval and freezing

The build first looks for:

```text
data/inputs/spatial/WFD_Catchments_Frozen.gpkg
```

If that file is absent, the script queries the public EPA WFD Catchments layer through the GSI FeatureServer mirror, verifies that 46 features were returned, and writes the result to the path above as a frozen GeoPackage.

This means a manual EPA download is optional. A locally supplied official catchment file can still be used by passing `--catchment-geometry`.

## Method

A static ED-to-catchment overlay is calculated once. If an ED intersects more than one catchment, its additive quantities are distributed using the fraction of intersected ED area:

```text
ED_CATCHMENT_WEIGHT = ED/catchment intersection area / total mapped intersection area for that ED
```

Weights are normalised to sum to exactly 1 within each model ED. This guarantees national closure for additive variables.

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
data/processed/catchment_closure_diagnostics.csv
```

### Primary WFD output

`goblin_spatial_wfd_catchment_2015_2025.csv` preserves the official WFD catchment identifier and name. It is the preferred dataset for future hydrological and water-quality analysis.

### Colm compatibility output

`goblin_spatial_colm_catchment_2015_2025.csv` aggregates the official WFD result into the 37-name system used by `catchment_data_api`. It exists for comparison and integration with the existing GOBLIN catchment package.

The catchment and county outputs contain the additive livestock cohorts, livestock totals, selected agricultural areas and additive Standard Output components already present in the ED master.

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
