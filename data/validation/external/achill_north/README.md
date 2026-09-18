# Achill North external validation benchmark

This directory contains a compact external-application benchmark extracted from the 2026 Aqualicense / Sea-Fisheries Protection Authority sanitary survey for Achill North, Co. Mayo.

It is **not a controlling GOBLIN-Spatial model input**. The validated ED x year baseline remains authoritative. These files are retained only for validation, method comparison and future environmental applications.

## Why it is useful

The sanitary survey faced the same spatial problem addressed by the GOBLIN-Spatial catchment bridge: agricultural statistics are reported for Electoral Divisions (EDs), while environmental assessment requires a hydrologically defined contributing catchment.

The survey identified 23 EDs overlapping its bespoke Achill North contributing catchment and produced overlap-corrected 2020 livestock and land estimates by assuming an even within-ED spatial distribution. This provides a real Irish regulatory workflow that GOBLIN-Spatial can reproduce and then improve through alternative spatial weighting.

## Files

- `ED_Livestock_2020.csv`: Table 2-8 livestock data for the 23 overlapping EDs, published corrected values and QA fields reproduced from the extraction workbook.
- `ED_Land_2020.csv`: Table 2-9 holdings, farmed area, cereals and grassland, with derived intensity fields.
- `ED_Name_Crosswalk.csv`: explicit mapping from the sanitary-survey ED labels to the stable GOBLIN-Spatial `CSOED` identifiers. This is required because several Mayo ED labels are Irish-language or harmonised/merged in the model baseline.
- `Agriculture_SPR.csv`: agriculture-specific Source-Pathway-Receptor information for the principal livestock-source EDs.
- `Agri_Context.csv`: catchment area, sub-basin count, farmed share, seasonality and other agricultural context.
- `Faecal_Load_Context.csv`: microbial-loading coefficients reported in the sanitary survey. These are contextual evidence only and must not be adopted as GOBLIN-Spatial coefficients without separate source review.
- `Validation_Plan.csv`: proposed checks against the GOBLIN-Spatial 2020 baseline and catchment-allocation workflow.

## Intended validation use

The main checks are:

1. compare 2020 GOBLIN-Spatial cattle, sheep and dairy-cow values with the published 23-ED benchmark;
2. test spatial ranking of sheep-dominated EDs, particularly Ballycroy South, Ballycroy North, Sheskin and Knocknalower;
3. reproduce the sanitary survey's simple ED-area overlap correction;
4. compare simple area weighting with agricultural-land or grassland weighting;
5. use Achill North as a livestock-signature plausibility case, not as validation of the full 31-cohort biological reconstruction.

Because the sanitary survey itself draws on Census of Agriculture 2020 data, this is an **external applied implementation benchmark**, not a statistically independent validation dataset for the underlying 2020 agricultural census counts.

## Important boundaries

This dataset does not independently validate DxD/DxB/BxB parental-origin cohorts, age-sex cattle cohorts, 2015-2025 temporal trajectories, animal movements or seasonal grazing. E. coli observations and coefficients should not be interpreted as direct validation of GOBLIN-Spatial livestock populations.

For later water-quality work, the recommended conceptual separation is:

    GOBLIN-Spatial livestock system -> SOURCE
    soil / drainage / rivers / connectivity -> PATHWAY
    WFD waterbody / shellfish area / status -> RECEPTOR

Source PDF is not committed here. The extracted values should be traceable back to Tables 2-7, 2-8, 2-9 and 2-11 of the Achill North sanitary survey.
