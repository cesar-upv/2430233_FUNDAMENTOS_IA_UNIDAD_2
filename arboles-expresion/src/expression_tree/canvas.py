from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from .models import ExprNode, format_number
from .tree import to_infix_string, traverse_preorder
from .ui.theme import BLUE, BORDER, INK, MUTED, NODE_STYLES, ORANGE, PAPER


class NodeGraphicsItem(QGraphicsItem):
    def __init__(self, node: ExprNode, canvas: ExpressionTreeCanvas, collapsed: int = 0) -> None:
        super().__init__()
        self.node, self.canvas, self.collapsed = node, canvas, collapsed
        self.is_selected = self.is_active_step = False
        self.visit_order: int | None = None
        self.eval_visible_now = True
        self.recessive = False
        self.highlight_color: str | None = None
        self.setPos(node.x, node.y)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh()
        self.setZValue(2)

    def refresh(self) -> None:
        message = f"{to_infix_string(self.node)}\nValor: {format_number(self.node.evaluated)}"
        if self.node.repair_note:
            message += f"\n{self.node.repair_note}"
        if self.collapsed:
            message += f"\n{self.collapsed} nodos ocultos. Aumenta los niveles visibles para explorarlos."
        if self.recessive:
            message += "\nGen recesivo: se conserva, pero no participa en la evaluación."
        self.setToolTip(message)
        self.update()

    def boundingRect(self) -> QRectF:
        if not self.canvas.show_eval_badges:
            return QRectF(-44, -35, 88, 94)
        return QRectF(-64, -35, 128, 100)

    def mousePressEvent(self, event) -> None:
        self.canvas.select_node(self.node.id)
        self.canvas.nodeSelected.emit(self.node)
        event.accept()

    def hoverEnterEvent(self, event) -> None:
        self.setOpacity(0.8)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setOpacity(1)
        super().hoverLeaveEvent(event)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        bg, fg, kind = NODE_STYLES[self.node.kind]
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(-30, -25, 60, 50)
        if self.node.kind == "func":
            rect = QRectF(-36, -25, 72, 50)
        color = ORANGE if self.node.repaired else fg
        border = self.highlight_color or (BLUE if self.is_selected or self.is_active_step else color if self.node.kind != "number" else BORDER)
        pen = QPen(QColor(border), 2.8 if self.highlight_color else 2.2 if self.is_selected or self.is_active_step else 1.2)
        if self.recessive:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor("#E2EDF7" if self.is_active_step else bg))
        if self.node.kind in ("number", "variable", "constant"):
            painter.drawEllipse(QRectF(-25, -25, 50, 50))
        else:
            painter.drawRoundedRect(rect, 10, 10)
        painter.setFont(QFont("DejaVu Sans Mono", 12, QFont.Weight.Medium))
        painter.setPen(QColor(color))
        text = "sen" if self.node.value == "sin" else {"*": "×", "/": "÷", "u-": "−", "^": "^"}.get(self.node.value, self.node.display_label)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.setFont(QFont("Inter", 8))
        if self.recessive:
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(-60, 31, 120, 18), Qt.AlignmentFlag.AlignCenter, "recesivo")
        elif self.collapsed:
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(-60, 31, 120, 18), Qt.AlignmentFlag.AlignCenter, f"+ {self.collapsed} nodos")
        elif self.canvas.show_eval_badges and self.eval_visible_now and not self.node.is_leaf:
            painter.setPen(QColor(ORANGE if self.node.repaired else MUTED))
            text = "error" if self.node.error else f"= {format_number(self.node.evaluated)}"
            painter.drawText(QRectF(-64, 31, 128, 20), Qt.AlignmentFlag.AlignCenter, text)
        if self.visit_order is not None or self.node.repaired:
            text = str(self.visit_order) if self.visit_order is not None else "R"
            painter.setBrush(QColor(BLUE if self.visit_order is not None else ORANGE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(18, -34, 20, 20))
            painter.setPen(QColor(PAPER))
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(18, -34, 20, 20), Qt.AlignmentFlag.AlignCenter, text)


