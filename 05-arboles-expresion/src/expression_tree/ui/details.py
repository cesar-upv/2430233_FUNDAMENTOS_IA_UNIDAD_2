from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit, QListWidget, QListWidgetItem, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..models import EvalStep, ExprNode, RepairConfig, format_number
from ..tree import traverse_inorder, traverse_preorder, traverse_postorder
from .theme import BLUE, MUTED, ORANGE, RED
from .widgets import button, icon_button, label


class TraversalsPanel(QWidget):
    nodeSelected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 10, 4, 0)
        self.layout.setSpacing(8)

    def set_tree(self, root: ExprNode) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for title, order, nodes in (("Inorden", "Izquierda · raíz · derecha", traverse_inorder(root)), ("Preorden", "Raíz · izquierda · derecha", traverse_preorder(root)), ("Postorden", "Izquierda · derecha · raíz", traverse_postorder(root))):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            name = label(title)
            name.setFixedWidth(84)
            name.setToolTip(order)
            layout.addWidget(name)
            scroller = QScrollArea()
            scroller.setWidgetResizable(True)
            scroller.setFixedHeight(48)
            scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            inner = QWidget()
            tokens = QHBoxLayout(inner)
            tokens.setContentsMargins(0, 1, 0, 1)
            tokens.setSpacing(4)
            for n in nodes:
                token = button(n.token_label, lambda checked=False, node=n: self.nodeSelected.emit(node.id))
                token.setToolTip(f"Nodo {n.id} · {format_number(n.evaluated)}")
                token.setMinimumWidth(30)
                tokens.addWidget(token)
            tokens.addStretch()
            scroller.setWidget(inner)
            layout.addWidget(scroller, 1)
            text = " ".join(n.token_label for n in nodes)
            layout.addWidget(icon_button("copy", f"Copiar {title.lower()}", lambda checked=False, value=text: QApplication.clipboard().setText(value)))
            self.layout.addWidget(row)
        self.layout.addStretch()


class StepsPanel(QWidget):
    nodeSelected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Paso", "Operación", "Valor"])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 52)
        self.table.setColumnWidth(2, 100)
        self.table.itemSelectionChanged.connect(self.selected)
        layout.addWidget(self.table)
        self.stack = label("Selecciona un paso para ver la pila de evaluación.", "Muted")
        layout.addWidget(self.stack)
        self.steps: list[EvalStep] = []

    def set_steps(self, steps: list[EvalStep]) -> None:
        self.steps = steps
        self.table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            for col, value in enumerate((str(step.step_index), step.description, format_number(step.result))):
                item = QTableWidgetItem(value)
                item.setToolTip(step.description)
                if step.repaired:
                    item.setForeground(QColor(ORANGE))
                self.table.setItem(row, col, item)
        self.stack.setText("Selecciona un paso para ver la pila de evaluación.")

    def selected(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.steps):
            step = self.steps[row]
            self.stack.setText("Pila:  " + "   ·   ".join(step.stack_snapshot) + "   ← tope")
            self.nodeSelected.emit(step.node_id)


class InterpreterPanel(QWidget):
    executeRequested = Signal(str)
    expressionRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self.history = QListWidget()
        self.history.setAccessibleName("Historial del intérprete")
        self.history.itemDoubleClicked.connect(lambda item: self.expressionRequested.emit(item.data(Qt.ItemDataRole.UserRole)) if item.data(Qt.ItemDataRole.UserRole) else None)
        layout.addWidget(self.history)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Prueba a = 3, luego sen(x) + a. Doble clic en el historial para ver su árbol.")
        self.input.setAccessibleName("Comando del intérprete")
        self.input.returnPressed.connect(self.execute)
        row.addWidget(self.input, 1)
        row.addWidget(button("Ejecutar", self.execute))
        layout.addLayout(row)

    def execute(self) -> None:
        command = self.input.text().strip()
        if command:
            self.executeRequested.emit(command)

    def record(self, command: str, response: str, error: bool = False) -> None:
        item = QListWidgetItem(f"> {command}\n  {response}")
        item.setForeground(QColor(RED if error else BLUE))
        if not error:
            item.setData(Qt.ItemDataRole.UserRole, command.split("=", 1)[-1].strip())
        self.history.addItem(item)
        self.history.scrollToBottom()
        if not error:
            self.input.clear()


class RepairsPanel(QWidget):
    configChanged = Signal()
    rewriteRequested = Signal()

    def __init__(self, config: RepairConfig) -> None:
        super().__init__()
        self.config = config
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 0)
        controls = QVBoxLayout()
        form = QFormLayout()
        self.sqrt = QComboBox()
        self.sqrt.addItem("Usar valor absoluto", "abs")
        self.sqrt.addItem("Devolver cero", "zero")
        form.addRow("Raíz negativa", self.sqrt)
        self.division = QComboBox()
        for text, data in (("Devolver cero", "zero"), ("Usar ε = 0.000001", "epsilon"), ("Conservar numerador", "numerator"), ("Devolver uno", "one")):
            self.division.addItem(text, data)
        form.addRow("División por cero", self.division)
        controls.addLayout(form)
        self.syntax = QCheckBox("Reparar sintaxis incompleta")
        self.syntax.setChecked(True)
        controls.addWidget(self.syntax)
        self.rewrite = button("Aplicar reparaciones al árbol", self.rewriteRequested.emit)
        controls.addWidget(self.rewrite)
        controls.addWidget(label("La reescritura usa los valores actuales y puede sustituir subexpresiones por constantes.", "Muted", True))
        controls.addStretch()
        layout.addLayout(controls, 1)
        self.log = QListWidget()
        self.log.setAccessibleName("Reparaciones aplicadas")
        layout.addWidget(self.log, 2)
        for signal in (self.sqrt.currentIndexChanged, self.division.currentIndexChanged, self.syntax.toggled):
            signal.connect(self.changed)

    def changed(self, *_args) -> None:
        self.config.neg_root_strategy = self.sqrt.currentData()
        self.config.div_zero_strategy = self.division.currentData()
        self.config.syntax_repair = self.syntax.isChecked()
        self.configChanged.emit()

    def set_notes(self, notes: list[str], enabled: bool) -> None:
        self.log.clear()
        self.log.addItems(notes or ["No se necesitaron reparaciones." if enabled else "Reparación desactivada. Se evalúa en el dominio real."])
        self.rewrite.setEnabled(enabled and bool(notes))
        for control in (self.sqrt, self.division, self.syntax):
            control.setEnabled(enabled)
