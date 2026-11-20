import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from evolutionary_lab.domain.models import Representation
from evolutionary_lab.presentation.generation_summary import GenerationSummary
from evolutionary_lab.presentation.plotting import (
    PlotHeader,
    PlotLegend,
    configure_plot,
    style_plot,
)
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.presentation.theme import ThemeColors
from evolutionary_lab.simulation.snapshots import GenerationSnapshot


class StatisticsWorkspace(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.history: tuple[GenerationSnapshot, ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        self.summary = QLabel(text("statistics_empty"))
        self.summary.setWordWrap(True)
        self.summary.setObjectName("muted")
        layout.addWidget(self.summary)
        self.metrics = GenerationSummary()
        layout.addWidget(self.metrics)
        self.fitness_header = PlotHeader("fitness_chart_title", self.reset_fitness_view)
        layout.addWidget(self.fitness_header)
        self.fitness_graph = pg.PlotWidget()
        self.fitness_graph.setLabel("bottom", text("generation"))
        self.fitness_graph.setLabel("left", text("objective"))
        self.best = self.fitness_graph.plot(name=text("generation_best"))
        self.mean = self.fitness_graph.plot(name=text("generation_mean"))
        self.best_so_far = self.fitness_graph.plot(name=text("best_so_far"))
        self.diversity_graph = pg.PlotWidget()
        self.diversity_graph.setLabel("bottom", text("generation"))
        self.diversity_graph.setLabel("left", text("diversity_axis"))
        self.diversity = self.diversity_graph.plot()
        self.fitness_cursor = pg.InfiniteLine(angle=90, movable=False)
        self.diversity_cursor = pg.InfiniteLine(angle=90, movable=False)
        self.fitness_graph.addItem(self.fitness_cursor)
        self.diversity_graph.addItem(self.diversity_cursor)
        self.fitness_legend = PlotLegend(
            (
                ("generation_best", "line"),
                ("generation_mean", "dash"),
                ("best_so_far", "accent_line"),
            )
        )
        layout.addWidget(self.fitness_graph, 1)
        layout.addWidget(self.fitness_legend)
        self.diversity_header = PlotHeader(
            "diversity_chart_title", self.reset_diversity_view
        )
        layout.addWidget(self.diversity_header)
        layout.addWidget(self.diversity_graph, 1)
        for graph in (self.fitness_graph, self.diversity_graph):
            configure_plot(graph)

    @Slot(object)
    def set_history(self, history: tuple[GenerationSnapshot, ...]) -> None:
        self.history = history
        x = [snapshot.generation_index for snapshot in history]
        self.best.setData(
            x,
            [
                snapshot.statistics.best_individual.objective_value
                for snapshot in history
            ],
        )
        self.mean.setData(
            x, [snapshot.statistics.objective_mean for snapshot in history]
        )
        self.best_so_far.setData(
            x, [snapshot.best_so_far.objective_value for snapshot in history]
        )
        self.diversity.setData(
            x,
            [snapshot.statistics.normalized_diversity for snapshot in history],
        )
        if not history:
            self.summary.setText(text("statistics_empty"))
            self.summary.show()
            self.fitness_cursor.hide()
            self.diversity_cursor.hide()
            self.metrics.clear()
        else:
            is_real = history[0].config.representation == Representation.REAL
            self.diversity_graph.setLabel(
                "left", text("real_diversity_axis" if is_real else "diversity_axis")
            )
            self.diversity_header.title.setToolTip(
                text("real_diversity_help" if is_real else "binary_diversity_help")
            )
            self.reset_fitness_view()
            self.reset_diversity_view()
            self.select_generation(
                min(int(self.fitness_cursor.value()), len(history) - 1)
            )
        for header in (self.fitness_header, self.diversity_header):
            header.reset_button.setEnabled(bool(history))

    @Slot(int)
    def select_generation(self, index: int) -> None:
        if not 0 <= index < len(self.history):
            return
        snapshot = self.history[index]
        for cursor in (self.fitness_cursor, self.diversity_cursor):
            cursor.setValue(index)
            cursor.show()
        self.summary.setText(
            text("generation_meta").format(
                generation=index, size=len(snapshot.population)
            )
        )
        self.metrics.set_snapshot(snapshot)
        self.summary.hide()

    def reset_fitness_view(self) -> None:
        if not self.history:
            return
        values = [
            value
            for snapshot in self.history
            for value in (
                snapshot.statistics.best_individual.objective_value,
                snapshot.statistics.objective_mean,
                snapshot.best_so_far.objective_value,
            )
            if value is not None
        ]
        lower, upper = min(values, default=0.0), max(values, default=1.0)
        if lower == upper:
            lower, upper = 0.0, max(1.0, upper)
        self.fitness_graph.setXRange(
            0, max(1, self.history[-1].generation_index), padding=0.02
        )
        self.fitness_graph.setYRange(lower, upper, padding=0.08)

    def reset_diversity_view(self) -> None:
        if self.history:
            self.diversity_graph.setXRange(
                0, max(1, self.history[-1].generation_index), padding=0.02
            )
            self.diversity_graph.setYRange(0, 1, padding=0.02)

    def apply_theme(self, colors: ThemeColors) -> None:
        for graph in (self.fitness_graph, self.diversity_graph):
            style_plot(graph, colors)
        self.best.setPen(pg.mkPen(colors.foreground, width=1.5))
        self.mean.setPen(pg.mkPen(colors.muted, width=2, style=Qt.PenStyle.DashLine))
        self.best_so_far.setPen(pg.mkPen(colors.accent, width=2.5))
        self.diversity.setPen(pg.mkPen(colors.accent, width=2))
        for cursor in (self.fitness_cursor, self.diversity_cursor):
            cursor.setPen(pg.mkPen(colors.muted, width=1))
        self.fitness_legend.apply_theme(colors)
