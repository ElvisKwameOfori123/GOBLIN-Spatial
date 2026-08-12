# Methodology

## Overview

GOBLIN-Spatial is a constraint-preserving spatialisation framework that connects the national GOBLIN AFOLU modelling approach to fine-scale local agricultural geography.

GOBLIN operates at national scale and provides the internally consistent livestock and land-use logic needed for pathway analysis. GOBLIN-Spatial adds the spatial layer by expressing those national and higher-level controls at Electoral Division (ED) level while preserving the official population, composition and land accounting constraints from which the spatial representation is derived.

The current Irish implementation uses **2,857 Electoral Divisions** as the fine local spatial unit. The objective is not to create 2,857 independent national models. Instead, the framework translates a nationally consistent agricultural system into a locally resolved representation.

The framework separates three distinct functions:

1. fine-scale official data determine spatial pattern;
2. coarser official annual statistics determine temporal totals and composition;
3. the GOBLIN cohort structure determines biological livestock disaggregation.

These roles are not interchangeable.

## Relationship to national GOBLIN

GOBLIN remains the parent national AFOLU framework. It governs national pathway consistency and the biological structure of the livestock system.

GOBLIN-Spatial governs the spatial response. It answers where the nationally controlled livestock and land-use system is represented across EDs, subject to the official spatial and statistical controls available for Ireland.

The conceptual relationship is therefore:

```text
National GOBLIN / official agricultural controls
                    |
                    v
      Constraint-preserving reconciliation
                    |
                    v
       Electoral Division representation
                    |
                    v
 Livestock cohorts + land + farm structure
```

This separation allows national scenario logic to remain coherent while enabling analysis of local livestock structure, land availability, spatial exposure and future land-use opportunity.

## Spatial anchor

The 2020 Census of Agriculture ED dataset is the fixed fine-scale baseline. It provides the authoritative ED geography and 2020 agricultural structure used by the workflow.

Annual non-2020 ED values are reconstructed around that baseline using official higher-level controls. They should therefore be described as reconstructed annual ED estimates rather than independently observed ED statistics.

Higher-level controls are used to move the ED system through time without replacing the fixed 2020 spatial anchor.

## Hierarchical reconciliation

GOBLIN-Spatial uses hierarchical reconciliation to combine statistical products published at different geographical scales.

The governing rule is simple:

```text
fine-scale data provide spatial weights
coarser official data provide population and composition controls
```

Depending on the variable, reconciliation may operate through national, regional, county and ED levels.

Reusable allocation methods include proportional reconciliation, Hamilton/largest-remainder integer allocation and iterative proportional fitting where both row and column constraints must be satisfied.

The same reconciliation machinery is intended to be shared across package modules rather than reimplemented separately for each dataset.

## Livestock

### Cattle

The annual cattle panel is constrained to official county totals and an ED age-sex structure. `OTHER_CATTLE` is first represented in the six CSO age-sex containers, with breeding bulls retained separately. The fixed ED cattle population is then expressed in the 21 cattle cohorts used by GOBLIN.

For every ED-year:

`sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE`

and, for each CSO pre-adult age-sex container:

`DxD + DxB + BxB = fixed CSO ED age-sex total`

The GOBLIN cohort relationships determine the national biological composition of the six pre-adult age-sex containers. They do not generate or replace the CSO ED cattle population.

Genetic support is **ED-first**. The default biological support follows the adult-cow structure observed in the ED:

- EDs with dairy cows support dairy-origin `DxD` and `DxB` cohorts;
- EDs with other/suckler cows support `BxB` cohorts;
- mixed EDs can support all three genetic groups;
- breeding bulls remain a separate adult cohort and are never split into DxD, DxB or BxB.

Biological dependency does not imply geographical co-location. Young cattle can move from breeding to rearing or finishing areas. For that reason, the framework admits a **sparse receiver/rearing exception** rather than imposing absolute genetic zeros on every ED without the corresponding adult-cow class. EDs with non-cow cattle but no adult cows are treated as receiver locations. Where additional dairy-origin support is required to reproduce the national GOBLIN margins, zero-dairy EDs are admitted in descending order of their own 2020 young-stock-to-adult-cow signal until exact closure becomes feasible across the complete 2015–2025 panel.

This rule deliberately avoids the previous blanket county-context fallback. County statistics continue to control the official cattle totals and age-sex composition, but **county context does not make every ED genetically eligible**. The result preserves genuine rearing/finishing movement while retaining structural zeros in most EDs where the corresponding breeding origin is absent.

The distinction is therefore:

```text
CSO ED cattle + county controls  -> how many cattle and what age/sex
ED adult-cow / receiver support  -> where genetic cohorts are plausible
GOBLIN cohort relationships      -> national DxD/DxB/BxB composition
```

### Sheep

Annual sheep controls are reconciled through a region-to-county-to-ED hierarchy. DAFM sheep composition information is used to distinguish Lowland and Mountain-type structure. The Mountain + Mountain Cross aggregate is used as the operational proxy for the GOBLIN Upland cohort naming convention.

For every ED-year:

`sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP`

## Land

The 2020 ED land variables remain fixed. Annual CSO AQA06 regional land-use series supply temporal change for farmed area, grassland and cereals.

For every ED-year:

`AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA`

`AREA_FARMED` is the controlling land total. The reconciliation prevents negative land components and preserves exact accounting between the land categories.

## Farm structure

Agricultural holdings are reconstructed around the locked 2020 ED distribution using official Farm Structure Survey and Census controls.

The 2020 ED values are not replaced by national survey totals. Official higher-level statistics are used as temporal-change controls around the ED baseline.

Average holding size is reconstructed around the exact reported 2020 ED value using annual change in farmed area and agricultural holdings.

## Holder age

The 2020 ED mean and median holder ages are retained exactly.

Pre-2020 ages are reconstructed from official national Farm Structure Survey/Census age trajectories. Post-2020 ages use county-level 2020 to 2023 changes where available, with the 2023 controlled structure held for 2024–2025 in the current baseline.

These values represent reconstructed ED structural characteristics, not longitudinal ageing of the same individual holder.

## Constraint preservation

The framework is designed so that biological or spatial enrichment does not alter the official population being represented. Reconciliation and integer allocation are used where required to preserve exact count controls.

The principal validation identities are:

```text
2020 final values = 2020 baseline values exactly
sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE
sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP
AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA
```

The cattle module additionally validates that non-receiver zero-dairy EDs contain no DxD/DxB cattle and that non-receiver zero-suckler EDs contain no BxB cattle.

A package build should fail rather than silently continue if a protected accounting constraint is violated.

## Generalisation

Ireland is the current demonstration of GOBLIN-Spatial rather than the methodological boundary of the framework.

The intended package architecture separates generic reconciliation and validation routines from country-specific geography, mappings and statistical inputs. This allows the same national-to-local logic to be adapted where another jurisdiction provides a suitable fine-scale agricultural baseline and higher-level temporal controls.
