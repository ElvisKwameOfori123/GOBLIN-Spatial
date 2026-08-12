# Agricultural soil integration

## Role in GOBLIN-Spatial

Soil is an ED-level grass-productivity and downstream land-opportunity layer.
It is not a separate livestock model, it does not change the frozen livestock
baseline, and individual holdings are not modelling units.

The principal production-soil workflow now follows the same broad logic used by
GOBLIN grassland production: agricultural soil observations are aggregated to
three production soil groups and used as proportions in the grass-yield
calculation. GOBLIN-Spatial adds spatial resolution by estimating those
proportions separately for each Electoral Division (ED).

```text
holding-linked agricultural soil source
        -> collapse immediately by CSOED using UAA weights
        -> ED GOBLIN soil Group 1/2/3 shares
        -> apply shares to validated ED ALL_GRASSLAND
        -> GOBLIN feed / grass-yield calculation
        -> scenario grassland required
        -> potential spared grassland
```

The holding-linked source is therefore a data-construction input only. Holding
identifiers and source rows do not enter the GOBLIN-Spatial master dataset.

## Agricultural use-range mapping

The source agricultural soil classification contains six use-range classes.
The documented production mapping is:

| Agricultural soil class | Use-range interpretation | GOBLIN production soil group |
| --- | --- | --- |
| 1 | Wide use range | 1 |
| 2 | Moderately wide use range | 1 |
| 3 | Somewhat limited use range | 2 |
| 4 | Limited use range | 2 |
| 5 | Very limited use range | 3 |
| 6 | Extremely limited use range | 3 |

Operationally:

```text
classes 1 + 2 -> G1
classes 3 + 4 -> G2
classes 5 + 6 -> G3
```

`soil_code_nfs` is the mapping authority in the current source. Historical
`soil1_orig`, `soil2_orig` and `soil3_orig` fields are retained in the raw file
for provenance but are not used as the production mapping authority because
they do not reproduce the explicit six-class use-range grouping row by row.

## ED aggregation

For source holding `i` in ED `e`, let `UAA_i` be `fsizuaa` and let `g_i` be the
mapped GOBLIN production soil group. The ED source-area total for soil group `g`
is

```text
A[e,g] = sum_i UAA_i * I(g_i = g)
```

and the ED soil share is

```text
Share[e,g] = A[e,g] / sum_g A[e,g].
```

The source UAA is a **weighting denominator only**. It is not substituted for
the validated CSO/GOBLIN-Spatial land account.

If an ED has validated baseline grassland `ALL_GRASSLAND_e`, its production-soil
hectares are therefore

```text
G1_GRASSLAND_HA = ALL_GRASSLAND_e * G1_SHARE
G2_GRASSLAND_HA = ALL_GRASSLAND_e * G2_SHARE
G3_GRASSLAND_HA = ALL_GRASSLAND_e * G3_SHARE
```

with the enforced identity

```text
G1_GRASSLAND_HA + G2_GRASSLAND_HA + G3_GRASSLAND_HA
    = ALL_GRASSLAND_e.
```

This preserves the authoritative ED land total while introducing spatially
heterogeneous GOBLIN production-soil composition.

## Missing-ED fallback

The compact source profile may not contain every ED in the validated livestock
universe. GOBLIN-Spatial therefore records an explicit hierarchy:

```text
1. ED profile
2. source-UAA-weighted county profile
3. source-UAA-weighted national profile
```

The selected level is recorded as `SOIL_PROFILE_SOURCE` with values `ED`,
`COUNTY_FALLBACK` or `NATIONAL_FALLBACK`. Fallback affects only the soil
production context; it never reallocates livestock or changes `ALL_GRASSLAND`.

## Forestry context

The source also contains Irish Forest Soil (`ifs_soil`) and forest Yield Class
(`yc`) information. These fields are aggregated separately because they answer a
different question from grass production.

The compact ED profile retains, where available:

- UAA-weighted shares of forest Yield Classes 14, 18, 20 and 24;
- `FOREST_YC_WEIGHTED_MEAN`;
- dominant Irish Forest Soil code and its source-area share; and
- number of represented Irish Forest Soil classes.

These are downstream opportunity/context variables. They do **not** determine
livestock reductions and they do **not** mean that potentially spared land is
automatically afforested.

## Source and compact control

The development source is expected at:

`data/external/soil/cathal.csv`

The raw file is excluded from Git because it contains holding-linked records.
Its checksum and role are recorded in `data_manifest.yaml`.

A compact ED control can be generated with:

```text
python scripts/build_ed_agricultural_soil_profile.py \
    data/external/soil/cathal.csv \
    --output data/controls/soil/ED_GOBLIN_soil_profile.csv.xz
```

Normal model execution prefers the compact profile when it exists. During
development the main pipeline can regenerate the ED profile from the external
source if the compact file is absent. If neither soil input is available, the
validated livestock/land baseline can still be built without soil enrichment.

## Relationship to the SIS spatial layer

The Irish Soil Information System (SIS) overlay remains in GOBLIN-Spatial, but
it is no longer required for the principal GOBLIN production-soil calculation.
The existing neutral overlay still answers a valuable spatial question:

```text
validated ED universe
        -> SAPS ED geometry
        -> SIS association polygons
        -> ED x SIS association hectares and shares
```

SIS is retained for:

- independent spatial validation of broad soil patterns;
- peat/mineral/wetness interpretation after potential land release;
- future higher-resolution opportunity analysis; and
- later parcel/spatial extensions when the location of released agricultural
  land is represented at finer than ED resolution.

This avoids false parcel precision in the current model: livestock contraction
and potential grassland release are resolved to the ED, so the principal soil
production input is also an ED-level composition rather than an assumed exact
released parcel.

## Frozen spatial release

The optional SAPS/SIS GIS inputs remain preserved in the published dataset:

**GOBLIN-Spatial Frozen Spatial Input Bundle for Irish Electoral Division and
Soil Analysis, Version 0.1.0**

- version-specific DOI: `10.5281/zenodo.21906755`
- all-versions/concept DOI: `10.5281/zenodo.21906754`
- published: 2026-08-12
- licence recorded on Zenodo: CC BY 4.0

The record contains `Electoral_Divisions.zip` and `INSM250k_ING_1b.zip`. They
remain checksum-pinned and fetchable for optional GIS validation/refinement.

## Authoritative ED universe

The CSO SAPS geography contains 3,409 ED geometries while the current validated
2020 GOBLIN-Spatial livestock baseline contains 2,857 production EDs. The
livestock baseline remains authoritative for scenario modelling. Neither the
Cathal source nor the SAPS/SIS geometry is allowed to redefine that ED universe.

## Interpretation boundary

Production soil answers:

> What GOBLIN grass-production soil composition should characterise this ED?

Potential spared grassland then emerges from the livestock feed/grass balance.
Only afterwards do forestry, peat, wetness, nature, cropland and other land-use
layers become relevant.

The core rule remains:

`PotentialRelease != Opportunity != RealisedConversion`.
