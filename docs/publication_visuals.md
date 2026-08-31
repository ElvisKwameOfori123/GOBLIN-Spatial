# GOBLIN-Spatial publication visuals

## Purpose

This visual layer is downstream of the validated GOBLIN-Spatial numerical results. It does **not** alter SC1, SC2 or SC3 calculations. It consumes the frozen final-results SQLite database, the map-ready CSV and the frozen ED geometry.

The main-paper visual focus is deliberately restricted to the two contraction pathways:

- `BE_SG`: Bioeconomy / Split Gas
- `ALL_GAS_NZ`: All-Gas Net Zero

`SI_SG` remains part of the validated scenario envelope and can be reported in supplementary material, but it is excluded from the main-paper publication visual layer so the main comparison stays focused on moderate versus deep contraction.

## Scientific story

The figure package is SC1-led:

```text
national transition pressure
    -> local livestock incidence
    -> agricultural production-value exposure
    -> economic and social vulnerability
    -> protection relief and displaced burden
    -> released-land geography
    -> downstream opportunity / SC3 feasibility
```

Standard Output is interpreted only as agricultural production-value exposure. It is not income, profit, welfare loss or a compensation requirement.

## Graph package

`goblin_spatial.publication_visuals.generate_publication_graphs()` creates:

1. `pub_fig01_exposure_concentration`
   - cumulative incidence curves for cattle adjustment and Standard Output exposure under PRORATA;
   - compares `BE_SG` and `ALL_GAS_NZ` directly.

2. `pub_fig02_ed_exposure_distributions`
   - publication-style violin + box small multiples across the four incidence rules;
   - physical adjustment, production-value exposure and released grassland;
   - one column per main pathway.

3. `pub_fig03_protection_redistribution`
   - signed ED-level difference from PRORATA;
   - negative values are protection relief;
   - positive values are displaced burden;
   - shown for both physical cattle adjustment and Standard Output exposure.

4. `pub_fig04_exposure_vulnerability`
   - ED-level production-value exposure against economic and social vulnerability;
   - point size represents released grassland;
   - no composite just-transition or risk index is constructed.

5. `pub_fig05_target_realised_unmet`
   - compact secondary SC2/SC3 consequence figure;
   - target versus realised land-use demand under PRORATA;
   - retained as the downstream consequence of the SC1 geography rather than the paper's main story.

Every graph is written as 500-dpi PNG and vector SVG, with a manifest recording the scientific question and interpretation note.

## Map package

`generate_publication_maps()` uses the frozen `GOBLIN_Spatial_Map_Data.csv` and the same model ED geometry used by the existing map reporter.

The publication map style follows these principles:

- national map plus analytical inset/callout where useful;
- thin ED outlines with subtle county context;
- explicit no-data colour;
- Irish Transverse Mercator (`EPSG:2157`) for distance-aware cartography;
- real scale bars from projected metres;
- consistent shared scales across the two paper pathways;
- maps answer a scientific question rather than merely display a variable.

The package creates:

1. `pub_map01_standard_output_exposure`
   - BE-SG and All-Gas NZ production-value exposure;
   - each pathway includes a high-exposure geographic callout and summary statistics.

2. `pub_map02_protection_redistribution`
   - two pathways by three protection rules;
   - signed deviation from PRORATA in Standard Output exposure;
   - one centred diverging scale: relief to displaced burden.

3. `pub_map03_exposure_vulnerability`
   - bivariate exposure-vulnerability maps;
   - economic and social vulnerability shown separately;
   - no opaque composite index.

4. `pub_map04_persistent_exposure`
   - top-decile Standard Output exposure frequency recomputed across the eight main-paper runs only (`2 pathways x 4 incidence rules`);
   - this is frequency across modelled runs, not probability or confidence.

5. `pub_map05_released_grassland`
   - SC1 released-land bridge showing where livestock adjustment makes land available for downstream transition uses.

## Run

From an installed development checkout:

```bash
goblin-spatial-publication-visuals data/processed/final_results
```

Graphs only:

```bash
goblin-spatial-publication-visuals data/processed/final_results --graphs-only
```

Explicit geometry:

```bash
goblin-spatial-publication-visuals data/processed/final_results \
  --geometry /path/to/EDs.gpkg
```

The default output location is:

```text
<final_results>/publication_visuals/
    graphs/
    maps/
```

## Interpretation guardrails

- The four allocation rules are distributional policy counterfactuals, not probabilities.
- `PRORATA` is the neutral spatial incidence benchmark.
- Protection redistributes a fixed national adjustment rather than removing it.
- Economic and social vulnerability remain separate dimensions.
- Standard Output is production-value exposure only.
- Persistent exposure is frequency over the specified paper-run envelope, not forecast likelihood.
- SC2 eligibility sets overlap and must not be added across alternative uses.
- SC3 realised land use is a model allocation, not an adoption forecast.
