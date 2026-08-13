"""End-to-end study workflow built on the validated historical ED baseline.

The historical ``pipeline.build`` product ends at livestock/cohorts, land and SE.
This module is the downstream study layer.  It selects either the 2020 or 2025
state, records the 18 pre-adult cattle cohort relationships in every ED, runs a
cattle-only scenario, optionally values Standard Output, optionally calculates
GOBLIN-style grassland release when authoritative pasture-DM controls are
supplied, and optionally allocates released land after soil enrichment.

The separation is deliberate::

    historical baseline -> scenario context -> cattle transition -> impacts

Soil and Standard Output never become requirements for reconstructing the
historical baseline itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from goblin_spatial.config import SpatialConfig, load_config
from goblin_spatial.dynamics.baseline import select_baseline_year
from goblin_spatial.land.opportunity import LandUseAllocationDefinition
from goblin_spatial.pipeline import build
from goblin_spatial.scenario.cohort_response import (
    BXB_COHORTS,
    DXB_COHORTS,
    DXD_COHORTS,
    build_ed_cohort_dependency_profile,
)
from goblin_spatial.scenario.sequential import (
    SequentialScenarioDefinition,
    SequentialScenarioResult,
    run_sequential_scenario,
)
from goblin_spatial.soil import add_ed_agricultural_soil


PRE_ADULT_CATTLE_COHORTS = tuple(DXD_COHORTS) + tuple(DXB_COHORTS) + tuple(BXB_COHORTS)
if len(PRE_ADULT_CATTLE_COHORTS) != 18:
    raise AssertionError("the cattle study must contain exactly 18 pre-adult cohorts")


@dataclass
class CattleStudyRun:
    """Complete outputs for one cattle-only ED scenario."""

    baseline: pd.DataFrame
    dependency: pd.DataFrame
    cohort_audit: pd.DataFrame
    scenario: SequentialScenarioResult
    output_dir: Path | None = None


def _resolve_config(config: str | Path | SpatialConfig | None) -> SpatialConfig | None:
    if config is None:
        return None
    return config if isinstance(config, SpatialConfig) else load_config(config)


def _assert_cattle_only(definition: SequentialScenarioDefinition) -> None:
    if abs(float(definition.sheep_reduction)) > 1e-12:
        raise ValueError("the principal cattle study must keep sheep unchanged")
    if definition.milestone_reductions is not None:
        for year, values in definition.milestone_reductions.items():
            if abs(float(values.get("sheep_reduction", 0.0))) > 1e-12:
                raise ValueError(
                    f"cattle study milestone {year} changes sheep; sheep must remain fixed"
                )


def _scenario_context(
    panel: pd.DataFrame,
    *,
    config: SpatialConfig | None,
    require_soil: bool,
) -> pd.DataFrame:
    """Attach static soil only when the downstream land stage actually needs it."""

    context = panel.copy()
    if not require_soil or "GOBLIN_SOIL_G1_SHARE" in context.columns:
        return context
    if config is None:
        raise ValueError(
            "land-use allocation requires a SpatialConfig so the ED soil profile can be resolved"
        )

    profile = config.files.get("agricultural_soil_profile")
    if profile is None or not profile.exists():
        raise FileNotFoundError(
            "land-use allocation requires the compact ED agricultural-soil profile; "
            "the historical baseline itself does not"
        )
    return add_ed_agricultural_soil(context, profile)


def build_18_cohort_dependency_audit(baseline: pd.DataFrame) -> pd.DataFrame:
    """Return one baseline row for every ED x 18 pre-adult cattle cohorts.

    A normal ED records its observed cohort/parent-adult ratio.  If the cohort is
    present but the relevant parent adults are absent in that ED, the row is a
    ``COUNTY_RECEIVER`` and records the cohort relative to the corresponding
    county parent-adult pool.  This is an accounting dependency used for scenario
    propagation, not an observed animal movement matrix.
    """

    audit = build_ed_cohort_dependency_profile(baseline)
    audit = audit.loc[audit["COHORT"].isin(PRE_ADULT_CATTLE_COHORTS)].copy()
    audit = audit.sort_values(["CSOED", "COHORT"], kind="stable").reset_index(drop=True)

    n_eds = baseline["CSOED"].nunique()
    if len(audit) != n_eds * 18:
        raise AssertionError("ED x 18-cohort dependency audit is incomplete")
    if audit[["CSOED", "COHORT"]].duplicated().any():
        raise AssertionError("duplicate ED-cohort relationship in dependency audit")
    if set(audit["COHORT"].unique()) != set(PRE_ADULT_CATTLE_COHORTS):
        raise AssertionError("dependency audit does not contain the exact 18 cohorts")

    local = audit["COHORT_SPATIAL_ROLE"] == "LOCAL_ED"
    receiver = audit["COHORT_SPATIAL_ROLE"] == "COUNTY_RECEIVER"
    if (audit.loc[local, "BASE_ORIGIN_ADULTS"] <= 0).any():
        raise AssertionError("LOCAL_ED relationship has no parent adults")
    if (audit.loc[receiver, "BASE_ORIGIN_ADULTS"] != 0).any():
        raise AssertionError("COUNTY_RECEIVER unexpectedly has local parent adults")
    if (audit.loc[receiver, "COUNTY_ORIGIN_ADULT_TOTAL"] <= 0).any():
        raise AssertionError("COUNTY_RECEIVER has no county parent-adult pool")

    expected_ratio = np.divide(
        audit["BASE_COHORT_HEAD"].to_numpy(dtype=float),
        audit["BASE_ORIGIN_ADULTS"].to_numpy(dtype=float),
        out=np.zeros(len(audit), dtype=float),
        where=audit["BASE_ORIGIN_ADULTS"].to_numpy(dtype=float) > 0,
    )
    if not np.allclose(
        audit["ED_COHORT_PER_ADULT_RATIO"].to_numpy(dtype=float),
        expected_ratio,
        atol=1e-12,
    ):
        raise AssertionError("ED adult-to-cohort ratio is not the observed baseline ratio")

    return audit


def build_scenario_cohort_audit(
    scenario_ed: pd.DataFrame,
    dependency: pd.DataFrame,
) -> pd.DataFrame:
    """Return long ED x milestone x 18-cohort scenario accounting.

    This table is intended for validation, publication diagnostics and maps.  It
    makes the ripple explicit for every pre-adult cohort rather than hiding the
    response inside the wide scenario dataframe.
    """

    required = {"CSOED", "County", "MILESTONE_YEAR"}
    missing = sorted(required - set(scenario_ed.columns))
    if missing:
        raise ValueError(f"scenario cohort audit missing columns: {missing}")

    rows: list[pd.DataFrame] = []
    for cohort in PRE_ADULT_CATTLE_COHORTS:
        cols = {
            "BASE_COHORT_HEAD": f"BASE_COHORT_{cohort}",
            "PREVIOUS_COHORT_HEAD": f"PREVIOUS_COHORT_{cohort}",
            "INCREMENTAL_REDUCTION_HEAD": f"INCREMENTAL_REDUCTION_COHORT_{cohort}",
            "CUMULATIVE_REDUCTION_HEAD": f"CUMULATIVE_REDUCTION_COHORT_{cohort}",
            "SCENARIO_COHORT_HEAD": f"SCENARIO_COHORT_{cohort}",
            "APPLIED_REDUCTION_RATE": f"REDUCTION_SIGNAL_{cohort}",
            "APPLIED_SIGNAL_SOURCE": f"REDUCTION_SIGNAL_SOURCE_{cohort}",
        }
        missing_cols = [column for column in cols.values() if column not in scenario_ed.columns]
        if missing_cols:
            raise ValueError(
                f"scenario output missing {cohort} accounting columns: {missing_cols}"
            )

        block = scenario_ed[["CSOED", "County", "MILESTONE_YEAR", *cols.values()]].copy()
        block = block.rename(columns={value: key for key, value in cols.items()})
        block.insert(3, "COHORT", cohort)
        rows.append(block)

    audit = pd.concat(rows, ignore_index=True)
    dependency_cols = [
        "CSOED",
        "COHORT",
        "ADULT_ORIGIN",
        "BASE_ORIGIN_ADULTS",
        "ED_COHORT_PER_ADULT_RATIO",
        "COUNTY_ORIGIN_ADULT_TOTAL",
        "COUNTY_COHORT_TOTAL",
        "ORPHAN_COHORT_PER_COUNTY_ADULT_RATIO",
        "ORPHAN_SHARE_OF_COUNTY_COHORT",
        "COHORT_SPATIAL_ROLE",
    ]
    audit = audit.merge(
        dependency[dependency_cols],
        on=["CSOED", "COHORT"],
        how="left",
        validate="many_to_one",
    )
    if audit["ADULT_ORIGIN"].isna().any():
        raise AssertionError("scenario audit could not join baseline ED-cohort relationship")

    for column in (
        "BASE_COHORT_HEAD",
        "PREVIOUS_COHORT_HEAD",
        "INCREMENTAL_REDUCTION_HEAD",
        "CUMULATIVE_REDUCTION_HEAD",
        "SCENARIO_COHORT_HEAD",
    ):
        audit[column] = pd.to_numeric(audit[column], errors="raise").astype(np.int64)
        if (audit[column] < 0).any():
            raise AssertionError(f"negative count in scenario cohort audit: {column}")

    if not np.array_equal(
        audit["PREVIOUS_COHORT_HEAD"].to_numpy(dtype=np.int64)
        - audit["INCREMENTAL_REDUCTION_HEAD"].to_numpy(dtype=np.int64),
        audit["SCENARIO_COHORT_HEAD"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("scenario cohort audit fails previous - incremental = scenario")
    if not np.array_equal(
        audit["BASE_COHORT_HEAD"].to_numpy(dtype=np.int64)
        - audit["CUMULATIVE_REDUCTION_HEAD"].to_numpy(dtype=np.int64),
        audit["SCENARIO_COHORT_HEAD"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("scenario cohort audit fails baseline - cumulative = scenario")

    return audit.sort_values(
        ["MILESTONE_YEAR", "CSOED", "COHORT"], kind="stable"
    ).reset_index(drop=True)


def load_pasture_dm_profiles(path: str | Path) -> dict[int, dict[str, float]]:
    """Read an auditable GOBLIN pasture-DM control table from CSV.

    Required columns are ``YEAR``, ``COHORT`` and
    ``PASTURE_DM_T_PER_HEAD_YEAR``.  The table should be generated from upstream
    GOBLIN animal/feed definitions; this loader deliberately does not invent or
    fill missing coefficients.
    """

    frame = pd.read_csv(path)
    required = {"YEAR", "COHORT", "PASTURE_DM_T_PER_HEAD_YEAR"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"pasture-DM control table missing columns: {missing}")

    frame["YEAR"] = pd.to_numeric(frame["YEAR"], errors="raise").astype(int)
    frame["PASTURE_DM_T_PER_HEAD_YEAR"] = pd.to_numeric(
        frame["PASTURE_DM_T_PER_HEAD_YEAR"], errors="raise"
    ).astype(float)
    if (~np.isfinite(frame["PASTURE_DM_T_PER_HEAD_YEAR"])).any() or (
        frame["PASTURE_DM_T_PER_HEAD_YEAR"] < 0
    ).any():
        raise ValueError("pasture-DM coefficients must be finite and non-negative")
    if frame[["YEAR", "COHORT"]].duplicated().any():
        raise ValueError("duplicate YEAR-COHORT rows in pasture-DM control table")

    profiles: dict[int, dict[str, float]] = {}
    for year, block in frame.groupby("YEAR", sort=True):
        profiles[int(year)] = dict(
            zip(
                block["COHORT"].astype(str),
                block["PASTURE_DM_T_PER_HEAD_YEAR"].astype(float),
            )
        )
    return profiles


def write_cattle_study_outputs(
    run: CattleStudyRun,
    output_dir: str | Path,
) -> Path:
    """Write transparent CSV outputs for one scenario run."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    run.scenario.schedule.to_csv(out / "scenario_schedule.csv", index=False)
    run.scenario.national.to_csv(out / "scenario_national_summary.csv", index=False)
    run.scenario.ed.to_csv(out / "scenario_ed_results.csv", index=False)
    run.dependency.to_csv(out / "baseline_ed_18_cohort_relationships.csv", index=False)
    run.cohort_audit.to_csv(out / "scenario_ed_18_cohort_audit.csv", index=False)
    run.output_dir = out
    return out


