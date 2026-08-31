# GOBLIN-Spatial publication visuals

## Purpose

This visual layer is downstream of the validated GOBLIN-Spatial numerical results. It does **not** alter SC1, SC2 or SC3 calculations. It consumes the frozen final-results SQLite database, the map-ready CSV and the frozen ED geometry.

The main-paper visual focus is deliberately restricted to the two contraction pathways:

- `BE_SG`: Bioeconomy / Split Gas
- `ALL_GAS_NZ`: All-Gas Net Zero

`SI_SG` remains part of the validated scenario envelope and can be reported in supplementary material, but it is excluded from the main-paper publication visual layer so the main comparison stays focused on two contraction depths.

## Scientific story

The figure package is SC1-led:

```text
national transition pressure
    -> local livestock incidence
    -> agricultural production-value exposure
    -> economic and social vulnerability
    -> protection relief and displaced burden
    -> early-attention geography
    -> released-land geography
    -> downstream opportunity / SC3 feasibility
```

Standard Output is interpreted only as agricultural production-value exposure. It is not income, profit, welfare loss or a compensation requirement.

## Final manuscript polish

The command-line publication workflow now routes through `publication_visuals_final.py`. The original publication visual module remains the reproducible base layer. The final layer regenerates only the panels that need stricter cross-pathway comparability and then overwrites those same output filenames, so no additional manuscript figures are created.

The final refinements are:

- the exposure-vulnerability scatter uses one pooled BE-SG / All-Gas NZ exposure cut-line and one common baseline vulnerability cut-line, so quadrant positions have the same numerical meaning in both pathways;
- the exposure-vulnerability maps use pooled exposure terciles and common baseline vulnerability terciles, rather than recalculating classes separately inside each pathway;
- the high-exposure/high-vulnerability quadrant is identified as an **early-attention** diagnostic, not as a probabilistic risk class;
- the released-grassland figure now uses the same national-map + callout + statistics grammar as the headline exposure figure and reports future-use eligibility context where available;
- dedicated synthetic tests cover both the final graph wrapper and the polished publication map functions.

## Graph package

`goblin_spatial.publication_visuals.generate_publication_graphs()` provides the reproducible base graphs. `goblin_spatial.publication_visuals_final.generate_final_publication_visuals()` applies the final manuscript polish and is the function used by the CLI.

The package contains:

1. `pub_fig01_exposure_concentration`
   - cumulative incidence curves for cattle adjustment and Standard Output exposure under PRORATA;
   - compares `BE_SG` and `ALL_GAS_NZ` directly.

2. `pub_fig02_ed_exposure_distributions`
   - violin + box small multiples across the four incidence rules;
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
   - common cross-pathway cut-lines identify the high-exposure/high-vulnerability early-attention quadrant;
   - no composite just-transition or risk index is constructed.

5. `pub_fig05_target_realised_unmet`
   - compact secondary SC2/SC3 consequence figure;
   - target versus realised land-use demand under PRORATA;
   - retained as the downstream consequence of the SC1 geography rather than the paper's main story.

Every graph is written as 500-dpi PNG and vector SVG, with a manifest recording the scientific question and interpretation note.

## Map package

The map workflow uses the frozen `GOBLIN_Spatial_Map_Data.csv` and the same model ED geometry used by the existing map reporter.

The publication map style follows these principles:

- national map plus analytical inset/callout where useful;
- thin ED outlines with subtle county context;
- explicit no-data colour;
- Irish Transverse Mercator (`EPSG:2157`) for distance-aware cartography;
- real scale bars from projected metres;
- consistent shared scales and shared class thresholds across the two paper pathways;
- maps answer a scientific question rather than merely display a variable.

The package contains:

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
   - pooled exposure terciles and common baseline vulnerability terciles ensure direct cross-pathway comparability;
   - no opaque composite index.

4. `pub_map04_persistent_exposure`
   - top-decile Standard Output exposure frequency recomputed across the eight main-paper runs only (`2 pathways x 4 incidence rules`);
   - this is frequency across modelled runs, not probability or confidence.

5. `pub_map05_released_grassland`
   - SC1 released-land bridge showing where livestock adjustment makes land available for downstream transition uses;
   - each pathway now includes an analytical released-land callout and compact opportunity-eligibility statistics where the variables are available.

## Main-paper selection

The code deliberately creates a slightly richer reproducible visual library than should appear in the manuscript. The recommended main-paper architecture remains four composite figures:

1. transition incidence and production-value exposure;
2. protection relief and displaced burden;
3. vulnerability, persistence and early-attention geography;
4. released land and future-use opportunity.

Other generated panels are retained for supplementary material, diagnostics and alternative journal layouts rather than being forced into the main text.

Two or three compact manuscript tables can complement the figures: scenario/allocation design, headline SC1 results, and an optional early-attention hotspot summary if the empirical results justify it.

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
- Early-attention is a descriptive high-exposure/high-vulnerability diagnostic, not a probability of harm.
- SC2 eligibility sets overlap and must not be added across alternative uses.
- SC3 realised land use is a model allocation, not an adoption forecast.
