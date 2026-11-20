from collections.abc import Callable
from typing import Any

import numpy as np
import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import Individual, Interval
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.presentation.theme import ThemeColors
from evolutionary_lab.presentation.workers import FunctionCurve, FunctionSurface
from evolutionary_lab.simulation.snapshots import GenerationSnapshot


def configure_plot(graph: Any) -> None:
    graph.setMenuEnabled(False)
    graph.hideButtons()
    graph.getViewBox().setMouseEnabled(x=False, y=False)
    graph.getViewBox().setMouseMode(pg.ViewBox.PanMode)
    graph.disableAutoRange()
    graph.showGrid(x=True, y=True, alpha=0.12)
    for name in ("bottom", "left"):
        axis = graph.getAxis(name)
        # Disabling prefixes alone can retain a scale from the initial range.
        axis.setSIPrefixEnableRanges(())
        axis.enableAutoSIPrefix(False)


def style_plot(graph: Any, colors: ThemeColors) -> None:
    graph.setBackground(colors.surface)
    for name in ("bottom", "left"):
        axis = graph.getAxis(name)
        axis.setPen(colors.border)
        axis.setTextPen(colors.foreground)
        font = QFont(QApplication.font())
        font.setPointSizeF(9.5)
        axis.setTickFont(font)
        axis.setLabel(
            axis.labelText,
            siPrefixEnableRanges=(),
            color=colors.foreground,
            **{"font-size": "10pt"},
        )


class PlotHeader(QWidget):
    def __init__(self, title_key: str, reset: Callable[[], None]) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.title = QLabel(text(title_key))
        self.title.setObjectName("chartTitle")
        self.title.setWordWrap(True)
        layout.addWidget(self.title, 1)
        self.reset_button = QPushButton(text("reset_view"))
        self.reset_button.setToolTip(text("reset_view_help"))
        self.reset_button.clicked.connect(reset)
        self.reset_button.setEnabled(False)
        layout.addWidget(self.reset_button)


class LegendSwatch(QWidget):
    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind
        self.color = QColor()
        self.setFixedSize(24, 18)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color, 2)
        if self.kind == "dash":
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        if self.kind in ("line", "accent_line", "dash"):
            painter.drawLine(1, 9, 23, 9)
        elif self.kind == "diamond":
            painter.setBrush(self.color)
            painter.drawPolygon(
                QPolygonF(
                    [QPointF(12, 3), QPointF(18, 9), QPointF(12, 15), QPointF(6, 9)]
                )
            )
        else:
            if self.kind == "point":
                painter.setBrush(self.color)
            radius = 4 if self.kind == "point" else 6
            painter.drawEllipse(QPointF(12, 9), radius, radius)
        painter.end()


class PlotLegend(QWidget):
    def __init__(self, entries: tuple[tuple[str, str], ...]) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.swatches: list[LegendSwatch] = []
        for key, kind in entries:
            item = QHBoxLayout()
            item.setSpacing(4)
            swatch = LegendSwatch(kind)
            self.swatches.append(swatch)
            item.addWidget(swatch)
            label = QLabel(text(key))
            label.setObjectName("legendLabel")
            item.addWidget(label)
            layout.addLayout(item)
        layout.addStretch()

    def apply_theme(self, colors: ThemeColors) -> None:
        for swatch in self.swatches:
            color = (
                colors.accent
                if swatch.kind in ("accent_line", "diamond")
                else colors.muted
                if swatch.kind == "dash"
                else colors.foreground
            )
            swatch.color = QColor(color)
            swatch.update()


