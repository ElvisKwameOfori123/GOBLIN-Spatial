"""Historical baseline interface for GOBLIN-Spatial v1.

The historical baseline is complete after cattle, sheep, livestock merge, land
and farm-structure enrichment, clean validation/export, fixed-2020 Standard
Output, and frozen ED cohort signatures. Spatial soil and LPIS evidence enter
only after a scenario has completed SC1 and advances to SC2.
"""

from .cattle import build_cattle_baseline
from .land_farm_structure import add_land_farm_structure
from .merge import merge_livestock
from .sheep import build_sheep_baseline
from .signatures import build_signatures
from .standard_output import add_standard_output

__all__ = [
    "build_cattle_baseline",
    "build_sheep_baseline",
    "merge_livestock",
    "add_land_farm_structure",
    "add_standard_output",
    "build_signatures",
]
