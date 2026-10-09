"""Canonical biological baseline contract for GOBLIN-Spatial.

The historical model has two authoritative livestock representations on the
same YEAR x CSOED backbone:

1. CSO-13: the statistical input state (9 cattle + 4 sheep groups).
2. GOBLIN-31: the biological expansion (21 cattle + 10 sheep cohorts).

All later land, Standard Output, signature, catchment and optional synthesis
layers must consume these products downstream and must not redefine them.
"""

from __future__ import annotations

from dataclasses import dataclass

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.export.livestock_panels import (
    CSO_13,
    CSO_CATTLE_9,
    CSO_SHEEP_4,
    COHORTS_31,
)
from goblin_spatial.sheep.cohorts import GOBLIN_SHEEP_10

BASELINE_BACKBONE = ("YEAR", "CSOED")
CSO_13_NAME = "CSO_13_Cohort_Annual_Panel_2015_2025"
GOBLIN_31_NAME = "GOBLIN_31_Cohort_Annual_Panel_2015_2025"

BASELINE_SEQUENCE = (
    "CSO_13",
    "GOBLIN_31",
    "LAND_FARM_STRUCTURE",
    "STANDARD_OUTPUT",
    "MULTISCALE_REPORTING",
    "SYNTHESIS_REFERENCE_LAYERS",
)


@dataclass(frozen=True)
class BaselineContract:
    cso13: tuple[str, ...]
    cso_cattle9: tuple[str, ...]
    cso_sheep4: tuple[str, ...]
    goblin31: tuple[str, ...]
    goblin_cattle21: tuple[str, ...]
    goblin_sheep10: tuple[str, ...]


CANONICAL_BASELINE = BaselineContract(
    cso13=tuple(CSO_13),
    cso_cattle9=tuple(CSO_CATTLE_9),
    cso_sheep4=tuple(CSO_SHEEP_4),
    goblin31=tuple(COHORTS_31),
    goblin_cattle21=tuple(FINAL_21_COHORTS),
    goblin_sheep10=tuple(GOBLIN_SHEEP_10),
)


def validate_baseline_contract() -> None:
    """Fail loudly if the canonical biological input contract drifts."""
    if len(CANONICAL_BASELINE.cso13) != 13:
        raise AssertionError("CSO-13 must contain exactly 13 groups")
    if len(CANONICAL_BASELINE.cso_cattle9) != 9:
        raise AssertionError("CSO-13 cattle component must contain 9 groups")
    if len(CANONICAL_BASELINE.cso_sheep4) != 4:
        raise AssertionError("CSO-13 sheep component must contain 4 groups")
    if len(CANONICAL_BASELINE.goblin31) != 31:
        raise AssertionError("GOBLIN-31 must contain exactly 31 cohorts")
    if len(CANONICAL_BASELINE.goblin_cattle21) != 21:
        raise AssertionError("GOBLIN-31 cattle component must contain 21 cohorts")
    if len(CANONICAL_BASELINE.goblin_sheep10) != 10:
        raise AssertionError("GOBLIN-31 sheep component must contain 10 cohorts")
    if tuple(CANONICAL_BASELINE.goblin_cattle21 + CANONICAL_BASELINE.goblin_sheep10) != CANONICAL_BASELINE.goblin31:
        raise AssertionError("GOBLIN-31 ordering differs from 21 cattle + 10 sheep contract")


validate_baseline_contract()
