# LPIS and soil opportunity v2

LPIS remains downstream of the validated historical baseline. It does not change livestock allocation or replace `ALL_GRASSLAND`.

## Frozen sources and version pinning

The spatial bridge deliberately pins immutable, version-specific Zenodo records:

- SAPS ED geography: Zenodo record `21906755`, DOI `10.5281/zenodo.21906755`.
- LPIS concept/version family: parent record `21918923`.
- **LPIS 2020:** corrected Zenodo **v2** record `21922002`, DOI `10.5281/zenodo.21922002`, file `LPIS_2020_GOBLIN_reduced_v2.parquet`, Zenodo MD5 `ef6ff159320a13d7059770d20d1a0c3a`.
- **LPIS 2025:** validated Zenodo **v1** record `21918924`, DOI `10.5281/zenodo.21918924`, file `LPIS_2025_GOBLIN_reduced.parquet`, Zenodo MD5 `8c10e49514997b9bedec77bebd5d52ed`.

The split-version pin is intentional. Version v2 was published to correct the 2020 commonage/share-adjusted fields and currently does not include the unchanged 2025 parquet. Do not substitute the old 2020 v1 file merely to make both years come from the same record. If a later Zenodo version becomes self-contained, change the model pin only after verifying hashes and rerunning the ED-profile QA.

## Why 2020 was replaced

The original v1 2020 reduced parquet predated the final commonage treatment. The local QA master retained `COM_NUM` and `COM_DEN`, allowing the corrected publication derivative to rebuild:

- `COMMONAGE_FRACTION = COM_NUM / COM_DEN`;
- `SHARE_DIGITISED_HA`;
- `SHARE_ELIGIBLE_HA`;
- `SHARE_GEOMETRY_HA`.

`CLAIMED_AREA_HA` remains the primary agricultural accounting quantity and is **not** multiplied by the commonage fraction a second time.

The corrected 2020 build passed the frozen national controls:

- 1,362,738 records;
- 1,311,162 unique parcel IDs;
- 65,660 rows belonging to repeated parcel IDs;
- 48,132 commonage records;
- claimed area = 4,428,557.86 ha;
- share-adjusted digitised area = 5,000,253.25 ha;
- share-adjusted eligible area = 4,293,825.24 ha;
- share-adjusted geometry area = 4,998,435.39 ha;
- commonage claimed area = 337,500.60 ha;
- commonage share-adjusted eligible area = 360,121.64 ha.

Repeated parcel IDs are deliberately preserved. Applicant/herd QA identifiers are excluded from the publication-safe reduced parquet.

## Grass and scheme semantics

The 2020 core grassland classification is conservative and explicit: permanent pasture, low-input permanent pasture, traditional hay meadow and Grass Year 1-5. Forestry, bog/peat, habitat, energy crops and other agriculture remain separate context classes.

2020 source flags are harmonised as:

- `GLAS_IND` -> `IS_GLAS` / `IS_AGRI_ENVIRONMENT`;
- `ANC_IND` -> `IS_ANC`;
- `ORG_STATUS` -> `IS_ORGANIC`.

The validated 2020 counts are 265,179 GLAS records, 1,084,424 ANC records and 24,690 organic records. The 2025 QA derivative exposes complete binary `IS_ACRES`, `IS_ANC` and `IS_ORGANIC` fields; preserve source semantics and do not reinterpret missing/raw codes without checking the source release.

## Build the compact ED control

Place the version-pinned GeoParquets and ED shapefile at the configured paths, or pass their local paths explicitly:

```bash
goblin-spatial-lpis --year both
```

Configured parcel paths are:

```text
data/external/spatial/lpis/LPIS_2020_GOBLIN_reduced_v2.parquet
data/external/spatial/lpis/LPIS_2025_GOBLIN_reduced.parquet
```

The output is `data/controls/lpis/ED_LPIS_opportunity_2020_2025.csv.xz`, one row per model ED for each observed LPIS snapshot. Expected rows after a complete rebuild are `2,857 x 2 = 5,714`. `CSOED` is the join authority; ED/county names are QA labels.

For every parcel/ED intersection, record-level accounting values are apportioned using the spatial intersection fraction. Claimed area is never multiplied by the commonage fraction again.

## Downstream opportunity screen

Run the downstream screen from a completed cattle scenario:

```bash
goblin-spatial-opportunity screen --scenario-ed-results PATH/scenario_ed_results.csv --baseline-year 2025
```

Soil v2 preserves compound `CSOED` identifiers, resolves compound model EDs from component source profiles before fallback, and can add a continuous source-UAA-weighted IFS peat/cutover share. LPIS v2 adds observed low-input, peat and riparian grass context at the selected 2020 or 2025 baseline.

Opportunity scores remain overlapping ED screening indices. `PotentialRelease != Opportunity != RealisedConversion`. Explicit hectare targets are still required before alternative land is allocated.

## Non-negotiable architecture

Historical baseline:

```text
Cattle -> Sheep -> 31 cohorts -> Land -> SE -> VALIDATE / EXPORT
```

Downstream study layer only:

```text
choose 2020 or 2025
-> cattle scenario
-> cohort ripple
-> fixed sheep
-> Standard Output exposure
-> GOBLIN pasture demand
-> POTENTIAL_SPARED_GRASSLAND_HA
-> LPIS + soil opportunity context
-> explicit alternative-land allocation only when targets/shares are supplied
```

LPIS and soil must never alter historical animal allocation, and LPIS must never replace the validated `ALL_GRASSLAND` ED accounting total.
