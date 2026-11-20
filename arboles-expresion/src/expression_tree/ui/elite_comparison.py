"""Live, sampled reference-versus-elite curves with generation inspection."""
from __future__ import annotations

import bisect
import math
import sys
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

from ..evolution import EvolutionRun, GenerationElites, Individual
from ..sampling import SamplePoint, sample_points
from .theme import BLUE, BORDER, INK, MUTED, ORANGE, PAPER
from .widgets import label


def axis_bounds(values: list[float]) -> tuple[float, float, float]:
    """Scale first to keep coordinate arithmetic finite, including extreme CSV x."""
    scale = max(abs(v) for v in values) or 1.0
    low, high = min(values) / scale, max(values) / scale
    padding = (high - low) * .06 if high > low else .1
    bound = sys.float_info.max / scale if scale > 1 else math.inf
    return scale, max(-bound, low - padding), min(bound, high + padding)


class EliteComparisonChart(QWidget):
    sampleHovered = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.reference: tuple[SamplePoint, ...] = ()
        self.predictions: tuple[SamplePoint, ...] = ()
        self.variable = "x"
        self.order: list[int] = []
        self.positions: list[float] = []
        self.x_axis = self.y_axis = (1.0, -1.0, 1.0)
        self.hover_index: int | None = None
        self.setMinimumHeight(220)
        self.setMouseTracking(True)
        self.setAccessibleName("Comparación de la referencia y la predicción del élite sobre los mismos puntos")

    def set_data(self, reference: tuple[SamplePoint, ...], predictions: tuple[SamplePoint, ...], variable: str) -> None:
        if len(reference) != len(predictions) or any(r.x != p.x for r, p in zip(reference, predictions)):
            raise ValueError("Las dos curvas deben compartir exactamente sus valores x.")
        self.reference, self.predictions, self.variable = reference, predictions, variable
        self.hover_index = None
        self.order = sorted(range(len(reference)), key=lambda i: reference[i].x)
        if reference:
            self.x_axis = axis_bounds([p.x for p in reference])
            values = [p.y for p in (*reference, *predictions) if p.y is not None and math.isfinite(p.y)]
            self.y_axis = axis_bounds(values or [0.0])
            self.positions = [reference[i].x / self.x_axis[0] for i in self.order]
        else:
            self.positions = []
        self.update()

    def plot_rect(self) -> QRectF:
        return QRectF(74, 34, max(10, self.width() - 96), max(10, self.height() - 82))

    def map_point(self, x: float, y: float) -> QPointF:
        xs, xl, xh = self.x_axis
        ys, yl, yh = self.y_axis
        rect = self.plot_rect()
        return QPointF(rect.left() + (x / xs - xl) / (xh - xl) * rect.width(),
                       rect.bottom() - (y / ys - yl) / (yh - yl) * rect.height())

    def segments(self, points: tuple[SamplePoint, ...]) -> list[list[SamplePoint]]:
        segments, current = [], []
        for i in self.order:
            point = points[i]
            if point.y is None or not math.isfinite(point.y):
                if current:
                    segments.append(current)
                    current = []
                continue
            if current and point.x <= current[-1].x:
                segments.append(current)
                current = []
            current.append(point)
        if current:
            segments.append(current)
        return segments

    def mouseMoveEvent(self, event) -> None:
        rect = self.plot_rect()
        if not self.order or not rect.contains(event.position()):
            self._hover(None)
            return
        _, low, high = self.x_axis
        position = low + (event.position().x() - rect.left()) / rect.width() * (high - low)
        index = bisect.bisect_left(self.positions, position)
        candidates = [i for i in (index - 1, index) if 0 <= i < len(self.order)]
        nearest = min(candidates, key=lambda i: abs(self.positions[i] - position))
        self._hover(self.order[nearest])

    def leaveEvent(self, event) -> None:
        self._hover(None)
        super().leaveEvent(event)

    def _hover(self, index: int | None) -> None:
        self.hover_index = index
        self.sampleHovered.emit(index)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(PAPER))
        if not self.reference:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect().adjusted(20, 20, -20, -20), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Inicia la ejecución para comparar la referencia con sus élites en cada generación.")
            return
        painter.setFont(QFont("Inter", 9))
        rect = self.plot_rect()
        for x, color, style, text in ((rect.left(), ORANGE, Qt.PenStyle.DashLine, "Referencia"),
                                     (rect.left() + 155, BLUE, Qt.PenStyle.SolidLine, "Predicción")):
            painter.setPen(QPen(QColor(color), 2, style))
            painter.drawLine(QPointF(x, 12), QPointF(x + 25, 12))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(x + 33, 1, 180, 22), Qt.AlignmentFlag.AlignVCenter, text)
        for fraction in (0, .25, .5, .75, 1):
            x = rect.left() + fraction * rect.width()
            y = rect.bottom() - fraction * rect.height()
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QColor(MUTED))
            xs, xl, xh = self.x_axis
            ys, yl, yh = self.y_axis
            painter.drawText(QRectF(x - 42, rect.bottom() + 6, 84, 20), Qt.AlignmentFlag.AlignCenter,
                             f"{(xl + fraction * (xh - xl)) * xs:.4g}")
            painter.drawText(QRectF(0, y - 10, 65, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{(yl + fraction * (yh - yl)) * ys:.4g}")
        painter.drawText(QRectF(rect.left(), rect.bottom() + 25, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, self.variable)
        painter.drawText(QRectF(0, 1, 65, 22), Qt.AlignmentFlag.AlignRight, "y")
        painter.save()
        painter.setClipRect(rect.adjusted(-1, -1, 1, 1))
        # Draw the dashed reference last: both colors stay visible for a perfect fit.
        for points, color, style in ((self.predictions, BLUE, Qt.PenStyle.SolidLine),
                                     (self.reference, ORANGE, Qt.PenStyle.DashLine)):
            painter.setPen(QPen(QColor(color), 2.2, style))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for segment in self.segments(points):
                path = QPainterPath(self.map_point(segment[0].x, segment[0].y))
                for point in segment[1:]:
                    path.lineTo(self.map_point(point.x, point.y))
                painter.drawPath(path)
                if len(points) <= 50 or len(segment) == 1:
                    painter.save()
                    painter.setPen(QPen(QColor(color), 1.5))
                    for point in segment:
                        painter.drawEllipse(self.map_point(point.x, point.y), 2.5, 2.5)
                    painter.restore()
        if self.hover_index is not None:
            point = self.reference[self.hover_index]
            x = self.map_point(point.x, point.y).x()
            painter.setPen(QPen(QColor(MUTED), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        painter.restore()


class EliteComparisonPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.run: EvolutionRun | None = None
        self.snapshots: tuple[GenerationElites, ...] = ()
        self.selected_generation: int | None = None
        self.selected_individual: Individual | None = None
        self._curve_cache = None
        self._latest_predictions: tuple[SamplePoint, ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 0)
        layout.setSpacing(9)
        layout.addWidget(label("Referencia y élites", "PanelTitle"))
        layout.addWidget(label("Sigue la mejor solución en vivo o consulta los mejores individuos de una generación anterior.", "Muted", True))
        row = QHBoxLayout()
        row.addWidget(label("Generación", "Muted"))
        self.generation_picker = QComboBox()
        self.generation_picker.addItem("En vivo · última generación", None)
        self.generation_picker.setAccessibleName("Generación de la comparación; en vivo sigue la última")
        row.addWidget(self.generation_picker, 1)
        row.addWidget(label("Individuo", "Muted"))
        self.elite_picker = QComboBox()
        self.elite_picker.setAccessibleName("Élite de la generación elegida, ordenado por adaptación")
        row.addWidget(self.elite_picker, 1)
        layout.addLayout(row)
        self.summary = label("Los datos aparecerán al evaluar la población inicial.", wrap=True)
        layout.addWidget(self.summary)
        self.warning = label("", "Warning", True)
        self.warning.hide()
        layout.addWidget(self.warning)
        self.equation = label("", "Muted", True)
        self.equation.setMinimumWidth(0)
        self.equation.setMaximumHeight(40)
        self.equation.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.equation)
        self.chart = EliteComparisonChart()
        layout.addWidget(self.chart, 1)
        self.coordinates = label("Mueve el cursor sobre la gráfica para consultar ambos valores.", "Muted", True)
        layout.addWidget(self.coordinates)
        self.note = label("La comparación usa los mismos puntos y la misma evaluación que la corrida.", "Muted", True)
        layout.addWidget(self.note)
        self.generation_picker.setEnabled(False)
        self.elite_picker.setEnabled(False)
        self.generation_picker.currentIndexChanged.connect(self._generation_changed)
        self.elite_picker.currentIndexChanged.connect(self._elite_changed)
        self.chart.sampleHovered.connect(self._show_coordinates)

    def set_run(self, run: EvolutionRun) -> None:
        new_run = self.run is not run
        self.run = run
        self.snapshots = tuple(run.elite_history)
        self._latest_predictions = run.latest_elite_predictions
        if new_run:
            self._curve_cache = None
            self.generation_picker.blockSignals(True)
            self.generation_picker.clear()
            self.generation_picker.addItem("En vivo · última generación", None)
            self.generation_picker.blockSignals(False)
        self.generation_picker.blockSignals(True)
        for snapshot in self.snapshots[self.generation_picker.count() - 1:]:
            self.generation_picker.addItem(f"Generación {snapshot.generation}", snapshot.generation)
        self.generation_picker.blockSignals(False)
        self.generation_picker.setEnabled(bool(self.snapshots))
        if new_run:
            self.elite_picker.blockSignals(True)
            self.elite_picker.clear()
            self.elite_picker.blockSignals(False)
        self._generation_changed()

    def _generation_changed(self, *_args) -> None:
        if not self.snapshots:
            return
        selected = self.generation_picker.currentData()
        snapshot = self.snapshots[-1] if selected is None else self.snapshots[selected]
        rank = self.elite_picker.currentData() or 0
        self.selected_generation = snapshot.generation
        self.elite_picker.blockSignals(True)
        self.elite_picker.clear()
        for i, ind in enumerate(snapshot.individuals):
            name = f"Élite {i + 1}" if self.run.config.elite_count else "Mejor individuo"
            self.elite_picker.addItem(f"{name} · #{ind.id}", i)
        self.elite_picker.setCurrentIndex(min(rank, len(snapshot.individuals) - 1))
        self.elite_picker.blockSignals(False)
        self.elite_picker.setEnabled(len(snapshot.individuals) > 1)
        self._elite_changed()

    @staticmethod
    def _value(value: float | None) -> str:
        return "—" if value is None or not math.isfinite(value) else f"{value:.6g}"

    def _elite_changed(self, *_args) -> None:
        if not self.snapshots or self.elite_picker.currentData() is None:
            return
        rank = self.elite_picker.currentData()
        individual = self.snapshots[self.selected_generation].individuals[rank]
        self.selected_individual = individual
        key = (self.selected_generation, rank)
        if self._curve_cache is not None and self._curve_cache[0] == key:
            predictions = self._curve_cache[1]
        elif self.selected_generation == self.snapshots[-1].generation and rank == 0:
            predictions = self._latest_predictions
        else:
            predictions = sample_points(individual.root, self.run.variables, (p.x for p in self.run.reference),
                variable=self.run.config.generation.variable, repair_config=replace(self.run.repairs))
        self._curve_cache = (key, predictions)
        self.chart.set_data(self.run.reference, predictions, self.run.config.generation.variable)
        self.summary.setText(f"Generación {self.selected_generation} · #{individual.id} · "
            f"MSE {self._value(individual.metrics.get('mse'))} · NMSE {self._value(individual.metrics.get('nmse'))} · "
            f"R² {self._value(individual.metrics.get('r2'))}")
        self.equation.setText("Predicción: " + individual.expression)
        self.equation.setToolTip(individual.expression)
        invalid = sum(point.y is None for point in predictions)
        self.warning.setText(individual.error or (f"{invalid} predicciones fuera de dominio; los huecos no se conectan." if invalid else ""))
        self.warning.setVisible(bool(self.warning.text()))
        policy = "evaluación protegida" if self.run.repairs.enabled else "dominio real"
        elite_note = (f"Los {self.run.config.elite_count} mejores de cada generación." if self.run.config.elite_count else
                      "Elitismo desactivado: se muestra el mejor individuo.")
        self.note.setText(f"{len(self.run.reference)} puntos exactos · {policy} · {individual.repaired_samples} predicciones reparadas. " + elite_note)
        self._show_coordinates(None)

    def _show_coordinates(self, index: int | None) -> None:
        if index is None:
            self.coordinates.setText("Mueve el cursor sobre la gráfica para consultar ambos valores.")
            return
        reference, prediction = self.chart.reference[index], self.chart.predictions[index]
        self.coordinates.setText(f"{self.chart.variable} = {reference.x:.12g} · referencia = {reference.y:.12g} · "
                                 f"predicción = {self._value(prediction.y)}")
