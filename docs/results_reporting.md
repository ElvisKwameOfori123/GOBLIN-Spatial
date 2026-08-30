# GOBLIN-Spatial final results reporting

## Purpose

The final reporting layer is deliberately downstream of the scientific model. SC1, SC2 and SC3 continue to write canonical CSV outputs. Reporting code reads those completed runs and produces a coherent scientific package without altering any model mathematics or overwriting canonical results.

SC1, SC2 and SC3 are not interpreted as independent scenarios. They are linked analytical views of one internally consistent national GOBLIN pathway:

```text
national pathway
    -> livestock transition incidence
    -> Standard Output exposure and vulnerability context
    -> released-land geography
    -> natural-capital opportunity and physical eligibility
    -> feasible land-use response
    -> unmet targets and final residual constraint
```

The reporting architecture follows the GOBLIN principle that scenario computation first materialises structured result frames and visualisation/assessment consumes those frames afterwards.

## Principal study matrix

The final 2020 spatial foresight study is the exact cross-product of:

```text
Pathways
  SI_SG
  BE_SG
  ALL_GAS_NZ

Incidence rules
  PRORATA
  DAIRY_PROTECTION
  ECONOMIC_CAPACITY_PROTECTION
  SOCIAL_VULNERABILITY_PROTECTION
```

This gives 12 principal runs. The final study-report command requires the complete matrix by default. `--allow-partial` exists only for development and testing.

## Scientific questions reported

The final results system is organised around the questions a reader or policymaker needs answered rather than around internal model stages alone.

1. **What national transition is required?** National dairy, suckler and complete cattle endpoints and livestock-land release.
2. **Where does the transition fall?** ED and county cattle reduction/expansion and local incidence.
3. **What production value is exposed?** Gross livestock Standard Output exposure, gains and relative exposure. Standard Output is production-value exposure, not income, profit, welfare or compensation.
4. **How concentrated is the adjustment?** Gini, top-share measures, Lorenz data and the number of EDs carrying 50% or 80% of national exposure.
5. **How much heterogeneity is hidden by county averages?** GE(2) decomposition separates within-county from between-county variation for non-negative exposure quantities.
6. **What does protection do?** Protection relief and displaced burden are measured relative to PRORATA under the same fixed national endpoint.
7. **Which places remain highly exposed across the modeled futures?** The package reports continuous robust minimum/mean/maximum exposure and a transparent top-decile appearance frequency across the 12 scenario-rule combinations. This frequency is not a probability or confidence interval.
8. **What type of land is released?** Released land is decomposed by dairy/beef/sheep system origin and G1/G2/G3 agricultural capability.
9. **What can the released geography support?** SC2 reports natural-capital opportunity scores and use-specific physically eligible released hectares.
10. **Does transition exposure coincide with opportunity?** A combined ED-level `transition_conditions` table joins SC1 exposure/vulnerability, SC2 opportunity and SC3 realised response without constructing an opaque composite risk index.
11. **Can the pathway's alternative land uses actually be delivered?** SC3 reports target, realised and unmet hectares plus use-specific opportunity mobilisation and shared physical-pool utilisation.
12. **What remains after feasible allocation?** The corrected three-ledger land accounting distinguishes parent GOBLIN Available, post-Stage-A unallocated release and the strict post-rewetting final residual.

## Final outputs

Running:

```bash
goblin-spatial-study-report data/processed/final_principal \
  --output-dir data/processed/final_results
```

produces:

```text
GOBLIN_Spatial_Final_Results_Master.xlsx
GOBLIN_Spatial_Final_Results.sqlite
GOBLIN_Spatial_Figure_Data.csv
GOBLIN_Spatial_Map_Data.csv
GOBLIN_Spatial_Transition_Conditions.csv
figures/
```

The Excel workbook is the human-readable scientific reporting object. SQLite is the complete portable query store. `Transition_Conditions.csv` is the integrated ED-level bridge from exposure to opportunity to feasible response. `Map_Data.csv` is a deliberately compact map-ready table so later cartography consumes the same frozen numerical results rather than rebuilding model science.

## Workbook structure

The final workbook is question-driven:

```text
00_Read_Me
01_Scenario_Design
02_Headline_Results
03_National_Pathways
04_SC1_Livestock
05_SC1_Distribution
06_SC1_Protection
07_SC1_Persistence
08_SC1_Robustness
09_SC1_Land_Release
10_SC2_Opportunity
11_Transition_Conditions
12_Opportunity_Mobilisation
13_SC3_Target_Realised
14_SC3_Shared_Pools
15_SC3_Rewetting
16_SC3_Land_Accounting
17_County_Results
18_Map_Data
19_Figure_Data
20_Validation
21_Reconciliation
22_Data_Dictionary
23_Figures
90_ED_SC1_Full
91_ED_SC2_Full
92_ED_SC3_Full
```

The front and middle sheets are interpretation-focused. Full ED tables remain at the end for auditability, while SQLite remains the preferred store for detailed machine analysis.

## New integrated result tables

The final database adds the following reporting-only tables to the previously validated cross-run store:

