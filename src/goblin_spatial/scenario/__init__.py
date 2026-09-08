"""Supported public scenario API for GOBLIN-Spatial.

The production framework is deliberately narrow:

1. read editable national GOBLIN controls;
2. allocate adult dairy and suckler endpoints across EDs;
3. propagate the 21 cattle cohorts while preserving ED signatures;
4. keep sheep fixed in the current principal cattle transition;
5. reconcile exactly to national livestock controls;
6. spatialise authoritative released land from solved livestock/pasture-DM
   transition pressure, bounded only by ``ALL_GRASSLAND``;
7. pass the frozen SC1 result to SC2/SC3 for physical-resource context,
   evidence-backed eligibility and finite-resource allocation.

Superseded generic pathway, sequential, net-zero and cattle-study interfaces are
not part of the supported runtime API. Reconstruction utilities remain separate
from the principal scenario chain.
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
