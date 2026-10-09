# LCAD 2.02 reference bridge

This note documents the small LCAD-derived reference layer added to GOBLIN-Spatial.

## Purpose

The reference layer is intentionally narrow. It does **not** port the LCAD 2.02 process model into GOBLIN-Spatial and it does not change the validated historical baseline. It only preserves a subset of agricultural feedstock characteristics that are directly useful for later spatial bioresource calculations.

Source workbook: `LCAD 2.02 - LCI tool of AD biorefineries.xlsx`, version 2.02 (March 2026).

When using these values, cite:

Martinez-Arce, A., O'Flaherty, V., & Styles, D. (2026). *Critical evaluation of prospective biorefinery configurations to deliver a circular, climate neutral economy*. Resources, Conservation and Recycling, 231, 108907. https://doi.org/10.1016/j.resconrec.2026.108907

## Extracted variables

The frozen CSV records, where available:

- methane yield in m3 CH4 per tonne dry matter;
- dry-matter fraction;
- total nitrogen per tonne dry matter;
- ammonium-N share reported by LCAD;
- P2O5 per tonne dry matter;
- K2O per tonne dry matter;
- total carbon per tonne dry matter;
- specific heat capacity.

The first extraction is restricted to feedstocks with a plausible agriculture/land-use link to GOBLIN-Spatial: cattle slurry, farmyard manure, grass, grass-clover, maize, crop waste, spring barley, wholecrop cereal silage, miscanthus and willow.

## Python interface

`goblin_spatial.synthesis.lcad_reference` provides three small operations:

1. load the frozen reference table;
2. retrieve one feedstock record;
3. convert an **already estimated** feedstock dry-matter quantity into transparent technical reference quantities such as methane potential and N/P/K/C content.

Example:

```python
from goblin_spatial.synthesis.lcad_reference import technical_potential_from_dm

grass = technical_potential_from_dm("Grass", dry_matter_t=1.0)
# fresh_matter_t = 4.0
# methane_potential_m3_ch4 = 306.0
# total_n_kg = 21.5
```

A vectorised helper can attach the same reference values to an ED-level resource table containing `feedstock` and `dry_matter_t`.

## Important scientific boundary

The module starts **after** spatial resource quantity has been estimated. It does not infer:

- cattle housing duration;
- manure excretion or collection;
- recoverable manure fraction;
- crop-residue production or sustainable removal;
- collection losses;
- transport radius;
- AD plant size or technology;
- adoption;
- digestate fate;
- realised methane or energy output.

For example, GOBLIN-Spatial may later estimate a recoverable cattle-manure dry-matter quantity from its cohort geography plus a separately justified manure-management model. Only then should the LCAD reference methane and nutrient coefficients be applied.

Therefore:

```text
GOBLIN-Spatial livestock / land geography
                  |
        spatial resource quantity
                  |
      LCAD reference coefficients
                  |
 methane potential + N/P/K/C resource
```

is valid, whereas:

```text
number of cattle -> LCAD methane output
```

without an explicit manure-production and recoverability step is not.

## Why this belongs in the main repository

The extracted coefficients describe physical characteristics of agricultural resources and can support baseline-derived resource accounting without specifying a future pathway. Scenario assumptions such as "75% of housed cattle manure enters AD", "130,000 ha grass for AD", plant siting, circularity strategies or energy-crop allocation should remain outside the historical baseline, for example in GOBLIN-Spatial-SC or a later dedicated bioresource module.

## Files

- `data/inputs/reference/lcad_feedstock_characteristics.csv`
- `src/goblin_spatial/synthesis/lcad_reference.py`
- `tests/test_lcad_reference.py`

The dataset is registered as an optional `REFERENCE` input in `data_manifest.yaml`.
