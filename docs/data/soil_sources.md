# Soil and land-context sources

## Role in the production model

The production 2020 scenario runtime uses the frozen repository bundle:

```text
data/controls/land/ED_Land_Context_2020/
├── ED_Soil_Capability_08B.csv
├── ED_Physical_Soil_08C.csv
└── ED_LPIS_Context_2020_RUNTIME.csv
```

These three controls cover the same 2,857 model EDs and are verified by checksum before use. Source-level holding records, parcel files and GIS overlays are not normal runtime inputs.

The historical livestock and land baseline remains authoritative. Soil and LPIS evidence cannot redefine the ED universe, alter historical animal allocation or replace `ALL_GRASSLAND`.

## 08B agricultural capability

08B is the agricultural-capability control used in the principal framework. Six agricultural-use classes are retained and grouped as:

```text
Class 1 + Class 2 -> G1
Class 3 + Class 4 -> G2
Class 5 + Class 6 -> G3
```

The final model-level 08B control preserves the validated source-resolution hierarchy:

```text
2,820 direct ED profiles
37 county-fallback profiles
```

Runtime attaches this already-resolved control directly. It does not repeat the source-resolution procedure.

For each ED, G1/G2/G3 shares are applied to the authoritative historical `ALL_GRASSLAND` total when grassland capacities are required. Therefore:

```text
G1_GRASSLAND_HA + G2_GRASSLAND_HA + G3_GRASSLAND_HA
    = ALL_GRASSLAND
```

08B may constrain where the authoritative national livestock-land release can be represented spatially. It does not determine the national released-land total.

## 08C independent mapped physical soil

08C is a separate mapped physical-soil evidence layer. It is attached only after SC1 livestock and released-land geography are frozen.

08C is not blended into 08B and cannot change livestock allocation or SC1 released hectares. Its purpose is downstream interpretation and physical eligibility in SC2/SC3.

Mapped peat is not automatically farmed peat and is not automatically rewettable land.

## LPIS 2020 context

The frozen LPIS control is a neutral 2020 ED context layer used downstream of SC1. It provides agricultural, grassland, commonage, scheme and other land-context measures required by SC2.

LPIS does not replace `ALL_GRASSLAND`, create released land or determine the national alternative-land targets. It is evidence about opportunity and eligibility only.

## Scenario sequence

The scientific ordering is fixed:

```text
validated historical livestock + land baseline
        -> national scenario livestock endpoint
        -> SC1 ED livestock incidence
        -> authoritative national released land spatialised using livestock pressure + 08B capacity
        -> freeze SC1
        -> attach LPIS 2020 + independent 08C context
        -> SC2 opportunity / eligibility
        -> SC3 feasible allocation of explicit national land-use targets
```

The interpretation rule is:

```text
PotentialRelease != Opportunity != RealisedConversion
```

## Reconstruction boundary

First-principles reconstruction is outside the production runtime. Local reconstruction scripts may be used manually when a researcher possesses the underlying source files, but rebuilt controls must be independently validated before they can replace the frozen repository controls.

Normal model execution does not download source data and does not run GIS reconstruction.
