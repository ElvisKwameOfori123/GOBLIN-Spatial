# Scripts

The validated workflow consists of seven sequential stages.

| Stage | Purpose |
|---|---|
| `01` | Reconcile the 2020 cattle baseline and construct cattle age-sex controls |
| `02` | Construct the 2015–2025 ED cattle panel from annual official controls |
| `03A` | Reconcile annual sheep controls from region to county |
| `03B` | Allocate annual county sheep controls to EDs |
| `04` | Merge cattle and sheep into the annual ED livestock master |
| `05A` | Prepare annual DAFM sheep-composition controls |
| `05B` | Enrich ED sheep with Lowland/Mountain-type composition |
| `05C` | Express fixed CSO ED cattle populations in the 21 GOBLIN cattle cohorts |
| `05D` | Express fixed sheep populations in the 10 GOBLIN sheep cohorts and form the final 31-cohort master |
| `06` | Add annual land, agricultural holdings and holder-age characteristics |
| `07` | Export the clean four-sheet research workbook |

## Portability rule

The research versions of these scripts currently reflect the validated local workflow. Before the scripts are committed here, their hard-coded local Windows paths will be replaced by repository-relative paths only. The calculations, controls and validation rules will not be altered during that portability step.

## Execution order

Run scripts in numerical order. Each stage validates its inputs and outputs before the next stage is used.