class PopulationPlot(QWidget):
    individual_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.header = PlotHeader("population_chart_title", self.reset_view)
        layout.addWidget(self.header)
        self.explanation = QLabel(text("parallel_help"))
        self.explanation.setWordWrap(True)
        self.explanation.setObjectName("muted")
        self.explanation.hide()
        layout.addWidget(self.explanation)
        self.graph = pg.PlotWidget()
        configure_plot(self.graph)
        self.graph.setLabel("bottom", text("phenotype_axis"))
        self.graph.setLabel("left", text("objective_axis"))
        self.curve = self.graph.plot()
        self.projection_lines = self.graph.plot(connect="finite")
        self.best_path = self.graph.plot()
        self.selected_path = self.graph.plot()
        self.surface = pg.ImageItem(axisOrder="col-major")
        self.surface.setZValue(-10)
        self.graph.addItem(self.surface)
        self.color_bar = pg.ColorBarItem(
            colorMap=pg.colormap.get("viridis"),
            interactive=False,
            colorMapMenu=False,
            label=text("objective"),
        )
        self.color_bar.setImageItem(self.surface, insert_in=self.graph.plotItem)
        self.color_bar.hide()
        self.population = pg.ScatterPlotItem(size=10, pxMode=True)
        self.best = pg.ScatterPlotItem(size=17, symbol="d", pxMode=True)
        self.selected = pg.ScatterPlotItem(size=21, symbol="o", pxMode=True)
        for item in (self.population, self.best, self.selected):
            self.graph.addItem(item)
        self.population.sigClicked.connect(self._clicked)
        self.best.sigClicked.connect(self._clicked)
        layout.addWidget(self.graph, 1)
        self.legend = PlotLegend(
            (
                ("legend_population", "point"),
                ("legend_best", "diamond"),
                ("legend_selected", "ring"),
            )
        )
        layout.addWidget(self.legend)
        self.snapshot: GenerationSnapshot | None = None
        self._curve: FunctionCurve | None = None
        self.domains: tuple[Interval, ...] = (Interval(0, 1),)
        self.dimensions = 1

    def set_problem(self, config: ExperimentConfig) -> None:
        self.domains = config.domains
        self.dimensions = len(config.domains)
        self._curve = None
        self.curve.clear()
        self.surface.clear()
        self.color_bar.setVisible(self.dimensions == 2)
        self.explanation.setVisible(self.dimensions > 2)
        self.header.title.setText(
            text(
                "population_chart_title"
                if self.dimensions == 1
                else "surface_chart_title"
                if self.dimensions == 2
                else "parallel_chart_title"
            )
        )
        self.graph.getAxis("bottom").setTicks(None)
        self.graph.setLabel(
            "bottom",
            text(
                "phenotype_axis"
                if self.dimensions == 1
                else "x1_axis"
                if self.dimensions == 2
                else "variable_axis"
            ),
        )
        self.graph.setLabel(
            "left",
            text(
                "objective_axis"
                if self.dimensions == 1
                else "x2_axis"
                if self.dimensions == 2
                else "normalized_axis"
            ),
        )
        self.graph.showGrid(x=True, y=True, alpha=0.12 if self.dimensions != 2 else 0)
        if self.dimensions > 2:
            self.graph.getAxis("bottom").setTicks(
                [[(i + 1, f"x{i + 1}") for i in range(self.dimensions)]]
            )
        self.header.reset_button.setEnabled(self.dimensions > 2)
        self.reset_view()

    def set_surface(self, data: FunctionSurface) -> None:
        values = np.asarray(data.values)
        self.surface.setImage(values, autoLevels=False)
        low, high = float(values.min()), float(values.max())
        self.color_bar.setLevels((low, high if high > low else low + 1))
        dx, dy = data.x[1] - data.x[0], data.y[1] - data.y[0]
        self.surface.setRect(
            QRectF(
                data.x[0] - dx / 2,
                data.y[0] - dy / 2,
                data.x[-1] - data.x[0] + dx,
                data.y[-1] - data.y[0] + dy,
            )
        )
        self.header.reset_button.setEnabled(True)
        self.reset_view()

    def set_curve(self, curve: FunctionCurve) -> None:
        self._curve = curve
        self.curve.setData(curve.x, curve.y)
        self.header.reset_button.setEnabled(True)
        self.reset_view()

    def reset_view(self) -> None:
        if self.dimensions == 1 and self._curve is not None:
            self.graph.setXRange(self._curve.x[0], self._curve.x[-1], padding=0.02)
            self.graph.setYRange(min(self._curve.y), max(self._curve.y), padding=0.06)
        elif self.dimensions == 2:
            self.graph.setXRange(
                self.domains[0].lower, self.domains[0].upper, padding=0.02
            )
            self.graph.setYRange(
                self.domains[1].lower, self.domains[1].upper, padding=0.02
            )
        elif self.dimensions > 2:
            self.graph.setXRange(1, self.dimensions, padding=0.05)
            self.graph.setYRange(0, 1, padding=0.05)

    def _coordinates(self, individual: Individual) -> tuple[list[float], list[float]]:
        if self.dimensions == 1:
            assert individual.objective_value is not None
            return [individual.phenotype[0]], [individual.objective_value]
        if self.dimensions == 2:
            return [individual.phenotype[0]], [individual.phenotype[1]]
        return list(range(1, self.dimensions + 1)), [
            (value - domain.lower) / (domain.upper - domain.lower)
            for value, domain in zip(individual.phenotype, self.domains, strict=True)
        ]

    def set_snapshot(self, snapshot: GenerationSnapshot) -> None:
        self.snapshot = snapshot
        members = snapshot.population.individuals
        coordinates = [self._coordinates(item) for item in members]
        self.population.setData(
            x=[x for xs, _ in coordinates for x in xs],
            y=[y for _, ys in coordinates for y in ys],
            data=[
                item.identifier
                for item in members
                for _ in range(self.dimensions if self.dimensions > 2 else 1)
            ],
        )
        if self.dimensions > 2:
            self.projection_lines.setData(
                [value for xs, _ in coordinates for value in (*xs, float("nan"))],
                [value for _, ys in coordinates for value in (*ys, float("nan"))],
            )
        best = snapshot.statistics.best_individual
        x, y = self._coordinates(best)
        self.best.setData(x=x, y=y, data=[best.identifier] * len(x))
        if self.dimensions > 2:
            self.best_path.setData(x, y)

    def select_individual(self, identifier: int) -> None:
        if self.snapshot is None:
            return
        individual = next(
            item for item in self.snapshot.population if item.identifier == identifier
        )
        x, y = self._coordinates(individual)
        self.selected.setData(x=x, y=y)
        if self.dimensions > 2:
            self.selected_path.setData(x, y)

    def clear(self) -> None:
        self.snapshot = None
        for item in (self.population, self.best, self.selected):
            item.clear()
        for item in (self.projection_lines, self.best_path, self.selected_path):
            item.clear()

    def apply_theme(self, colors: ThemeColors) -> None:
        style_plot(self.graph, colors)
        self.legend.apply_theme(colors)
        self.curve.setPen(pg.mkPen(colors.accent, width=2))
        self.projection_lines.setPen(pg.mkPen(colors.muted, width=1))
        self.best_path.setPen(pg.mkPen(colors.accent, width=2.5))
        self.selected_path.setPen(pg.mkPen(colors.foreground, width=2))
        self.color_bar.axis.setPen(colors.border)
        self.color_bar.axis.setTextPen(colors.foreground)
        self.color_bar.axis.setLabel("", siPrefixEnableRanges=())
        self.color_bar.getAxis("left").setLabel(
            text("objective"),
            color=colors.foreground,
            siPrefixEnableRanges=(),
            **{"font-size": "10pt"},
        )
        self.color_bar.axis.setSIPrefixEnableRanges(())
        self.color_bar.axis.enableAutoSIPrefix(False)
        self.population.setPen(pg.mkPen(colors.surface, width=1))
        self.population.setBrush(pg.mkBrush(colors.foreground))
        self.best.setPen(pg.mkPen(colors.surface, width=1.5))
        self.best.setBrush(pg.mkBrush(colors.accent))
        self.selected.setPen(pg.mkPen(colors.foreground, width=2))
        self.selected.setBrush(pg.mkBrush(None))

    def _clicked(self, _item: object, points: list[Any], _event: object) -> None:
        if points:
            self.individual_selected.emit(int(points[0].data()))
