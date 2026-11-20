from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLineEdit, QStackedWidget, QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget

from ..csv_io import read_points_csv
from ..metrics import METRICS, ComparisonResult, ComparisonRow, compare_against_points
from ..models import ExprNode, ParseError, RepairConfig
from ..parsing import detect_and_parse
from ..presets import COSINE_EXPRESSION
from ..sampling import SamplePoint, SamplingConfig, sample_points
from ..tree import extract_variables, to_infix_string
from .widgets import button, label


class ComparisonTableModel(QAbstractTableModel):
    columns = ("x", "y referencia", "y predicción", "Error", "|Error|")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows: tuple[ComparisonRow, ...] = ()

    def set_rows(self, rows: tuple[ComparisonRow, ...]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section] if orientation == Qt.Orientation.Horizontal else str(section + 1)
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (row.x, row.reference, row.prediction, row.error, abs(row.error) if row.error is not None else None)
            value = values[index.column()]
            return "—" if value is None else f"{value:.12g}"
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ToolTipRole:
            if row.error is None:
                return "Par excluido: falta un valor real de referencia o predicción."
            return "Se aplicó una reparación en este par." if row.repaired else "Error = predicción − referencia."
        return None


class MetricsWindow(QDialog):
    """Nonmodal comparison window. All numerical work lives in the engine modules."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Métricas de error · Expresiones")
        self.setObjectName("Root")
        self.setModal(False)
        self.resize(1000, 730)
        self.setMinimumSize(760, 600)
        self.root: ExprNode | None = None
        self.variables: dict[str, float] = {}
        self.variable = "x"
        self.sampling = SamplingConfig()
        self.repair_config = RepairConfig(enabled=False)
        self.csv_points: tuple[SamplePoint, ...] | None = None
        self.result: ComparisonResult | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        heading.addWidget(label("Métricas de error", "Title"))
        heading.addStretch()
        self.calculate = button("Calcular métricas", self.calculate_metrics, name="Primary")
        heading.addWidget(self.calculate)
        layout.addLayout(heading)
        self.model_label = label("", wrap=True)
        self.model_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.model_label)
        self.context = label("", "Muted", True)
        layout.addWidget(self.context)
        source_row = QHBoxLayout()
        self.source = QComboBox()
        self.source.addItems(["Expresión de referencia", "CSV de referencia"])
        self.source.setAccessibleName("Origen de los valores de referencia")
        source_row.addWidget(self.source)
        self.sources = QStackedWidget()
        self.reference = QLineEdit(COSINE_EXPRESSION)
        self.reference.setAccessibleName("Expresión de referencia")
        self.reference.setPlaceholderText("y = expresión de referencia")
        self.reference.returnPressed.connect(self.calculate_metrics)
        self.sources.addWidget(self.reference)
        csv_source = QWidget()
        csv_row = QHBoxLayout(csv_source)
        csv_row.setContentsMargins(0, 0, 0, 0)
        csv_row.addWidget(button("Cargar CSV…", self.load_csv))
        self.csv_label = label("Columnas x,y · los valores x se toman del archivo", "Muted", True)
        csv_row.addWidget(self.csv_label, 1)
        self.sources.addWidget(csv_source)
        source_row.addWidget(self.sources, 1)
        layout.addLayout(source_row)
        self.error = label("", "Error", True)
        self.error.hide()
        layout.addWidget(self.error)
        self.summary = label("Elige una referencia y calcula la comparación.", "Muted", True)
        layout.addWidget(self.summary)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setDrawBase(False)
        self.metric_table = QTableWidget(len(METRICS), 3)
        self.metric_table.setHorizontalHeaderLabels(["Métrica", "Valor", "Definición e interpretación"])
        self.metric_table.verticalHeader().hide()
        self.metric_table.setShowGrid(False)
        self.metric_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.metric_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.metric_table.setColumnWidth(0, 105)
        self.metric_table.setColumnWidth(1, 150)
        for i, metric in enumerate(METRICS):
            for col, value in enumerate((metric.name, "—", metric.description)):
                item = QTableWidgetItem(value)
                item.setToolTip(metric.description)
                self.metric_table.setItem(i, col, item)
            self.metric_table.setRowHeight(i, 44)
        tabs.addTab(self.metric_table, "Métricas")
        self.point_table = QTableView()
        self.point_table.setAccessibleName("Puntos de referencia, predicción y error")
        self.point_model = ComparisonTableModel(self)
        self.point_table.setModel(self.point_model)
        self.point_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.point_table.setAlternatingRowColors(True)
        tabs.addTab(self.point_table, "Puntos y errores")
        layout.addWidget(tabs, 1)
        self.notes = label("NMSE usa la varianza poblacional de la referencia. Las métricas se calculan sin redondear los valores.", "Muted", True)
        layout.addWidget(self.notes)
        footer = QHBoxLayout()
        footer.addWidget(label("La variable y la reparación se eligen en la pestaña Curva.", "Muted", True), 1)
        footer.addWidget(button("Cerrar", self.close))
        layout.addLayout(footer)
        self.source.currentIndexChanged.connect(self.source_changed)
        self.reference.textChanged.connect(self.invalidate)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "metric_table"):
            QTimer.singleShot(0, self.metric_table.resizeRowsToContents)

    def source_changed(self, index: int) -> None:
        self.sources.setCurrentIndex(index)
        self.invalidate()
        if index == 1:
            self.summary.setText("El CSV aporta sus propios valores x; el intervalo y paso de la curva no filtran sus filas.")

    def set_context(self, root: ExprNode, variables: dict[str, float], variable: str, sampling: SamplingConfig, config: RepairConfig) -> None:
        self.root, self.variables, self.variable = root, dict(variables), variable
        self.sampling, self.repair_config = sampling, replace(config)
        expression = to_infix_string(root)
        self.model_label.setText("Predicción:  " + (expression[:180] + "…" if len(expression) > 180 else expression))
        self.model_label.setToolTip(expression)
        policy = "con reparaciones" if config.enabled else "dominio real"
        fixed = ", ".join(f"{key}={value:g}" for key, value in variables.items() if key != variable and key in extract_variables(root))
        self.context.setText(f"Variable: {variable} · intervalo [{sampling.x_min:g}, {sampling.x_max:g}] · paso {sampling.step:g} · {policy}" + (f" · constantes: {fixed}" if fixed else ""))
        self.invalidate()

    def invalidate(self, *_args) -> None:
        self.result = None
        self.point_model.set_rows(())
        for row in range(len(METRICS)):
            self.metric_table.item(row, 1).setText("—")
        self.error.hide()
        self.summary.setText("Datos o expresión actualizados. Pulsa Calcular métricas.")
        self.notes.setText("NMSE usa la varianza poblacional de la referencia. Las métricas se calculan sin redondear los valores.")

    def load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Cargar referencia x,y", "", "Datos CSV (*.csv);;Todos los archivos (*)")
        if not path:
            return
        self.invalidate()
        try:
            points = read_points_csv(path)
        except (OSError, UnicodeError, ValueError) as exc:
            self.csv_points = None
            self.csv_label.setText("No se cargó una referencia válida.")
            self.show_error(str(exc))
            return
        self.csv_points = points
        self.csv_label.setText(f"{Path(path).name} · {len(points)} filas · x del archivo")
        self.source.setCurrentIndex(1)
        self.calculate_metrics()

    def show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()

    def calculate_metrics(self) -> None:
        self.invalidate()
        if self.root is None:
            self.show_error("Construye una expresión antes de comparar.")
            return
        try:
            if self.source.currentIndex() == 1:
                if self.csv_points is None:
                    raise ValueError("Carga un CSV con las columnas x,y para usarlo como referencia.")
                points = self.csv_points
            else:
                reference, _, _ = detect_and_parse(self.reference.text(), "infix", allow_syntax_repair=False)
                points = sample_points(reference, self.variables, self.sampling.grid(), variable=self.variable, repair_config=self.repair_config)
            result = compare_against_points(self.root, self.variables, points, variable=self.variable, repair_config=self.repair_config)
        except (ParseError, ValueError) as exc:
            self.show_error(str(exc))
            self.summary.setText("No se calcularon métricas. Revisa los valores de referencia.")
            return
        self.result = result
        for row, metric in enumerate(METRICS):
            value = result.metrics.values[metric.key]
            self.metric_table.item(row, 1).setText("N/D" if value is None else f"{value:.12g}")
        self.point_model.set_rows(result.rows)
        self.summary.setText(f"{result.metrics.count} pares válidos · {result.excluded} excluidos por datos ausentes o dominio · {result.repaired} pares con reparación")
        self.notes.setText(" ".join(result.metrics.notes) or "NMSE = MSE / Var(referencia); varianza poblacional. Error = predicción − referencia.")
        self.metric_table.resizeRowsToContents()
