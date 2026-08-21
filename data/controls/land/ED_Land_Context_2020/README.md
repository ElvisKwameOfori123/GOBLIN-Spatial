# Frozen ED Land Context 2020

This directory is one logical 2,857-row runtime control. Its `part-*` files are repository-storage shards only and have no scientific meaning.

Normal GOBLIN-Spatial 2020 runs concatenate the shards into one ED table before use. The control combines validated 08B agricultural soil capability, independent 08C mapped physical soil, and neutral LPIS 2020 context.

The historical baseline remains authoritative for `ALL_GRASSLAND`, livestock and agricultural accounting. LPIS does not replace baseline grassland, 08C does not drive SC1 release, and the frozen control contains no SC1, SC2 or SC3 allocation result.

LPIS 2020 was recovered from the SI_SG SC2 full result and cross-checked against BE_SG and all four spatial allocation policies. Variables not represented by the 2020 LPIS source are deliberately absent rather than encoded as observed zeros.

Normal 2020 runtime requires no LPIS parcel download, soil-package download, shapefile download, GIS overlay or external data fetch. Heavy rebuild scripts remain optional provenance/reconstruction tools.

A 2025 LPIS-dependent SC2/SC3 run must fail until a validated 2025 snapshot is added.
