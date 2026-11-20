from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from ..csv_io import write_points_csv
from ..evaluation import evaluate_tree
from ..models import ExprNode, RepairConfig, format_number
from ..plotting import CurveData, sample_curve
from ..sampling import SamplingConfig
from .theme import BLUE, BORDER, INK, MUTED, ORANGE, PAPER
from .widgets import button, label


class CurveCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.data: CurveData | None = None
        self.current_point: tuple[float, float] | None = None
        self.mouse_point: QPointF | None = None
        self.setMinimumHeight(80)
        self.setMouseTracking(True)
        self.setAccessibleName("Gráfica de la función. Mueve el cursor para consultar coordenadas.")

    def plot_rect(self) -> QRectF:
        return QRectF(60, 10, max(10, self.width() - 82), max(10, self.height() - 40))

    def map_point(self, x: float, y: float) -> QPointF:
        d, r = self.data, self.plot_rect()
        return QPointF(r.left() + (x - d.x_min) / (d.x_max - d.x_min) * r.width(), r.bottom() - (y - d.y_min) / (d.y_max - d.y_min) * r.height())

    def mouseMoveEvent(self, event) -> None:
        self.mouse_point = event.position()
        self.update()

    def leaveEvent(self, event) -> None:
        self.mouse_point = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(PAPER))
        d, r = self.data, self.plot_rect()
        if d is None:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Construye una expresión para explorar su curva.")
            return
        painter.setFont(QFont("Inter", 8))
        for i in range(6):
            x = d.x_min + (d.x_max - d.x_min) * i / 5
            xx = self.map_point(x, d.y_min).x()
            painter.setPen(QPen(QColor("#E6E4D9"), 1))
            painter.drawLine(QPointF(xx, r.top()), QPointF(xx, r.bottom()))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(xx - 35, r.bottom() + 5, 70, 20), Qt.AlignmentFlag.AlignCenter, format_number(x))
        for i in range(5):
            y = d.y_min + (d.y_max - d.y_min) * i / 4
            yy = self.map_point(d.x_min, y).y()
            painter.setPen(QPen(QColor("#E6E4D9"), 1))
            painter.drawLine(QPointF(r.left(), yy), QPointF(r.right(), yy))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(0, yy - 10, 52, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{y:.2g}".replace("e+0", "e").replace("e-0", "e-"))
        painter.save()
        painter.setClipRect(r.adjusted(-1, -1, 1, 1))
        painter.setPen(QPen(QColor("#B7B5AC"), 1.2))
        if d.x_min <= 0 <= d.x_max:
            p = self.map_point(0, 0)
            painter.drawLine(QPointF(p.x(), r.top()), QPointF(p.x(), r.bottom()))
        if d.y_min <= 0 <= d.y_max:
            p = self.map_point(0, 0)
            painter.drawLine(QPointF(r.left(), p.y()), QPointF(r.right(), p.y()))
        painter.setPen(QPen(QColor(ORANGE if d.repaired else BLUE), 2.2))
        for segment in d.segments:
            if not segment:
                continue
            path = QPainterPath(self.map_point(*segment[0]))
            for x, y in segment[1:]:
                path.lineTo(self.map_point(x, y))
            painter.drawPath(path)
        if self.current_point:
            point = self.map_point(*self.current_point)
            painter.setBrush(QColor(BLUE))
            painter.setPen(QPen(QColor(PAPER), 2))
            painter.drawEllipse(point, 4, 4)
        if self.mouse_point and r.contains(self.mouse_point):
            px = self.mouse_point.x()
            painter.setPen(QPen(QColor(MUTED), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(px, r.top()), QPointF(px, r.bottom()))
        painter.restore()
        if self.mouse_point and r.contains(self.mouse_point):
            x = d.x_min + (self.mouse_point.x() - r.left()) / r.width() * (d.x_max - d.x_min)
            points = (p for segment in d.segments for p in segment)
            nearest = min(points, key=lambda p: abs(p[0] - x), default=None)
            if nearest:
                painter.setPen(QColor(INK))
                painter.drawText(QRectF(r.left() + 8, 13, r.width() - 16, 20), Qt.AlignmentFlag.AlignLeft, f"{d.variable} ≈ {format_number(nearest[0])}    f ≈ {format_number(nearest[1])}")
        if not d.valid_samples:
            painter.setPen(QColor(ORANGE))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "Sin valores reales en este intervalo.\nCambia el intervalo o activa la curva reparada.")


class CurvePanel(QWidget):
    settingsChanged = Signal()
    statusChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.root: ExprNode | None = None
        self.variables: dict[str, float] = {}
        self.config = RepairConfig()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 0)
        layout.setSpacing(3)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(label("Variable", "Muted"))
        self.variable = QComboBox()
        self.variable.setMinimumWidth(62)
        self.variable.addItem("x")
        controls.addWidget(self.variable)
        controls.addWidget(label("Intervalo", "Muted"))
        self.minimum, self.maximum = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, value in ((self.minimum, -10), (self.maximum, 10)):
            spin.setRange(-10000, 10000)
            spin.setDecimals(3)
            spin.setValue(value)
            spin.setFixedWidth(95)
            spin.setKeyboardTracking(False)
            controls.addWidget(spin)
        self.minimum.setAccessibleName("Inicio del intervalo")
        self.maximum.setAccessibleName("Final del intervalo")
        controls.addWidget(label("Paso", "Muted"))
        self.step = QDoubleSpinBox()
        self.step.setDecimals(6)
        self.step.setRange(0.000001, 10000)
        self.step.setValue(0.05)
        self.step.setSingleStep(0.001)
        self.step.setFixedWidth(108)
        self.step.setKeyboardTracking(False)
        self.step.setAccessibleName("Paso del muestreo y del CSV")
        self.step.setToolTip("x = inicio + i × paso. El extremo final se incluye si el paso lo alcanza. Máximo 10001 puntos.")
        controls.addWidget(self.step)
        controls.addStretch()
        layout.addLayout(controls)
        self.canvas = CurveCanvas()
        layout.addWidget(self.canvas, 1)
        bottom = QHBoxLayout()
        self.note = label("", "Muted", True)
        self.note.setMinimumWidth(0)
        bottom.addWidget(self.note, 1)
        self.repaired = QCheckBox("Curva reparada")
        self.repaired.setToolTip("Aplica las mismas políticas de reparación del evaluador a cada punto de la curva y a su CSV.")
        bottom.addWidget(self.repaired)
        self.export = button("Exportar CSV", self.export_csv, glyph="export")
        self.export.setEnabled(False)
        bottom.addWidget(self.export)
        layout.addLayout(bottom)
        for signal in (self.minimum.valueChanged, self.maximum.valueChanged, self.step.valueChanged, self.variable.currentTextChanged, self.repaired.toggled):
            signal.connect(self.refresh)

    def sampling_config(self) -> SamplingConfig:
        return SamplingConfig(self.minimum.value(), self.maximum.value(), self.step.value())

    def curve_config(self) -> RepairConfig:
        return replace(self.config, enabled=self.repaired.isChecked())

    def set_sampling(self, config: SamplingConfig) -> None:
        for widget, value in ((self.minimum, config.x_min), (self.maximum, config.x_max), (self.step, config.step)):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.refresh()

    def export_csv(self) -> None:
        data = self.canvas.data
        if data is None or not data.points:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar puntos de la curva", "curva.csv", "Datos CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            count = write_points_csv(path, data.points, step=self.step.value(), x_min=data.x_min)
        except (OSError, ValueError) as exc:
            self.note.setText(f"No se pudo exportar: {exc}")
        else:
            missing = f" · {data.invalid_samples} valores y vacíos por dominio" if data.invalid_samples else ""
            self.statusChanged.emit(f"CSV guardado: {Path(path).name} · {count} filas{missing}")

    def set_expression(self, root: ExprNode, variables: dict[str, float], config: RepairConfig, active_vars: list[str], result: float | None) -> None:
        self.root, self.variables, self.config = root, dict(variables), config
        previous = self.variable.currentText()
        self.variable.blockSignals(True)
        self.variable.clear()
        self.variable.addItems(active_vars or ["x"])
        self.variable.setCurrentText(previous if previous in active_vars else (active_vars[0] if active_vars else "x"))
        self.variable.blockSignals(False)
        self.refresh()

    def refresh(self, *_args) -> None:
        if self.root is None:
            return
        try:
            cfg = self.curve_config()
            value, _, error, _ = evaluate_tree(self.root, self.variables, cfg, annotate=False, trace=False)
            self.canvas.current_point = (self.variables.get(self.variable.currentText(), 1), value) if error is None and value is not None else None
            data = sample_curve(self.root, self.variables, variable=self.variable.currentText(), x_min=self.minimum.value(), x_max=self.maximum.value(), step=self.step.value(), repair_config=cfg)
        except ValueError as exc:
            self.note.setText(str(exc))
            self.canvas.data = None
            self.export.setEnabled(False)
        else:
            self.canvas.data = data
            self.export.setEnabled(True)
            prefix = "Reparada" if data.repaired else "Dominio real"
            extra = f" · {data.invalid_samples} puntos fuera de dominio" if data.invalid_samples else ""
            extra += f" · {data.repaired_samples} puntos reparados" if data.repaired_samples else ""
            self.note.setText(f"{prefix} · {data.valid_samples} muestras{extra} · radianes")
        self.canvas.update()
        self.settingsChanged.emit()
