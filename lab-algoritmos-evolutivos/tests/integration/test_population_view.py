import pytest
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from evolutionary_lab.evolution.encoding.binary import genotype_to_string
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.presentation.simulation_workspace import demo_config
from evolutionary_lab.presentation.windows.main_window import MainWindow
from evolutionary_lab.problems.registry import PROJECT_01_F1


def wait_until_idle(window: MainWindow) -> None:
    for _ in range(300):
        if not window.simulation.controller.is_running:
            return
        QTest.qWait(10)
    pytest.fail("Simulation worker did not finish")


def test_real_population_curve_and_inspector_arrive_on_gui_thread(
    window: MainWindow, qt_app: QApplication
) -> None:
    workspace = window.simulation
    received_threads = []
    workspace.controller.snapshots_ready.connect(
        lambda _batch: received_threads.append(QThread.currentThread())
    )
    workspace.start_button.click()
    wait_until_idle(window)
    expected = run_evolution(demo_config(), PROJECT_01_F1).generations[-1]
    assert workspace.snapshot == expected
    assert received_threads and all(
        thread == qt_app.thread() for thread in received_threads
    )
    x, y = workspace.plot.population.getData()
    assert tuple(x) == tuple(item.phenotype[0] for item in expected.population)
    assert tuple(y) == tuple(item.objective_value for item in expected.population)
    curve_x, curve_y = workspace.plot.curve.getData()
    assert curve_x[0] == 0 and curve_x[-1] == 1
    assert len(curve_x) == len(curve_y) == 601
    for index in (0, 60, 311, 600):
        assert curve_y[index] == PROJECT_01_F1.evaluate((curve_x[index],))
    best_x, best_y = workspace.plot.best.getData()
    assert best_x[0] == expected.statistics.best_individual.phenotype[0]
    assert best_y[0] == expected.statistics.best_individual.objective_value
    identifier = workspace.inspector.selector.currentData()
    member = expected.population.individuals[identifier]
    assert workspace.inspector.values["genotype"].text() == genotype_to_string(
        member.genotype
    )


def test_generation_update_and_point_selection_preserve_snapshot_truth(
    window: MainWindow,
) -> None:
    snapshots = run_evolution(demo_config(3), PROJECT_01_F1).generations
    workspace = window.simulation
    for snapshot in (snapshots[0], snapshots[3], snapshots[1]):
        workspace.show_snapshot(snapshot)
        workspace.plot.individual_selected.emit(4)
        member = snapshot.population.individuals[4]
        assert workspace.inspector.selector.currentData() == 4
        assert workspace.inspector.values["generation"].text() == str(
            snapshot.generation_index
        )
        assert workspace.inspector.values["genotype"].text() == genotype_to_string(
            member.genotype
        )
        assert float(workspace.inspector.values["objective"].text()) == pytest.approx(
            member.objective_value
        )
        selected_x, selected_y = workspace.plot.selected.getData()
        assert (
            selected_x[0] == member.phenotype[0]
            and selected_y[0] == member.objective_value
        )
        if snapshot.trace is not None:
            assert (
                "Descendiente adoptado"
                == workspace.inspector.values["replacement_decision"].text()
            )


def test_plot_themes_preserve_real_data(window: MainWindow) -> None:
    snapshot = run_evolution(demo_config(0), PROJECT_01_F1).generations[0]
    window.simulation.show_snapshot(snapshot)
    for theme in (1, 2, 0):
        window.appearance.setCurrentIndex(theme)
        assert window.simulation.plot.snapshot == snapshot
        assert window.simulation.plot.curve.opts["pen"].color().isValid()
        assert len(window.simulation.plot.population.points()) == 10
