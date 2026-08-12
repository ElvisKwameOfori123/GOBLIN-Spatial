# Reference workflow

The original research implementation was developed and validated as sequential Scripts 01–07. These scripts define the numerical reference that the modular `goblin_spatial` package must reproduce.

The package itself is now organised around four scientific modules: `cattle`, `sheep`, `land`, and `se`.

| Reference stage | Modular destination |
|---|---|
| `01` 2020 cattle reconciliation and age-sex controls | `cattle` |
| `02` annual ED cattle panel | `cattle` |
| `03A` region-to-county sheep controls | `sheep` |
| `03B` county-to-ED sheep panel | `sheep` |
| `04` cattle/sheep merge | top-level pipeline |
| `05A` DAFM sheep composition controls | `sheep` |
| `05B` ED sheep type enrichment | `sheep` |
| `05C` 21 GOBLIN cattle cohorts | `cattle` |
| `05D` 10 GOBLIN sheep cohorts / 31-cohort master | `sheep` + pipeline |
| `06` land enrichment | `land` |
| `06` farm structure and holder age | `se` |
| `07` clean workbook | export layer |

The corrected Script 5C-equivalent implementation is now `src/goblin_spatial/cattle/cohorts.py`. It uses ED adult-cow structure plus a sparse ED receiver/rearing exception and no longer uses blanket county context to give every ED positive DxD/DxB/BxB support. The original standalone Script 5C should therefore be treated only as a historical regression reference, not as the current scientific implementation.

The legacy scripts are not intended to become the public package API. Normal users should run:

```bash
goblin-spatial fetch-data --verify-only
goblin-spatial build --config configs/ireland_2015_2025.yaml
```
