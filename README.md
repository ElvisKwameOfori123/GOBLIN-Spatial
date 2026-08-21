# GOBLIN-Spatial

GOBLIN-Spatial is a constraint-preserving spatialisation framework for translating national GOBLIN livestock and land-use pathways to Irish Electoral Divisions (EDs). The national model remains authoritative for national livestock totals, released land and land-use targets. GOBLIN-Spatial resolves where those transitions occur, how livestock cohorts respond locally, and where released land is compatible with alternative uses.

## Supported production framework

```text
Historical Stages 01-09
        |
        v
Validated ED livestock + land + Standard Output baseline
        |
        v
Frozen repository 2020 land-context bundle
        |
        v
SC1  National livestock transition -> ED livestock incidence -> 21 cattle cohorts
        |
        v
     Authoritative GOBLIN released land -> ED released-land geography
        |
        v
SC2  Frozen release -> LPIS/physical-soil opportunity and eligibility
        |
        v
SC3  Explicit national land-use targets -> feasible ED allocation
```

The central modelling contract is:

> **GOBLIN establishes the national livestock and land-use transition. GOBLIN-Spatial resolves its geography.**

## Historical baseline

The validated historical pipeline reconstructs 2015-2025 livestock and agricultural context for 2,857 EDs. The 2020 ED state is the principal spatial scenario baseline. A 2025 livestock baseline can be selected for SC1 sensitivity analysis, but LPIS-dependent SC2/SC3 runs are deliberately disabled until a separately validated 2025 compact land-context control is frozen.

The baseline contains cattle, sheep, agricultural land, farm-structure variables and fixed-2020 Standard Output exposure. Stage 09 preserves ED-specific livestock cohort signatures used by the scenario engine.

## SC1: livestock transition and released land

SC1 starts from an editable national GOBLIN scenario control and a selected historical ED baseline. Adult dairy and suckler populations are allocated spatially under a selected incidence rule. The remaining cattle cohorts are propagated using the validated cohort relationships while preserving ED-specific signatures and exact national reconciliation where controls are available.

Sheep remain fixed in the principal cattle transition unless an explicit sheep control is supplied. A zero in a scenario table is not interpreted as a command to remove sheep unless that field is explicitly activated as a sheep control.

Protection policies redistribute a fixed national adjustment across EDs. They do not reduce the national adjustment requirement.

Standard Output is a fixed-2020 livestock production-value exposure measure. It is not farm income, profit, welfare or compensation.

### Released land

National GOBLIN land accounting is authoritative. SC1 does not invent a national spared-land total from local pasture calculations. Pasture-DM controls resolve spatial pressure and provide diagnostics, while the externally controlled national released-land total is spatialised across EDs under grassland and 08B agricultural-capability constraints.

All principal pathways use the same system-release method. Dairy, beef and sheep contributions are derived from solved baseline/scenario pasture-DM states and rescaled to the authoritative national release.

## Frozen 2020 land-context bundle

Normal 2020 scenario execution uses the repository directory:

`data/controls/land/ED_Land_Context_2020/`

The authoritative compact files are:

```text
ED_Soil_Capability_08B.csv
ED_Physical_Soil_08C.csv
ED_LPIS_Context_2020_RUNTIME.csv
manifest.json
README.md
```

The three CSV controls cover the same 2,857 ED model universe. Their exact SHA256 checksums are frozen in `manifest.json`. The runtime verifies the original component bytes and joins only the required fields in memory to form the 40-field scientific context used by SC1/SC2.

The previously validated canonical merged-object identity is:

`6a94c125413260ed462c9d5430fe6d39be7df48d282734eea218351829aa6e5d`

### 08B agricultural capability

08B is the principal agricultural-capability layer. It contains Class 1-6 shares, G1/G2/G3 shares, forest yield-class context and peat/cutover context. Its validated provenance is:

```text
2,820 direct ED profiles
37 county-fallback profiles
```

The required relationship is:

```text
Class1 + Class2 = G1
Class3 + Class4 = G2
Class5 + Class6 = G3
```

08B may constrain where livestock-driven released grassland is spatialised.

### 08C independent mapped physical soil

08C is independent physical-soil evidence used only after SC1 is frozen. It does not alter livestock allocation or released-land hectares and is never blended into the 08B capability signal.

Mapped peat is not automatically farmed peat and is not automatically rewettable land.

### LPIS 2020 context

The compact LPIS 2020 control is a neutral evidence layer used in SC2. It was recovered from mature 2020 SC2 results and cross-validated between SI_SG and BE_SG across all four allocation policies.

LPIS does not replace `ALL_GRASSLAND`, allocate livestock, create released land, or directly determine realised SC3 hectares.

## SC2: opportunity and eligibility

SC2 accepts the frozen ED release from SC1 and appends opportunity and physical-eligibility evidence. It never recomputes livestock or released land.

The interpretation is intentionally conservative:

```text
PotentialRelease != Opportunity != RealisedConversion
```

Released land is therefore a spatial budget created by the national livestock pathway, not a prediction that all such land changes use.

## SC3: land-use target allocation

SC3 allocates explicit national land-use targets across the released-land budgets identified in SC1 and screened in SC2. Targets come from `data/controls/scenario/GOBLIN_Scenario_Controls.csv` and are never invented by the spatial allocator.

The allocator respects ED-level released-land budgets, physical eligibility and shared capacity pools. Infeasible targets remain unmet rather than being forced into unsuitable EDs.

Rewetting is handled after the main Stage-A allocation because the organic-soil transition is conceptually distinct from gross livestock-release accounting. Outputs distinguish the GOBLIN parent `Available` land before rewetting from the stricter exclusive residual after realised rewetting.

## Principal commands

Verify the repository-contained inputs without contacting external services:

```bash
goblin-spatial fetch-data --verify-only
```

Build the validated historical baseline:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Run the production scenario chain:

```bash
goblin-spatial-principal SI_SG --baseline-year 2020 --stage SC1
goblin-spatial-principal SI_SG --baseline-year 2020 --stage SC2
goblin-spatial-principal SI_SG --baseline-year 2020 --stage SC3
```

The active scenario IDs are data-driven from `data/controls/scenario/GOBLIN_Scenario_Controls.csv`.

## Reproducibility boundary

A normal clone is intended to contain all compact inputs required to build the historical model and run the complete 2020 SC1-SC3 chain. It must not require a Zenodo download, raw LPIS parcels, soil packages, ED shapefiles or GIS intersections.

Heavy first-principles reconstruction remains possible for provenance work. It requires explicit opt-in:

```bash
goblin-spatial fetch-data --include-reconstruction-sources
```

The LPIS reconstruction command and heavy GitHub workflow are manual reconstruction tools only. They are not part of normal runtime or normal CI.

## Interpretation

GOBLIN-Spatial is a spatial strategic-foresight model, not a parcel-level land-use prediction model. Its purpose is to identify where nationally plausible transitions create concentrated adjustment pressure, where alternative land uses appear spatially compatible, and where transition constraints may require earlier policy preparation.

Results should therefore be interpreted as transition exposure, opportunity and spatial compatibility, not forecasts of individual farm behaviour or realised parcel conversion.

## Validation gate

The scenario framework is accepted only when the repository-contained 2020 land bundle verifies exactly and the relevant SC1-SC3 tests and one real 2020 integrated scenario run are green. Heavy spatial reconstruction is not part of that acceptance gate.
