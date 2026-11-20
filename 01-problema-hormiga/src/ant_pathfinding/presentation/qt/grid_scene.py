"""Scene drawing for one scenario: cell geometry, element items and mouse input.

Cells are square :data:`CELL_PX` units with ``x`` to the right and ``y`` downwards, which is
how the domain numbers them; every mouse position is floored onto that grid before it becomes
a :class:`~ant_pathfinding.domain.position.Position`.
"""

from __future__ import annotations

from math import floor

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.presentation.qt.editor import EditTool, ScenarioEditor

CELL_PX = 40
"""Drawn size of one cell; the view scales the scene, so this is only a design unit."""

_START_COLOR = QColor("#2f9e52")
_GOAL_COLOR = QColor("#2b6cb0")
_FOOD_COLOR = QColor("#e0a11b")
_BLOCKED_COLOR = QColor("#4a4a4a")
_OUTLINE_COLOR = QColor("#1c1c1c")
_LINE_COLOR = QColor("#b8b8b8")


class GridScene(QGraphicsScene):
    """Draws one scenario and turns mouse positions into cell edits."""

    def __init__(self, editor: ScenarioEditor) -> None:
        super().__init__()
        self._editor = editor
        self._scenario = editor.scenario
        self._drag_tool: EditTool | None = None
        self._drag_cell: Position | None = None

    @property
    def cell_size(self) -> int:
        return CELL_PX

    @property
    def cell_count(self) -> int:
        """Test accessor for the number of cells the current grid draws."""
        return self._scenario.grid.width * self._scenario.grid.height

    def set_scenario(self, scenario: AntScenario) -> None:
        self._scenario = scenario
        self.clear()
        self.addItem(_GridLines(scenario.grid, CELL_PX))
        for position in sorted(scenario.grid.blocked):
            self.addItem(self._rect(position, _BLOCKED_COLOR))
        for position in sorted(scenario.foods):
            self.addItem(self._ellipse(position, _FOOD_COLOR, 8.0))
        self.addItem(self._ellipse(scenario.start, _START_COLOR, 3.0))
        self.addItem(self._rect(scenario.goal, _GOAL_COLOR))
        self.setSceneRect(
            0.0,
            0.0,
            scenario.grid.width * CELL_PX,
            scenario.grid.height * CELL_PX,
        )

    def cell_rect(self, position: Position) -> QRectF:
        return QRectF(
            position.x * CELL_PX,
            position.y * CELL_PX,
            CELL_PX,
            CELL_PX,
        )

    def position_at(self, point: QPointF) -> Position | None:
        """Return the cell containing ``point``, or ``None`` when it is outside the grid."""
        position = Position(floor(point.x() / CELL_PX), floor(point.y() / CELL_PX))
        return position if self._scenario.grid.contains(position) else None

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        position = self.position_at(event.scenePos())
        if position is None:
            return
        if self._editor.tool is EditTool.SELECT:
            self._drag_tool = self._tool_at(position)
            self._drag_cell = position
        else:
            self._editor.edit(self._editor.tool, position)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._drag_to(self.position_at(event.scenePos()))

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._drag_to(self.position_at(event.scenePos()))
        self._drag_tool = None
        self._drag_cell = None

    def _drag_to(self, position: Position | None) -> None:
        source = self._drag_cell
        if position is None or self._drag_tool is None or source is None or position == source:
            return
        if self._editor.move(self._drag_tool, source, position):
            self._drag_cell = position

    def _tool_at(self, position: Position) -> EditTool | None:
        """The kind of element on ``position``, which is what a select-tool drag would move."""
        scenario = self._scenario
        if position == scenario.start:
            return EditTool.START
        if position == scenario.goal:
            return EditTool.GOAL
        if position in scenario.foods:
            return EditTool.FOOD
        if position in scenario.grid.blocked:
            return EditTool.OBSTACLE
        return None

    def _rect(self, position: Position, color: QColor) -> QGraphicsRectItem:
        item = QGraphicsRectItem(self.cell_rect(position).adjusted(1.0, 1.0, -1.0, -1.0))
        item.setBrush(QBrush(color))
        item.setPen(QPen(_OUTLINE_COLOR, 1.0))
        item.setZValue(1)
        return item

    def _ellipse(self, position: Position, color: QColor, inset: float) -> QGraphicsEllipseItem:
        item = QGraphicsEllipseItem(self.cell_rect(position).adjusted(inset, inset, -inset, -inset))
        item.setBrush(QBrush(color))
        item.setPen(QPen(_OUTLINE_COLOR, 1.0))
        item.setZValue(1)
        return item


class _GridLines(QGraphicsItem):
    """The cell borders of one grid, drawn as a single item."""

    def __init__(self, grid: Grid, cell_px: int) -> None:
        super().__init__()
        self._grid = grid
        self._cell_px = cell_px

    def boundingRect(self) -> QRectF:
        return QRectF(0.0, 0.0, self._grid.width * self._cell_px, self._grid.height * self._cell_px)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setPen(QPen(_LINE_COLOR, 1.0))
        width = self._grid.width * self._cell_px
        height = self._grid.height * self._cell_px
        for column in range(self._grid.width + 1):
            x = float(column * self._cell_px)
            painter.drawLine(QPointF(x, 0.0), QPointF(x, height))
        for row in range(self._grid.height + 1):
            y = float(row * self._cell_px)
            painter.drawLine(QPointF(0.0, y), QPointF(width, y))
