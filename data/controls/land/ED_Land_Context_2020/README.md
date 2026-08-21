# ED_Land_Context_2020

This directory is the authoritative compact spatial input bundle for the normal 2020 GOBLIN-Spatial scenario runtime.

It contains three validated ED-level CSV controls:

- `ED_Soil_Capability_08B.csv` — 08B agricultural capability used in SC1 released-land capacity and SC2 capability/eligibility context.
- `ED_Physical_Soil_08C.csv` — independent mapped physical-soil context used only after SC1 is frozen.
- `ED_LPIS_Context_2020_RUNTIME.csv` — neutral 2020 LPIS evidence/context used by SC2.

All three controls cover the same 2,857 model EDs. Their exact SHA256 checksums and validation tolerances are recorded in `manifest.json`.

## Runtime boundary

A normal model run is repository-contained:

```text
historical Stage 01-09
        -> frozen ED_Land_Context_2020
        -> SC1
        -> SC2
        -> SC3
```

Normal SC1/SC2/SC3 execution must not download LPIS parcels, soil packages, ED shapefiles or run GIS intersections.

Large first-principles spatial sources are retained only as optional provenance/reconstruction inputs. They are not runtime dependencies.

## Scientific separation

The three files share one runtime directory but remain distinct evidence layers.

### 08B agricultural capability

- 2,820 direct ED profiles
- 37 county-fallback profiles
- Class 1-6 shares close to one
- Class1 + Class2 = G1
- Class3 + Class4 = G2
- Class5 + Class6 = G3

08B may constrain the geography of released grassland in SC1.

### 08C mapped physical soil

08C is independent physical-soil context. It must not alter SC1 livestock allocation or released-land hectares and must not be blended into the 08B capability signal.

### LPIS 2020

LPIS is evidence/context only. It does not replace `ALL_GRASSLAND`, allocate livestock, create released land, or directly choose realised SC3 hectares.

The runtime LPIS control was recovered from mature 2020 SC2 output and cross-validated between SI_SG and BE_SG across all four allocation policies.

## Interpretation rule

```text
PotentialRelease != Opportunity != RealisedConversion
```

GOBLIN establishes the national livestock and land-use transition. GOBLIN-Spatial resolves its geography.
