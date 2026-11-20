from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFormLayout, QGridLayout, QHBoxLayout, QLineEdit, QSpinBox, QVBoxLayout, QWidget

from ..generation import GenerationConfig
from ..operators import GENERATOR_OPERATORS, OPERATORS
from .widgets import button, label, rule


class GeneratorPanel(QWidget):
    generateRequested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(label("Generar una expresión", "PanelTitle"))
        layout.addWidget(label("Elige los ingredientes. Explora otra forma.", "Muted", True))
        form = QFormLayout()
        form.setVerticalSpacing(9)
        self.height = QSpinBox()
        self.height.setRange(1, 8)
        self.height.setValue(4)
        self.height.setSuffix(" niveles")
        self.height.setAccessibleName("Altura máxima del árbol generado")
        form.addRow("Altura máxima", self.height)
        self.seed = QLineEdit()
        self.seed.setPlaceholderText("Aleatoria")
        self.seed.setAccessibleName("Semilla del generador, opcional")
        self.seed.setToolTip("Un entero reproduce el mismo árbol con los mismos ajustes.")
        form.addRow("Semilla", self.seed)
        layout.addLayout(form)
        layout.addWidget(label("La raíz cuenta como nivel 1. Máximo 63 nodos.", "Muted", True))
        layout.addWidget(rule())
        row = QHBoxLayout()
        row.addWidget(label("Operadores permitidos", "PanelTitle"))
        row.addStretch()
        layout.addLayout(row)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(5)
        self.operators: dict[str, QCheckBox] = {}
        display = {"*": "×  multiplicar", "+": "+  suma", "-": "−  resta", "/": "÷  división", "%": "%  módulo", "^": "^  potencia", "sqrt": "sqrt", "log": "log₁₀", "sin": "sen", "cos": "cos", "tan": "tan"}
        for i, token in enumerate(GENERATOR_OPERATORS):
            checkbox = QCheckBox(display[token])
            checkbox.setChecked(token not in ("%", "tan"))
            checkbox.setToolTip(OPERATORS[token].label + (" · radianes" if token in ("sin", "cos", "tan") else ""))
            checkbox.setAccessibleName(OPERATORS[token].label)
            checkbox.toggled.connect(self.validate)
            self.operators[token] = checkbox
            grid.addWidget(checkbox, i // 2, i % 2)
        layout.addLayout(grid)
        self.hint = label("sen(x) y sin(x) son equivalentes. log usa base 10.", "Muted", True)
        layout.addWidget(self.hint)
        self.error = label("", "Error", True)
        self.error.hide()
        layout.addWidget(self.error)
        self.generate = button("Generar expresión", self.request, name="Primary", glyph="dice")
        self.generate.setMinimumHeight(24)
        layout.addWidget(self.generate)
        self.seed.textChanged.connect(self.validate)

    def validate(self, *_args) -> bool:
        seed = self.seed.text().strip()
        message = "Selecciona al menos un operador." if not any(c.isChecked() for c in self.operators.values()) else ""
        if seed:
            try:
                int(seed)
            except ValueError:
                message = "La semilla debe ser un entero o quedar vacía."
        self.error.setText(message)
        self.error.setVisible(bool(message))
        self.generate.setEnabled(not message)
        return not message

    def request(self) -> None:
        if self.validate():
            self.generateRequested.emit(GenerationConfig(self.height.value(), tuple(t for t, c in self.operators.items() if c.isChecked()), int(self.seed.text()) if self.seed.text().strip() else None))
