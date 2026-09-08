"""Guard against reintroducing superseded land-runtime paths or documentation."""

from __future__ import annotations

from pathlib import Path


FORBIDDEN_RUNTIME_TOKENS = (
    "08B",
    "G1-G2-G3",
    "G1/G2/G3",
    "ED_Soil_Capability_08B",
    "GOBLIN_RELEASED_G1_HA",
    "GOBLIN_RELEASED_G2_HA",
    "GOBLIN_RELEASED_G3_HA",
    "GOBLIN_SOIL_G1_SHARE",
    "GOBLIN_SOIL_G2_SHARE",
    "GOBLIN_SOIL_G3_SHARE",
    "GOBLIN_RELEASE_08C_USED",
    "sc2_opportunity",
    "context_attach",
    "principal_context",
    "add_frozen_08b_context",
    "TILLAGE_STRICT",
    "WILLOW_WIDE",
    "REQUIRE_FOREST_YC",
)


def test_superseded_land_runtime_cannot_reenter_live_v1_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    live_files = [
        *sorted((root / "src" / "goblin_spatial").rglob("*.py")),
        *sorted((root / "docs").rglob("*.md")),
        root / "README.md",
        root / "configs" / "ireland_2015_2025.yaml",
        root / "data" / "README.md",
        root / "data" / "controls" / "land" / "ED_Land_Context_2020" / "README.md",
    ]

    hits: list[str] = []
    for path in live_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_RUNTIME_TOKENS:
            if token in text:
                hits.append(f"{path.relative_to(root)}: {token}")

    assert not hits, "superseded land-runtime breadcrumb(s) found:\n" + "\n".join(hits)
