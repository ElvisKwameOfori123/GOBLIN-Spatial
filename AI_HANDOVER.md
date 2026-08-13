# GOBLIN-Spatial collaborator / AI handover

Last updated: 2026-08-13
Working branch: `agent/ed-dynamics-foundation`
Pull request: keep the current PR in draft unless Elvis Kwame Ofori explicitly asks to merge or mark it ready.

This file is a continuity note for a future collaborator or AI agent. Read it before changing model architecture, LPIS, soil, scenario or land-opportunity code.

## 1. Historical baseline boundary is fixed

The validated historical build ends here:

```text
Cattle
-> Sheep
-> 21 cattle + 10 sheep cohorts
-> Land
-> SE
-> VALIDATE / EXPORT
```

Do not insert soil, LPIS, Standard Output, future scenarios, potential grassland release or alternative-land allocation into the historical reconstruction.

The Ireland implementation contains 2,857 agricultural EDs for 2015-2025, giving 31,427 ED-year rows.

## 2. Scenario architecture

Downstream only:

```text
select 2020 or 2025 baseline
-> cattle scenario
-> 18 distinct pre-adult cattle cohort ripple + adult cohorts
-> sheep unchanged
-> Standard Output exposure
-> GOBLIN pasture-DM demand
-> POTENTIAL_SPARED_GRASSLAND_HA
-> LPIS + soil opportunity context
-> explicit alternative-land allocation only when real targets/shares are supplied
```

`ALL_GRASSLAND` remains the authoritative ED land-accounting total. LPIS does not replace it.

## 3. LPIS frozen source pins

LPIS version family parent record: Zenodo parent `21918923`.

### 2020 — USE THIS FILE

Corrected Zenodo v2 record:

- record: `21922002`
- DOI: `10.5281/zenodo.21922002`
- file: `LPIS_2020_GOBLIN_reduced_v2.parquet`
- Zenodo MD5: `ef6ff159320a13d7059770d20d1a0c3a`
- configured destination: `data/external/spatial/lpis/LPIS_2020_GOBLIN_reduced_v2.parquet`

The corrected 2020 publication derivative was rebuilt from the local QA parquet because the original v1 reduced file predated the final commonage-share fields.

Frozen 2020 QA controls passed:

- records: 1,362,738
- unique parcel IDs: 1,311,162
- rows belonging to repeated parcel IDs: 65,660
- commonage records: 48,132
- claimed area: 4,428,557.86 ha
- share-adjusted digitised area: 5,000,253.25 ha
- share-adjusted eligible area: 4,293,825.24 ha
- share-adjusted geometry area: 4,998,435.39 ha
- commonage claimed area: 337,500.60 ha
- commonage share-adjusted eligible area: 360,121.64 ha

Commonage rule:

```text
COMMONAGE_FRACTION = COM_NUM / COM_DEN
SHARE_DIGITISED_HA = PARCEL_AREA_HA * COMMONAGE_FRACTION
SHARE_ELIGIBLE_HA  = ELIGIBLE_AREA_HA * COMMONAGE_FRACTION
SHARE_GEOMETRY_HA  = GEOMETRY_AREA_HA * COMMONAGE_FRACTION
```

Do NOT multiply `CLAIMED_AREA_HA` by the commonage fraction again.

Repeated parcel IDs are preserved; never blindly `drop_duplicates(PARCEL_ID)`.

Applicant/herd identifiers are QA-only and must not be distributed or used as model controls.

### 2025 — KEEP USING THE VALIDATED v1 FILE

Zenodo v1 record:

- record: `21918924`
- DOI: `10.5281/zenodo.21918924`
- file: `LPIS_2025_GOBLIN_reduced.parquet`
- Zenodo MD5: `8c10e49514997b9bedec77bebd5d52ed`
- configured destination: `data/external/spatial/lpis/LPIS_2025_GOBLIN_reduced.parquet`

Why 2025 is still pinned to v1: Zenodo v2 was created to correct 2020 and currently does not contain the unchanged 2025 parquet. This split-version pin is deliberate, not an error. Do not switch 2020 back to v1 for symmetry.

2025 source QA already established:

- populated LPIS records: 1,543,817
- attribute-empty geometry records excluded from the modelling derivative: 3,378,257
- claimed area: 4,779,815.50 ha
- share-adjusted eligible area: 4,935,728.64 ha
- share-adjusted reference area: 4,798,195.68 ha
- commonage fraction missing records: 0

The DAFM `grasslnd` flag is the primary 2025 grassland authority. `perm_ind` is not permanent pasture and must not be interpreted as such.

## 4. LPIS grass / scheme semantics

2020 core grassland classification is deliberately conservative:

