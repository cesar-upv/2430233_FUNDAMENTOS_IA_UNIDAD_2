from typing import Any

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QTabWidget

from evolutionary_lab.presentation.windows.main_window import MainWindow


def load_run(window: MainWindow) -> None:
    window.parameters.generation_limit.setValue(5)
    window.simulation.start_button.click()
    for _ in range(300):
        if not window.simulation.controller.is_running:
            break
        QTest.qWait(10)
    assert not window.simulation.controller.is_running
    assert len(window.simulation.history) == 6


def ranges(graph: Any) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(axis) for axis in graph.getViewBox().viewRange())


def wheel(graph: Any, position: QPoint) -> None:
    viewport = graph.viewport()
    event = QWheelEvent(
        QPointF(position),
        QPointF(viewport.mapToGlobal(position)),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(viewport, event)


@pytest.mark.parametrize("chart", ["population", "fitness", "diversity"])
def test_wheel_drag_restore_and_replay_keep_correct_view(
    window: MainWindow, chart: str
) -> None:
    load_run(window)
    workspace = window.simulation
    tabs = window.workspaces.widget(0)
    assert isinstance(tabs, QTabWidget)
    if chart == "population":
        graph, button = workspace.plot.graph, workspace.plot.header.reset_button
    else:
        tabs.setCurrentIndex(1)
        graph = getattr(window.statistics, f"{chart}_graph")
        button = getattr(window.statistics, f"{chart}_header").reset_button
    QTest.qWait(30)
    saved_history = tuple(workspace.history)
    baseline = ranges(graph)
    for name in ("bottom", "left"):
        axis_item = graph.getAxis(name)
        assert axis_item.autoSIPrefixScale * axis_item.scale == 1.0
    assert graph.getViewBox().mouseEnabled() == [False, False]
    center = graph.mapFromScene(graph.getViewBox().sceneBoundingRect().center())
    axis = graph.mapFromScene(graph.getAxis("left").sceneBoundingRect().center())
    wheel(graph, center)
    wheel(graph, axis)
    for mouse_button in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
        destination = center + QPoint(20, 15)
        QTest.mousePress(graph.viewport(), mouse_button, pos=center)
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(destination),
            QPointF(graph.viewport().mapToGlobal(destination)),
            Qt.MouseButton.NoButton,
            mouse_button,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(graph.viewport(), move)
        QTest.mouseRelease(graph.viewport(), mouse_button, pos=destination)
    QTest.qWait(20)
    assert ranges(graph) == baseline
    graph.setXRange(5, 6, padding=0)
    graph.setYRange(10, 20, padding=0)
    button.click()
    assert ranges(graph) == baseline
    workspace.toggle_playback()
    workspace.replay_timer.timeout.emit()
    workspace.stop_playback()
    assert workspace.current_index == 1
    assert ranges(graph) == baseline
    assert tuple(workspace.history) == saved_history


def test_summaries_and_external_legends_follow_real_snapshot_across_themes(
    window: MainWindow,
) -> None:
    load_run(window)
    workspace = window.simulation
    workspace.seek(3)
    snapshot = workspace.history[3]
    for appearance in (1, 2):
        window.appearance.setCurrentIndex(appearance)
        for graph in (
            window.statistics.fitness_graph,
            window.statistics.diversity_graph,
        ):
            axis = graph.getAxis("bottom")
            scale = axis.autoSIPrefixScale * axis.scale
            assert axis.tickStrings([0, 100], scale, 20) == ["0", "100"]
        for summary in (workspace.metrics, window.statistics.metrics):
            assert summary.values["generation"].text() == "3"
            assert float(summary.values["best"].text()) == pytest.approx(
                snapshot.statistics.objective_max, abs=1e-6
            )
            assert float(summary.values["mean"].text()) == pytest.approx(
                snapshot.statistics.objective_mean, abs=1e-6
            )
            assert float(summary.values["best_so_far"].text()) == pytest.approx(
                snapshot.best_so_far.objective_value, abs=1e-6
            )
            assert float(summary.values["diversity"].text()) == pytest.approx(
                snapshot.statistics.mean_normalized_hamming_distance, abs=1e-6
            )
        assert (
            workspace.plot.legend.geometry().top()
            > workspace.plot.graph.geometry().bottom()
        )
        assert window.statistics.fitness_graph.plotItem.legend is None
    section_titles = [
        label.text()
        for label in window.parameters.findChildren(QLabel, "parameterSectionTitle")
    ]
    assert section_titles == [
        "Problema",
        "Población",
        "Operadores genéticos",
        "Ejecución",
    ]


def test_buttons_distinguish_idle_playing_paused_and_empty_history(
    window: MainWindow,
) -> None:
    workspace = window.simulation
    assert workspace.start_button.isEnabled()
    assert not any(
        button.isEnabled()
        for button in (
            workspace.cancel_button,
            workspace.reset_button,
            workspace.play_button,
            workspace.stop_button,
            workspace.previous_button,
            workspace.next_button,
        )
    )
    load_run(window)
    assert workspace.reset_button.isEnabled() and workspace.previous_button.isEnabled()
    assert (
        not workspace.next_button.isEnabled()
        and not workspace.cancel_button.isEnabled()
    )
    workspace.play_button.click()
    assert workspace.play_button.isChecked() and workspace.stop_button.isEnabled()
    workspace.play_button.click()
    assert not workspace.play_button.isChecked()
    assert workspace.play_button.text() == "Reanudar"
    assert workspace.stop_button.isEnabled()
    workspace.stop_button.click()
    assert (
        workspace.play_button.text() == "Reproducir"
        and not workspace.stop_button.isEnabled()
    )
    workspace.reset_button.click()
    assert not workspace.reset_button.isEnabled()
    assert workspace.metrics.isHidden() and window.statistics.metrics.isHidden()
    window.parameters.seed.setText("no es entero")
    workspace.start_button.click()
    assert workspace.error_label.isVisible() and workspace.reset_button.isEnabled()
    workspace.reset_button.click()
    assert (
        not workspace.error_label.isVisible() and not workspace.reset_button.isEnabled()
    )
