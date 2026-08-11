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

The legacy scripts are not intended to become the public package API. They are retained as the regression reference until the modular implementation reproduces every validated control and output.

Normal users should ultimately run:

```bash
goblin-spatial fetch-data
goblin-spatial build --config configs/ireland_2015_2025.yaml
```
