# CSO ED 2020 dairy reconciliation

This folder contains the production inputs used by GOBLIN-Spatial. The 2020 CSO ED cattle composition requires a one-off reconciliation because the AVA42 ED dairy field contains published values, published numeric zeros, and blank/unpublished cells. Treating every blank as zero distorts the dairy/other-cattle split.

The reconciliation is deliberately **outside the normal model runtime**. The standalone utility is:

`../../scripts/reconcile_cso_ed_2020_production.py`

From the repository root the actual path is:

`scripts/reconcile_cso_ed_2020_production.py`

## Frozen rule

The rebuild utility:

1. keeps the existing 2,857-row production ED frame and row order;
2. keeps `TOTAL_CATTLE` and `OTHER_COW` unchanged;
3. keeps published positive 2020 dairy values unchanged;
4. keeps published numeric zero dairy values unchanged in the primary reconstruction;
5. reconstructs only raw 2020 **blank** dairy cells;
6. uses local 2020 DAFM/AIM dairy-type share first, then 2010 census evidence, then 2000 evidence where 2010 is blank, then county AIM share as fallback;
7. closes each county exactly to the 2020 CSO AAA10 dairy control;
8. derives `OTHER_CATTLE = TOTAL_CATTLE - DAIRY_COW - OTHER_COW` after dairy reconciliation;
9. hard-fails if the ED cattle identity, county closure, non-negative residual, row order, schema, or protected-column invariants are violated.

## Rebuild command

The AVA42 workbook is a provenance input and is not part of the normal runtime package. Run, for example:

```bash
python scripts/reconcile_cso_ed_2020_production.py \
  --baseline-2020 data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020.csv \
  --ava42 /path/to/AVA42.20260625T140648.xlsx \
  --aim data/inputs/baseline/02_DAFM_AIM_ED_Cattle_Profile_2020.csv \
  --aaa10 data/inputs/baseline/01_CSO_AAA10_Cattle_County_2015_2025.csv \
  --out data/inputs/baseline/01_CSO_ED_Agricultural_Baseline_2020_RECONCILED.csv \
  --audit data/inputs/baseline/CSO_ED_2020_Dairy_Reconciliation_Audit.csv
```

After review, the reconciled CSV can replace the contents of `01_CSO_ED_Agricultural_Baseline_2020.csv` while retaining that filename. No new configuration path or runtime reconciliation step is then required.

## Propagation

Once the corrected 2020 CSO ED input is installed, the existing historical build propagates the corrected cattle composition through the 2015-2025 annual panel, age-sex cohorts, genetics, Standard Output, livestock signatures, catchment aggregation, validation and reporting. Downstream products should be rebuilt rather than manually edited.
