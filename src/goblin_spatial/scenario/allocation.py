"""Integer allocation helper for the principal cohort-response engine.

The former generic fractional scenario allocator has been retired. Production
SC1 uses absolute GOBLIN endpoints through ``endpoint_allocation`` and
``principal_allocation``. This module remains only as the small bounded integer
utility required by the validated cohort-response logic.
"""

from __future__ import annotations

import numpy as np

from goblin_spatial.scenario.integer_allocation import bounded_integer_allocate


# Private compatibility name used by cohort_response. Keeping the alias avoids
# changing the validated cohort-response mathematics while removing the stale
# generic scenario implementation that previously occupied this module.
def _bounded_integer_allocate(
    weights: np.ndarray,
    capacities: np.ndarray,
    target: int,
) -> np.ndarray:
    return bounded_integer_allocate(weights, capacities, target)


__all__ = ["bounded_integer_allocate"]
