# GOBLIN-Spatial

**A multiscale agricultural baseline and spatial foresight framework for Ireland**

GOBLIN-Spatial resolves national agricultural statistics into a consistent small-area representation of Irish agriculture: **where it is, what it is made of, and how it has changed**.

The historical baseline covers cattle, sheep, agricultural land, farm structure and production-value exposure **annually from 2015 to 2025 across 2,857 Electoral Divisions (EDs)**. The same agricultural system can be examined at **ED, county, Water Framework Directive (WFD) catchment and national scales**.

Published statistics are retained where they exist. Missing small-area detail is reconstructed under explicit rules while preserving the authoritative CSO controls.

> **What does Irish agriculture look like when national totals are resolved into the places, production systems and biological populations through which policy and environmental change actually occur?**

GOBLIN-Spatial extends the wider GOBLIN modelling framework into place. The historical baseline is a research product in its own right and provides the spatial foundation for future analysis of agricultural and land-use change.

---

## Why spatial agricultural evidence matters

National totals combine very different agricultural systems.

Places can differ in dairy, suckler, sheep, rearing and finishing activity, in the age and biological composition of their livestock, in agricultural land use and in farm structure. Areas with similar livestock totals can therefore represent very different production systems.

These differences matter for agricultural research, environmental assessment and policy. Measures aimed at dairy production, suckler systems, finishing cattle, sheep or particular land uses encounter different geographies.

GOBLIN-Spatial provides a common spatial evidence base for examining those differences consistently.

Instead of asking only:

> **Where are there many animals?**

the framework also allows users to ask:

> **Where are the production systems relevant to this question concentrated?**

---

## Data products

Two complementary livestock representations are provided.

| Product | Resolution | Content |
| --- | --- | --- |
| `CSO_13_Cohort_Annual_Panel_2015_2025` | ED × year | 9 cattle groups and 4 sheep groups representing the statistical livestock structure |
| `GOBLIN_31_Cohort_Annual_Panel_2015_2025` | ED × year | 21 cattle and 10 sheep biological cohorts |
| Standard Output | ED × year | Fixed-2020 production-value exposure by livestock and crop component |
| County view | 26 counties × year | Regional agricultural structure |
| WFD catchment view | 46 catchments × year | Agricultural structure aligned with water-quality geography |
| GOBLIN catchment view | 37 catchments × year | Compatibility with existing GOBLIN and GeoGOBLIN workflows |
| National view | Ireland × year | National accounting and aggregation |
| ED cohort signatures | ED, 2020 | Livestock-system composition of each ED |

Both ED livestock panels carry the same agricultural context:

`AREA_FARMED`, `ALL_GRASSLAND`, `TOTAL_CEREALS`, `OTHER_CROPS_HA`, `AGRICULTURAL_HOLDINGS`, `AVERAGE_SIZE_OF_HOLDINGS`, `AVERAGE_AGE_OF_HOLDER`, and `MEDIAN_AGE_OF_HOLDER`.

**Choosing a panel:** use **CSO 13** when the statistical livestock structure is sufficient. Use **GOBLIN 31** when biological cohorts are required, including applications involving emissions, herd structure or GOBLIN-compatible analysis.

A separately labelled layer calibrated to national GOBLIN/COHORTS totals is planned as a later development.

---

## Cattle, sheep or both

**Cattle** can be used independently. The cattle system represents dairy and suckler cows, bulls, male and female cattle by age, and dairy-bred, dairy-beef-cross and beef-bred youngstock within a complete **21-cohort GOBLIN representation**. It supports analysis of dairy and suckler geography, breeding, rearing and finishing structure, cattle age composition and change through time.

**Sheep** can also be used independently. The sheep system contains ewes aged two years and over, younger ewes, rams and other sheep, subsequently resolved into the **10 sheep cohorts used by GOBLIN**. DAFM breed information provides a broad distinction between **upland-type and lowland-type production systems**.

**Combined**, cattle and sheep share the same ED × year structure. The baseline can therefore describe dairy-, suckler-, sheep-dominated and mixed livestock systems alongside agricultural land and farm structure.

---

## Spatial scales

The Electoral Division is the authoritative small-area modelling unit.

County, catchment and national products are derived from the same ED baseline.

```text
                         Ireland
                            ▲
                            │
              ┌─────────────┴─────────────┐
              │                           │
          26 counties              46 WFD catchments
              ▲                           ▲
              │                           │
              └─────────────┬─────────────┘
                            │
                       2,857 EDs
```

