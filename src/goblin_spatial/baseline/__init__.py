"""Historical baseline interface for GOBLIN-Spatial v1.

The historical baseline is complete after cattle, sheep, livestock merge,
land and farm-structure/SE enrichment, clean validation/export, fixed-2020
Standard Output (Stage 08), and frozen ED cohort signatures (Stage 09).

Agricultural soil capability (08B) and mapped physical soil (08C) are not part
of the historical reconstruction. They are downstream spatial context layers
used when preparing the completed baseline for scenario analysis.
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
