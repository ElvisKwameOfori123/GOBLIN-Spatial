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

## Frozen reproducibility release

The two large spatial inputs used by the first soil stage are preserved in the
published Zenodo dataset:

**GOBLIN-Spatial Frozen Spatial Input Bundle for Irish Electoral Division and
Soil Analysis, Version 0.1.0**

- version-specific DOI: `10.5281/zenodo.21906755`
- all-versions/concept DOI: `10.5281/zenodo.21906754`
- published: 2026-08-12
- licence recorded on Zenodo: CC BY 4.0

Model execution pins the **version-specific DOI/record** so a later Zenodo
version cannot silently change the spatial inputs underlying an analysis. The
concept DOI is retained for citation/discovery of the evolving dataset family.

The record currently contains:

- `Electoral_Divisions.zip`
- `INSM250k_ING_1b.zip`

The files are fetched on demand by `goblin-spatial fetch-data`, checksum
verified, and unpacked under `data/external/spatial/`, which is excluded from
ordinary Git history.

## Authoritative ED universe

The CSO SAPS shapefile contains 3,409 ED geometries. The current validated 2020
GOBLIN-Spatial livestock baseline contains 2,857 production EDs. The baseline
is authoritative: the overlay must select exactly those 2,857 geometries before
intersecting soil. A successful geometry source therefore has 100% key coverage
of the baseline but may contain additional ED polygons.

Compound codes are canonicalised member-by-member, e.g.
`08045/08046 -> 8045/8046`, so leading zeros cannot break the join.

## Raw sources

### CSO SAPS ED geography

Zenodo archive destination:

`data/external/spatial/ed/Electoral_Divisions.zip`

After verified extraction, the principal file is:

`data/external/spatial/ed/Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.shp`

The `.shx`, `.dbf` and `.prj` members are required beside it.

### Irish Soil Information System

Zenodo archive destination:

`data/external/spatial/sis_soils/INSM250k_ING_1b.zip`

The bundle contains `INSM250k_ING.shp` and its sidecars plus source metadata.
The shapefile's raw `Associatio` field is retained as the initial soil
identifier. The neutral overlay does not infer component-series proportions
from the association code.

### LPIS 2020 audit

Expected local workbook:

`data/external/spatial/lpis/LPIS_2020_audit.xlsx`

LPIS is **not** part of Zenodo spatial release v0.1.0. It is retained for the
later agricultural-grassland mask / denominator validation stage and is not yet
used to alter the first ED x SIS association overlay.

## Why the raw files are external

The SIS `.shp` inside the supplied archive is larger than GitHub's normal
single-file workflow is intended to carry. Raw GIS binaries are therefore kept
outside Git. The Zenodo release provides the frozen research copy; the manifest
pins the archive checksums and principal extracted shapefiles so downloaded data
can be verified before scientific use.

This gives the project the following separation:

```text
GitHub repository
    -> code, tests, controls, manifest

Zenodo version 0.1.0
    -> frozen ED + SIS raw spatial inputs

local data/external/spatial/
    -> verified cache/extraction used at runtime
```

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

Those are later stages. In particular:

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