def run_cattle_study(
    panel: pd.DataFrame,
    definition: SequentialScenarioDefinition,
    *,
    config: str | Path | SpatialConfig | None = None,
    expected_eds: int | None = None,
    include_standard_output: bool = True,
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]] | None = None,
    supply_multiplier_by_year: float | Mapping[int, float] = 1.0,
    land_use: LandUseAllocationDefinition | None = None,
    output_dir: str | Path | None = None,
) -> CattleStudyRun:
    """Run the cattle study downstream from an already validated ED panel."""

    _assert_cattle_only(definition)
    cfg = _resolve_config(config)
    if expected_eds is None and cfg is not None:
        expected_eds = cfg.expected_eds

    context = _scenario_context(
        panel,
        config=cfg,
        require_soil=land_use is not None,
    )
    baseline = select_baseline_year(
        context,
        definition.baseline_year,
        expected_eds=expected_eds,
    )
    dependency = build_18_cohort_dependency_audit(baseline)

    mapping_path = None
    coefficient_path = None
    if cfg is not None:
        mapping = cfg.files.get("standard_output_mapping")
        coefficients = cfg.files.get("standard_output_coefficients")
        mapping_path = None if mapping is None else str(mapping)
        coefficient_path = None if coefficients is None else str(coefficients)

    scenario = run_sequential_scenario(
        context,
        definition,
        expected_eds=expected_eds,
        include_standard_output=include_standard_output,
        mapping_path=mapping_path,
        coefficient_path=coefficient_path,
        pasture_dm_t_per_head_by_year=pasture_dm_t_per_head_by_year,
        supply_multiplier_by_year=supply_multiplier_by_year,
        land_use=land_use,
    )
    cohort_audit = build_scenario_cohort_audit(scenario.ed, dependency)

    run = CattleStudyRun(
        baseline=baseline,
        dependency=dependency,
        cohort_audit=cohort_audit,
        scenario=scenario,
    )
    if output_dir is not None:
        write_cattle_study_outputs(run, output_dir)
    return run


def build_and_run_cattle_study(
    config: str | Path | SpatialConfig,
    definition: SequentialScenarioDefinition,
    *,
    include_standard_output: bool = True,
    pasture_dm_t_per_head_by_year: Mapping[int, Mapping[str, float]] | None = None,
    supply_multiplier_by_year: float | Mapping[int, float] = 1.0,
    land_use: LandUseAllocationDefinition | None = None,
    output_dir: str | Path | None = None,
) -> CattleStudyRun:
    """Fresh-build acceptance route: historical baseline -> cattle scenario."""

    cfg = _resolve_config(config)
    assert cfg is not None
    panel = build(cfg)
    return run_cattle_study(
        panel,
        definition,
        config=cfg,
        expected_eds=cfg.expected_eds,
        include_standard_output=include_standard_output,
        pasture_dm_t_per_head_by_year=pasture_dm_t_per_head_by_year,
        supply_multiplier_by_year=supply_multiplier_by_year,
        land_use=land_use,
        output_dir=output_dir,
    )
