"""Human-edible protein reference metrics.

This module provides small, transparent accounting helpers for protein-security
metrics used in Irish agricultural systems research.

It deliberately does not create new GOBLIN-Spatial baseline quantities. The
functions operate only on protein flows supplied by the caller.

References
----------
Henn et al. (2026), Circularity measures enhance resilience of net zero
pathways for agriculture, Communications Earth & Environment 7, 772.
Hennessy et al. (2021), The net contribution of livestock to the supply of
human edible protein: the case of Ireland, Journal of Agricultural Science
159, 463-471.
"""

from __future__ import annotations


def net_human_edible_protein_production(
    *,
    human_food_protein_kt: float,
    export_human_edible_protein_kt: float,
    import_human_edible_protein_kt: float,
) -> float:
    """Return net human-edible protein production in kt protein.

    Henn et al. (2026) interpret a positive balance as a situation in which
    more human-edible protein is utilised as food and exports than is imported.

    Parameters are kept explicit so callers must provide already harmonised
    human-edible protein flows. This function does not infer edible fractions,
    digestibility, protein quality, trade origin, or spatial allocation.

    Formula
    -------
    food + exports - imports
    """
    return (
        float(human_food_protein_kt)
        + float(export_human_edible_protein_kt)
        - float(import_human_edible_protein_kt)
    )


def net_export_human_edible_protein(
    *,
    export_human_edible_protein_kt: float,
    import_human_edible_protein_kt: float,
) -> float:
    """Return the net trade contribution of human-edible protein in kt."""
    return float(export_human_edible_protein_kt) - float(import_human_edible_protein_kt)


def edible_protein_conversion_ratio(
    *,
    human_digestible_protein_feed: float,
    human_digestible_protein_output: float,
) -> float:
    """Return the edible protein conversion ratio (EPCR).

    EPCR = human-digestible protein in feed / human-digestible protein in
    livestock products. Following Hennessy et al. (2021), values below 1 imply
    that the livestock system produces more human-digestible protein than it
    consumes in human-edible feed.

    Units cancel, but numerator and denominator must use the same unit.
    """
    output = float(human_digestible_protein_output)
    if output <= 0:
        raise ValueError("human_digestible_protein_output must be > 0")
    feed = float(human_digestible_protein_feed)
    if feed < 0:
        raise ValueError("human_digestible_protein_feed must be >= 0")
    return feed / output


def land_use_ratio(
    *,
    potential_crop_human_digestible_protein: float,
    livestock_human_digestible_protein_output: float,
) -> float:
    """Return the land-use ratio (LUR) of Hennessy et al. (2021).

    LUR = potential human-digestible protein from crops on the land used for
    livestock feed / human-digestible protein produced by livestock.

    Values below 1 indicate that livestock produces more human-digestible
    protein than the crop opportunity on that land.
    """
    output = float(livestock_human_digestible_protein_output)
    if output <= 0:
        raise ValueError("livestock_human_digestible_protein_output must be > 0")
    potential = float(potential_crop_human_digestible_protein)
    if potential < 0:
        raise ValueError("potential_crop_human_digestible_protein must be >= 0")
    return potential / output
