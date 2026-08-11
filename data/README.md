# Data

GOBLIN-Spatial separates versioned package controls from downloaded raw source data and generated outputs.

## `data/controls/`

Small, auditable files that are part of the package logic are versioned with the code. Current examples include:

- social-economic controls used by the SE module;
- DAFM sheep composition anchors;
- GOBLIN cohort relationships;
- county-to-region mappings used by the Irish implementation.

These files are small enough for Git and benefit from line-by-line version history.

## `data/raw/`

Raw or binary source datasets are **not stored in normal Git history**. The package obtains them using `data_manifest.yaml` and the command:

```bash
goblin-spatial fetch-data
```

Each external file is pinned by SHA256 checksum. This prevents a later update to an official website or data repository from silently changing a historical GOBLIN-Spatial build.

The first Irish data snapshot is being prepared for a versioned Zenodo record. Until that record is published, developers may place the required files manually at the destinations listed in `data_manifest.yaml`; `fetch-data` will verify the checksums before accepting them.

## `data/interim/`

Intermediate module outputs are generated automatically. They are not source data and are not committed to Git.

## `data/processed/`

Final generated CSV and Excel outputs are written here. Stable public releases can be archived separately with a DOI.

## 2020 principle

The 2020 CSO Electoral Division agricultural baseline is the fixed fine-scale spatial anchor. Coarser annual statistics provide temporal controls around that baseline rather than replacing it.
