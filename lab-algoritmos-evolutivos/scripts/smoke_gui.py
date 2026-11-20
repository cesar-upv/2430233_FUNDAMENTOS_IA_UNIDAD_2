import argparse
from importlib.metadata import distribution
from math import isclose
from pathlib import Path
from statistics import mean

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTabWidget

from evolutionary_lab.domain.models import BinaryGenotype, OptimizationDirection
from evolutionary_lab.domain.variation import RealCrossoverMethod
from evolutionary_lab.evolution.encoding.binary import genotype_to_string
from evolutionary_lab.presentation.windows.main_window import MainWindow
from evolutionary_lab.problems.registry import PROBLEMS, get_problem
from evolutionary_lab.simulation.snapshots import GenerationSnapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the installed Qt application.")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--problem", choices=tuple(PROBLEMS), default="project_01.f1")
    parser.add_argument("--dimensions", type=int)
    parser.add_argument("--project", type=int, choices=(1, 2), default=1)
    parser.add_argument(
        "--real-crossover", choices=tuple(RealCrossoverMethod), default="sbx"
    )
    parser.add_argument("--settings", action="store_true")
    parser.add_argument(
        "--simulate", action="store_true", help="Run and replay the problem twice."
    )
    parser.add_argument("--theme", choices=("system", "light", "dark"))
    parser.add_argument(
        "--minimum", action="store_true", help="Use the minimum window size."
    )
    args = parser.parse_args()
    event_loop = QApplication.exec

    def checked_event_loop() -> int:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("The entry point did not create QApplication")
        saved: tuple[GenerationSnapshot, ...] = ()
        original_theme: int | None = None

        def capture(window: MainWindow, suffix: str = "") -> None:
            if args.screenshot is None:
                return
            path = args.screenshot
            if suffix:
                path = path.with_name(path.stem + suffix + path.suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            app.processEvents()
            if not window.grab().save(str(path)):
                raise RuntimeError(f"Could not save {path}")

        def finish(window: MainWindow, detail: str) -> None:
            if original_theme is not None:
                window.appearance.setCurrentIndex(original_theme)
            print(f"Qt smoke OK: {app.platformName()}, {detail}")
            window.close()
            app.exit(0)

        def check_window() -> None:
            nonlocal original_theme
            try:
                windows = [
                    widget
                    for widget in app.topLevelWidgets()
                    if isinstance(widget, QMainWindow) and widget.isVisible()
                ]
                if len(windows) != 1 or not isinstance(windows[0], MainWindow):
                    raise RuntimeError("Expected one visible MainWindow")
                window = windows[0]
                handle = window.windowHandle()
                if handle is None or not handle.isExposed():
                    raise RuntimeError("The Qt window was not exposed")
                original_theme = window.appearance.currentIndex()
                if args.theme is not None:
                    window.appearance.setCurrentIndex(
                        ("system", "light", "dark").index(args.theme)
                    )
                if args.minimum:
                    window.resize(window.minimumSize())
                if args.simulate:
                    window.simulation.controller.finished.connect(
                        lambda outcome: QTimer.singleShot(
                            50, lambda: check_simulation(window, outcome)
                        )
                    )
                    tabs = window.workspaces.widget(0)
                    assert isinstance(tabs, QTabWidget)
                    tabs.setCurrentIndex(2)
                    window.parameters.project_selector.setCurrentIndex(args.project - 1)
                    problem = get_problem(args.problem, args.dimensions)
                    window.parameters.direction.setCurrentIndex(
                        0 if problem.direction == OptimizationDirection.MAXIMIZE else 1
                    )
                    window.parameters.problem_selector.setCurrentIndex(
                        window.parameters.problem_selector.findData(args.problem)
                    )
                    if args.dimensions is not None:
                        window.parameters.dimensions.setValue(args.dimensions)
                    if args.project == 2:
                        target = window.parameters.real_crossover.findData(
                            args.real_crossover
                        )
                        assert target >= 0, "Crossover is incompatible with dimensions"
                        window.parameters.real_crossover.setCurrentIndex(target)
                    app.processEvents()
                    window.parameters.scroll_area.ensureWidgetVisible(
                        window.parameters.run_button
                    )
                    QTest.mouseClick(
                        window.parameters.run_button, Qt.MouseButton.LeftButton
                    )
                    return
                if args.settings:
                    button = window.findChild(QPushButton, "settingsNavigation")
                    if button is None:
                        raise RuntimeError("Settings navigation is missing")
                    button.click()
                capture(window)
                finish(window, "window opened and closed")
            except Exception as error:
                print(f"Qt smoke failed: {error}")
                app.exit(1)

        def check_simulation(window: MainWindow, outcome: str) -> None:
            nonlocal saved
            try:
                workspace = window.simulation
                assert outcome == "completed" and not workspace.controller.is_running
                assert len(workspace.history) == 101 and workspace.current_index == 100
                assert all(
                    len(snapshot.population) == 10 for snapshot in workspace.history
                )
                problem = window.parameters.selected_problem()
                for snapshot in workspace.history:
                    assert snapshot.statistics.objective_mean == mean(
                        item.objective_value for item in snapshot.population
                    )
                    if args.project == 2:
                        assert (
                            snapshot.statistics.mean_normalized_hamming_distance is None
                        )
                        diversity = snapshot.statistics.mean_normalized_real_distance
                        assert diversity is not None and 0 <= diversity <= 1
                    for item in snapshot.population:
                        assert isclose(
                            item.objective_value,
                            problem.evaluate(item.phenotype),
                            rel_tol=1e-12,
                            abs_tol=1e-12,
                        )
                        assert all(
                            d.contains(value)
                            for d, value in zip(
                                snapshot.config.domains, item.phenotype, strict=True
                            )
                        )
                if not saved:
                    saved = tuple(workspace.history)
                    QTest.mouseClick(workspace.reset_button, Qt.MouseButton.LeftButton)
                    assert workspace.history == [] and workspace.snapshot is None
                    QTest.mouseClick(workspace.start_button, Qt.MouseButton.LeftButton)
                    return
                assert tuple(workspace.history) == saved
                QTest.mouseClick(workspace.previous_button, Qt.MouseButton.LeftButton)
                assert workspace.current_index == 99
                QTest.mouseClick(workspace.next_button, Qt.MouseButton.LeftButton)
                assert workspace.current_index == 100
                workspace.generation_spin.setValue(42)
                QTest.mouseClick(workspace.play_button, Qt.MouseButton.LeftButton)
                QTest.qWait(300)
                assert workspace.current_index > 42
                QTest.mouseClick(workspace.play_button, Qt.MouseButton.LeftButton)
                assert not workspace.replay_timer.isActive()
                QTest.mouseClick(workspace.play_button, Qt.MouseButton.LeftButton)
                QTest.qWait(280)
                QTest.mouseClick(workspace.stop_button, Qt.MouseButton.LeftButton)
                assert not workspace.replay_timer.isActive()
                # The completed run's initial population displays distinct real points.
                workspace.generation_spin.setValue(0)
                workspace.inspector.selector.setCurrentIndex(4)
                individual = workspace.snapshot.population.individuals[4]
                if isinstance(individual.genotype, BinaryGenotype):
                    expected = genotype_to_string(individual.genotype.chromosomes[0])
                else:
                    expected = f"{individual.genotype.values[0]:.12g}"
                assert expected in workspace.inspector.values["genotype"].text()
                assert isclose(
                    float(workspace.inspector.values["objective"].text()),
                    individual.objective_value,
                    rel_tol=1e-10,
                )
                x, y = workspace.plot.population.getData()
                if len(saved[0].config.domains) <= 2:
                    assert tuple(x) == tuple(
                        item.phenotype[0] for item in saved[0].population
                    )
                    assert tuple(y) == tuple(
                        item.objective_value
                        if len(item.phenotype) == 1
                        else item.phenotype[1]
                        for item in saved[0].population
                    )
                else:
                    assert len(x) == 10 * len(saved[0].config.domains)
                    assert all(0 <= value <= 1 for value in y)
                capture(window)
                workspace.seek(100)
                tabs = window.workspaces.widget(0)
                assert isinstance(tabs, QTabWidget)
                tabs.setCurrentIndex(1)
                stats_x, stats_y = window.statistics.mean.getData()
                assert tuple(stats_x) == tuple(range(101))
                assert tuple(stats_y) == tuple(
                    snapshot.statistics.objective_mean for snapshot in saved
                )
                capture(window, "-analysis")
                tabs.setCurrentIndex(2)
                window.parameters.scroll_area.verticalScrollBar().setValue(0)
                capture(window, "-parameters")
                finish(
                    window,
                    "101 generations; deterministic rerun, replay and inspection OK",
                )
            except Exception as error:
                print(f"Qt simulation smoke failed: {error}")
                window.close()
                app.exit(1)

        QTimer.singleShot(200, check_window)
        QTimer.singleShot(15000, lambda: app.exit(2))
        return event_loop()

    # Bound only the developer check; the installed application's loop is unchanged.
    QApplication.exec = staticmethod(checked_event_loop)
    try:
        entry = next(
            entry
            for entry in distribution("evolutionary-lab").entry_points
            if entry.group == "console_scripts" and entry.name == "evolutionary-lab"
        )
        return int(entry.load()())
    finally:
        QApplication.exec = staticmethod(event_loop)


if __name__ == "__main__":
    raise SystemExit(main())
