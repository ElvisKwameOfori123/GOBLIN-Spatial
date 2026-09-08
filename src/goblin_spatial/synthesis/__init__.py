"""Scientific cross-run synthesis for frozen GOBLIN-Spatial outputs.

This layer may compare already-validated model runs, but it does not rerun
Baseline, SC1, SC2, SC3, or alter their scientific mathematics.
"""

from goblin_spatial.synthesis.sc1_crossrun import (
    Sc1CrossRunSynthesis,
    Sc1FrozenRun,
    build_sc1_crossrun_synthesis,
    discover_sc1_runs,
    load_sc1_ensemble,
)

__all__ = [
    "Sc1CrossRunSynthesis",
    "Sc1FrozenRun",
    "build_sc1_crossrun_synthesis",
    "discover_sc1_runs",
    "load_sc1_ensemble",
]
