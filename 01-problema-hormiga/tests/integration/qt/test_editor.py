"""Behaviour of the Qt editor: cells, edits, drags, generation and layering.

Everything here is asserted through the editor, the scenario it holds and the cells the scene
reports, never through colours, item counts or pixels.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.generation.scenario_generator import GenerationRequest
from ant_pathfinding.presentation.qt.editor import (
    MIN_SIDE,
    EditTool,
    ScenarioEditor,
    starter_scenario,
)
from ant_pathfinding.presentation.qt.main_window import MainWindow

_PRESENTATION_ROOT = Path("src/ant_pathfinding/presentation/qt")
_LAYER_DENIED_ROOTS = (
    "ant_pathfinding.application",
    "ant_pathfinding.persistence",
)
"""Presentation sits above the application layer, so it may not import either of these.

Importing ``search`` is the point of the search panel: the widgets drive the engine's
incremental ``step()`` and consume its reported progress, and no search logic moves down here.
"""


@pytest.fixture
def window(qtbot: pytest.QtBot) -> MainWindow:
    """A shown window, so the view maps scene positions the way a user sees them."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    return main_window


def _press_at(qtbot: pytest.QtBot, window: MainWindow, position: Position) -> None:
    """Press the left button over the centre of ``position``, as a user click would."""
    point = window.view.mapFromScene(window.scene.cell_rect(position).center())
    qtbot.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)


def _release_at(qtbot: pytest.QtBot, window: MainWindow, position: Position) -> None:
    point = window.view.mapFromScene(window.scene.cell_rect(position).center())
    qtbot.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)


def test_the_window_builds_a_grid_and_closes_cleanly(window: MainWindow) -> None:
    assert window.scene.cell_count == 10 * 10
    assert (window.editor.scenario.grid.width, window.editor.scenario.grid.height) == (10, 10)

    window.close()

    assert not window.isVisible()


def test_a_grid_preset_resizes_the_grid(window: MainWindow) -> None:
    index = next(
        position
        for position in range(window.preset_combo.count())
        if window.preset_combo.itemData(position) == 20
    )

    window.preset_combo.setCurrentIndex(index)

    assert window.scene.cell_count == 20 * 20
    assert window.editor.scenario.grid.width == 20


def test_a_custom_grid_size_is_clamped_to_the_minimum(window: MainWindow) -> None:
    window.rows_spin.setValue(3)
    window.columns_spin.setValue(3)

    assert (window.editor.scenario.grid.height, window.editor.scenario.grid.width) == (
        MIN_SIDE,
        MIN_SIDE,
    )
    assert window.scene.cell_count == MIN_SIDE * MIN_SIDE


def test_placing_start_goal_and_food_builds_the_scenario() -> None:
    editor = ScenarioEditor(starter_scenario(8, 8))

    assert editor.edit(EditTool.START, Position(1, 1))
    assert editor.edit(EditTool.GOAL, Position(6, 6))
    assert editor.edit(EditTool.FOOD, Position(2, 2))
    assert editor.edit(EditTool.FOOD, Position(3, 3))

    scenario = editor.scenario
    assert scenario.start == Position(1, 1)
    assert scenario.goal == Position(6, 6)
    assert scenario.foods == {Position(2, 2), Position(3, 3), Position(4, 4)}


def test_food_cannot_be_placed_on_a_blocked_cell() -> None:
    editor = ScenarioEditor(starter_scenario(8, 8))
    editor.edit(EditTool.OBSTACLE, Position(2, 2))

    assert not editor.edit(EditTool.FOOD, Position(2, 2))

    assert Position(2, 2) not in editor.scenario.foods
    assert Position(2, 2) in editor.scenario.grid.blocked


def test_the_ant_and_the_goal_cannot_be_left_blocked() -> None:
    """Whatever the repair policy, the scenario stays valid after painting over ant or goal."""
    editor = ScenarioEditor(starter_scenario(8, 8))
    scenario = editor.scenario

    editor.edit(EditTool.OBSTACLE, scenario.start)
    editor.edit(EditTool.OBSTACLE, scenario.goal)

    edited = editor.scenario
    assert AntScenario(edited.grid, edited.start, edited.goal, edited.foods) == edited
    assert edited.grid.is_walkable(edited.start)
    assert edited.grid.is_walkable(edited.goal)


def test_a_click_maps_to_the_cell_containing_it(window: MainWindow) -> None:
    cell = window.scene.cell_size

    assert window.scene.position_at(QPointF(3 * cell + 7, 2 * cell + 19)) == Position(3, 2)
    assert window.scene.position_at(QPointF(-4, -4)) is None
    assert window.scene.position_at(QPointF(10.5 * cell, 4 * cell)) is None


def test_dragging_moves_the_element_under_the_pointer(
    qtbot: pytest.QtBot, window: MainWindow
) -> None:
    window.editor.tool = EditTool.SELECT
    ant = window.editor.scenario.start
    goal = window.editor.scenario.goal

    _press_at(qtbot, window, goal)
    _release_at(qtbot, window, Position(1, 1))
    _press_at(qtbot, window, ant)
    _release_at(qtbot, window, Position(7, 7))

    assert (window.editor.scenario.goal, window.editor.scenario.start) == (
        Position(1, 1),
        Position(7, 7),
    )


def test_generate_fills_a_valid_scenario_for_a_fixed_seed(window: MainWindow) -> None:
    window.rows_spin.setValue(10)
    window.columns_spin.setValue(10)
    window.foods_spin.setValue(3)
    window.seed_spin.setValue(7)

    window.generate_button.click()

    scenario = window.editor.scenario
    assert (scenario.grid.width, scenario.grid.height) == (10, 10)
    assert len(scenario.foods) == 3
    assert scenario.grid.blocked
    assert window.scene.cell_count == 10 * 10


def test_a_generation_too_large_to_search_is_refused(window: MainWindow) -> None:
    window.rows_spin.setValue(40)
    window.columns_spin.setValue(40)
    window.foods_spin.setValue(9)
    before = window.editor.scenario
    assert not window.statusBar().currentMessage()

    window.generate_button.click()

    assert window.editor.scenario == before
    assert window.statusBar().currentMessage()


def test_an_unsatisfiable_generation_request_is_reported(qtbot: pytest.QtBot) -> None:
    editor = ScenarioEditor(starter_scenario(8, 8))
    before = editor.scenario

    with qtbot.waitSignal(editor.statusMessage) as reported:
        assert not editor.generate(
            GenerationRequest(rows=1, columns=1, food_count=1, obstacle_ratio=0.0)
        )

    assert reported.args
    assert editor.scenario == before


def test_the_presentation_layer_imports_nothing_above_the_search_layer() -> None:
    """``AGENTS.md`` fixes presentation above application; the import graph is the evidence."""
    modules = sorted(_PRESENTATION_ROOT.glob("*.py"))
    assert modules, "no presentation modules were checked"

    offenders = {
        module.name: sorted(
            name for name in _imports(module) if name.startswith(_LAYER_DENIED_ROOTS)
        )
        for module in modules
    }
    offenders = {name: names for name, names in offenders.items() if names}

    assert not offenders, f"presentation modules importing above themselves: {offenders}"


def _imports(path: Path) -> set[str]:
    """Every module name imported by the file at ``path``, relative imports included."""
    tree = ast.parse(path.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or "" if node.level == 0 else "ant_pathfinding.presentation.qt"
            imported.add(base)
            imported.update(f"{base}.{alias.name}" for alias in node.names)
    return imported
