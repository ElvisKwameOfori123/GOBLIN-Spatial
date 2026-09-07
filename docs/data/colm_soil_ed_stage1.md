# Colm mapped soil: Stage 1 ED evidence workflow

## Decision

The first soil task is deliberately limited to one question:

> What mapped soil evidence from Colm's soil-group package is present in each GOBLIN-Spatial Electoral Division?

This stage does **not** derive G1/G2/G3 and does not alter SC1, SC2 or SC3 scenario results.

The direct scientific source is:

```text
soil-group-package.zip
└── soil-group-package/
    ├── agrisyn_soils_reference.gpkg
    └── ed_soil_shares.csv
```

`ed_soil_shares.csv` is the direct ED-level modelling input. The GeoPackage is retained as the spatial provenance/reconstruction resource.

## Physical soil evidence retained

The canonical ED profile retains the mapped hectares and shares of:

```text
Deep well drained
Shallow well drained
Poorly drained
Poorly drained peaty
Alluvium
Peat
Miscellaneous
```

The source fields are:

```text
IFS_MAP_DEEP_WELL_DRAINED_HA
IFS_MAP_SHALLOW_WELL_DRAINED_HA
IFS_MAP_POORLY_DRAINED_HA
IFS_MAP_POORLY_DRAINED_PEATY_HA
IFS_MAP_ALLUVIUM_HA
IFS_MAP_PEAT_HA
IFS_MAP_MISCELLANEOUS_HA
```

The adapter recalculates the corresponding area shares from these source hectares and checks that they close to one.

## ED resolution rules

The model uses the exact GOBLIN-Spatial ED universe.

1. A direct Colm ED match is used as supplied.
2. A compound model ED may be reconstructed only when every component ED is present in Colm's source; physical areas are summed and shares are recalculated.
3. A missing mapped ED is treated as a source/bridge error.
4. County and national average fallback soil is not permitted.

This is intentionally stricter than the historic Cathal/NFS agricultural-capability workflow because Colm's source is mapped spatial evidence rather than a survey profile requiring statistical fallback.

## Critical scientific boundary

Stage 1 must not infer agricultural capability.

```text
Colm mapped physical soil
        -> ED physical soil profile
        -> STOP
```

The output is explicitly marked:

```text
COLM_G1_G2_G3_STATUS = NOT_DERIVED_STAGE_1
```

The later crosswalk from Colm's physical soil evidence to GOBLIN capability groups G1/G2/G3 is a separate scientific decision that must be documented and validated before it can replace the current production 08B capability layer.

## Relationship to ALL_GRASSLAND and LPIS

This Stage-1 adapter does not use `ALL_GRASSLAND` and does not use LPIS. It only establishes what mapped soil resource occurs within each ED.

Later modelling may intersect or interpret this evidence with the agricultural/grassland resource, but that must not be confused with the source soil mapping itself.

Therefore:

```text
Colm soil = mapped physical evidence
LPIS = observed agricultural land-use context
ALL_GRASSLAND = authoritative model grassland accounting total
G1/G2/G3 = later derived agricultural-capability interpretation
```

## Production migration rule

The current production runtime is not changed merely by adding this adapter. The migration sequence is:

```text
1. validate Colm -> ED physical soil evidence
2. freeze the source-derived ED profile
3. design and justify the G1/G2/G3 crosswalk
4. validate the new capability geography against the old production system
5. only then replace the production capability source and rerun SC1 -> SC2 -> SC3
```

This prevents an unvalidated soil classification from silently changing released-land geography or the paper results.
