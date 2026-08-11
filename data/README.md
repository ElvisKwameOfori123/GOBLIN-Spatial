# Data

This repository separates **small reproducibility controls** from **large/raw source data** and **generated outputs**.

## `data/controls/`

Small, auditable control tables used directly by the workflow may be versioned here. These should contain official control values, not large source extracts.

## Raw data

Large raw CSO, DAFM and other source files are intentionally not committed to the normal Git history. The repository documentation will identify each required input, its expected filename, source, and role in the workflow.

## Generated data

Generated CSV and Excel outputs are also excluded from normal Git history. Stable public versions should be distributed through a versioned release/archive rather than repeatedly committed as binary files.

## 2020 principle

The 2020 CSO Electoral Division agricultural baseline is treated as the fixed fine-scale spatial anchor. Coarser annual statistics are used as temporal controls around that baseline rather than to overwrite it.