County and WFD catchment are parallel reporting geographies.

Where an ED intersects more than one catchment, additive quantities are distributed using a frozen ED-to-catchment area crosswalk. The WFD geometry is stored with the model and protected by a checksum so that the same spatial allocation can be reproduced.

For every year:

```text
sum(ED) = sum(County) = sum(WFD catchment) = Ireland
```

Average holding size is recalculated from aggregate farmed area and holdings. Average holder age is weighted by holdings. Median holder age remains an ED-level statistic.

This allows one agricultural baseline to support administrative, catchment, environmental and national analysis.

---

## Quick start

Install GOBLIN-Spatial with geospatial dependencies:

```bash
pip install -e ".[geo]"
```

Verify the frozen production inputs:

```bash
goblin-spatial fetch-data --verify-only
```

Build the complete historical release (baseline, validation, catchment views, coherence audit, and the CSV/Parquet/SQLite/DuckDB bundle) in one step:

```bash
python scripts/build_historical_release.py
```

Everything lands in `reporting/report_data/historical/`; start with `historical_results.sqlite` and read [`docs/historical_outputs.md`](docs/historical_outputs.md).

Build only the core historical baseline:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

Build the livestock panels:

```bash
python scripts/build_livestock_panels.py
```

Build cattle only:

```bash
python scripts/build_cattle_annual_panel.py
```

Build sheep only:

```bash
python scripts/build_sheep_annual_panel.py
```

Build county, catchment and national views:

```bash
python scripts/build_catchment_baseline.py
```

ED panels are written to `data/interim/`. The master dataset, Standard Output, cohort signatures, clean workbook and aggregate reporting products are written to `data/processed/`.

---

## How the reconstruction works

The historical reconstruction follows a simple principle:

> **Keep published ED values where they exist. Reconstruct missing spatial detail within the authoritative statistical controls.**

The 2010 and 2020 agricultural censuses provide the principal fine-scale spatial information. Annual CSO livestock statistics determine the population levels that surrounding years must reproduce.

Supporting administrative evidence contributes additional information about spatial and biological composition. GOBLIN biological relationships then divide fixed livestock populations into the cohorts required for more detailed analysis.

```text
Official CSO controls
        ↓
annual ED reconstruction
        ↓
age, sex and production-system structure
        ↓
biological cohorts
        ↓
land and farm structure
        ↓
fixed-2020 Standard Output
        ↓
ED, county, catchment and national products
```

CSO statistics determine population levels. Supporting DAFM/AIM evidence informs spatial composition where additional detail is required. GOBLIN relationships provide the biological cohort structure.

Each stage preserves the population from which it is derived.

### Evidence represented in the baseline

| Quantity | Representation |
| --- | --- |
| 2020 ED cattle and sheep | Published CSO observations |
| 2020 ED agricultural land and farm structure | Published observations |
| ED livestock populations in surrounding years | Reconstructed within official annual controls |
| Cattle age-sex and genetic composition | Biological subdivision of fixed livestock populations |
| Sheep upland-type and lowland-type composition | Breed/system-based subdivision |
| Standard Output | Derived using fixed 2020 coefficients |
| County, catchment and national values | Derived from the ED baseline |

This structure allows annual spatial analysis while keeping the evidence supporting each layer transparent.

---

## Standard Output

GOBLIN-Spatial applies Irish 2020 Standard Output coefficients to the reconstructed agricultural activities to provide a consistent measure of **production-value exposure** across places and years.

The same 2020 coefficient set is applied throughout 2015–2025, so temporal differences reflect changes in agricultural activity and production structure rather than changes in valuation coefficients.

Livestock and crop components are retained separately alongside the combined covered total, allowing users to identify the activities contributing to production-value exposure within each ED, county or catchment.

---

## Using the baseline

The historical baseline supports agricultural, environmental and policy analysis without requiring a future scenario.

It can be used to examine where livestock populations and production systems are concentrated, how agricultural structure differs between places, and how that structure changes through time.

Because the same agricultural populations can be examined at ED, county and WFD catchment scales, the framework provides a common spatial basis for connecting agricultural structure with water-quality, emissions, land-use and other environmental evidence.

For policy analysis, the baseline makes it possible to identify the geography of the production systems through which an intervention would operate. Measures affecting dairy cows, suckler systems, finishing cattle or sheep can therefore be examined against the agricultural geography they encounter.

