# InformBio D2.1 reference bridge

## Purpose

This bridge keeps a small curated subset of the InformBio D2.1 Bioresource
Mapping Tool available to GOBLIN-Spatial as a reference library. It does not
replace CSO/GOBLIN-Spatial livestock or land accounting.

The inspected D2.1 workbook has a Ricardo Energy & Environment lineage and was
later updated in InformBio. Its DataLog records Manure arisings as imported
from an earlier non-public Irish bioresource database working file. The
BioRes Factors composition table is separately linked to the workbook DataRefs
bibliography.

## What is retained

The curated CSV contains selected agriculture/land-use materials relevant to
future GOBLIN-Spatial work:

- cereal straws
- grass/silage
- maize silage
- miscanthus and willow
- livestock manure/slurry reference rows

The retained fields are dry-matter content, gross calorific value, protein,
carbon, nitrogen, phosphorus and potassium fractions where available.

## Critical boundary

Do not use the InformBio manure rows to generate GOBLIN-Spatial manure
arisings.

D2.1 does not document the livestock excretion coefficients behind the manure
arisings table. In addition, the BioRes Factors sheet applies the same cattle
composition row to dairy cattle, other cows/sucklers, bulls and dry stock, with
a dry-matter fraction of 0.754. Those rows are therefore retained only for
provenance and sensitivity work until their reporting basis and Irish
representativeness are independently verified.

For operational manure modelling use the chain:

    ED livestock population
      -> documented excretion coefficient
      -> housing/storage fraction
      -> recoverable fraction
      -> fresh/dry manure quantity
      -> composition/process model

The first four steps require transparent independent sources.

## Why the reference layer is useful

The 2026 InformBio foresight report describes its feedstock estimates as
theoretical and explicitly notes uncertainty from variable conversion factors,
data gaps and limited sector-specific information. It also argues that
continuous monitoring and spatial mapping of grass production are needed to
identify surplus zones for grass biorefineries.

That makes InformBio useful to GOBLIN-Spatial as:

- a feedstock and fate vocabulary,
- a composition/reference library,
- a county-level comparison dataset,
- and a source of candidate bioresource opportunity variables.

It should not override the validated ED livestock, land or cohort baseline.

## Redistribution scope

Only a small factual subset needed for interoperability is committed here.
The original macro-enabled workbook is not copied into this repository.
