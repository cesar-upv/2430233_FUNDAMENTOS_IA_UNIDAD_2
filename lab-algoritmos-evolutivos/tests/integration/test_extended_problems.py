import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.presentation.windows.main_window import MainWindow


def finish(window: MainWindow) -> None:
    for _ in range(1000):
        if not window.simulation.controller.is_running:
            return
        QTest.qWait(10)
    pytest.fail("Worker did not finish")


@pytest.mark.parametrize(
    "identifier", ["project_01.min1", "project_01.min2", "project_01.min3"]
)
def test_minimization_from_gui_keeps_objectives_separate_from_weights(
    window: MainWindow, identifier: str
) -> None:
    form = window.parameters
    form.direction.setCurrentIndex(1)
    assert form.problem_selector.findData("project_01.f1") == -1
    form.problem_selector.setCurrentIndex(form.problem_selector.findData(identifier))
    form.generation_limit.setValue(5)
    problem = form.selected_problem()
    config = form.configuration()
    form.run_button.click()
    finish(window)
    assert not window.simulation.error_label.isVisible()
    assert (
        tuple(window.simulation.history) == run_evolution(config, problem).generations
    )
    window.simulation.seek(3)
    snapshot = window.simulation.snapshot
    assert float(window.simulation.metrics.values["best"].text()) == pytest.approx(
        snapshot.statistics.objective_min, abs=1e-6
    )
    assert tuple(window.statistics.best.getData()[1]) == tuple(
        s.statistics.objective_min for s in window.simulation.history
    )
    assert window.simulation.plot.snapshot == snapshot
    assert form.fitness_policy.count() == (2 if identifier == "project_01.min1" else 1)


@pytest.mark.parametrize(
    "identifier, dimensions",
    [
        ("project_01.schaffer", 2),
        ("project_01.rastrigin", 2),
        ("project_01.rastrigin", 5),
        ("project_01.sine_power", 3),
        ("project_01.schwefel", 2),
    ],
)
def test_multivariable_gui_matches_engine_and_uses_correct_plot(
    window: MainWindow, identifier: str, dimensions: int
) -> None:
    from evolutionary_lab.domain.models import OptimizationDirection
    from evolutionary_lab.problems.registry import get_problem

    problem = get_problem(identifier, dimensions)
    form = window.parameters
    form.direction.setCurrentIndex(
        0 if problem.direction == OptimizationDirection.MAXIMIZE else 1
    )
    form.problem_selector.setCurrentIndex(form.problem_selector.findData(identifier))
    if dimensions != 2:
        form.dimensions.setValue(dimensions)
    form.generation_limit.setValue(6)
    form.variables[0].precision.setText("0.01")
    form.variables[1].precision.setText("0.03")
    config = form.configuration()
    form.run_button.click()
    finish(window)
    assert not window.simulation.error_label.isVisible()
    assert (
        tuple(window.simulation.history) == run_evolution(config, problem).generations
    )
    workspace = window.simulation
    workspace.seek(0)
    plot = workspace.plot
    assert plot.dimensions == dimensions
    if dimensions == 2:
        image = plot.surface.image
        assert image.shape == (161, 161)
        for ix, iy in ((0, 0), (80, 80), (160, 160)):
            point = tuple(
                d.lower + (d.upper - d.lower) * index / 160
                for d, index in zip(config.domains, (ix, iy), strict=True)
            )
            assert image[ix, iy] == pytest.approx(problem.evaluate(point))
        x, y = plot.population.getData()
        assert tuple(x) == tuple(i.phenotype[0] for i in workspace.snapshot.population)
        assert tuple(y) == tuple(i.phenotype[1] for i in workspace.snapshot.population)
    else:
        x, y = plot.population.getData()
        assert len(x) == dimensions * config.population_size
        assert all(0 <= value <= 1 for value in y)
        first = workspace.snapshot.population.individuals[0]
        assert tuple(y[:dimensions]) == pytest.approx(
            tuple(
                (v - d.lower) / (d.upper - d.lower)
                for v, d in zip(first.phenotype, config.domains, strict=True)
            )
        )
        assert plot.explanation.isVisible()
    if dimensions == 2:
        workspace.inspector.selector.setCurrentIndex(0)
        target = workspace.snapshot.population.individuals[4]
        scene_point = plot.graph.getViewBox().mapViewToScene(QPointF(*target.phenotype))
        QTest.mouseClick(
            plot.graph.viewport(),
            Qt.MouseButton.LeftButton,
            pos=plot.graph.mapFromScene(scene_point),
        )
        assert workspace.inspector.selector.currentData() == target.identifier
    workspace.inspector.selector.setCurrentIndex(4)
    assert "x1:" in workspace.inspector.values["genotype"].text()
    assert "x2:" in workspace.inspector.values["decimal_genotype"].text()
    baseline = tuple(tuple(r) for r in plot.graph.getViewBox().viewRange())
    workspace.toggle_playback()
    workspace.replay_timer.timeout.emit()
    workspace.stop_playback()
    assert workspace.current_index == 1
    assert tuple(tuple(r) for r in plot.graph.getViewBox().viewRange()) == baseline
    snapshot = workspace.snapshot
    member = snapshot.population.individuals[4]
    assert float(workspace.inspector.values["objective"].text()) == pytest.approx(
        member.objective_value
    )
    for theme in (1, 2):
        window.appearance.setCurrentIndex(theme)
        assert plot.snapshot == snapshot
    assert tuple(window.statistics.best.getData()[1]) == tuple(
        s.statistics.best_individual.objective_value for s in workspace.history
    )


def test_parameter_layout_and_independent_inputs_at_both_sizes(
    window: MainWindow,
) -> None:
    from PySide6.QtWidgets import QTabWidget

    tabs = window.workspaces.widget(0)
    assert isinstance(tabs, QTabWidget)
    tabs.setCurrentIndex(2)
    form = window.parameters
    form.direction.setCurrentIndex(1)
    form.problem_selector.setCurrentIndex(
        form.problem_selector.findData("project_01.rastrigin")
    )
    window.resize(1600, 1000)
    QTest.qWait(30)
    assert form._columns == 2
    window.resize(900, 740)
    QTest.qWait(30)
    assert form._columns == 1
    assert form.scroll_area.verticalScrollBar().maximum() > 0
    form.variables[0].lower.setText("-1")
    form.variables[0].upper.setText("1")
    form.variables[1].lower.setText("-2")
    form.variables[1].upper.setText("2")
    form.variables[0].precision.setText("0.01")
    form.variables[1].precision.setText("0.03")
    config = form.configuration()
    assert tuple((d.lower, d.upper) for d in config.domains) == ((-1, 1), (-2, 2))
    assert config.precision == (0.01, 0.03)
    assert form.crossover.text() == "70 %"
    form.mutation.setValue(0.25)
    assert form.mutation.text() == "0.25 %"
    form.variables[1].upper.setText("nan")
    with pytest.raises(ValueError, match="Variable 2"):
        form.configuration()
    form.selection.setCurrentIndex(2)
    assert form.zero_weights.isHidden()
    form.selection.setCurrentIndex(0)
    assert not form.zero_weights.isHidden()
