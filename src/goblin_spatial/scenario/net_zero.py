"""Principal adult-driven net-zero livestock scenario for GOBLIN-Spatial.

The scientific contract is intentionally simple:

1. select the immutable 2020 or 2025 ED baseline;
2. specify reduction fractions for the national adult livestock controls;
3. remove those adults pro-rata from the EDs where they already exist;
4. propagate cattle reductions into young/follower cohorts from the observed
   ED adult-to-cohort relationships;
5. allow receiver/rearing/finishing EDs with follower cattle but no matching
   breeding cows to inherit the same-county breeding reduction signal;
6. use a national reduction rate only for true orphan follower locations where
   the county contains no corresponding breeding adults;
7. preserve the ten-cohort sheep structure while applying the selected total-
   sheep reduction;
8. value the solved physical state with Standard Output only afterwards.

There are no Policy/SplitGas/AllGas pathway names in this interface and no
independent national targets for young cattle cohorts. Young-cohort change is an
endogenous consequence of the selected adult reductions and the validated ED
baseline structure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.dynamics.baseline import (
    SUPPORTED_SCENARIO_BASE_YEARS,
    select_baseline_year,
)
from goblin_spatial.scenario.allocation import (
    _allocate_reduction,
    _bounded_integer_allocate,
)
from goblin_spatial.scenario.cohort_response import (
    FOLLOWER_COHORTS,
    _cohort_origin,
    _reduction_signal,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10
from goblin_spatial.standard_output import add_pathway_standard_output


@dataclass(frozen=True)
class NetZeroScenarioDefinition:
    """Editable controls for one net-zero livestock endpoint.

    Reduction values are fractions of the selected baseline population. For
    example, ``dairy_reduction=0.30`` means 30% fewer dairy cows at the target
    year relative to the selected 2020 or 2025 baseline.

    The reduction fractions are deliberately required arguments: this module
    does not invent study-specific net-zero assumptions.
    """

    baseline_year: int
    target_year: int
    dairy_reduction: float
    suckler_reduction: float
    sheep_reduction: float
    name: str = "NET_ZERO"

    def __post_init__(self) -> None:
        if self.baseline_year not in SUPPORTED_SCENARIO_BASE_YEARS:
            raise ValueError(
                f"baseline_year must be one of {SUPPORTED_SCENARIO_BASE_YEARS}"
            )
        if int(self.target_year) <= int(self.baseline_year):
            raise ValueError("target_year must follow baseline_year")
        if not str(self.name).strip():
            raise ValueError("scenario name cannot be empty")
        for label, value in (
            ("dairy_reduction", self.dairy_reduction),
            ("suckler_reduction", self.suckler_reduction),
            ("sheep_reduction", self.sheep_reduction),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{label} must lie between 0 and 1")


def _integer_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        raise KeyError(f"missing net-zero scenario column: {column}")
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype=float)
    rounded = np.rint(values).astype(np.int64)
    if np.max(np.abs(values - rounded)) > 1e-8 or (rounded < 0).any():
        raise AssertionError(f"{column} must contain non-negative integer counts")
    return rounded


def _adult_scenario(
    panel: pd.DataFrame,
    definition: NetZeroScenarioDefinition,
    *,
    expected_eds: int | None,
) -> pd.DataFrame:
    """Apply the editable adult reduction controls pro-rata to the ED baseline."""

    out = select_baseline_year(
        panel,
        definition.baseline_year,
        expected_eds=expected_eds,
    ).copy()
    out.insert(0, "SCENARIO_NAME", definition.name)
    out.insert(1, "SCENARIO_BASELINE_YEAR", definition.baseline_year)
    out.insert(2, "SCENARIO_TARGET_YEAR", definition.target_year)
    out.insert(3, "SCENARIO_ENGINE", "NET_ZERO_ADULT_DRIVEN")

    controls = {
        "DAIRY_COW": float(definition.dairy_reduction),
        "OTHER_COW": float(definition.suckler_reduction),
        "TOTAL_SHEEP": float(definition.sheep_reduction),
    }
    for column, reduction_fraction in controls.items():
        base = _integer_array(out, column)
        scenario, reduction, target = _allocate_reduction(
            base,
            reduction_fraction,
            base.astype(float),
        )
        out[f"BASE_{column}"] = base
        out[f"REDUCTION_{column}"] = reduction
        out[f"SCENARIO_{column}"] = scenario
        out[f"REDUCTION_PCT_{column}"] = np.where(
            base > 0,
            100.0 * reduction / base,
            0.0,
        )
        if int(scenario.sum()) != int(target):
            raise AssertionError(f"national target failed for {column}")

    out["BASE_ADULT_COWS"] = out["BASE_DAIRY_COW"] + out["BASE_OTHER_COW"]
    out["REDUCTION_ADULT_COWS"] = (
        out["REDUCTION_DAIRY_COW"] + out["REDUCTION_OTHER_COW"]
    )
    out["SCENARIO_ADULT_COWS"] = (
        out["SCENARIO_DAIRY_COW"] + out["SCENARIO_OTHER_COW"]
    )
    return out


def _add_cattle_response(adult: pd.DataFrame) -> pd.DataFrame:
    """Derive all 21 cattle cohorts from the realised adult reductions.

    No external young-cohort targets are required. For each follower cohort the
    continuous implied reduction is ``cohort_base * adult_reduction_rate``.
    Integer reductions are then allocated to close exactly to the rounded sum of
    those ED-level implied reductions.
    """

    out = adult.copy()
    base_dairy = _integer_array(out, "BASE_DAIRY_COW")
    base_suckler = _integer_array(out, "BASE_OTHER_COW")
    base_adults = _integer_array(out, "BASE_ADULT_COWS")
    red_dairy = _integer_array(out, "REDUCTION_DAIRY_COW")
    red_suckler = _integer_array(out, "REDUCTION_OTHER_COW")
    red_adults = _integer_array(out, "REDUCTION_ADULT_COWS")
    counties = out["County"].astype(str).to_numpy(dtype=object)

    adult_mapping = {
        "dairy_cows": ("BASE_DAIRY_COW", "REDUCTION_DAIRY_COW", "SCENARIO_DAIRY_COW"),
        "suckler_cows": ("BASE_OTHER_COW", "REDUCTION_OTHER_COW", "SCENARIO_OTHER_COW"),
    }
    for cohort, (base_col, reduction_col, scenario_col) in adult_mapping.items():
        out[f"BASE_COHORT_{cohort}"] = _integer_array(out, base_col)
        out[f"REDUCTION_COHORT_{cohort}"] = _integer_array(out, reduction_col)
        out[f"SCENARIO_COHORT_{cohort}"] = _integer_array(out, scenario_col)

    for cohort in FOLLOWER_COHORTS:
        base = _integer_array(out, cohort)
        origin = _cohort_origin(cohort)
        if origin == "DAIRY":
            signal, source = _reduction_signal(base_dairy, red_dairy, base, counties)
        elif origin == "SUCKLER":
            signal, source = _reduction_signal(base_suckler, red_suckler, base, counties)
        else:
            signal, source = _reduction_signal(base_adults, red_adults, base, counties)

        implied = base.astype(float) * signal
        reduction_total = int(round(float(implied.sum())))
        reductions = _bounded_integer_allocate(implied, base, reduction_total)
        scenario = base - reductions

        out[f"BASE_COHORT_{cohort}"] = base
        out[f"REDUCTION_SIGNAL_{cohort}"] = signal
        out[f"REDUCTION_SIGNAL_SOURCE_{cohort}"] = source
        out[f"REDUCTION_COHORT_{cohort}"] = reductions
        out[f"SCENARIO_COHORT_{cohort}"] = scenario
        out[f"REDUCTION_PCT_COHORT_{cohort}"] = np.where(
            base > 0,
            100.0 * reductions / base,
            0.0,
        )

        if int(reductions.sum()) != reduction_total:
            raise AssertionError(f"adult-driven reduction failed for {cohort}")
        if not np.array_equal(base - reductions, scenario):
            raise AssertionError(f"baseline-minus-reduction failed for {cohort}")

    base_cols = [f"BASE_COHORT_{c}" for c in FINAL_21_COHORTS]
    reduction_cols = [f"REDUCTION_COHORT_{c}" for c in FINAL_21_COHORTS]
    scenario_cols = [f"SCENARIO_COHORT_{c}" for c in FINAL_21_COHORTS]
    out["BASE_GOBLIN_21_CATTLE_TOTAL"] = out[base_cols].sum(axis=1)
    out["REDUCTION_GOBLIN_21_CATTLE_TOTAL"] = out[reduction_cols].sum(axis=1)
    out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] = out[scenario_cols].sum(axis=1)
    if not np.array_equal(
        out["BASE_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64)
        - out["REDUCTION_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64),
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"].to_numpy(dtype=np.int64),
    ):
        raise AssertionError("21-cohort cattle identity failed")
    return out


def _add_sheep_response(frame: pd.DataFrame) -> pd.DataFrame:
    """Preserve each ED's ten-cohort sheep structure under the sheep reduction."""

    out = frame.copy()
    base_total = _integer_array(out, "BASE_TOTAL_SHEEP")
    reduction_total = _integer_array(out, "REDUCTION_TOTAL_SHEEP")
    scenario_total = _integer_array(out, "SCENARIO_TOTAL_SHEEP")
    base_cohorts = {cohort: _integer_array(out, cohort) for cohort in GOBLIN_SHEEP_10}

    reconstructed = np.sum(np.vstack(list(base_cohorts.values())), axis=0)
    if not np.array_equal(reconstructed, base_total):
        raise AssertionError("baseline ten sheep cohorts do not close to TOTAL_SHEEP")

    reductions = {cohort: np.zeros(len(out), dtype=np.int64) for cohort in GOBLIN_SHEEP_10}
    scenarios = {cohort: np.zeros(len(out), dtype=np.int64) for cohort in GOBLIN_SHEEP_10}

    for i in range(len(out)):
        base = np.array([base_cohorts[c][i] for c in GOBLIN_SHEEP_10], dtype=np.int64)
        cut = _bounded_integer_allocate(base.astype(float), base, int(reduction_total[i]))
        scenario = base - cut
        if int(scenario.sum()) != int(scenario_total[i]):
            raise AssertionError("ten-cohort sheep scenario failed ED closure")
        for j, cohort in enumerate(GOBLIN_SHEEP_10):
            reductions[cohort][i] = cut[j]
            scenarios[cohort][i] = scenario[j]

    for cohort in GOBLIN_SHEEP_10:
        out[f"BASE_SHEEP_COHORT_{cohort}"] = base_cohorts[cohort]
        out[f"REDUCTION_SHEEP_COHORT_{cohort}"] = reductions[cohort]
        out[f"SCENARIO_SHEEP_COHORT_{cohort}"] = scenarios[cohort]

    base_cols = [f"BASE_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
    reduction_cols = [f"REDUCTION_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
    scenario_cols = [f"SCENARIO_SHEEP_COHORT_{c}" for c in GOBLIN_SHEEP_10]
    out["BASE_GOBLIN_10_SHEEP_TOTAL"] = out[base_cols].sum(axis=1)
    out["REDUCTION_GOBLIN_10_SHEEP_TOTAL"] = out[reduction_cols].sum(axis=1)
    out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"] = out[scenario_cols].sum(axis=1)
    return out


def build_net_zero_livestock_scenario(
    panel: pd.DataFrame,
    definition: NetZeroScenarioDefinition,
    *,
    expected_eds: int | None = None,
    include_standard_output: bool = True,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Build one complete baseline-relative net-zero ED livestock endpoint.

    Changing only ``definition`` changes the scenario. The validated baseline
    itself remains unchanged. Standard Output is optional and strictly
    downstream of the physical livestock solution.
    """

    out = _adult_scenario(panel, definition, expected_eds=expected_eds)
    out = _add_cattle_response(out)
    out = _add_sheep_response(out)

    out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_21_CATTLE_TOTAL"] + out["BASE_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["SCENARIO_GOBLIN_21_CATTLE_TOTAL"] + out["SCENARIO_GOBLIN_10_SHEEP_TOTAL"]
    )
    out["REDUCTION_GOBLIN_31_LIVESTOCK_TOTAL"] = (
        out["BASE_GOBLIN_31_LIVESTOCK_TOTAL"]
        - out["SCENARIO_GOBLIN_31_LIVESTOCK_TOTAL"]
    )

    if include_standard_output:
        out = add_pathway_standard_output(
            out,
            mapping_path=mapping_path,
            coefficient_path=coefficient_path,
        )
    return out


def run_net_zero_scenario(
    panel: pd.DataFrame,
    *,
    baseline_year: int,
    target_year: int,
    dairy_reduction: float,
    suckler_reduction: float,
    sheep_reduction: float,
    expected_eds: int | None = None,
    include_standard_output: bool = True,
    mapping_path: str | None = None,
    coefficient_path: str | None = None,
) -> pd.DataFrame:
    """Convenience interface: edit the scenario numbers and rerun."""

    definition = NetZeroScenarioDefinition(
        baseline_year=baseline_year,
        target_year=target_year,
        dairy_reduction=dairy_reduction,
        suckler_reduction=suckler_reduction,
        sheep_reduction=sheep_reduction,
    )
    return build_net_zero_livestock_scenario(
        panel,
        definition,
        expected_eds=expected_eds,
        include_standard_output=include_standard_output,
        mapping_path=mapping_path,
        coefficient_path=coefficient_path,
    )
