"""The dependency rules of the search layer, asserted rather than assumed.

``AGENTS.md`` fixes the shape of the layers: the domain must not know about Qt or the
presentation, the search layer must not import PySide6, and the progress vocabulary must not
depend on the engine that produces it. Those are properties of the import graph, so they are
checked against the import graph - the modules as they are on disk, read as source - rather than
left to a reviewer's eye.

Each rule is one loop over a list of files or modules rather than a parametrized case per file:
the files are the data, and a failure message names the one that broke the rule.
"""

import ast
import subprocess
import sys
from pathlib import Path

SOURCE_ROOT = Path("src/ant_pathfinding")
LAYER_MODULES = sorted(
    path
    for path in (
        *SOURCE_ROOT.joinpath("search").rglob("*.py"),
        *SOURCE_ROOT.joinpath("domain").rglob("*.py"),
    )
)
FORBIDDEN_ROOTS = (
    "PySide6",
    "PyQt5",
    "PyQt6",
    "ant_pathfinding.presentation",
    "ant_pathfinding.application",
)
"""Nothing in these two layers may name any of these: no Qt, nothing above the search layer."""


def _dotted_name(path: Path) -> str:
    """The module's real dotted name, derived from where it sits in the package."""
    parts = list(path.relative_to(SOURCE_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["ant_pathfinding", *parts])


def _imports(path: Path) -> set[str]:
    """Every module name imported by the file at ``path``, absolute and relative alike.

    A relative import is resolved against the importing module's own package, so
    ``from ..presentation.qt import Widget`` is reported as the presentation layer rather than
    as an unrecognisable ``.presentation.qt``: a forbidden import written relatively would
    otherwise slip past the rule it breaks.
    """
    tree = ast.parse(path.read_text())
    dotted = _dotted_name(path)
    package = dotted.split(".") if path.name == "__init__.py" else dotted.split(".")[:-1]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Level 1 is this module's own package, level 2 the one above it.
                base = ".".join(package[: len(package) - node.level + 1])
                base = f"{base}.{node.module}" if node.module else base
            else:
                base = node.module or ""
            imported.add(base)
            imported.update(f"{base}.{alias.name}" for alias in node.names)
    return imported


def test_the_search_and_domain_layers_import_nothing_above_themselves() -> None:
    """No Qt, no presentation, no application - checked on every module of both layers.

    The domain is the bottom of the dependency graph and the search layer sits directly on it, so
    a single import pointing upwards would invert the whole architecture.
    """
    offenders = {
        str(path): sorted(
            imported
            for imported in _imports(path)
            for root in FORBIDDEN_ROOTS
            if imported.split(".")[0] == root or imported.startswith(root)
        )
        for path in LAYER_MODULES
    }
    offenders = {path: names for path, names in offenders.items() if names}
    assert len(LAYER_MODULES) >= 12, f"only {len(LAYER_MODULES)} modules were checked"
    assert not offenders, f"modules importing above their layer: {offenders}"


def test_progress_does_not_import_the_engine() -> None:
    """``progress.py`` is a leaf: it may report on a state, never on a run.

    The dependency direction is ``runner -> progress -> state``. If progress reached back into the
    runner the progress vocabulary could no longer be read on its own, which is the whole reason
    it is a separate module.
    """
    imported = _imports(SOURCE_ROOT / "search" / "progress.py")

    assert "ant_pathfinding.search.runner" not in imported, "progress.py imports the runner"
    assert "runner" not in imported, "progress.py imports the runner by relative name"
    assert "ant_pathfinding.search.state" in imported, "progress.py should report on a state"


def test_the_three_algorithms_do_not_import_each_other() -> None:
    """Each entry point is written against the shared engine, never against a sibling.

    The three are the same loop with different settings, so an import between them would mean one
    of them had started depending on another's policy rather than on the engine.
    """
    modules = ["bfs", "dijkstra", "astar"]
    offenders = {
        module: sorted(set(_imports(SOURCE_ROOT / "search" / f"{module}.py")) & siblings)
        for module, siblings in (
            (
                module,
                {f"ant_pathfinding.search.{other}" for other in modules}
                - {f"ant_pathfinding.search.{module}"},
            )
            for module in modules
        )
    }
    offenders = {module: names for module, names in offenders.items() if names}
    assert not offenders, f"the algorithms import each other: {offenders}"


def test_the_search_package_init_exports_nothing() -> None:
    """``search/__init__.py`` is empty, so importing the package pulls in no module."""
    assert (SOURCE_ROOT / "search" / "__init__.py").read_text() == ""
    assert (SOURCE_ROOT / "domain" / "__init__.py").read_text() == ""


def test_the_heuristics_alias_does_not_import_the_runner() -> None:
    """A heuristic is a function of a scenario and a state; it knows nothing about a run.

    This is what lets an estimate be tested without starting a search, and what keeps the
    composition mechanism a plain function rather than an interface.
    """
    imported = _imports(SOURCE_ROOT / "search" / "heuristics" / "__init__.py")

    assert "ant_pathfinding.search.runner" not in imported, "the alias imports the runner"
    assert "ant_pathfinding.search.progress" not in imported, "the alias imports the progress types"
    assert "ant_pathfinding.search.heuristics.lower_bounds" in imported, "the alias is empty"


def test_no_suppression_was_introduced_in_the_package() -> None:
    """No ``type: ignore`` and no ``noqa`` hides a typing or lint problem in production code.

    ``AGENTS.md`` allows a suppression only with a real technical reason. A blanket check is the
    cheapest way to notice one appearing without anyone deciding to allow it.
    """
    offenders = [
        f"{path}:{number}"
        for path in SOURCE_ROOT.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if "type: ignore" in line or "noqa" in line
    ]

    assert not offenders, f"suppressions found in the package: {offenders}"


def test_the_package_imports_without_a_qt_application() -> None:
    """Importing the whole search layer must not need a display, a QApplication or Qt at all.

    Run in a subprocess so the check is on a clean interpreter: if a Qt import had already
    happened in this one, the assertion below would pass for the wrong reason.
    """
    modules = [
        "ant_pathfinding.domain.grid",
        "ant_pathfinding.domain.position",
        "ant_pathfinding.domain.scenario",
        "ant_pathfinding.search.algorithms",
        "ant_pathfinding.search.astar",
        "ant_pathfinding.search.bfs",
        "ant_pathfinding.search.dijkstra",
        "ant_pathfinding.search.heuristics",
        "ant_pathfinding.search.progress",
        "ant_pathfinding.search.result",
        "ant_pathfinding.search.runner",
        "ant_pathfinding.search.state",
    ]
    script = (
        "import sys\n"
        + "".join(f"import {module}\n" for module in modules)
        + "leaked = [name for name in sys.modules "
        + "if name.split('.')[0] in {'PySide6', 'PyQt5', 'PyQt6'}]\n"
        + "assert not leaked, f'Qt was imported: {leaked}'\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )

    assert completed.returncode == 0, completed.stderr
