# GOBLIN-Spatial v1 scientific-engine freeze

This file defines the boundary for declaring the GOBLIN-Spatial v1 scientific engine complete.

The v1 engine is frozen when the repository passes CI with the following architecture:

```text
GOBLIN national pathway authority
        ↓
Baseline
        ↓
SC1 transition incidence
        ↓
SC2 spatial response potential
        ↓
SC3 spatial transformability
        ↓
post-SC3 spatial flexibility
```

## Frozen scientific boundaries

- GOBLIN remains authoritative for national pathway quantities.
- SC1 is independent of mapped soil, LPIS and future-use suitability.
- `ALL_GRASSLAND` is the only ED land-capacity ceiling in SC1.
- Pasture-DM land balance remains an independent diagnostic.
- SC2 uses the frozen seven-class mapped physical soil resource and separate LPIS context only after SC1 is frozen.
- No parcel-level soil × LPIS relationship is fabricated.
- Eligibility must be explicit, versioned and evidence-backed.
- SC3 uses a finite shared land budget and reports realised, unmet and residual hectares.
- Rewetting is a separate environmental/restoration requirement and requires validated capacity evidence.
- Post-SC3 flexibility preserves the same realised national end-use vector while testing alternative feasible geographies.
- Reporting is downstream and may not recalculate model science.

## What remains outside the engine freeze

The generic SC3 optimiser is part of the frozen engine, but final publication SC3 results require a scientifically approved eligibility-control file and, for pathways with positive rewetting targets, a validated rewetting-capacity control.

Maps, charts, tables, GIS layers and publication figures are a separate reporting phase built from frozen engine outputs.

New scientific mechanisms introduced after this freeze belong to a later model version or a separate study unless they correct a demonstrated scientific or software error.
