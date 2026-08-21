"""Definitions for the supported principal SC1 allocation experiment."""

from __future__ import annotations

from enum import Enum


class AllocationRule(str, Enum):
    """Validated rules for distributing a fixed national adult-cattle change."""

    PRORATA = "PRORATA"
    DAIRY_PROTECTION = "DAIRY_PROTECTION"
    ECONOMIC_CAPACITY_PROTECTION = "ECONOMIC_CAPACITY_PROTECTION"
    SOCIAL_VULNERABILITY_PROTECTION = "SOCIAL_VULNERABILITY_PROTECTION"


__all__ = ["AllocationRule"]
