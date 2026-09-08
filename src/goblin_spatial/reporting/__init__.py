"""Downstream reporting interfaces for frozen GOBLIN-Spatial results.

Reporting code may read and format validated outputs, but must not recalculate
or mutate model science.
"""

from goblin_spatial.reporting.build import ReportDataBuild, build_report_data
from goblin_spatial.reporting.figure_data import export_figure_data
from goblin_spatial.reporting.geometry import join_ed_results, load_frozen_ed_geometry
from goblin_spatial.reporting.metric_registry import MetricSpec, get_metric_spec

__all__ = [
    "MetricSpec",
    "ReportDataBuild",
    "build_report_data",
    "export_figure_data",
    "get_metric_spec",
    "join_ed_results",
    "load_frozen_ed_geometry",
]
