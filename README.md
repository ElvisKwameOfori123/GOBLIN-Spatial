# GOBLIN-Spatial

GOBLIN-Spatial is a constraint-preserving spatialisation framework for translating national GOBLIN livestock and land-use pathways to Irish Electoral Divisions (EDs). The national model remains authoritative for national livestock totals, released land and land-use targets. GOBLIN-Spatial resolves where those transitions occur, how livestock cohorts respond locally, and where released land is compatible with alternative uses.

## Current production framework

The supported workflow is deliberately narrow and sequential:

```text
Historical Stages 01-09
        |
        v
Validated ED livestock + land + Standard Output baseline
        |
        v
Frozen neutral ED_Land_Context_2020
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

The validated historical pipeline reconstructs 2015-2025 livestock and agricultural context for 2,857 EDs. The 2020 ED state is the principal scenario baseline. A 2025 livestock baseline can be selected for SC1 sensitivity analysis, but LPIS-dependent SC2/SC3 runs are deliberately disabled until a separately validated 2025 land-context control is frozen.

The baseline contains cattle, sheep, agricultural land, farm-structure variables and fixed-2020 Standard Output exposure. Stage 09 preserves ED-specific livestock cohort signatures used by the scenario engine.

## SC1: livestock transition and released land

SC1 starts from an editable national GOBLIN scenario control and a selected historical ED baseline. Adult dairy and suckler populations are allocated spatially under a selected incidence rule. The remaining cattle cohorts are propagated using the validated cohort relationships while preserving ED-specific signatures and exact national reconciliation where controls are available.

Sheep remain fixed in the principal cattle transition unless an explicit sheep control is supplied. A zero in a scenario table is not interpreted as a command to remove sheep unless that field is explicitly activated as a sheep control.

Supported livestock-incidence policies are defined in `scenario/principal_allocation.py`. Protection policies redistribute national adjustment across EDs. They do not reduce the national adjustment requirement.

Standard Output is a fixed-2020 livestock production-value exposure measure. It is not farm income, profit, welfare or compensation.

### Released land

National GOBLIN land accounting is authoritative. SC1 does not invent a national spared-land total from local pasture calculations. The pasture-DM machinery is used to resolve spatial pressure and as a diagnostic, while the externally controlled national released-land total is spatialised across EDs under grassland and 08B agricultural-capability constraints.

All principal pathways use the same system-release method. Dairy, beef and sheep contributions are derived from solved baseline/scenario pasture-DM states and rescaled to the authoritative national release.

## Frozen 2020 land context

Normal 2020 scenario execution uses one repository-contained neutral ED-level control:

`data/controls/land/ED_Land_Context_2020`

Its logical scientific contract is:

- 2,857 EDs;
- 40 fields;
- 08B agricultural capability;
- independent 08C mapped physical-soil context;
- LPIS 2020 opportunity context;
- preserved 08B provenance of 2,820 direct ED profiles and 37 county fallbacks;
- canonical logical SHA256 `6a94c125413260ed462c9d5430fe6d39be7df48d282734eea218351829aa6e5d`.

These evidence layers share one storage object for reproducible runtime use, but they remain scientifically distinct. 08B can constrain where livestock-driven released land is spatialised. LPIS and 08C enter only after SC1 is frozen.

Heavy soil packages, LPIS parcels and ED geometry are optional first-principles reconstruction sources. They are not normal scenario runtime requirements.

## SC2: opportunity and eligibility

SC2 accepts the frozen ED release from SC1 and appends opportunity and physical-eligibility evidence. It never recomputes livestock or released land.

The interpretation is intentionally conservative:

```text
Potential release != Opportunity != Realised conversion
```

Released land therefore represents a spatial budget created by the national livestock pathway, not a prediction that all such land changes use.

## SC3: land-use target allocation

SC3 allocates explicit national land-use targets across the released-land budgets identified in SC1 and screened in SC2. Targets come from the editable scenario control and are never invented by the spatial allocator.

The allocator respects ED-level released-land budgets, physical eligibility and shared capacity pools. Infeasible targets remain unmet rather than being forced into unsuitable EDs.

Rewetting is handled after the main released-land allocation because the organic-soil transition is conceptually distinct from the gross livestock-release accounting. Outputs distinguish GOBLIN parent `Available` land from the stricter residual after realised rewetting.

## Principal commands

Build or manage the historical baseline:

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

The LPIS reconstruction command remains available only for explicit first-principles rebuild work:

```bash
goblin-spatial-lpis ...
```

It is not called by the principal runtime.

## Reproducibility boundary

A normal validated 2020 scenario run should require only repository-contained compact controls and historical inputs. It should not download Zenodo data, rebuild LPIS intersections, reconstruct soil overlays, or fetch spatial geometry.

First-principles reconstruction remains separately reproducible from version-pinned provenance sources. Heavy reconstruction workflows are manual-only in GitHub Actions so they cannot be confused with routine scenario validation.

## Interpretation

GOBLIN-Spatial is a spatial strategic-foresight model, not a parcel-level land-use prediction model. Its purpose is to identify where nationally plausible transitions create concentrated adjustment pressure, where alternative land uses appear spatially compatible, and where transition constraints may require earlier policy preparation.

The model therefore supports questions such as:

- Which EDs are robustly exposed to livestock adjustment across pathways or allocation rules?
- Which EDs are sensitive to the way national adjustment is distributed?
- Where does released land align with the opportunity and eligibility conditions of national land-use targets?
- Where do spatial constraints make a national pathway harder to implement?

Results should be interpreted as transition exposure, opportunity and spatial compatibility, not forecasts of individual farm behaviour or realised parcel conversion.

## Development status

The repository is being finalised around this principal framework. Stale experimental scenario surfaces are being removed from the supported API and command-line interface. The 2020 scenario architecture is considered scientifically fixed once the canonical frozen land-context payload passes its checksum and contract tests and the SC1-SC3 validation suite is green.
