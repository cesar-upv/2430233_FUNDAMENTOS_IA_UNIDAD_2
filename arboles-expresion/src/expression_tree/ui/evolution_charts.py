from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..evolution import GenerationStats, SelectionResult
from .theme import BLUE, BORDER, GREEN, INK, MUTED, ORANGE, PAPER


class SelectionChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result: SelectionResult | None = None
        self.ids: list[int] = []
        self.setMinimumHeight(115)
        self.setAccessibleName("Probabilidades de selección y posiciones de los punteros")

    def set_selection(self, result: SelectionResult, ids: list[int]) -> None:
        self.result, self.ids = result, ids
        self.update()

    def clear(self) -> None:
        self.result, self.ids = None, []
        self.setToolTip("")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(MUTED))
        if not self.result:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Selecciona una pareja para ver cómo se eligió.")
            return
        result = self.result
        if result.contestants:
            for i, group in enumerate(result.contestants[:2]):
                winner = self.ids[result.indices[i]]
                text = "  ·  ".join(f"#{self.ids[index]}" for index in group)
                p.setPen(QColor(INK))
                p.drawText(QRectF(0, i * 44, self.width(), 40), Qt.AlignmentFlag.AlignVCenter,
                           f"Torneo {i + 1}:  {text}     →     #{winner} gana")
            return
        left, width = 8, self.width() - 16
        colors = (BLUE, GREEN, ORANGE, "#5E409D", "#1C6C66")
        position = left
        for i, probability in enumerate(result.probabilities):
            size = width * probability
            p.fillRect(QRectF(position, 28, size, 32), QColor(colors[i % len(colors)]))
            if size > 38:
                p.setPen(QColor(PAPER))
                p.drawText(QRectF(position, 28, size, 32), Qt.AlignmentFlag.AlignCenter, f"#{self.ids[i]}")
            position += size
        for i, point in enumerate(result.pointers):
            x = left + width * point
            p.setPen(QPen(QColor(INK), 1.8))
            p.drawLine(QPointF(x, 20), QPointF(x, 68))
            p.drawText(QRectF(max(0, min(x - 36, self.width() - 72)), 73, 72, 20),
                       Qt.AlignmentFlag.AlignCenter, f"{point:.3f}")
        self.setToolTip(" · ".join(f"#{key}: {probability:.2%}" for key, probability in zip(self.ids, result.probabilities)))


class ProgressChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.history: list[GenerationStats] = []
        self.setMinimumHeight(240)
        self.setAccessibleName("Adaptación por generación; menor pérdida es mejor")

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = QRectF(75, 22, max(40, self.width() - 100), max(50, self.height() - 65))
        finite = [v for s in self.history for v in (s.best, s.mean) if math.isfinite(v)]
        p.setPen(QColor(MUTED))
        if not finite:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "La gráfica aparecerá al evaluar una población con individuos válidos.")
            return
        # log1p is defined at zero and keeps large losses legible without hiding the optimum.
        maximum = max(math.log1p(v) for v in finite) or 1
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(QColor(BORDER), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 10, 65, 20), Qt.AlignmentFlag.AlignRight, f"{math.expm1(maximum * i / 4):.2g}")
        for attribute, color in (("mean", ORANGE), ("best", BLUE)):
            path = QPainterPath()
            connected = False
            for i, stats in enumerate(self.history):
                value = getattr(stats, attribute)
                if not math.isfinite(value):
                    connected = False
                    continue
                point = QPointF(plot.left() + plot.width() * i / max(1, len(self.history) - 1),
                                plot.bottom() - plot.height() * math.log1p(value) / maximum)
                if connected:
                    path.lineTo(point)
                else:
                    path.moveTo(point)
                connected = True
                p.setPen(QPen(QColor(color), 2))
                p.drawEllipse(point, 2.5, 2.5)
            p.setPen(QPen(QColor(color), 2))
            p.drawPath(path)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(plot.left(), plot.bottom() + 15, plot.width(), 24), Qt.AlignmentFlag.AlignCenter,
                   f"Generación 0 → {self.history[-1].generation} · escala log(1 + pérdida)")
