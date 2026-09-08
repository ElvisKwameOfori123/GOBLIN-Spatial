# Frozen 2020 Colm + LPIS runtime context

This directory is the complete spatial context used by GOBLIN-Spatial SC2 and SC3.
SC1 does not read it.

It contains exactly two scientific controls:

- `ED_Colm_Physical_Soil_2020.csv` — seven mapped physical-soil area categories for each of the 2,857 model EDs.
- `ED_LPIS_Context_2020.csv` — neutral LPIS 2020 agricultural-use and management context for the same ED universe.

The runtime reader verifies both SHA-256 checksums, canonicalises ED identifiers,
requires an exact one-to-one ED universe, and joins the two controls in memory.
The resulting contract has 2,857 rows and 26 fields.

Colm soil describes physical resource composition. LPIS describes agricultural
context. Neither layer changes the frozen SC1 livestock solution or released-land
vector. Future-use eligibility is supplied separately through explicit versioned
scientific controls.