- Permanent Pasture
- Low Input Permanent Pasture
- Traditional Hay Meadow
- Grass Year 1-5

Keep forestry, bog/peat, habitat, energy crops and other agriculture separate.

2020 scheme flags:

```text
GLAS_IND   -> IS_GLAS / IS_AGRI_ENVIRONMENT
ANC_IND    -> IS_ANC
ORG_STATUS -> IS_ORGANIC
```

Validated 2020 record counts:

- GLAS: 265,179
- ANC: 1,084,424
- organic: 24,690

The 2025 QA derivative exposes binary `IS_ACRES`, `IS_ANC` and `IS_ORGANIC` fields. Preserve source semantics; do not invent interpretations for raw/missing codes.

## 5. ED spatial bridge

Frozen SAPS ED geography:

- Zenodo record: `21906755`
- DOI: `10.5281/zenodo.21906755`
- full SAPS geography: 3,409 geometries
- model agricultural ED universe: 2,857 EDs

`CSOED` is the spatial/model join authority. ED names and county names are QA labels only.

The SAPS geography already contains compound model identifiers such as `08045/08046`, so do not perform fuzzy name matching.

For every parcel/ED intersection:

```text
intersection_fraction = intersection_geometry_area / source_record_geometry_area
```

Allocate record-level claimed/eligible/context values by this spatial fraction. Do not apply the commonage fraction to claimed area again.

The compact control must contain exactly:

```text
2,857 EDs x 2 observed LPIS snapshots = 5,714 rows
```

Build command:

```bash
goblin-spatial-lpis --year both
```

Output:

```text
data/controls/lpis/ED_LPIS_opportunity_2020_2025.csv.xz
```

Rebuild this compact control after placing the corrected 2020 v2 parquet and validated 2025 v1 parquet at their configured paths. Do not treat an older 2020 ED control generated from the v1 parcel file as final.

## 6. Soil v2 scientific role

Agricultural soil is a downstream opportunity screen, not an animal-allocation driver.

Cathal/NFS agricultural soil mapping:

```text
soil_code_nfs 1-2 -> G1
soil_code_nfs 3-4 -> G2
soil_code_nfs 5-6 -> G3
```

`fsizuaa` weights source soil shares only. It is not authoritative land area.

Validated `ALL_GRASSLAND` is partitioned by G1/G2/G3 after the livestock baseline is solved.

Soil v2 also retains forestry context and a continuous source-UAA-weighted peat/cutover share for downstream screening. Compound model `CSOED` identifiers must be resolved from component profiles before county/national fallback where possible.

The national SIS soil map remains geographic context/validation and should not be blindly blended with holding-weighted agricultural soil shares as if both represented the same denominator.

## 7. Opportunity v2 interpretation

LPIS and soil inform opportunity, not realised conversion.

Always preserve:

```text
PotentialRelease != Opportunity != RealisedConversion
```

Current opportunity screens include forestry, rewetting, AD grass, willow, energy grass and nature/restoration. They are overlapping screening scores and are not hectare allocations.

LPIS low-input, peat and riparian grass context should constrain conversion-oriented opportunity and strengthen restoration/rewetting evidence where appropriate.

Alternative-land allocation occurs only when explicit national targets/shares are supplied. Never invent policy targets to make the allocator run.

## 8. What to do next

1. Keep the corrected 2020 v2 and validated 2025 v1 source pins.
2. Rebuild the 5,714-row ED LPIS control using the same frozen SAPS geography for both years.
3. Confirm both snapshots report complete commonage-adjusted diagnostics; 2020 should no longer carry the old `CLAIMED_AREA_VALID_ADJUSTED_AREA_INCOMPLETE` warning when using v2.
4. Validate ED/national closure and compare LPIS composition against, but do not replace, `ALL_GRASSLAND`.
5. Feed the selected baseline-year LPIS ED profile into soil/opportunity v2 after `POTENTIAL_SPARED_GRASSLAND_HA` is calculated.
6. Freeze the LPIS/soil opportunity layer only after the corrected 2020 ED profile is regenerated and reviewed.
7. Continue to Standard Output/scenario reporting only after this control is stable.

## 9. Repository / change-management guardrails

- Current development work belongs on `agent/ed-dynamics-foundation`.
- Do not merge the draft PR or mark it ready without explicit owner instruction.
- Do not modify the validated historical cattle/sheep/cohort/land/SE accounting merely to accommodate LPIS or soil.
- Large parcel GeoParquets remain external; normal model/CI runs should consume the compact ED control rather than reprocessing millions of parcels.
- Record exact Zenodo version IDs and checksums whenever changing a frozen external source.

For LPIS-specific implementation details also read `docs/lpis_v2.md` and `data_manifest.yaml`.
