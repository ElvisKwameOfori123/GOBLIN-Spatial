# GOBLIN-Spatial collaborator / AI handover

Last updated: 2026-08-21
Working branch: `scenario-v1-refactor`

This is the continuity note for the current v1 scenario refactor. Read it before changing scenario, soil, LPIS, released-land or alternative-land allocation code.

## 1. Historical baseline is frozen

The verified historical reconstruction is already merged into `main` and has a permanent `baseline-v1-verified` checkpoint. Do not redesign it to make scenario code easier.

```text
CATTLE
01 -> 02 -> 05C
          \
           04 MERGE
          /
SHEEP
03A -> 03B -> 05A -> 05B -> 05D
          |
          v
31 livestock cohorts
          |
          v
06 Land + crops + farm structure / SE
          |
          v
07 Clean validated export
          |
          v
08 Fixed-2020 Standard Output
          |
          v
09 ED cohort signatures
          |
          v
HISTORICAL BASELINE COMPLETE
```

Historical controls are 2,857 agricultural EDs, 2015-2025, 31,427 ED-year rows, 21 cattle cohorts and 10 sheep cohorts. Stage 08 Standard Output is production-value exposure, not income, profit or welfare. Stage 09 is the final historical boundary because it freezes the ED-specific biological relationships used by future cattle transitions.

08B, 08C, LPIS and SC1-SC3 are downstream of the historical baseline.

## 2. Governing scenario rule

> National GOBLIN controls quantities. GOBLIN-Spatial resolves spatial incidence, opportunity and feasibility.

The principal chain is:

```text
select 2020 or 2025 Stage-08 baseline
        +
editable national scenario row
        |
        v
SC1 cattle transition + exposure + released land
        |
        v
freeze SC1
        |
        v
SC2 08B + matched LPIS + independent 08C
        |
        v
mature opportunity / physical eligibility
        |
        v
SC3 explicit national targets
        |
        v
joint Stage-A allocation
        |
        v
sequential rewetting on remaining feasible land
        |
        v
realised conversion + unmet target + residual land
```

Always preserve:

```text
PotentialRelease != Opportunity != RealisedConversion
GrossRelease != ResidualAvailableLand
```

## 3. Editable pathway authority

Current national scenario endpoints and land-use targets come from:

```text
data/controls/scenario/GOBLIN_Scenario_Controls.csv
```

Do not copy obsolete values from older standalone SC3 scripts into the package. The standalone scripts are used to recover scientific mathematics, not to override the editable control table.

Current active pathways are `SI_SG`, `BE_SG` and `ALL_GAS_NZ`.

The control table does not store a fixed baseline grassland total. A run selects 2020 or 2025 and calculates:

```text
BaselineGrassland = sum(ALL_GRASSLAND in selected baseline)
GrossRelease      = BaselineGrassland - TARGET_LIVESTOCK_LAND_HA
```

## 4. SC1 scientific contract

SC1 is the complete pre-opportunity transition stage.

It:

- solves the dairy and suckler endpoint across the existing ED livestock footprint;
- propagates the validated 21-cattle-cohort structure using Stage-09 ED signatures;
- keeps sheep unchanged in the principal cattle-transition study;
- calculates fixed-2020 Standard Output exposure after the physical livestock state is solved;
- reports Gini, concentration, county incidence, protection relief, displaced burden and pathway/allocation sensitivity as diagnostics only;
- spatialises the externally controlled national livestock-land release; and
- freezes the ED released-land vector for all downstream work.

Principal allocation policies currently include `PRORATA`, `DAIRY_PROTECTION`, `ECONOMIC_CAPACITY_PROTECTION` and `SOCIAL_VULNERABILITY_PROTECTION`. Protection changes where contraction falls, not the national endpoint. Expansion, where an endpoint requires it, remains within the existing category footprint rather than seeding new ED livestock activity.

Stage-09 follower relationships remain `LOCAL_ED`, `COUNTY_RECEIVER`, `NATIONAL_ORPHAN` and `NONE`. These are accounting/propagation relationships, not observed animal movements.

### SC1 land release and 08B

08B agricultural capability is attached before the principal released-land spatialisation because its G1/G2/G3 grassland cells provide physical capacity for the fixed national release. This does not make soil the national land-release authority.

The correct hierarchy is:

```text
external/pathway national gross release
        +
solved livestock / pasture-DM spatial propensity
        +
08B G1/G2/G3 ED capacity
        |
        v
GOBLIN_RELEASED_G1_HA
GOBLIN_RELEASED_G2_HA
GOBLIN_RELEASED_G3_HA
        |
        v
GOBLIN_RELEASED_GRASSLAND_HA
```

