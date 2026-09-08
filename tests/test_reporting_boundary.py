from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_REPORTING_IMPORTS = (
    "goblin_spatial.scenario.principal_endpoint",
    "goblin_spatial.scenario.principal_allocation",
    "goblin_spatial.pressure.national_release",
    "goblin_spatial.land.sc3_colm_allocation",
    "goblin_spatial.land.sc3_feasible_geographies",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_reporting_package_cannot_import_model_mutation_or_solver_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    reporting = root / "src" / "goblin_spatial" / "reporting"
    hits: list[str] = []
    for path in sorted(reporting.rglob("*.py")):
        imported = _imports(path)
        for forbidden in FORBIDDEN_REPORTING_IMPORTS:
            if any(name == forbidden or name.startswith(forbidden + ".") for name in imported):
                hits.append(f"{path.relative_to(root)} imports {forbidden}")
    assert not hits, "reporting crossed the frozen-model boundary:\n" + "\n".join(hits)
