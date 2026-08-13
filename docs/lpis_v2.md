# LPIS and soil opportunity v2

LPIS remains downstream of the validated historical baseline. It does not change livestock allocation or replace `ALL_GRASSLAND`.

Frozen sources:
- SAPS ED geography: Zenodo record `21906755`.
- Harmonised LPIS 2020/2025 parcel inputs: Zenodo record `21918924`.

Build the compact ED control after placing the published GeoParquets and ED shapefile at the configured paths, or pass their local paths explicitly:

```bash
goblin-spatial-lpis --year both
```

The output is `data/controls/lpis/ED_LPIS_opportunity_2020_2025.csv.xz`, one row per model ED for each observed LPIS snapshot. `CSOED` is the join authority; ED/county names are QA labels.

Run the downstream screen from a completed cattle scenario:

```bash
goblin-spatial-opportunity screen --scenario-ed-results PATH/scenario_ed_results.csv --baseline-year 2025
```

Soil v2 preserves compound `CSOED` identifiers, resolves compound model EDs from component source profiles before fallback, and can add a continuous source-UAA-weighted IFS peat/cutover share. LPIS v2 adds observed low-input, peat and riparian grass context at the selected 2020 or 2025 baseline.

Opportunity scores remain overlapping ED screening indices. `PotentialRelease != Opportunity != RealisedConversion`. Explicit hectare targets are still required before alternative land is allocated.
