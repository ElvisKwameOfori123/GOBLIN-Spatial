"""Spatialise category-resolved national livestock-land release across EDs.

The originating GOBLIN pathway remains authoritative for national hectares.
GOBLIN-Spatial supplies geography. This allocator is designed for pathway
controls such as Styles Table S3 where gross livestock-land release can be
resolved into dairy, beef and sheep components.

The three spatial signals deliberately differ:

* dairy release is allocated over the baseline dairy-system pasture footprint,
  because national dairy land can fall even when dairy cow numbers rise;
* beef release follows positive decline in suckler/BxB pasture pressure, with a
  baseline beef-footprint fallback if the decline signal is degenerate;
* sheep release is allocated over the baseline sheep pasture footprint when the
  pathway changes sheep land requirement without changing sheep head numbers.

These are transparent spatialisation proxies. They do not claim observed
parcel-level intensification or movement of particular hectares.
"""
