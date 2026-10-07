# GOBLIN-Spatial

**A small-area livestock cohort framework for place-based agricultural and environmental analysis**

GOBLIN-Spatial provides a constraint-preserving spatial representation of Irish agriculture. The active repository scope is deliberately limited to the **2015-2025 historical baseline, multiscale reporting, livestock-system signatures and evaluation**.

The baseline represents **2,857 Electoral Divisions (EDs)** annually from 2015 to 2025 and combines cattle, sheep, agricultural land, selected farm structure and fixed-coefficient Standard Output. County, Water Framework Directive (WFD) catchment and national views are derived from the same ED foundation.

> **Livestock abundance and livestock-system function are distinct forms of spatial information.**

The model therefore retains not only how many animals are represented in each place, but also the biological composition and parent-follower organisation of the livestock system.

---

## What the baseline contains

Two complementary livestock representations are provided:

| Product | Resolution | Content |
| --- | --- | --- |
| `CSO_13_Cohort_Annual_Panel_2015_2025` | ED × year | 9 cattle groups and 4 sheep groups |
| `GOBLIN_31_Cohort_Annual_Panel_2015_2025` | ED × year | 21 cattle and 10 sheep biological cohorts |
| Standard Output | ED × year | fixed-2020 production-value exposure |
| County view | county × year | administrative agricultural structure |
| WFD catchment view | catchment × year | agricultural structure aligned with environmental receiving geography |
| National view | Ireland × year | national accounting and aggregation |
| Livestock signatures | 2020 and 2025 | composition and parent-follower structure at multiple scales |

The 21 cattle cohorts comprise adult dairy cows, suckler cows and bulls plus 18 follower cohorts distinguished by parental origin (DxD, DxB, BxB), sex and age. Sheep are represented through 10 GOBLIN cohorts.

---

## Reconstruction logic

The model follows an explicit evidence hierarchy:

```text
published census structure
        +
annual official controls
        +
supporting DAFM/AIM composition evidence
        +
GOBLIN biological relationships
        ↓
historical ED reconstruction
        ↓
biological cohorts
        ↓
land / farm structure / Standard Output
        ↓
ED, county, WFD catchment and national views
        ↓
livestock signatures, catchment structure and evaluation
```

Published 2020 ED livestock values are retained as published; cells the CSO withheld for confidentiality are filled before the model runs (Stage 00, `scripts/prepare_census_inputs.py`) so that the census county and State totals hold exactly. Surrounding years are census-anchored reconstructions under the authoritative annual controls. Supporting administrative data inform composition without replacing those controlling quantities.

All biological subdivisions preserve the population from which they are derived.

---

## Multiscale reporting

The ED is the base modelling geography. County and WFD catchment are parallel reporting geographies derived from the same ED state.

For additive quantities:

```text
sum(ED) = sum(County) = sum(WFD catchment) = Ireland
```

Where an ED intersects more than one WFD catchment, additive quantities are allocated using a frozen ED-to-catchment area crosswalk. Ratios are always recomputed from aggregated numerators and denominators rather than averaged across EDs.

---

## Livestock signatures

A livestock signature describes the **organisation** of the livestock system represented in a place. The implemented signature includes dairy share of adult cows, DxD/DxB/BxB follower shares, followers per adult cow, cattle and sheep density on farmed land, grassland and cereal shares of farmed area, Standard Output intensity and broad sheep production type.

Parent-follower relationships are supported at the finest valid scale: local ED, county-supported or national fallback. These are relationship-support classes, not observations of animal movement or trade.

---

## Catchment structure

WFD catchments are reported in two complementary ways. The **accounting view**
aggregates ED populations and land fractionally with the frozen ED-catchment
crosswalk and then recalculates ratios from the aggregated numerators and
denominators. The **structural view** retains the signatures of the EDs
intersecting each catchment and reports denominator-weighted P10, P50 and P90
values. The first describes the catchment as one agricultural accounting unit;
the second shows the local heterogeneity that the catchment total can conceal.

Neither view implies exact within-ED animal locations.

---

## Quick start

Python 3.10 or newer is required.

```bash
pip install -e ".[geo,reporting,query]"
```

Verify the repository-contained inputs:

```bash
goblin-spatial fetch-data --verify-only
```

The prepared 2010 and 2020 census inputs are committed. To regenerate them from the raw CSO AVA42 table (Stage 00), or to confirm they regenerate exactly:

```bash
python scripts/prepare_census_inputs.py          # rewrite prepared census inputs and audit tables
python scripts/prepare_census_inputs.py --check  # verify only (first step of the release build)
```

Build the complete historical release:

```bash
python scripts/build_historical_release.py
```

The complete release is written to:

```text
reporting/report_data/historical/
```

It includes CSV, Parquet, SQLite and DuckDB copies of the principal historical, signature, catchment-structure and evaluation tables.

To build only the core historical baseline:

```bash
goblin-spatial build --config configs/ireland_2015_2025.yaml
```

See [`docs/running.md`](docs/running.md) and [`docs/historical_outputs.md`](docs/historical_outputs.md).

---

## Verification and evaluation

The repository separates accounting verification from empirical evaluation. The coherence audit independently recomputes the cross-product accounting, closure and aggregation identities from released outputs and raw inputs. Input sources used in reconstruction are described as pattern-fidelity or coherence diagnostics rather than independent validation. More independent checks include the withheld sheep-composition comparison and the Achill North applied benchmark.

Production inputs and checksums are registered in `data_manifest.yaml`.

---

## Repository scope

This repository contains the historical GOBLIN-Spatial baseline and its
multiscale reporting and evaluation products. It does not contain a future
scenario or policy-response experiment.

---

## Documentation

| File | Purpose |
| --- | --- |
| [`docs/methodology.md`](docs/methodology.md) | reconstruction methodology and model architecture |
| [`docs/SCIENTIFIC_ASSUMPTIONS.md`](docs/SCIENTIFIC_ASSUMPTIONS.md) | scientific assumptions and interpretation |
| [`docs/catchment_bridge.md`](docs/catchment_bridge.md) | county and WFD catchment aggregation |
| [`docs/historical_outputs.md`](docs/historical_outputs.md) | released tables and databases |
| [`docs/historical_results_bundle.md`](docs/historical_results_bundle.md) | historical manuscript/query bundle |
| [`docs/validation.md`](docs/validation.md) | evaluation and reproducibility |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | variables and definitions |
| [`docs/running.md`](docs/running.md) | installation and execution |

---

## Citation

Suggested software/data citation:

> Ofori, E. K. (2026). *GOBLIN-Spatial historical baseline v1.1: ED-level cattle and sheep cohorts, agricultural land and farm structure for Ireland, 2015-2025* [Software and data]. University of Galway.
