from dataclasses import replace

import pytest
from PySide6.QtTest import QTest

from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod
from evolutionary_lab.domain.variation import ReproductionPolicy
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.presentation.windows.main_window import MainWindow
from evolutionary_lab.problems.registry import PROJECT_01_F1


def wait_for_finish(window: MainWindow) -> None:
    for _ in range(300):
        if not window.simulation.controller.is_running:
            return
        QTest.qWait(10)
    pytest.fail("Worker did not finish")


@pytest.mark.parametrize("selection", list(SelectionMethod))
@pytest.mark.parametrize("replacement", list(ReplacementStrategy))
def test_visible_parameters_drive_real_engine_and_statistics(
    window: MainWindow, selection: SelectionMethod, replacement: ReplacementStrategy
) -> None:
    parameters = window.parameters
    parameters.population_size.setValue(7)
    parameters.generation_limit.setValue(6)
    parameters.precision.setText("0,002")
    parameters.seed.setText("-9")
    parameters.selection.setCurrentIndex(list(SelectionMethod).index(selection))
    parameters.replacement.setCurrentIndex(list(ReplacementStrategy).index(replacement))
    parameters.reproduction.setCurrentIndex(1)
    parameters.crossover.setValue(55)
    parameters.mutation.setValue(0.25)
    config = parameters.configuration()
    assert config.crossover_probability == 0.55
    assert config.mutation_probability == 0.0025
    assert config.reproduction_policy == ReproductionPolicy.PAIRWISE
    parameters.run_button.click()
    assert not parameters.isEnabled()
    wait_for_finish(window)
    assert parameters.isEnabled()
    expected = run_evolution(config, PROJECT_01_F1)
    assert tuple(window.simulation.history) == expected.generations
    statistics = window.statistics
    x, y = statistics.best.getData()
    assert tuple(x) == tuple(range(7))
    assert tuple(y) == tuple(
        snapshot.statistics.selection_fitness_max for snapshot in expected.generations
    )
    _, mean = statistics.mean.getData()
    assert tuple(mean) == tuple(
        snapshot.statistics.selection_fitness_mean for snapshot in expected.generations
    )
    _, diversity = statistics.diversity.getData()
    assert tuple(diversity) == tuple(
        snapshot.statistics.mean_normalized_hamming_distance
        for snapshot in expected.generations
    )
    _, best_so_far = statistics.best_so_far.getData()
    assert tuple(best_so_far) == tuple(
        snapshot.best_so_far.selection_fitness for snapshot in expected.generations
    )
    window.simulation.seek(3)
    assert statistics.fitness_cursor.value() == statistics.diversity_cursor.value() == 3
    assert "Generación 3" in statistics.summary.text()
    parameters.seed.setText("123")
    assert window.simulation.snapshot.config.seed == -9
    for theme in (1, 2):
        window.appearance.setCurrentIndex(theme)
        assert tuple(statistics.best.getData()[1]) == tuple(y)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("precision", "0", "precisión positiva"),
        ("precision", "nan", "precisión positiva"),
        ("precision", "texto", "precisión positiva"),
        ("precision", "1e-100", "demasiado fina"),
        ("precision", "2", "un bit"),
        ("seed", "42.5", "número entero"),
    ],
)
def test_invalid_inputs_are_spanish_errors_before_worker_creation(
    window: MainWindow, field: str, value: str, message: str
) -> None:
    getattr(window.parameters, field).setText(value)
    window.simulation.start_button.click()
    assert not window.simulation.controller.is_running
    assert window.simulation.history == []
    assert window.simulation.error_label.isVisible()
    assert message in window.simulation.error_label.text()


def test_history_limit_and_valid_initial_only_configuration(window: MainWindow) -> None:
    parameters = window.parameters
    parameters.population_size.setValue(500)
    parameters.generation_limit.setValue(2000)
    window.simulation.start_button.click()
    assert not window.simulation.controller.is_running
    assert "Reduce la población" in window.simulation.error_label.text()
    parameters.population_size.setValue(1)
    parameters.generation_limit.setValue(0)
    parameters.precision.setText("2")
    parameters.crossover.setValue(0)
    window.simulation.start_button.click()
    wait_for_finish(window)
    assert len(window.simulation.history) == 1
    assert len(window.simulation.snapshot.population) == 1


def test_speed_and_reduced_animation_only_change_replay(window: MainWindow) -> None:
    workspace = window.simulation
    workspace.start_button.click()
    wait_for_finish(window)
    saved = tuple(workspace.history)
    workspace.speed.setCurrentIndex(4)
    assert workspace.replay_timer.interval() == 33
    workspace.seek(4)
    workspace.animate.setChecked(False)
    assert not workspace.speed.isEnabled() and not workspace.replay_timer.isActive()
    workspace.play_button.click()
    assert workspace.current_index == 100
    assert not workspace.replay_timer.isActive()
    assert tuple(workspace.history) == saved
    workspace.animate.setChecked(True)
    workspace.play_button.click()
    assert workspace.replay_timer.isActive()
    workspace.stop_button.click()


def test_worker_failure_keeps_valid_snapshot_and_localizes_zero_fitness(
    window: MainWindow,
) -> None:
    workspace = window.simulation
    workspace.problem = replace(PROJECT_01_F1, objective=lambda point: 0.0)
    workspace.problem_provider = lambda: workspace.problem
    workspace.start_button.click()
    wait_for_finish(window)
    assert len(workspace.history) == 1
    assert "aptitudes son cero" in workspace.error_label.text()
    assert workspace.start_button.isEnabled() and window.parameters.isEnabled()
    window.parameters.selection.setCurrentIndex(2)
    workspace.start_button.click()
    wait_for_finish(window)
    assert len(workspace.history) == 101 and not workspace.error_label.isVisible()
