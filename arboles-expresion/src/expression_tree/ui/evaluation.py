from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QVBoxLayout, QWidget

from ..models import format_number
from ..session import ExpressionSession
from ..tree import extract_variables
from .widgets import button, label


class EvaluationPanel(QWidget):
    variableChanged = Signal(str, float)
    repairChanged = Signal(bool)
    detailsRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(label("Evaluar", "PanelTitle"))
        self.variables = QFormLayout()
        layout.addLayout(self.variables)
        self.inputs: dict[str, QDoubleSpinBox] = {}
        self.result = label("= —", "Result")
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.result)
        self.note = label("", "Muted", True)
        layout.addWidget(self.note)
        self.repair = QCheckBox("Reparar expresiones inválidas")
        self.repair.setChecked(True)
        self.repair.toggled.connect(self.repairChanged.emit)
        layout.addWidget(self.repair)
        layout.addWidget(button("Ver políticas y reparaciones", self.detailsRequested.emit, name="Quiet"))

    def set_session(self, session: ExpressionSession) -> None:
        names = extract_variables(session.root)
        if names != list(self.inputs):
            while self.variables.rowCount():
                self.variables.removeRow(0)
            self.inputs.clear()
            for name in names:
                spin = QDoubleSpinBox()
                spin.setRange(-1e9, 1e9)
                spin.setDecimals(4)
                spin.setValue(session.variables[name])
                spin.setKeyboardTracking(False)
                spin.setAccessibleName(f"Valor de {name}")
                spin.valueChanged.connect(lambda value, key=name: self.variableChanged.emit(key, value))
                self.inputs[name] = spin
                self.variables.addRow(f"{name} =", spin)
        else:
            for name, spin in self.inputs.items():
                spin.blockSignals(True)
                spin.setValue(session.variables[name])
                spin.blockSignals(False)
        self.result.setText(f"= {format_number(session.result)}" if session.result is not None else "Sin resultado")
        repairs = len(session.runtime_repairs) + len(session.syntax_repairs)
        self.note.setText(session.error or (f"{repairs} reparaciones aplicadas; consulta el detalle." if repairs else "Evaluada sin reparaciones."))
        self.note.setStyleSheet(f"color: {'#AF3029' if session.error else '#9D4310' if repairs else '#6F6E69'};")
