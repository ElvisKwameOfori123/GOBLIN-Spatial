# Frozen 2020 soil + LPIS runtime context

This directory is the complete spatial land context used by GOBLIN-Spatial SC2 and SC3. **SC1 does not read it.**

It contains exactly two scientific controls:

- `ED_Colm_Physical_Soil_2020.csv` — seven mapped physical-soil and drainage area categories for each of the 2,857 model EDs;
- `ED_LPIS_Context_2020.csv` — LPIS 2020 agricultural-use and management context for the same ED universe.

The runtime reader verifies both SHA-256 checksums, canonicalises ED identifiers, requires an exact one-to-one ED universe and joins the two controls in memory. The resulting contract contains 2,857 rows and 26 fields.

The scientific roles are distinct:

- mapped physical soil describes the physical composition of the frozen SC1 released-land resource;
- LPIS describes current agricultural context;
- neither layer changes livestock, national land release or the frozen ED release vector;
- future-use eligibility is supplied separately through explicit, versioned scientific controls.

The source-specific `Colm` identifier is retained in the physical-soil filename and internal provenance fields only. Scientific-facing documentation uses the neutral terms **mapped physical soil**, **soil/drainage class** and **physical land-resource evidence**.

The two controls are ED-level summaries. They are not an observed parcel-level soil × LPIS overlay, and the runtime does not create such an overlay by assuming statistical independence.
