"""Irish 2020 Standard Output coefficient controls for GOBLIN-Spatial."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BMW_COUNTIES = {
    "CAVAN", "DONEGAL", "GALWAY", "LAOIS", "LEITRIM", "LONGFORD",
    "LOUTH", "MAYO", "MONAGHAN", "OFFALY", "ROSCOMMON", "SLIGO",
    "WESTMEATH",
}
SOUTH_EAST_COUNTIES = {
    "CARLOW", "CLARE", "CORK", "DUBLIN", "KERRY", "KILDARE", "KILKENNY",
    "LIMERICK", "MEATH", "TIPPERARY", "WATERFORD", "WEXFORD", "WICKLOW",
}
ALL_IRISH_COUNTIES = BMW_COUNTIES | SOUTH_EAST_COUNTIES

# Historic two-region coding used by the Irish SOC2020 table.
FADN_REGION_LABELS = {
    "381": "Border, Midland and Western",
    "382": "Southern and Eastern",
}

# Product-code crosswalk retained as an explicit scientific contract and for
# validation against the source IFS SOC table. Runtime valuation uses the
# Git-tracked GOBLIN_SO_mapping.csv so model variables, coefficients and
# imputation flags live in one auditable control file.
COHORT_PRODUCT_CODE = {
    "dairy_cows": "A2300F",
    "suckler_cows": "A2300G",
    "bulls": "A2130",
    "DxD_calves_m": "A2010",
    "DxD_calves_f": "A2010",
    "DxB_calves_m": "A2010",
    "DxB_calves_f": "A2010",
    "BxB_calves_m": "A2010",
    "BxB_calves_f": "A2010",
    "DxD_heifers_less_2_yr": "A2220",
    "DxB_heifers_less_2_yr": "A2220",
    "BxB_heifers_less_2_yr": "A2220",
    "DxD_steers_less_2_yr": "A2120",
    "DxB_steers_less_2_yr": "A2120",
    "BxB_steers_less_2_yr": "A2120",
    "DxD_heifers_more_2_yr": "A2230",
    "DxB_heifers_more_2_yr": "A2230",
    "BxB_heifers_more_2_yr": "A2230",
    "DxD_steers_more_2_yr": "A2130",
    "DxB_steers_more_2_yr": "A2130",
    "BxB_steers_more_2_yr": "A2130",
    "Lowland ewes": "A4110K",
    "Upland ewes": "A4110K",
    "Lowland lamb_less_1_yr": "A4120",
    "Lowland male_less_1_yr": "A4120",
    "Lowland lamb_more_1_yr": "A4120",
    "Lowland ram": "A4120",
    "Upland lamb_less_1_yr": "A4120",
    "Upland male_less_1_yr": "A4120",
    "Upland lamb_more_1_yr": "A4120",
    "Upland ram": "A4120",
}

CEREAL_PRODUCT_CODES = {
    "wheat": "C1110T",
    "barley": "C1300T",
    "oats": "C1400T",
}

# 2020 Census of Agriculture cereal areas aligned to the historic Irish SO
# regions. These are used only to reproduce/validate the aggregate cereal
# composite in the model mapping CSV.
CEREAL_AREAS_2020_HA = {
    "381": {"wheat": 8061.0, "barley": 39399.0, "oats": 5167.0},
    "382": {"wheat": 38909.0, "barley": 153787.0, "oats": 20241.0},
}

DEFAULT_CONTROL_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "controls"
    / "standard_output"
    / "IFS_SOC2020_IE_model_controls.csv"
)

DEFAULT_MAPPING_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "controls"
    / "standard_output"
    / "GOBLIN_SO_mapping.csv"
)


def normalise_county(value: object) -> str:
    """Return a canonical uppercase Irish county label."""

    text = str(value).strip().upper()
    text = text.replace("COUNTY ", "").replace("CO. ", "").replace("CO.", "")
    return " ".join(text.split())


def fadn_region_for_county(value: object) -> str:
    """Map one county to the historic Irish SOC2020 region code."""

    county = normalise_county(value)
    if county in BMW_COUNTIES:
        return "381"
    if county in SOUTH_EAST_COUNTIES:
        return "382"
    raise ValueError(f"unknown Irish county for SO region assignment: {value!r}")


def add_fadn_region(frame: pd.DataFrame, county_col: str = "County") -> pd.DataFrame:
    """Attach historic SO region code and label without modifying the input."""

    if county_col not in frame.columns:
        raise KeyError(f"missing county column: {county_col}")
    out = frame.copy()
    out["FADN_REGION"] = out[county_col].map(fadn_region_for_county)
    out["FADN_REGION_LABEL"] = out["FADN_REGION"].map(FADN_REGION_LABELS)
    return out


def load_soc2020_controls(path: str | Path | None = None) -> pd.DataFrame:
    """Load and validate the Irish 2020 source SO controls used for audit."""

    source = Path(path) if path is not None else DEFAULT_CONTROL_PATH
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(source, sheet_name="SOC2020")
    else:
        raw = pd.read_csv(source, dtype={"FADN_REGION": str})

    raw.columns = [str(column).strip() for column in raw.columns]
    required = {"YEAR", "COUNTRY", "CD_PRODUCT", "FADN_REGION", "SOC_EUR"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"SOC source missing columns: {missing}")

    raw["YEAR"] = pd.to_numeric(raw["YEAR"], errors="raise").astype(int)
    raw["COUNTRY"] = raw["COUNTRY"].astype(str).str.strip().str.upper()
    raw["FADN_REGION"] = raw["FADN_REGION"].astype(str).str.strip()
    raw["CD_PRODUCT"] = raw["CD_PRODUCT"].astype(str).str.strip()
    raw["SOC_EUR"] = pd.to_numeric(raw["SOC_EUR"], errors="raise")

    controls = raw.loc[
        (raw["YEAR"] == 2020) & (raw["COUNTRY"] == "IE")
    ].copy()
    needed = set(COHORT_PRODUCT_CODE.values()) | set(CEREAL_PRODUCT_CODES.values())
    controls = controls.loc[controls["CD_PRODUCT"].isin(needed)].copy()

    if set(controls["FADN_REGION"]) != {"381", "382"}:
        raise AssertionError("Irish SOC controls must contain regions 381 and 382")
    if controls.duplicated(["CD_PRODUCT", "FADN_REGION"]).any():
        raise AssertionError("duplicate SOC product-region controls")

    expected_pairs = {
        (code, region) for code in needed for region in ("381", "382")
    }
    actual_pairs = set(zip(controls["CD_PRODUCT"], controls["FADN_REGION"]))
    missing_pairs = sorted(expected_pairs - actual_pairs)
    if missing_pairs:
        raise AssertionError(f"missing SOC product-region pairs: {missing_pairs}")

    return controls.sort_values(
        ["CD_PRODUCT", "FADN_REGION"], kind="stable"
    ).reset_index(drop=True)


def load_model_mapping(path: str | Path | None = None) -> pd.DataFrame:
    """Load the direct GOBLIN variable -> fixed-2020 SO mapping control.

    This is the runtime control used by baseline/pathway valuation. The original
    IFS extract remains separately available through ``load_soc2020_controls``
    for source auditing.
    """

    source = Path(path) if path is not None else DEFAULT_MAPPING_PATH
    if not source.exists():
        raise FileNotFoundError(source)
    mapping = pd.read_csv(source)

    required = {
        "MODEL_VARIABLE",
        "DOMAIN",
        "IFS_PRODUCT_CODE",
        "SOC_EUR_381",
        "SOC_EUR_382",
        "APPLY_IN_SO",
        "IMPUTED",
        "SENSITIVITY_SOC_EUR_381",
        "SENSITIVITY_SOC_EUR_382",
    }
    missing = sorted(required - set(mapping.columns))
    if missing:
        raise ValueError(f"SO mapping missing columns: {missing}")

    mapping["MODEL_VARIABLE"] = mapping["MODEL_VARIABLE"].astype(str).str.strip()
    mapping["DOMAIN"] = mapping["DOMAIN"].astype(str).str.strip().str.upper()
    mapping["IFS_PRODUCT_CODE"] = mapping["IFS_PRODUCT_CODE"].fillna("").astype(str).str.strip()
    mapping["APPLY_IN_SO"] = mapping["APPLY_IN_SO"].astype(str).str.strip().str.upper()
    mapping["IMPUTED"] = mapping["IMPUTED"].astype(str).str.strip().str.upper()

    if mapping["MODEL_VARIABLE"].duplicated().any():
        duplicates = mapping.loc[
            mapping["MODEL_VARIABLE"].duplicated(keep=False), "MODEL_VARIABLE"
        ].tolist()
        raise AssertionError(f"duplicate SO mapping variables: {duplicates}")

    expected_cohorts = set(COHORT_PRODUCT_CODE)
    livestock = mapping.loc[mapping["DOMAIN"].isin(["CATTLE", "SHEEP"])].copy()
    actual_cohorts = set(livestock["MODEL_VARIABLE"])
    if actual_cohorts != expected_cohorts:
        missing_cohorts = sorted(expected_cohorts - actual_cohorts)
        extra_cohorts = sorted(actual_cohorts - expected_cohorts)
        raise AssertionError(
            f"SO livestock mapping mismatch; missing={missing_cohorts}, extra={extra_cohorts}"
        )

    actual_codes = livestock.set_index("MODEL_VARIABLE")["IFS_PRODUCT_CODE"]
    for cohort, code in COHORT_PRODUCT_CODE.items():
        if actual_codes.loc[cohort] != code:
            raise AssertionError(
                f"SO mapping product mismatch for {cohort}: "
                f"{actual_codes.loc[cohort]!r} != {code!r}"
            )

    if "A4100" in set(livestock["IFS_PRODUCT_CODE"]):
        raise AssertionError("detailed GOBLIN sheep cohorts must not use parent code A4100")
    if actual_codes.loc["Lowland ewes"] != "A4110K":
        raise AssertionError("Lowland ewes must map to A4110K")
    if actual_codes.loc["Upland ewes"] != "A4110K":
        raise AssertionError("Upland ewes must map to A4110K")

    required_land = {"TOTAL_CEREALS", "OTHER_CROPS_HA"}
    land_apply = set(
        mapping.loc[
            (mapping["DOMAIN"] == "LAND") & (mapping["APPLY_IN_SO"] == "YES"),
            "MODEL_VARIABLE",
        ]
    )
    if not required_land.issubset(land_apply):
        raise AssertionError(
            f"SO mapping missing valued land variables: {sorted(required_land - land_apply)}"
        )

    valued = mapping.loc[mapping["APPLY_IN_SO"] == "YES"].copy()
    for column in ("SOC_EUR_381", "SOC_EUR_382"):
        valued[column] = pd.to_numeric(valued[column], errors="raise")
        if (valued[column] < 0).any():
            raise AssertionError(f"negative coefficients in {column}")

    for column in ("SENSITIVITY_SOC_EUR_381", "SENSITIVITY_SOC_EUR_382"):
        mapping[column] = pd.to_numeric(mapping[column], errors="coerce")

    return mapping.reset_index(drop=True)


def model_coefficient_lookup(
    mapping: pd.DataFrame | None = None,
    *,
    sensitivity: bool = False,
) -> dict[tuple[str, str], float]:
    """Return ``(MODEL_VARIABLE, region) -> EUR/head-or-ha``."""

    table = load_model_mapping() if mapping is None else mapping
    column_by_region = {
        "381": "SENSITIVITY_SOC_EUR_381" if sensitivity else "SOC_EUR_381",
        "382": "SENSITIVITY_SOC_EUR_382" if sensitivity else "SOC_EUR_382",
    }
    lookup: dict[tuple[str, str], float] = {}
    for row in table.loc[table["APPLY_IN_SO"] == "YES"].itertuples(index=False):
        for region, column in column_by_region.items():
            raw = getattr(row, column)
            if pd.isna(raw):
                raw = getattr(row, f"SOC_EUR_{region}")
            lookup[(str(row.MODEL_VARIABLE), region)] = float(raw)
    return lookup


def coefficient_lookup(
    controls: pd.DataFrame | None = None,
) -> dict[tuple[str, str], float]:
    """Return source ``(product, region) -> SOC_EUR`` for audit/reproduction."""

    table = load_soc2020_controls() if controls is None else controls
    return {
        (str(row.CD_PRODUCT), str(row.FADN_REGION)): float(row.SOC_EUR)
        for row in table.itertuples(index=False)
    }


def cereal_composite_coefficients(
    controls: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Reproduce the fixed 2020 aggregate-cereal SO coefficients by region."""

    lookup = coefficient_lookup(controls)
    out: dict[str, float] = {}
    for region, areas in CEREAL_AREAS_2020_HA.items():
        total_area = float(sum(areas.values()))
        if total_area <= 0:
            raise AssertionError(f"zero cereal area for SO region {region}")
        total_so = 0.0
        for crop, area in areas.items():
            total_so += float(area) * lookup[(CEREAL_PRODUCT_CODES[crop], region)]
        out[region] = total_so / total_area
    return out