class ExpressionTreeCanvas(QGraphicsView):
    nodeSelected = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"border: none; background: {PAPER};")
        self.setMinimumSize(250, 210)
        self.root_node: ExprNode | None = None
        self.node_items: dict[int, NodeGraphicsItem] = {}
        self.edge_items = []
        self.edges_by_child: dict[int, object] = {}
        self.recessive_ids: set[int] = set()
        self.selected_node_id: int | None = None
        self.show_eval_badges = True
        self.max_visible_levels = 6
        self.layout_spacing = (110, 90)
        self.scene_padding = (55, 35, 55, 30)

    def drawBackground(self, painter, rect) -> None:
        painter.fillRect(rect, QColor(PAPER))
        painter.setPen(QPen(QColor("#E6E4D9"), 1.0))
        # Draw in viewport coordinates so zooming out cannot create millions of dots.
        painter.save()
        painter.resetTransform()
        for x in range(12, self.viewport().width(), 24):
            for y in range(12, self.viewport().height(), 24):
                painter.drawPoint(x, y)
        painter.restore()

    def set_tree(self, root: ExprNode | None) -> None:
        self.scene().clear()
        self.node_items.clear()
        self.edge_items.clear()
        self.edges_by_child.clear()
        self.recessive_ids.clear()
        self.root_node, self.selected_node_id = root, None
        if root is None:
            return
        def mark_recessive(node: ExprNode, inactive: bool = False) -> None:
            if inactive:
                self.recessive_ids.add(node.id)
            for i, child in enumerate(node.children):
                mark_recessive(child, inactive or i >= len(node.active_children))
        mark_recessive(root)
        widths: dict[int, float] = {}
        visible: list[ExprNode] = []

        def measure(node: ExprNode, level: int) -> float:
            node.depth = level - 1
            visible.append(node)
            widths[node.id] = max(1.0, sum(measure(c, level + 1) for c in node.children)) if level < self.max_visible_levels and node.children else 1.0
            return widths[node.id]

        measure(root, 1)

        def place(node: ExprNode, left: float) -> None:
            node.x, node.y = (left + widths[node.id] / 2) * self.layout_spacing[0], node.depth * self.layout_spacing[1]
            if node.depth + 1 < self.max_visible_levels:
                for child in node.children:
                    place(child, left)
                    left += widths[child.id]

        place(root, 0)
        for node in visible:
            if node.depth + 1 < self.max_visible_levels:
                for child in node.children:
                    path = QPainterPath(QPointF(node.x, node.y + 25))
                    path.cubicTo(QPointF(node.x, node.y + 55), QPointF(child.x, child.y - 45), QPointF(child.x, child.y - 26))
                    pen = QPen(QColor("#B7B5AC"), 1.3)
                    if child.id in self.recessive_ids:
                        pen.setStyle(Qt.PenStyle.DashLine)
                    edge = self.scene().addPath(path, pen)
                    self.edge_items.append(edge)
                    self.edges_by_child[child.id] = edge
            def count(n):
                return 1 + sum(count(c) for c in n.children)
            hidden = sum(count(c) for c in node.children) if node.depth + 1 == self.max_visible_levels else 0
            item = NodeGraphicsItem(node, self, hidden)
            item.recessive = node.id in self.recessive_ids
            item.refresh()
            self.node_items[node.id] = item
            self.scene().addItem(item)
        left, top, right, bottom = self.scene_padding
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-left, -top, right, bottom))
        self.fit_tree_in_view()

    def highlight_branch(self, node: ExprNode, color: str = BLUE) -> None:
        for child in traverse_preorder(node):
            if child.id in self.node_items:
                self.node_items[child.id].highlight_color = color
                self.node_items[child.id].update()
            if child.id in self.edges_by_child:
                edge = self.edges_by_child[child.id]
                pen = edge.pen()
                pen.setColor(QColor(color))
                pen.setWidthF(2.6)
                edge.setPen(pen)

    def select_node(self, node_id: int | None) -> None:
        self.selected_node_id = node_id
        for key, item in self.node_items.items():
            item.is_selected = key == node_id
            item.update()

    def set_show_eval_badges(self, visible: bool) -> None:
        self.show_eval_badges = visible
        self.refresh_evaluations()

    def refresh_evaluations(self) -> None:
        for item in self.node_items.values():
            item.refresh()

    def apply_animation_state(self, visited_order_map: dict[int, int], active_node_id: int | None, evaluation_mode: bool = False) -> None:
        for key, item in self.node_items.items():
            item.visit_order = visited_order_map.get(key)
            item.is_active_step = key == active_node_id
            item.eval_visible_now = not evaluation_mode or key in visited_order_map
            item.update()

    def clear_animation_state(self) -> None:
        self.apply_animation_state({}, None)

    def fit_tree_in_view(self) -> None:
        rect = self.scene().sceneRect()
        if not self.node_items or rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1.3:
            self.scale(1.3 / self.transform().m11(), 1.3 / self.transform().m11())

    def _zoom(self, factor: float) -> None:
        if 0.08 <= self.transform().m11() * factor <= 4:
            self.scale(factor, factor)

    def zoom_in(self) -> None:
        self._zoom(1.18)

    def zoom_out(self) -> None:
        self._zoom(1 / 1.18)

    def wheelEvent(self, event) -> None:
        self._zoom(1.14 if event.angleDelta().y() > 0 else 1 / 1.14)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if self.itemAt(event.position().toPoint()) is None:
            self.fit_tree_in_view()
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self.fit_tree_in_view)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_tree_in_view)
