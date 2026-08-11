# Data deposit and release plan

GOBLIN-Spatial separates the software package from the formal research-data release while keeping compact working inputs in GitHub for convenient development.

## Development bundle

A development data bundle has been assembled for the Ireland 2015-2025 implementation:

`GOBLIN_Spatial_Data_Bundle_DEV_2026-08-11.zip`

Development bundle properties:

- 25 packaged files;
- approximately 3.17 MB;
- SHA256: `6350d8c463cef3f8bcc791b2ebd689b41ff5f80bbdf0f6f95845ae2820ca0316`;
- contains a `README.txt` and `SHA256SUMS.txt`;
- separates `core/`, `derived_reference/`, `source_audit/`, and `documentation/` material.

This archive is a development handoff, not yet the final public v1.0 deposit.

## Full-data inputs currently external to Git

Two files are deliberately kept outside normal Git history:

### Fixed 2020 ED baseline

Expected package destination:

`data/raw/cattle/CSO_ED_2020.csv`

SHA256:

`bc93d1f9747809aed79ea7e7160f5853265d73e5056cceaae0353ee2fc63a657`

### AQA06 annual land controls

Expected package destination:

`data/raw/land/AQA06_Unpivoted_2013_2025.csv`

SHA256:

`df8a147dc2aa07815bd4bf68a33d29798d972388f938df9c69c0eec9fa5f8719`

The manifest will receive permanent Zenodo and/or stable official download URLs before the public release. No scientific module needs to change when those URLs are added.

## Compact inputs retained in GitHub

Compact inputs that are useful to version alongside the code remain in GitHub, including:

- annual county cattle controls;
- county and regional sheep controls;
- the combined sheep source workbook;
- DAFM sheep breed anchors;
- GOBLIN cohort relationships;
- social-economic control data;
- county-to-region mapping.

## Proposed Zenodo record

Working title:

**GOBLIN-Spatial: Ireland 2015-2025 Reproducibility Data Bundle**

Suggested description:

> Data inputs, control tables, audit sources and reference outputs supporting the Ireland 2015-2025 implementation of GOBLIN-Spatial, a constraint-preserving framework for translating nationally consistent livestock and land-use pathways to Electoral Division level. The 2020 Census of Agriculture Electoral Division baseline is retained as the fixed fine-scale spatial anchor. Annual higher-level statistics provide temporal controls, and the GOBLIN cohort structure provides biological livestock disaggregation.

The final Zenodo v1.0 record should be published only after the modular cattle, sheep, land and SE package reproduces the validated reference workflow and the redistribution/attribution metadata for each source has been checked.

## Release workflow

```text
GitHub package + compact controls
              |
              | goblin-spatial fetch-data
              v
Zenodo / official full-data inputs
              |
              v
          data/raw/
              |
              | goblin-spatial build
              v
validated ED data products
```

The public release should link the GitHub software version and Zenodo data version explicitly so that a future researcher can identify exactly which code and which data produced a given result.
