from math import isfinite

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTabWidget

from evolutionary_lab.domain.models import RealGenotype, Representation
from evolutionary_lab.domain.variation import RealCrossoverMethod
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.presentation.errors import ConfigurationInputError
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.presentation.windows.main_window import MainWindow
from evolutionary_lab.problems.registry import get_problem


def finish(window: MainWindow) -> None:
    for _ in range(1000):
        if not window.simulation.controller.is_running:
            return
        QTest.qWait(10)
    pytest.fail("Real simulation worker did not finish")


@pytest.mark.parametrize(
    "identifier, dimensions, method",
    [("project_01.rastrigin", 2, method) for method in RealCrossoverMethod]
    + [
        ("project_01.f1", 1, RealCrossoverMethod.SBX),
        ("project_01.rastrigin", 1, RealCrossoverMethod.UNIFORM),
        ("project_01.schwefel", 5, RealCrossoverMethod.ARITHMETIC),
    ],
)
def test_real_project_from_gui_uses_shared_engine_and_real_inspection(
    window: MainWindow, identifier: str, dimensions: int, method: RealCrossoverMethod
) -> None:
    form = window.parameters
    form.project_selector.setCurrentIndex(1)
    problem = get_problem(identifier, dimensions)
    form.direction.setCurrentIndex(0 if problem.direction.value == "maximize" else 1)
    form.problem_selector.setCurrentIndex(form.problem_selector.findData(identifier))
    if identifier in ("project_01.rastrigin", "project_01.schwefel"):
        form.dimensions.setValue(dimensions)
    form.real_crossover.setCurrentIndex(form.real_crossover.findData(method))
    if identifier == "project_01.rastrigin" and dimensions == 2:
        for variable, lower, upper in zip(
            form.variables, ("-1", "0"), ("2", "3"), strict=True
        ):
            variable.lower.setText(lower)
            variable.upper.setText(upper)
        form.uniform_swap.setValue(33)
        form.arithmetic_alpha.setValue(0.3)
        form.sbx_index.setValue(2.5)
        form.sbx_formula.setCurrentIndex(1)
    form.generation_limit.setValue(6)
    form.population_size.setValue(7)
    form.mutation.setValue(100)
    form.crossover.setValue(100)
    assert form.variables[0].precision.isHidden()
    form.variables[0].precision.setText("unused")
    config = form.configuration()
    assert config.representation == Representation.REAL and config.precision == ()
    assert config.real_crossover_method == method
    form.run_button.click()
    finish(window)
    workspace = window.simulation
    assert not workspace.error_label.isVisible()
    assert tuple(workspace.history) == run_evolution(config, problem).generations
    assert "Proyecto 2" in workspace.problem_title.text()
    assert "Proyecto 1" not in workspace.problem_title.text()
    assert "real" in window.section_description.text()
    for snapshot in workspace.history:
        assert len(snapshot.population) == 7
        assert snapshot.statistics.mean_normalized_hamming_distance is None
        assert 0 <= snapshot.statistics.mean_normalized_real_distance <= 1
        for item in snapshot.population:
            assert isinstance(item.genotype, RealGenotype)
            assert item.genotype.values == item.phenotype
            assert item.objective_value == problem.evaluate(item.phenotype)
            assert isfinite(item.selection_fitness) and item.selection_fitness >= 0
            assert all(
                d.contains(v)
                for d, v in zip(config.domains, item.phenotype, strict=True)
            )
    workspace.seek(3)
    workspace.inspector.selector.setCurrentIndex(0)
    item = workspace.snapshot.population.individuals[0]
    assert f"{item.phenotype[0]:.12g}" in workspace.inspector.values["genotype"].text()
    assert workspace.inspector.values["decimal_genotype"].isHidden()
    assert "x1 →" in workspace.inspector.values["mutation_attempt"].text()
    assert (
        text(f"real_cross_{method}")
        in workspace.inspector.values["operator_details"].text()
    )
    assert workspace.inspector.labels["genotype"].text() == text("real_genotype")
    assert tuple(window.statistics.diversity.getData()[1]) == tuple(
        s.statistics.mean_normalized_real_distance for s in workspace.history
    )
    assert (
        text("real_diversity_axis")
        in window.statistics.diversity_graph.getAxis("left").labelText
    )
    x, y = workspace.plot.population.getData()
    if dimensions <= 2:
        assert tuple(x) == tuple(i.phenotype[0] for i in workspace.snapshot.population)
    else:
        assert len(x) == 7 * dimensions and all(0 <= value <= 1 for value in y)
    saved = tuple(workspace.history)
    workspace.toggle_playback()
    workspace.replay_timer.timeout.emit()
    workspace.stop_playback()
    assert workspace.current_index == 4 and tuple(workspace.history) == saved
    for theme in (1, 2):
        window.appearance.setCurrentIndex(theme)
        assert tuple(workspace.history) == saved


def test_project_switching_filters_incompatible_controls_and_preserves_binary(
    window: MainWindow,
) -> None:
    form = window.parameters
    binary_config = form.configuration()
    tabs = window.workspaces.widget(0)
    assert isinstance(tabs, QTabWidget)
    tabs.setCurrentIndex(2)
    form.project_selector.setCurrentIndex(1)
    assert form.real_crossover.findData(RealCrossoverMethod.ONE_POINT) < 0
    assert form.reproduction.isHidden()
    assert not form.sbx_index.isHidden() and not form.bounds_policy.isHidden()
    form.real_crossover.setCurrentIndex(
        form.real_crossover.findData(RealCrossoverMethod.ARITHMETIC)
    )
    assert not form.arithmetic_alpha.isHidden() and form.sbx_index.isHidden()
    form.real_crossover.setCurrentIndex(
        form.real_crossover.findData(RealCrossoverMethod.UNIFORM)
    )
    assert not form.uniform_swap.isHidden() and form.arithmetic_alpha.isHidden()
    form.variables[0].lower.setText("nan")
    with pytest.raises(ConfigurationInputError, match="Variable 1"):
        form.configuration()
    form.project_selector.setCurrentIndex(0)
    assert form.configuration() == binary_config
    assert form.real_crossover.isHidden() and not form.reproduction.isHidden()
    assert not form.variables[0].precision.isHidden()
    form.generation_limit.setValue(100)
    form.run_button.click()
    finish(window)
    assert window.simulation.history[-1].best_so_far.objective_value == pytest.approx(
        0.9999361576410012, abs=1e-14
    )
    assert not window.simulation.inspector.values["decimal_genotype"].isHidden()
    assert window.simulation.inspector.values["operator_details"].isHidden()


def test_sbx_reject_policy_reports_failure_and_leaves_worker_stopped(
    window: MainWindow,
) -> None:
    form = window.parameters
    form.project_selector.setCurrentIndex(1)
    form.crossover.setValue(100)
    form.sbx_index.setValue(0)
    form.bounds_policy.setCurrentIndex(1)
    form.generation_limit.setValue(10)
    form.run_button.click()
    finish(window)
    assert window.simulation.error_label.isVisible()
    assert window.simulation.error_label.text() == text("error_real_bounds")
    assert not window.simulation.controller.is_running
    assert form.run_button.isEnabled()
