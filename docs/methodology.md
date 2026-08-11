# Methodology

## Overview

GOBLIN-Spatial is a hierarchical reconciliation framework for constructing an Electoral Division (ED) representation of livestock and agricultural land while preserving official statistical controls.

The framework separates three distinct functions:

1. fine-scale official data determine spatial pattern;
2. coarser official annual statistics determine temporal totals and composition;
3. the GOBLIN cohort structure determines biological livestock disaggregation.

These roles are not interchangeable.

## Spatial anchor

The 2020 Census of Agriculture ED dataset is the fixed fine-scale baseline. It provides the authoritative ED geography and 2020 agricultural structure used by the workflow.

Annual non-2020 ED values are reconstructed around that baseline using official higher-level controls. They should therefore be described as reconstructed annual ED estimates rather than independently observed ED statistics.

## Livestock

### Cattle

The annual cattle panel is constrained to official county totals and an ED age-sex structure. The fixed ED cattle population is then expressed in the 21 cattle cohorts used by GOBLIN.

For every ED-year:

`sum(21 GOBLIN cattle cohorts) = TOTAL_CATTLE`

GOBLIN cohort relationships inform DxD, DxB and BxB biological composition but do not replace the CSO livestock population.

### Sheep

Annual sheep controls are reconciled through a region-to-county-to-ED hierarchy. DAFM sheep composition information is used to distinguish Lowland and Mountain-type structure. The Mountain + Mountain Cross aggregate is used as the operational proxy for the GOBLIN Upland cohort naming convention.

For every ED-year:

`sum(10 GOBLIN sheep cohorts) = TOTAL_SHEEP`

## Land

The 2020 ED land variables remain fixed. Annual CSO AQA06 regional land-use series supply temporal change for farmed area, grassland and cereals.

For every ED-year:

`AREA_FARMED = ALL_GRASSLAND + TOTAL_CEREALS + OTHER_CROPS_HA`

The reconciliation prevents negative land components.

## Farm structure

Agricultural holdings are reconstructed around the locked 2020 ED distribution using official Farm Structure Survey and Census controls.

The 2020 ED values are not replaced by national survey totals. Official higher-level statistics are used as temporal-change controls around the ED baseline.

## Holder age

The 2020 ED mean and median holder ages are retained exactly.

Pre-2020 ages are reconstructed from official national Farm Structure Survey/Census age trajectories. Post-2020 ages use county-level 2020 to 2023 changes where available, with the 2023 controlled structure held for 2024–2025 in the current baseline.

These values represent reconstructed ED structural characteristics, not longitudinal ageing of the same individual holder.

## Constraint preservation

The framework is designed so that biological or spatial enrichment does not alter the official population being represented. Reconciliation and integer allocation are used where required to preserve exact count controls.
