# GOBLIN-Spatial data contract

The repository is self-contained for the **2015-2025 historical baseline, multiscale reporting, livestock signatures and evaluation**. `data_manifest.yaml` is the machine-readable authority for production inputs and checksums.

No normal model command downloads external data. Production inputs are read from frozen repository files.

## Historical baseline inputs

The validated reconstruction uses the canonical inputs under `data/inputs/baseline/` together with fixed Standard Output controls under `data/controls/standard_output/`.

The 2010 and 2020 agricultural censuses provide the principal fine-scale spatial anchors. Their livestock columns are prepared in Stage 00 from the raw AVA42 table (`00_CSO_AVA42_Livestock_ED_2000_2010_2020.csv`): published cells are kept, suppressed cells are filled to the exact census county totals (`00_CSO_Census_County_Livestock_2010_2020.csv`), and the audit tables are in `census_reconciliation/`. `python scripts/prepare_census_inputs.py --check` confirms that the committed census files regenerate exactly. Only livestock columns are written; all non-livestock fields (land, holdings, holder age, LSU, identifiers) are preserved exactly and the original CSV formatting round-trips. Annual CSO livestock and land statistics provide the higher-level controls used to reconstruct surrounding years. DAFM/AIM evidence contributes spatial and biological composition signals without replacing those controls. GOBLIN biological relationships provide the 21 cattle and 10 sheep cohorts. Fixed 2020 Standard Output coefficients provide production-value exposure.

For cattle, the DAFM/AIM file `02_DAFM_AIM_ED_Cattle_Profile_2020.csv` is a composition signal, not a population control. The prepared 2020 ED state remains the anchor, annual county margins control reconstructed years, and cohort subdivision preserves the fixed parent populations.

For sheep, DAFM county information is used as a relative within-region weighting input and as a pattern-fidelity diagnostic. It is not treated as independent validation.

## Spatial reporting inputs

Two frozen geometries support reproducible reporting:

- Electoral Division geometry for ED mapping and ED-to-catchment crosswalk construction;
- the 46 Water Framework Directive catchments used for catchment reporting.

Geometry does not alter the historical livestock, land or Standard Output reconstruction. Where an ED intersects more than one WFD catchment, additive quantities are allocated using the frozen ED-catchment area fraction.

## Generated outputs

Generated files are written beneath `data/interim/`, `data/processed/` and `reporting/report_data/historical/`.

The controlling distinction is:

```text
repository-contained canonical inputs
        -> historical reconstruction
        -> biological cohorts
        -> land / farm structure / Standard Output
        -> ED, county, WFD catchment and national reporting
        -> livestock signatures and parent-follower relationships
        -> evaluation and catchment-structure summaries
```

The complete manuscript/query release is produced by:

```bash
python scripts/build_historical_release.py
```

and written to:

```text
reporting/report_data/historical/
```

## External evaluation data

External datasets used only for evaluation, method comparison or application testing are stored under `data/validation/external/` and do not alter the controlling baseline quantities.

The Achill North benchmark is stored under `data/validation/external/achill_north/` and is used as an applied comparison of livestock, agricultural land and ED-to-catchment representation.

## Scenario work
