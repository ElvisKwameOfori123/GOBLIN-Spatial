# SIS soil integration

## Role in GOBLIN-Spatial

Soil is a spatial interpretation and grass-productivity layer inside
GOBLIN-Spatial; it is not a separate livestock model and it does not change the
frozen livestock baseline.

The first implementation stage is deliberately neutral:

```text
validated ED livestock baseline
        -> select matching SAPS ED polygons
        -> intersect with SIS association polygons
        -> ED x SIS association hectares and shares
```

No association is converted to a future land use or to GOBLIN soil Group
1/2/3 at this stage.

## Authoritative ED universe

The CSO SAPS shapefile contains 3,409 ED geometries.  The current validated
2020 GOBLIN-Spatial livestock baseline contains 2,857 production EDs.  The
baseline is authoritative: the overlay must select exactly those 2,857
geometries before intersecting soil.  A successful geometry source therefore
has 100% key coverage of the baseline but may contain additional ED polygons.

Compound codes are canonicalised member-by-member, e.g.
`08045/08046 -> 8045/8046`, so leading zeros cannot break the join.

## Raw sources

### CSO SAPS ED geography

Expected principal file:

`data/external/spatial/ed/Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.shp`

The `.shx`, `.dbf` and `.prj` members are required beside it.

### Irish Soil Information System

Expected bundle:

`data/external/spatial/sis_soils/INSM250k_ING_1b.zip`

The current bundle contains `INSM250k_ING.shp` and its sidecars plus source
metadata.  The shapefile's raw `Associatio` field is retained as the initial
soil identifier.  The neutral overlay does not infer component-series
proportions from the association code.

### LPIS 2020 audit

Expected workbook:

`data/external/spatial/lpis/LPIS_2020_audit.xlsx`

This is retained for the later agricultural-grassland mask / denominator
validation stage.  It is not yet used to alter the first ED x SIS association
overlay.

## Why the raw files are external

The SIS `.shp` inside the supplied archive is larger than GitHub's normal
single-file limit.  Raw GIS binaries are therefore gitignored.  Exact principal
inputs are pinned in `data_manifest.yaml` by SHA256 so local copies can be
verified without committing the binaries.

## First output schema

The first processed soil table is long-form and should retain at least:

- `CSOED_CANONICAL`
- `EDNAME` where available
- county identifiers where available
- `SIS_ASSOCIATION`
- `INTERSECTION_HA`
- `MAPPED_SOIL_HA`
- `ED_AREA_HA`
- `SOIL_COVERAGE_FRAC`
- `ASSOCIATION_SHARE_WITHIN_MAPPED_SOIL`

Shares must sum to approximately one within every mapped ED.

## Interpretation boundary

This initial profile answers: **which SIS soil associations are spatially
present inside each baseline ED, and in what mapped proportions?**

It does not yet answer:

- which hectares are agricultural grassland;
- which association components occur within a mapped association;
- which soils correspond to GOBLIN soil Groups 1/2/3;
- which hectares are actually released by the livestock scenario; or
- whether released hectares should become forestry, rewetting, nature,
  cropland or AD grass.

Those are later stages.  In particular:

```text
ED x SIS associations
    -> agricultural-grassland mask
    -> documented SIS/NFS -> GOBLIN G1/G2/G3 production crosswalk
    -> soil-aware grass yield and required grassland
    -> potential spared grassland
    -> soil/capability opportunity screening
    -> optional realised land-use allocation
```

This separation preserves the core model rule:

`PotentialRelease != Opportunity != RealisedConversion`.
