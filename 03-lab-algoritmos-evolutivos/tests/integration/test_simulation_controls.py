from dataclasses import replace
from threading import Event

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest

from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.presentation.simulation_workspace import demo_config
from evolutionary_lab.presentation.windows.main_window import MainWindow
from evolutionary_lab.problems.registry import PROJECT_01_F1


def wait_for_finish(window: MainWindow) -> None:
    for _ in range(500):
        if not window.simulation.controller.is_running:
            return
        QTest.qWait(10)
    pytest.fail("Worker did not finish")


def test_full_run_navigation_and_repeated_seed_are_real(window: MainWindow) -> None:
    workspace = window.simulation
    workspace.start_button.click()
    wait_for_finish(window)
    expected = run_evolution(demo_config(), PROJECT_01_F1)
    assert tuple(workspace.history) == expected.generations
    assert workspace.current_index == 100
    assert (
        workspace.generation_spin.maximum()
        == workspace.generation_slider.maximum()
        == 100
    )
    workspace.previous_button.click()
    assert workspace.snapshot == expected.generations[99]
    workspace.next_button.click()
    assert workspace.snapshot == expected.generations[100]
    workspace.generation_spin.setValue(42)
    assert workspace.snapshot == expected.generations[42]
    workspace.generation_slider.setValue(0)
    assert workspace.snapshot == expected.generations[0]
    workspace.start_button.click()
    wait_for_finish(window)
    assert tuple(workspace.history) == expected.generations


def test_replay_pause_resume_stop_never_recompute(window: MainWindow) -> None:
    workspace = window.simulation
    workspace.start_button.click()
    wait_for_finish(window)
    saved = tuple(workspace.history)
    workspace.play_button.click()
    assert workspace.replay_timer.isActive() and workspace.current_index == 0
    workspace.replay_timer.timeout.emit()
    assert workspace.current_index == 1
    workspace.play_button.click()
    assert not workspace.replay_timer.isActive()
    workspace.play_button.click()
    assert workspace.replay_timer.isActive()
    workspace.replay_timer.timeout.emit()
    assert workspace.current_index == 2
    workspace.stop_button.click()
    assert not workspace.replay_timer.isActive() and workspace.current_index == 2
    assert tuple(workspace.history) == saved and not workspace.controller.is_running
    workspace.seek(100)
    workspace.replay_timer.start()
    workspace.replay_timer.timeout.emit()
    assert not workspace.replay_timer.isActive()


@pytest.mark.parametrize("reset", [False, True])
def test_gui_stays_responsive_during_worker_cancellation_and_reset(
    window: MainWindow, reset: bool
) -> None:
    workspace = window.simulation
    entered, release = Event(), Event()

    def blocking_objective(point: tuple[float, ...]) -> float:
        if not entered.is_set():
            entered.set()
            assert release.wait(3)
        return PROJECT_01_F1.evaluate(point)

    workspace.problem = replace(PROJECT_01_F1, objective=blocking_objective)
    workspace.problem_provider = lambda: workspace.problem
    beats = []
    heartbeat = QTimer(window)
    heartbeat.timeout.connect(lambda: beats.append(1))
    heartbeat.start(5)
    try:
        workspace.start_button.click()
        for _ in range(100):
            if entered.is_set():
                break
            QTest.qWait(5)
        assert entered.is_set()
        QTest.qWait(40)
        assert len(beats) >= 2
        assert not workspace.start_button.isEnabled()
        if reset:
            workspace.reset_button.click()
        else:
            workspace.cancel_button.click()
        assert not workspace.cancel_button.isEnabled()
        assert workspace.controller.is_running
    finally:
        release.set()
        heartbeat.stop()
    wait_for_finish(window)
    assert workspace.start_button.isEnabled()
    if reset:
        assert workspace.history == [] and workspace.snapshot is None
    else:
        assert len(workspace.history) < 101
        assert "cancelado" in workspace.computation_status.text()
    workspace.problem = PROJECT_01_F1
    workspace.start_button.click()
    wait_for_finish(window)
    assert len(workspace.history) == 101


def test_reset_clears_snapshot_inspector_and_navigation(window: MainWindow) -> None:
    workspace = window.simulation
    workspace.start_button.click()
    wait_for_finish(window)
    workspace.play_button.click()
    workspace.reset_button.click()
    assert not workspace.replay_timer.isActive()
    assert workspace.history == [] and workspace.snapshot is None
    assert workspace.inspector.snapshot is None and workspace.plot.snapshot is None
    assert not workspace.generation_slider.isEnabled()
    assert workspace.generation_spin.maximum() == 0


def test_close_requests_cooperative_worker_shutdown(window: MainWindow) -> None:
    workspace = window.simulation
    workspace.start_button.click()
    window.close()
    # Process the finished signal to release the thread's controller references.
    QTest.qWait(20)
    assert not workspace.controller.is_running
    assert not window.isVisible()