```text
distribution_summary
lorenz_data
persistence
persistence_histogram
land_release_summary
opportunity_summary
transition_conditions
opportunity_mobilisation
shared_pool_summary
rewetting_summary
headline_results
map_data
figure_data
final_report_metadata
```

### Distribution and GE(2)

GE(2) is calculated only for non-negative quantities such as cattle reduction, gross SO loss and released land. The exact decomposition is used so total variation is separated into within-county and between-county components. Signed net changes are not put through this inequality decomposition.

### Persistence

For each run, the positive top decile of cattle-reduction rate and SO-exposure rate is identified. The ED-level persistence table counts the number of the supplied scenario-rule combinations in which each ED appears in that high-exposure set.

The terminology is deliberately:

```text
frequency across modeled scenarios
scenario envelope
robust minimum / maximum
pathway sensitivity
allocation-rule sensitivity
```

It must not be described as probability, statistical confidence or a forecast likelihood.

### Transition conditions

`transition_conditions` keeps the mechanisms visible rather than collapsing them into one weighted index. It contains, where available:

```text
transition intensity
economic production-value exposure
baseline economic/social vulnerability
released-land scale
use-specific physical eligibility
opportunity scores
realised SC3 alternative-use hectares
alternative-use uptake as share of released land
use-specific opportunity mobilisation
final unallocated released land
robust exposure
pathway and allocation sensitivity
protection relief and displaced burden
```

This permits descriptive exposure-opportunity analysis without claiming causal income replacement, welfare compensation or farmer adoption.

### Opportunity mobilisation

For each land use:

```text
opportunity mobilisation = realised use-specific hectares / use-specific eligible hectares
```

This measures how the national pathway mobilises modeled spatial opportunity. It is **not** an observed farmer adoption rate. Because eligibility sets overlap between alternative uses, eligible hectares must never be summed across land uses.

### Shared pools

SC3 shared-pool reporting exposes competition for the same physical released-land capacity:

```text
tillage / willow pool
AD / biorefinery pool
forest / wider mineral pool
```

Capacity, used hectares, unused hectares and utilisation are reported separately. This helps distinguish insufficient gross release, unsuitable land, spatial mismatch and competition among alternative uses.

## Figure package

The final reporter generates PNG at 400 dpi and vector SVG versions of the principal graph suite:

1. `fig01_livestock_endpoint`: national cattle composition, shown once per pathway because incidence rules do not alter the national endpoint;
2. `fig02_standard_output_exposure`: gross production-value exposure across all pathway-rule runs;
3. `fig03_released_land_allocation`: realised alternative uses plus strict final residual across all runs;
4. `fig04_transition_concentration`: Lorenz curves for SO exposure under PRORATA;
5. `fig05_protection_redistribution`: signed protection relief versus displaced production-value burden relative to PRORATA;
6. `fig06_pathway_allocation_sensitivity`: ED pathway sensitivity versus incidence-rule sensitivity;
7. `fig07_persistent_exposure`: frequency distribution of top-decile exposure appearances across the modeled futures;
8. `fig08_within_between_heterogeneity`: within-county versus between-county GE(2) variation in SO exposure;
9. `fig09_released_land_systems`: dairy/beef/sheep origin of released land;
10. `fig10_released_land_soil`: G1/G2/G3 capability composition of released land;
11. `fig11_exposure_forest_opportunity`: flagship ED exposure-versus-released-land opportunity relationship for the ambitious pathway under PRORATA;
12. `fig12_target_realised_unmet`: realised plus unmet hectares for each pathway land-use target;
13. `fig13_land_accounting`: strict Stage-A + rewetting + final residual closure;
14. `fig14_opportunity_mobilisation`: realised/eligible use-specific spatial opportunity.

The graph suite is intentionally richer than the parent GOBLIN plots because the spatial model can reveal incidence, redistribution, heterogeneity, robustness and spatial feasibility that are invisible at national scale.

## Land-accounting rule

The final reporting layer preserves three distinct quantities:

```text
GOBLIN parent Available target accounting
Realised post-Stage-A unallocated released land
Final unallocated released land after rewetting
```

The parent quantity reproduces national pathway target accounting. The latter two report realised spatial feasibility. They must not be silently substituted for one another. The strict land-accounting graph therefore uses realised Stage A, realised rewetting and final residual; it does not relabel the final physical residual as parent `Available`.

## Maps

Maps remain a separate downstream stage. `GOBLIN_Spatial_Map_Data.csv` now freezes the key cartographic variables so later mapping can join the same numerical results to frozen ED geometry by `CSOED`.

Main paper mapping should be selective rather than exhaustive. Strong candidates are:

- persistent transition exposure;
- Standard Output exposure;
- protection relief/displaced burden relative to PRORATA;
- exposure-opportunity conditions;
- opportunity mobilisation or realised conversion intensity;
- final unallocated released land.

Individual cattle cohorts, every opportunity variable, every soil category and the full 3 x 4 map matrix are more suitable for supplementary material.

## Reproducible full-run workflow

A manual GitHub Actions workflow, `.github/workflows/final-results.yml`, builds the historical baseline, runs all 12 principal SC1-SC3 combinations, creates the integrated final reporting package and uploads it as the `GOBLIN-Spatial-final-results` artifact.