The baseline also provides a shared starting point for agricultural economics, emissions modelling, catchment analysis and future land-use research.

---

## Validation and reproducibility

The historical baseline is designed to be auditable and reproducible.

Published 2020 ED livestock values are checked against their source data. Annual reconstructed populations are checked against their controlling CSO totals. Each biological subdivision must reproduce its parent population, and county, catchment and national aggregations must reproduce the ED totals.

Independent validation evidence is retained separately from the information used to construct the population.

Production inputs are registered in `data_manifest.yaml`, and frozen spatial files, including the WFD catchment geometry, are protected by checksums.

> **Software structure may improve; scientific mathematics must not change silently.**

---

## Data and provenance

The repository records the source and role of the datasets used in production.

`data_manifest.yaml` provides the machine-readable inventory of frozen model inputs and checksums.

The evidence hierarchy is:

```text
Official statistics
        ↓
population and land controls

Supporting administrative evidence
        ↓
spatial and biological composition

GOBLIN biological relationships
        ↓
cohort subdivision

Derived indicators and reporting geographies
```

This keeps statistical observations, supporting evidence and model-derived quantities distinguishable throughout the workflow.

---

## Future outlook

The historical baseline provides the spatial foundation for **foresight, preparedness and future agricultural and land-use analysis**.

Future development will use this frozen representation of Irish agriculture to explore how alternative national pathways interact with different production systems and places.

The aim is to understand where agricultural adjustment may be concentrated, how changing livestock populations alter land requirements, where alternative land uses may become possible, how environmental and spatial constraints shape those possibilities, and whether national objectives depend strongly on particular locations.

Foresight uses a detailed understanding of the present to explore alternative futures, identify emerging risks and opportunities, and improve preparedness for change.

Planned development includes national GOBLIN/COHORTS calibration of the biological baseline and spatial analysis of alternative GOBLIN agricultural and land-use pathways.

These future layers will build on the historical baseline as a separate, versioned foundation.

---

## Relationship to the wider GOBLIN tools

GOBLIN-Spatial sits within the wider family of GOBLIN and FORESIGHT modelling tools.

**GOBLIN** provides national agricultural and land-use pathway analysis.

**GOBLIN-Spatial** provides the small-area agricultural evidence needed to understand how those systems differ across places and to support future spatial analysis.

The framework can complement **Agrisyn** for synthetic farm populations and **GeoGOBLIN** for catchment-scale environmental assessment.

Together, these tools provide connected views of Ireland's agricultural and land-use system.

---

## Documentation

| File | Purpose |
| --- | --- |
| [`docs/methodology.md`](docs/methodology.md) | Reconstruction methodology and model architecture |
| [`docs/SCIENTIFIC_ASSUMPTIONS.md`](docs/SCIENTIFIC_ASSUMPTIONS.md) | Scientific assumptions and interpretation |
| [`docs/catchment_bridge.md`](docs/catchment_bridge.md) | County and WFD catchment aggregation |
| [`docs/historical_outputs.md`](docs/historical_outputs.md) | Using the outputs: tables, keys, databases, how to read them |
| [`docs/historical_results_bundle.md`](docs/historical_results_bundle.md) | Historical reporting products |
| [`docs/validation.md`](docs/validation.md) | Validation and reproducibility |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Variables and definitions |
| [`docs/running.md`](docs/running.md) | Installation and execution |
| [`docs/reporting_architecture.md`](docs/reporting_architecture.md) | Reporting architecture |

---

## Project context

GOBLIN-Spatial is developed at the **University of Galway** within the wider ecosystem of GOBLIN and integrated agricultural and land-use modelling.

The framework is developed by **Elvis Kwame Ofori** as part of doctoral research supervised by **Professor David Styles** and **Professor Cathal O'Donoghue**, building on wider modelling contributions from **Dr Daniel Henn** and **Dr Colm Duffy**.

Its design responds to a broader need in integrated land-use research for spatial evidence capable of connecting agricultural populations, land, economics, environmental geography and future pathways.

---

## Citation

If you use GOBLIN-Spatial, please cite the corresponding software/data release and associated methodological publication when available.

Suggested citation:

> Ofori, E. K. (2026). *GOBLIN-Spatial historical baseline v1.1: ED-level cattle and sheep cohorts, agricultural land and farm structure for Ireland, 2015–2025* [Software and data]. University of Galway.
