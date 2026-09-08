"""Presentation metadata for GOBLIN-Spatial result metrics.

The registry deliberately contains no scientific formulas.  It standardises
labels, units and visual semantics so the same model metric is described
consistently across tables, maps and charts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class MetricSpec:
    label: str
    unit: str
    family: str
    stage: str
    scale: str = "sequential"
    midpoint: float | None = None
    description: str = ""


METRICS: Mapping[str, MetricSpec] = {
    "TOTAL_CATTLE_REDUCTION_PCT_OF_BASE": MetricSpec(
        label="Total cattle reduction",
        unit="% of baseline cattle",
        family="transition_incidence",
        stage="SC1",
        description="Physical livestock transition incidence relative to the ED baseline.",
    ),
    "SO_LIVESTOCK_GROSS_LOSS_PCT_OF_BASE": MetricSpec(
        label="Livestock production-value exposure",
        unit="% of baseline livestock Standard Output",
        family="production_value_exposure",
        stage="SC1",
        description="Exposure of fixed-2020 livestock Standard Output; not farm income or profit.",
    ),
    "SO_LIVESTOCK_GROSS_LOSS_PER_HOLDING_2020_EUR": MetricSpec(
        label="Livestock production-value exposure per holding",
        unit="EUR per 2020 holding",
        family="production_value_exposure",
        stage="SC1",
        description="Gross fixed-2020 livestock Standard Output loss divided by 2020 holdings.",
    ),
    "GOBLIN_RELEASED_GRASSLAND_HA": MetricSpec(
        label="Released livestock grassland",
        unit="ha",
        family="released_transition_space",
        stage="SC1",
        description="Authoritative livestock-land release inherited from the same GOBLIN pathway and spatialised in SC1.",
    ),
    "GOBLIN_RELEASED_GRASSLAND_PCT_OF_BASE": MetricSpec(
        label="Released livestock grassland",
        unit="% of baseline grassland",
        family="released_transition_space",
        stage="SC1",
        description="Authoritative released livestock grassland relative to the ED baseline grassland resource.",
    ),
    "ROBUST_MIN_CATTLE_REDUCTION_PCT": MetricSpec(
        label="Robust minimum cattle exposure",
        unit="% of baseline cattle",
        family="robust_exposure",
        stage="SC1 synthesis",
        description="Minimum cattle-reduction exposure across the supplied pathway and implementation ensemble.",
    ),
    "ROBUST_MIN_SO_LOSS_PCT": MetricSpec(
        label="Robust minimum production-value exposure",
        unit="% of baseline livestock Standard Output",
        family="robust_exposure",
        stage="SC1 synthesis",
        description="Minimum production-value exposure across the supplied pathway and implementation ensemble.",
    ),
}


def get_metric_spec(metric: str) -> MetricSpec:
    """Return presentation metadata for a registered model metric."""
    try:
        return METRICS[metric]
    except KeyError as exc:
        raise KeyError(f"Unregistered reporting metric: {metric}") from exc
