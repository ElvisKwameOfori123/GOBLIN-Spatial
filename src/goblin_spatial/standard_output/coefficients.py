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

FADN_REGION_LABELS = {
    "381": "Border, Midland and Western",
    "382": "Southern and Eastern",
}

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

CEREAL_AREAS_2020_HA = {
    "381": {"wheat": 8061.0, "barley": 39399.0, "oats": 5167.0},
    "382": {"wheat": 38909.0, "barley": 153787.0, "oats": 20241.0},
}

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTROL_PATH = (
    ROOT / "data" / "controls" / "standard_output" / "IFS_SOC2020_IE_model_controls.csv"
)
DEFAULT_MAPPING_PATH = (
    ROOT / "data" / "inputs" / "baseline" / "08_IFS2020_Standard_Output_Mapping.xlsx"
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

    controls = raw.loc[(raw["YEAR"] == 2020) & (raw["COUNTRY"] == "IE")].copy()
    needed = set(COHORT_PRODUCT_CODE.values()) | set(CEREAL_PRODUCT_CODES.values())
    controls = controls.loc[controls["CD_PRODUCT"].isin(needed)].copy()

    if set(controls["FADN_REGION"]) != {"381", "382"}:
        raise AssertionError("Irish SOC controls must contain regions 381 and 382")
    if controls.duplicated(["CD_PRODUCT", "FADN_REGION"]).any():
        raise AssertionError("duplicate SOC product-region controls")

    expected_pairs = {(code, region) for code in needed for region in ("381", "382")}
    actual_pairs = set(zip(controls["CD_PRODUCT"], controls["FADN_REGION"]))
    missing_pairs = sorted(expected_pairs - actual_pairs)
    if missing_pairs:
        raise AssertionError(f"missing SOC product-region pairs: {missing_pairs}")

    return controls.sort_values(["CD_PRODUCT", "FADN_REGION"], kind="stable").reset_index(drop=True)


def load_model_mapping(path: str | Path | None = None) -> pd.DataFrame:
    """Load the canonical GOBLIN variable to fixed-2020 SO mapping.

    The repository authority is the packaged IFS-2020 workbook sheet
    ``SO_Mapping``. CSV input remains accepted only when an explicit path is
    supplied, which is useful for small tests or independently exported copies.
    """

    source = Path(path) if path is not None else DEFAULT_MAPPING_PATH
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() in {".xlsx", ".xls"}:
        mapping = pd.read_excel(source, sheet_name="SO_Mapping")
    else:
        mapping = pd.read_csv(source)

    mapping.columns = [str(column).strip() for column in mapping.columns]
    required = {"MODEL_VARIABLE", "CD_PRODUCT", "UNIT_BASIS"}
    missing = sorted(required - set(mapping.columns))
    if missing:
        raise ValueError(f"SO mapping missing columns: {missing}")

    mapping["MODEL_VARIABLE"] = mapping["MODEL_VARIABLE"].astype(str).str.strip()
    mapping["CD_PRODUCT"] = mapping["CD_PRODUCT"].astype(str).str.strip()
    mapping["UNIT_BASIS"] = mapping["UNIT_BASIS"].astype(str).str.strip().str.upper()
    if mapping["MODEL_VARIABLE"].duplicated().any():
        raise AssertionError("SO mapping contains duplicate MODEL_VARIABLE rows")

    expected_variables = set(COHORT_PRODUCT_CODE) | {"TOTAL_CEREALS"}
    actual_variables = set(mapping["MODEL_VARIABLE"])
    missing_variables = sorted(expected_variables - actual_variables)
    if missing_variables:
        raise AssertionError(f"SO mapping missing model variables: {missing_variables}")

    expected_codes = {
        variable: code for variable, code in COHORT_PRODUCT_CODE.items()
    }
    for variable, code in expected_codes.items():
        actual = mapping.loc[
            mapping["MODEL_VARIABLE"].eq(variable), "CD_PRODUCT"
        ].iloc[0]
        if actual != code:
            raise AssertionError(
                f"SO mapping code changed for {variable}: expected={code}, actual={actual}"
            )
    return mapping.reset_index(drop=True)