The G1+G2+G3 released hectares must close exactly to the frozen ED release. 08C never moves SC1 release. LPIS never moves SC1 release.

The parent-GOBLIN pasture-DM calculation remains a spatial/biological signal and diagnostic. It does not independently invent the national released hectares.

## 5. Two soil representations are deliberately separate

### 08B agricultural capability

Cathal/NFS capability retains Classes 1-6 and G groups:

```text
C1 + C2 -> G1
C3 + C4 -> G2
C5 + C6 -> G3
```

`fsizuaa` is a source weighting denominator only. `ALL_GRASSLAND` remains the authoritative ED grassland quantity.

The compact 08B source universe is resolved to the 2,857 model EDs using direct ED records, compound components and the validated fallback hierarchy. It must contain the six class shares, G1/G2/G3 shares, peat/cutover context and forest Yield Class information needed by SC2/SC3.

### 08C mapped physical soil

Colm/IFS mapped soil remains independent physical context. It carries categories such as deep/shallow well drained, poorly drained, peaty, alluvium, peat and miscellaneous, together with mapped SG summaries.

Do not blend 08C with 08B. Do not multiply 08C mapped soil shares by `ALL_GRASSLAND` and call the result observed grassland-by-soil hectares. In particular:

```text
G3 != peat
mapped peat != farmed peat
mapped peat != automatically rewettable grassland
```

## 6. Mature SC2 v3.1 has been recovered and ported

The recovered scientific source is `SC2_GOBLIN_Spatial_Dual_Soil_Land_Opportunity_v3_1_20260820.py`. Its package implementation is:

```text
src/goblin_spatial/land/sc2_opportunity.py
```

and it is wired through:

```text
src/goblin_spatial/land/sc2_context.py
```

SC2 sequence is now:

```text
frozen SC1 release including G1/G2/G3
        -> matched-year compact LPIS
        -> independent compact 08C
        -> mature Opportunity-v2 scores
        -> released Class 1-6 reconstruction
        -> organic/mineral indicators
        -> SC3 physical eligibility quantities
```

Required closure:

```text
C1 + C2 = frozen released G1
C3 + C4 = frozen released G2
C5 + C6 = frozen released G3
C1+...+C6 = frozen ED release
```

The mature `0.85*G1 + 0.80*G2 + 0.70*G3` expression is retained as SC2 Opportunity-v2 productivity science. It is not used to generate or divide SC1 released hectares.

SC2 opportunity scores include forestry, rewetting, AD grass, willow, energy grass and nature/restoration. They rank/describe overlapping opportunity and are not realised conversion hectares.

SC3-ready physical quantities include the Class 1-6 release, tillage, strict tillage, forest, AD/biorefinery grass, willow, wide-willow and organic/rewetting envelopes.

## 7. LPIS rule and cost guardrail

LPIS is an observed baseline-year context layer:

```text
2020 scenario start -> corrected 2020 LPIS v2
2025 scenario start -> validated 2025 LPIS v1
```

Source pins remain:

- 2020: Zenodo record `21922002`, `LPIS_2020_GOBLIN_reduced_v2.parquet`;
- 2025: Zenodo record `21918924`, `LPIS_2025_GOBLIN_reduced.parquet`.

The compact runtime target is exactly:

```text
2,857 EDs x 2 LPIS snapshots = 5,714 rows
```

Normal SC1-SC3 runs must consume the compact ED profile only. They must never automatically download the multi-GB parcel sources or rerun the parcel/ED spatial overlay.

`CLAIMED_AREA_HA` remains the principal LPIS agricultural accounting quantity. Do not apply commonage fraction to claimed area a second time. Repeated parcel IDs are not blindly dropped. Applicant/herd identifiers are QA-only and must not enter publication controls.

Previous local runs prove that compact LPIS caches existed and were reused without repeating the parcel overlay. Before any expensive rebuild, search local/File Library history for the existing corrected compact control or the cached 2020/2025 ED profiles.

## 8. Mature SC3 v2.7 has been recovered and ported

The recovered scientific source is `SC3_GOBLIN_Spatial_Final_Transition_Appraisal_v2_7_SEQUENTIAL_REWETTING_20260820.py`. Package implementation:

```text
src/goblin_spatial/land/sc3_allocation.py
```

The old simple sequential Stage-A allocator is no longer the principal design.

### Stage A

Five uses are solved jointly by continuous linear programming:

```text
AD_GRASS
BIOREFINERY_GRASS
WILLOW
ADDITIONAL_TILLAGE
FOREST
```

The LP is lexicographic:

1. minimise total unmet national target hectares;
2. hold that minimum unmet total fixed and maximise opportunity ranking, with target-normalised soft scores.

