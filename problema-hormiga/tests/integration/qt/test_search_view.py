"""Behaviour of the search panel: the controls, one expansion per step, results and playback.

Everything is asserted through the panel's metrics and control states, never through colours,
item counts or pixels.
"""

from __future__ import annotations

import pytest

from ant_pathfinding.domain.position import Position
from ant_pathfinding.presentation.qt.editor import EditTool
from ant_pathfinding.presentation.qt.main_window import MainWindow
from ant_pathfinding.presentation.qt.search_view import SearchPanel
from ant_pathfinding.search.algorithms import SearchAlgorithm, solve


@pytest.fixture
def window(qtbot: pytest.QtBot) -> MainWindow:
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    return main_window


def _full_speed(panel: SearchPanel) -> None:
    """Select the widest burst, so one timer tick can finish the whole run."""
    panel.burst_combo.setCurrentIndex(panel.burst_combo.count() - 1)


def _food_steps_onto(panel: SearchPanel, window: MainWindow) -> None:
    """Walk the playback up to the first food on the path and leave it there."""
    path = solve(SearchAlgorithm.BFS, window.editor.scenario).path
    for _ in range(min(path.index(food) for food in window.editor.scenario.foods)):
        panel.playback_step_button.click()


def test_the_controls_start_idle(window: MainWindow) -> None:
    panel = window.search_panel

    assert panel.outcome_label.text() == "idle"
    assert panel.expanded_label.text() == "0"
    assert panel.run_button.isEnabled()
    assert panel.step_button.isEnabled()
    assert not panel.pause_button.isEnabled()
    assert not panel.stop_button.isEnabled()
    assert not panel.reset_button.isEnabled()
    assert not panel.play_button.isEnabled()
    assert not panel.playback_step_button.isEnabled()


def test_step_advances_exactly_one_expansion(window: MainWindow) -> None:
    panel = window.search_panel

    for expected in range(1, 6):
        panel.step_button.click()

        assert panel.expanded_label.text() == str(expected)


def test_running_pausing_and_resuming_continues_the_same_run(
    qtbot: pytest.QtBot, window: MainWindow
) -> None:
    panel = window.search_panel

    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.expanded_label.text() != "0")
    panel.pause_button.click()
    paused = panel.expanded_label.text()
    qtbot.wait(80)

    assert panel.outcome_label.text() == "held"
    assert panel.expanded_label.text() == paused

    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.expanded_label.text() != paused)

    assert int(panel.expanded_label.text()) > int(paused)


def test_stopping_leaves_no_result_and_resetting_returns_to_idle(
    qtbot: pytest.QtBot, window: MainWindow
) -> None:
    panel = window.search_panel

    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.expanded_label.text() != "0")
    panel.stop_button.click()

    assert panel.outcome_label.text() == "stopped"
    assert panel.cost_label.text() == "-"
    assert not panel.play_button.isEnabled()

    panel.reset_button.click()

    assert panel.outcome_label.text() == "idle"
    assert panel.expanded_label.text() == "0"
    assert not panel.reset_button.isEnabled()


def test_a_solvable_map_reports_the_found_cost_and_walks_onto_the_food(
    qtbot: pytest.QtBot, window: MainWindow
) -> None:
    panel = window.search_panel
    expected = solve(SearchAlgorithm.BFS, window.editor.scenario)
    total = len(window.editor.scenario.foods)

    _full_speed(panel)
    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.outcome_label.text() == "found")

    assert panel.cost_label.text() == str(expected.cost)
    assert panel.path_length_label.text() == str(len(expected.path))
    assert panel.foods_label.text() == f"0 / {total}"

    _food_steps_onto(panel, window)

    assert panel.foods_label.text() == f"1 / {total}"


def test_a_new_run_stops_an_in_flight_playback(qtbot: pytest.QtBot, window: MainWindow) -> None:
    """The gap between two playback ticks is wide enough to start a run inside it."""
    panel = window.search_panel

    _full_speed(panel)
    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.outcome_label.text() == "found")
    panel.play_button.click()

    panel.step_button.click()

    assert panel.play_button.text() == "Play"
    assert not panel.play_button.isChecked()


def test_a_walled_off_goal_reports_no_solution(qtbot: pytest.QtBot, window: MainWindow) -> None:
    panel = window.search_panel
    goal = window.editor.scenario.goal
    window.editor.edit(EditTool.OBSTACLE, Position(goal.x - 1, goal.y))
    window.editor.edit(EditTool.OBSTACLE, Position(goal.x, goal.y - 1))

    _full_speed(panel)
    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.outcome_label.text() == "no solution")

    assert panel.cost_label.text() == "0"
    assert panel.expanded_label.text() != "0"


@pytest.mark.parametrize("algorithm", list(SearchAlgorithm))
def test_every_algorithm_in_the_combo_runs_to_completion(
    qtbot: pytest.QtBot, window: MainWindow, algorithm: SearchAlgorithm
) -> None:
    panel = window.search_panel
    panel.algorithm_combo.setCurrentIndex(
        next(
            index
            for index in range(panel.algorithm_combo.count())
            if panel.algorithm_combo.itemData(index) == algorithm
        )
    )

    _full_speed(panel)
    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.outcome_label.text() == "found")

    assert panel.cost_label.text() == str(solve(algorithm, window.editor.scenario).cost)


def test_editing_the_map_mid_run_resets_the_run(qtbot: pytest.QtBot, window: MainWindow) -> None:
    panel = window.search_panel
    panel.run_button.click()
    qtbot.waitUntil(lambda: panel.expanded_label.text() != "0")

    window.editor.edit(EditTool.OBSTACLE, Position(0, 1))

    assert panel.outcome_label.text() == "idle"
    assert panel.expanded_label.text() == "0"
    assert not panel.reset_button.isEnabled()
