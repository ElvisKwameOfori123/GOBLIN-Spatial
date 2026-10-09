"""Reference helpers for selected InformBio D2.1 bioresource factors.

This module is isolated from the validated historical baseline. InformBio is
used here as a composition/reference library, not as an authority for
GOBLIN-Spatial livestock manure arisings.
"""

from __future__ import annotations

import csv
from pathlib import Path

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "inputs"
    / "reference"
    / "informbio_bioresource_factors.csv"
)


def load_informbio_reference(path: str | Path | None = None) -> list[dict[str, str]]:
    source = Path(path) if path is not None else _DEFAULT_PATH
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def get_material_reference(
    material: str, path: str | Path | None = None
) -> dict[str, str]:
    matches = [
        row
        for row in load_informbio_reference(path)
        if row["material"].casefold() == material.casefold()
    ]
    if len(matches) != 1:
        raise KeyError(
            f"Expected exactly one InformBio material named {material!r}; "
            f"found {len(matches)}."
        )
    return matches[0]


def _as_float(value: str | None) -> float | None:
    return None if value in ("", None) else float(value)


def resource_content_from_dm(
    material: str,
    dry_matter_t: float,
    *,
    allow_restricted_reference: bool = False,
    path: str | Path | None = None,
) -> dict[str, float | str | None]:
    """Convert a dry-matter quantity to reference resource contents.

    This deliberately starts from dry matter. It does not infer dry matter
    from fresh manure/slurry because several D2.1 manure composition rows
    have unresolved reporting-basis/representativeness issues.
    """
    if dry_matter_t < 0:
        raise ValueError("dry_matter_t must be non-negative.")

    row = get_material_reference(material, path)
    status = row["use_status"]
    if status == "do_not_use_for_baseline" and not allow_restricted_reference:
        raise ValueError(
            f"{material!r} is retained as a reference-only InformBio row. "
            "Use allow_restricted_reference=True only for explicit sensitivity "
            "or provenance work, not baseline manure estimation."
        )

    def tonnes(column: str) -> float | None:
        frac = _as_float(row[column])
        return None if frac is None else dry_matter_t * frac

    gcv = _as_float(row["gross_calorific_value_mj_per_kg"])
    return {
        "material": row["material"],
        "category": row["category"],
        "dry_matter_t": float(dry_matter_t),
        "gross_energy_gj": None if gcv is None else dry_matter_t * gcv,
        "protein_t": tonnes("protein_fraction"),
        "carbon_t": tonnes("carbon_fraction"),
        "nitrogen_t": tonnes("nitrogen_fraction"),
        "phosphorus_t": tonnes("phosphorus_fraction"),
        "potassium_t": tonnes("potassium_fraction"),
        "use_status": status,
        "source_note": row["source_note"],
    }
