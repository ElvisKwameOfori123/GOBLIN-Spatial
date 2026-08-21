"""Public API for the principal GOBLIN-Spatial SC1 scenario workflow.

Older experimental pathway, sequential and net-zero modules remain internal for
provenance while the repository is finalised. They are intentionally not part of
the supported package surface. Production scenario execution starts from the
editable GOBLIN controls and ``run_principal_goblin_endpoint``.
"""

from goblin_spatial.scenario.control_table import (
    ScenarioControlSelection,
    active_scenario_ids,
    load_scenario_controls,
    read_scenario_control_table,
)
from goblin_spatial.scenario.definition import AllocationRule
from goblin_spatial.scenario.goblin_controls import (
    GoblinNationalMilestone,
    GoblinPathwayControls,
)
from goblin_spatial.scenario.metrics import (
    add_sc1_ed_metrics,
    build_sc1_county_summary,
    build_sc1_national_metrics,
    gini,
)
from goblin_spatial.scenario.comparison import (
    add_sc1_comparison_intensity,
    build_sc1_robust_exposure,
    compare_sc1_to_prorata,
    summarise_sc1_redistribution,
)
from goblin_spatial.scenario.national_cohort_targets import (
    derive_national_cohort_targets,
    load_goblin_cohort_reference,
)
from goblin_spatial.scenario.preflight import (
    assert_principal_ready,
    preflight_principal_inputs,
)
from goblin_spatial.scenario.principal_endpoint import run_principal_goblin_endpoint
from goblin_spatial.scenario.reconciliation import build_goblin_reconciliation

__all__ = [
    "AllocationRule",
    "GoblinNationalMilestone",
    "GoblinPathwayControls",
    "ScenarioControlSelection",
    "active_scenario_ids",
    "add_sc1_comparison_intensity",
    "add_sc1_ed_metrics",
    "assert_principal_ready",
    "build_goblin_reconciliation",
    "build_sc1_county_summary",
    "build_sc1_national_metrics",
    "build_sc1_robust_exposure",
    "compare_sc1_to_prorata",
    "derive_national_cohort_targets",
    "gini",
    "load_goblin_cohort_reference",
    "load_scenario_controls",
    "preflight_principal_inputs",
    "read_scenario_control_table",
    "run_principal_goblin_endpoint",
    "summarise_sc1_redistribution",
]