Hard SC2 capacities and shared physical pools prevent the same released hectare from satisfying overlapping uses twice. Principal individual envelopes are Classes 1-4 for AD/biorefinery, Classes 1-3 for willow, Classes 1-3 for tillage, and Classes 1-5 for forest. Forest also requires finite positive Yield Class context. Strict-tillage and wide-willow remain explicit sensitivity switches.

### Stage B rewetting

Rewetting is handled only after Stage A. Principal physical capacity uses the externally anchored 141,000 ha national drained-organic-grassland stock, spatialised by:

```text
ALL_GRASSLAND * IFS_PEAT_CUTOVER_UAA_SHARE
```

and normalized to the national stock. That ED stock is intersected with released land and then tightened to the actual post-Stage-A Available residual. This prevents physical double assignment.

`RELEASED_ORGANIC_WEIGHT_HA` remains an unscaled SC2 diagnostic/spatial signal. Colm/IFS mapped peat remains independent context and does not manufacture the 141 kha stock.

The parent-GOBLIN Available balancing item is not rewritten. SC3 additionally reports the physically uncommitted residual after the rewetting overlay.

For every use:

```text
Realised <= Target
Unmet = Target - Realised
```

and at ED level:

```text
Stage-A realised + rewetting realised + final residual = frozen SC1 release
```

The allocator must report unmet targets rather than broaden eligibility silently.

## 9. Current package wiring

The principal CLI now supports:

```text
--stage SC1
--stage SC2
--stage SC3
```

`SC3` first completes SC1, then mature SC2, then sends the exact `land_use_targets_ha` from the selected editable scenario row into the v2.7 allocator. No SC3 national target is hard-coded in the allocator.

`scipy` is deliberately an optional `scenario` dependency rather than a historical-baseline dependency. The SC3 module lazy-loads the optimizer so baseline users do not need SciPy.

Tiny deterministic contract tests have been added for SC2 closure and SC3 joint-pool/rewetting/forest-YC accounting. They are intended to catch mathematical errors cheaply before any integrated run.

## 10. Compute and Actions budget is a hard implementation constraint

Do not use GitHub Actions as an iterative debugger.

Development order is:

```text
static code/source comparison
        -> tiny deterministic unit/contract tests
        -> no-download preflight
        -> compact-control QA
        -> one meaningful integrated SC1->SC2->SC3 validation
        -> one deliberate CI checkpoint only when justified
```

The no-download preflight lives at:

```text
src/goblin_spatial/scenario/preflight.py
```

It checks Stage 08, scenario controls, compact 08B and, for SC2/SC3, compact LPIS and 08C. Missing compact controls are a hard stop. Preflight must never rebuild heavy sources.

Do not open a scenario PR yet. The heavy LPIS workflow watches the main configuration on pull requests and can trigger expensive work. Keep development on `scenario-v1-refactor` until compact controls and lightweight validation are settled.

## 11. Immediate next work

1. Recover or physically provide the compact runtime controls before considering heavy rebuilds:
   - compact 08B agricultural capability profile;
   - compact 08C mapped physical-soil profile;
   - corrected dual-year 5,714-row LPIS ED control, or the two validated per-year caches from which it can be assembled safely.
2. Validate those files locally/cheaply against the existing preflight schemas and known source universes.
3. Only after compact inputs are available, run one meaningful integrated 2020 scenario first, preferably `SI_SG` + `PRORATA`, and verify SC1, SC2 and SC3 national/ED closure before expanding to other pathways/rules.
4. Then run the full pathway/allocation comparison set and generate the foresight metrics.
5. Update `data_manifest.yaml` only after the exact compact files and checksums are known. Never invent checksums or mark a control frozen before it physically exists in the repository/runtime location.
6. Update public README/status wording after the integrated scenario validation. Do not describe SC1-SC3 as regression-verified before that acceptance run.

## 12. Change-management guardrails

- Work on `scenario-v1-refactor` until explicit approval to merge/open the scenario PR.
- Do not alter the verified Stage 01-09 historical mathematics to accommodate scenario code.
- Do not replace current editable scenario targets with values embedded in older standalone scripts.
- Do not let 08C or LPIS change livestock allocation or move the frozen SC1 release vector.
- Do not let opportunity scores define physical eligibility; SC2 physical capacities come first, scores rank within them.
- Do not force national targets into infeasible land. Report `UnmetTarget`.
- Do not rerun multi-GB LPIS processing when a validated compact control can be recovered/reused.
- Record exact source version IDs and checksums whenever a compact/frozen input is finally packaged.

For deeper detail also read `docs/sc1_sc2_sc3_pipeline.md`, `docs/lpis_v2.md`, `LPIS_SOURCE_PINS.yaml`, `data_manifest.yaml`, and the current editable scenario-control CSV.