from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import replace
from pathlib import Path as FilePath

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit, QScrollArea,
    QSizePolicy, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..canvas import ExpressionTreeCanvas
from ..csv_io import read_points_csv
from ..evolution import EvolutionConfig, EvolutionRun, Individual, SELECTIONS, evaluate_individual, select_parents
from ..generation import GenerationConfig
from ..genetics import MUTATIONS, GeneticChange, at_path, clone_tree, crossover, mutate, tree_paths
from ..models import ExprNode, ParseError, RepairConfig, format_number
from ..operators import GENERATOR_OPERATORS
from ..parsing import detect_and_parse
from ..sampling import SamplePoint, sample_points
from ..tree import to_infix_string, traverse_preorder, tree_height
from .evolution_charts import ProgressChart, SelectionChart
from .elite_comparison import EliteComparisonPanel
from .theme import BLUE, GREEN, ORANGE
from .widgets import button, icon, icon_button, label, rule, surface


class EvolutionWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, work, parent=None) -> None:
        super().__init__(parent)
        self.work = work

    def run(self) -> None:
        try:
            self.succeeded.emit(self.work())
        except Exception as exc:
            self.failed.emit(str(exc))


class TreePane(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        row = QHBoxLayout()
        self.title = label(title, "PanelTitle")
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.title, 1)
        self.open = button("Abrir", name="Quiet")
        self.open.setEnabled(False)
        self.open.setToolTip("Abrir el genotipo completo en el explorador de expresiones")
        self.canvas = ExpressionTreeCanvas()
        self.canvas.setMinimumSize(200, 190)
        self.canvas.max_visible_levels = 8
        self.canvas.show_eval_badges = False
        self.canvas.layout_spacing = (92, 76)
        self.canvas.scene_padding = (12, 8, 12, 8)
        self.view_controls = [
            icon_button("minus", "Alejar este árbol", self.canvas.zoom_out),
            icon_button("plus", "Acercar este árbol", self.canvas.zoom_in),
            icon_button("fit", "Ajustar este árbol a la vista", self.canvas.fit_tree_in_view), self.open]
        for control in self.view_controls:
            row.addWidget(control)
            control.hide()
        self.formula = label("El árbol aparecerá aquí.", "Muted", True)
        self.formula.setMinimumWidth(0)
        self.formula.setMaximumHeight(37)
        self.formula.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addLayout(row)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.formula)
        self.root: ExprNode | None = None

    def set_tree(self, root: ExprNode, path=None, color: str = BLUE, repairs=()) -> None:
        self.root = clone_tree(root)
        self.canvas.set_tree(self.root)
        if path is not None:
            try:
                self.canvas.highlight_branch(at_path(self.root, path), color)
            except (ValueError, IndexError):
                pass  # An ancestor may have been pruned; repaired nodes below explain it.
        for repaired in repairs:
            self.canvas.highlight_branch(at_path(self.root, repaired), ORANGE)
        expression = to_infix_string(root)
        self.formula.setText(expression)
        self.formula.setToolTip(expression)
        self.open.setEnabled(True)
        for control in self.view_controls:
            control.show()

    def clear(self) -> None:
        self.root = None
        self.canvas.set_tree(None)
        self.formula.setText("Aplica el operador para ver el resultado.")
        self.formula.setToolTip("")
        self.open.setEnabled(False)
        for control in self.view_controls:
            control.hide()


class OperationPreview(QDialog):
    """Read-only evidence from a formal run, separate from the editable demos."""
    treeRequested = Signal(object)

    def __init__(self, change: GeneticChange, title: str, parent=None) -> None:
        super().__init__(parent)
        self.change = change
        self.setWindowTitle("Detalle de operación · Evolución")
        self.setObjectName("Root")
        self.resize(1120, 820)
        self.setMinimumSize(850, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(label(title, "PanelTitle", True))
        layout.addWidget(label("Registro de la ejecución. Los árboles son copias para consulta.", "Muted", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content, content_layout = surface()
        grid = QGridLayout()
        self.panes: list[TreePane] = []
        for i, before in enumerate(change.before):
            for column, root in enumerate((before, change.after[i])):
                suffix = f" {'A' if i == 0 else 'B'}" if len(change.before) == 2 else ""
                pane = TreePane(("Antes" if column == 0 else "Después") + suffix)
                pane.open.clicked.connect(lambda checked=False, source=pane: self.treeRequested.emit(clone_tree(source.root)))
                color = (BLUE if i == 0 else GREEN) if column == 0 else (GREEN if i == 0 else BLUE)
                repairs = change.repairs[i] if column == 1 and change.repairs else ()
                pane.set_tree(root, change.paths[i], color, repairs)
                grid.addWidget(pane, i, column)
                self.panes.append(pane)
        content_layout.addLayout(grid, 1)
        content_layout.addWidget(label(" ".join(change.notes), "Muted", True))
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)


def spin(minimum: int, maximum: int, value: int, name: str) -> QSpinBox:
    control = QSpinBox()
    control.setRange(minimum, maximum)
    control.setValue(value)
    control.setAccessibleName(name)
    return control


def real(minimum: float, maximum: float, value: float, name: str, decimals: int = 4) -> QDoubleSpinBox:
    control = QDoubleSpinBox()
    control.setDecimals(decimals)
    control.setRange(minimum, maximum)
    control.setValue(value)
    control.setAccessibleName(name)
    return control


def table(headers: list[str]) -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.verticalHeader().hide()
    widget.setShowGrid(False)
    widget.setAlternatingRowColors(True)
    widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    widget.setWordWrap(False)
    return widget


class EvolutionWindow(QDialog):
    treeRequested = Signal(object)

    def __init__(self, root: ExprNode, variables: dict[str, float], generation: GenerationConfig,
                 repairs: RepairConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Evolución · Programación genética")
        self.setObjectName("Root")
        self.setModal(False)
        self.resize(1440, 940)
        self.setMinimumSize(1024, 740)
        self.variables, self.repairs = dict(variables), replace(repairs)
        self.explorer_root = clone_tree(root)
        self.initial_generation = generation
        self.run: EvolutionRun | None = None
        self.worker: EvolutionWorker | None = None
        self.busy = self.stale = self.close_pending = False
        self.csv_points: tuple[SamplePoint, ...] | None = None
        self.lab_rng = random.Random(generation.seed)
        self.displayed: list[Individual] = []
        self.archive_displayed: list[Individual] = []
        self.demo_population: list[Individual] = []
        self.operation_window: OperationPreview | None = None
        self.manual_parents: tuple[ExprNode, ExprNode] | None = None
        self.mutation_root = clone_tree(root)
        self.previous_mutation_root: ExprNode | None = None
        self.last_change: GeneticChange | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(180)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance)
        self.running = False
        self._build()
        self._demo_source_changed()
        self._example_cross()
        self._set_mutation_source(self.mutation_root)
        self._buttons()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)
        layout.addWidget(label("Evolución", "Title"))
        layout.addWidget(label("Ejecuta el algoritmo completo o estudia sus operadores por separado.", "Muted"))
        self.workspace = QTabWidget()
        self.workspace.setDocumentMode(True)
        self.workspace.tabBar().setDrawBase(False)
        self.workspace.setAccessibleName("Sección de evolución")
        self.algorithm_page = QWidget()
        formal = QVBoxLayout(self.algorithm_page)
        formal.setContentsMargins(0, 10, 0, 0)
        formal.setSpacing(10)
        actions = QHBoxLayout()
        self.workflow_note = label("Cada generación: selección → cruza → mutación → evaluación.", "Muted", True)
        actions.addWidget(self.workflow_note, 1)
        self.create = button("Iniciar ejecución", self.start_run, name="Primary")
        self.play = button("Pausar", self.toggle_running)
        self.next = button("Avanzar una generación", self.advance, name="Quiet")
        for control in (self.create, self.play, self.next):
            actions.addWidget(control)
        self.play.hide()
        self.next.hide()
        formal.addLayout(actions)
        self.error = label("", "Error", True)
        self.error.hide()
        formal.addWidget(self.error)
        self.formal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.formal_splitter.setHandleWidth(12)
        self.formal_splitter.setChildrenCollapsible(False)
        self._build_settings()
        body, body_layout = surface()
        self.summary = label("Define la referencia e inicia la ejecución. El algoritmo repetirá todas las fases hasta el criterio de paro.", wrap=True)
        body_layout.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.comparison = EliteComparisonPanel()
        comparison_scroll = QScrollArea()
        comparison_scroll.setWidgetResizable(True)
        comparison_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        comparison_scroll.setWidget(self.comparison)
        self.tabs.addTab(comparison_scroll, "Comparación")
        self._build_population()
        self._build_archive()
        self._build_progress()
        body_layout.addWidget(self.tabs, 1)
        self.formal_splitter.addWidget(body)
        self.formal_splitter.setSizes([310, 1070])
        self.formal_splitter.setStretchFactor(1, 1)
        formal.addWidget(self.formal_splitter, 1)
        self.status = label("Lista para iniciar. Las demostraciones están en su propia sección.", "Muted", True)
        formal.addWidget(self.status)
        self.workspace.addTab(self.algorithm_page, "Algoritmo completo")
        self._build_demonstrations()
        layout.addWidget(self.workspace, 1)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.population_size.valueChanged.connect(self._size_changed)
        self.selection.currentIndexChanged.connect(lambda: self.tournament.setEnabled(self.selection.currentData() == "tournament"))
        for control in self.settings.findChildren(QSpinBox) + self.settings.findChildren(QDoubleSpinBox):
            control.valueChanged.connect(self.invalidate)
        for control in self.settings.findChildren(QLineEdit):
            control.textChanged.connect(self.invalidate)
        for control in self.settings.findChildren(QComboBox):
            control.currentIndexChanged.connect(self.invalidate)
        for control in self.settings.findChildren(QCheckBox):
            control.toggled.connect(self.invalidate)

    def _build_settings(self) -> None:
        frame, frame_layout = surface()
        frame.setMinimumWidth(290)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings = QWidget()
        self.settings.setMinimumWidth(250)
        sidebar = QVBoxLayout(self.settings)
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(8)
        sidebar.addWidget(label("Referencia", "PanelTitle"))
        self.source = QComboBox()
        self.source.addItems(["Expresión", "CSV · columnas x,y"])
        self.source.setAccessibleName("Origen de la referencia de evolución")
        sidebar.addWidget(self.source)
        self.reference = QLineEdit(to_infix_string(self.explorer_root))
        self.reference.setAccessibleName("Ecuación objetivo")
        sidebar.addWidget(self.reference)
        self.csv_button = button("Cargar CSV…", self.load_csv)
        self.csv_button.hide()
        sidebar.addWidget(self.csv_button)
        self.data_note = label("101 puntos entre −1 y 1. Puedes ajustar los datos en Opciones avanzadas.", "Muted", True)
        sidebar.addWidget(self.data_note)
        sidebar.addWidget(rule())
        sidebar.addWidget(label("Configuración", "PanelTitle"))
        form = QFormLayout()
        form.setVerticalSpacing(4)
        self.population_size = spin(2, 500, 100, "Tamaño de la población")
        self.depth = spin(0, 7, self.initial_generation.max_height - 1, "Nivel máximo del genotipo, raíz en cero")
        self.selection = QComboBox()
        for key, value in SELECTIONS.items():
            self.selection.addItem("Universal (SUS)" if key == "sus" else value, key)
        self.selection.setAccessibleName("Método de selección")
        self.tournament = spin(2, 100, 3, "Participantes por torneo")
        self.generations = spin(1, 10000, 50, "Máximo de generaciones")
        for title, widget in (("Individuos", self.population_size), ("Nivel máximo", self.depth),
                              ("Selección", self.selection), ("Generaciones", self.generations)):
            form.addRow(title, widget)
        sidebar.addLayout(form)
        sidebar.addWidget(label("Raíz = nivel 0 · máximo 63 nodos.", "Muted", True))
        mutation_group = QWidget()
        mutation_layout = QVBoxLayout(mutation_group)
        mutation_layout.setContentsMargins(0, 0, 0, 0)
        mutation_layout.setSpacing(4)
        heading = QHBoxLayout()
        heading.addWidget(label("Mutaciones activas"))
        self.mutation_summary = label("", "Muted")
        heading.addWidget(self.mutation_summary, 1, Qt.AlignmentFlag.AlignRight)
        mutation_layout.addLayout(heading)
        self.mutation_types: dict[str, QCheckBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        descriptions = {
            "leaf": "Sustituye una hoja por otra constante o variable.",
            "operator": "Cambia una operación; conserva las ramas recesivas de los operadores unarios.",
            "switch": "Intercambia las ramas izquierda y derecha, incluidas las recesivas.",
            "subtree": "Genera una subrama nueva dentro de los límites; también puede reemplazar la raíz.",
        }
        for i, (key, title) in enumerate(MUTATIONS.items()):
            control = QCheckBox(title)
            control.setChecked(True)
            control.setAccessibleName(f"Mutación {title.lower()} en el algoritmo completo")
            control.setToolTip(descriptions[key])
            self.mutation_types[key] = control
            grid.addWidget(control, i // 2, i % 2)
        mutation_layout.addLayout(grid)
        self.mutation_hint = label("", "Muted", True)
        self.mutation_hint.setToolTip("Al mutar un hijo, se sortea un tipo activo con igual probabilidad. "
                                      "La probabilidad por hijo se ajusta en Opciones avanzadas.")
        mutation_layout.addWidget(self.mutation_hint)
        sidebar.addWidget(mutation_group)
        self.advanced_toggle = button("Opciones avanzadas", name="Quiet", glyph="plus")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setAccessibleName("Mostrar opciones avanzadas de la ejecución")
        sidebar.addWidget(self.advanced_toggle)
        self.advanced = QWidget()
        advanced = QVBoxLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(12)
        advanced.addWidget(rule())
        advanced.addWidget(label("Datos y evaluación", "PanelTitle"))
        form = QFormLayout()
        self.variable = QLineEdit(self.initial_generation.variable)
        self.variable.setAccessibleName("Variable independiente de evolución")
        self.minimum = real(-1e6, 1e6, -1, "Inicio del intervalo")
        self.maximum = real(-1e6, 1e6, 1, "Fin del intervalo")
        self.samples = spin(2, 1001, 101, "Cantidad de puntos de referencia")
        self.fitness_metric = QComboBox()
        for title, code in (("MSE", "mse"), ("NMSE", "nmse"), ("R²", "r2")):
            self.fitness_metric.addItem(title, code)
        self.fitness_metric.setAccessibleName("Métrica de adaptación")
        for title, widget in (("Variable", self.variable), ("Desde", self.minimum), ("Hasta", self.maximum),
                              ("Puntos", self.samples), ("Adaptación", self.fitness_metric)):
            form.addRow(title, widget)
        advanced.addLayout(form)
        self.protected = QCheckBox("Evaluación con reparaciones")
        self.protected.setChecked(self.repairs.enabled)
        advanced.addWidget(self.protected)
        advanced.addWidget(label("Cada individuo usa todos los puntos; una predicción inválida lo descalifica.", "Muted", True))
        advanced.addWidget(rule())
        advanced.addWidget(label("Reproducción y archivo", "PanelTitle"))
        form = QFormLayout()
        self.seed = QLineEdit(str(self.initial_generation.seed) if self.initial_generation.seed is not None else "42")
        self.seed.setPlaceholderText("Aleatoria")
        self.seed.setAccessibleName("Semilla de evolución")
        self.cross_probability = real(0, 100, 90, "Probabilidad de cruza por pareja", 1)
        self.mutation_probability = real(0, 100, 5, "Probabilidad de mutación por hijo", 1)
        self.cross_probability.setSuffix(" %")
        self.mutation_probability.setSuffix(" %")
        self.elite = spin(0, 99, 1, "Cantidad de élites por generación; cero desactiva elitismo")
        self.archive_size = spin(0, 100, 10, "Capacidad del Hall of Fame; cero lo desactiva")
        for title, widget in (("Torneo (k)", self.tournament), ("Semilla", self.seed), ("Cruza / pareja", self.cross_probability),
                              ("Mutación / hijo", self.mutation_probability), ("Élites", self.elite), ("Hall of Fame", self.archive_size)):
            form.addRow(title, widget)
        advanced.addLayout(form)
        advanced.addWidget(label("0 desactiva elitismo o Hall of Fame. Las ramas recesivas se conservan. Máximo 63 nodos por genotipo.", "Muted", True))
        self.operators: dict[str, QCheckBox] = {}
        grid = QGridLayout()
        for i, token in enumerate(GENERATOR_OPERATORS):
            control = QCheckBox(token)
            control.setChecked(token in self.initial_generation.operators)
            self.operators[token] = control
            grid.addWidget(control, i // 4, i % 4)
        advanced.addWidget(label("Operadores permitidos", "Muted"))
        advanced.addLayout(grid)
        advanced.addWidget(rule())
        form = QFormLayout()
        self.tolerance = real(0, 1e12, .000001, "Pérdida objetivo de paro", 9)
        form.addRow("Parar si pérdida ≤", self.tolerance)
        advanced.addLayout(form)
        advanced.addWidget(label("Pérdida: MSE, NMSE o 1 − R². Menor es mejor. El límite de generaciones se cuenta después de G0.", "Muted", True))
        sidebar.addWidget(self.advanced)
        self.advanced.hide()
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        for control in self.mutation_types.values():
            control.toggled.connect(self._mutation_types_changed)
        self._mutation_types_changed()
        sidebar.addStretch()
        scroll.setWidget(self.settings)
        frame_layout.addWidget(scroll)
        self.formal_splitter.addWidget(frame)

    def _toggle_advanced(self, visible: bool) -> None:
        self.advanced.setVisible(visible)
        self.advanced_toggle.setIcon(icon("minus" if visible else "plus"))

    def _mutation_types_changed(self) -> None:
        count = sum(control.isChecked() for control in self.mutation_types.values())
        self.mutation_summary.setText(f"{count} / {len(MUTATIONS)}" if count else "Sin mutación")
        self.mutation_hint.setText("Un tipo al azar por hijo que mute." if count else
                                   "Activa un tipo para habilitar la mutación.")
        self.mutation_probability.setEnabled(bool(count))
        self.mutation_probability.setToolTip("Probabilidad por hijo. Si muta, usa un solo tipo de los activos, elegido al azar."
                                             if count else "Activa un tipo de mutación para usar esta probabilidad.")

    def _build_demonstrations(self) -> None:
        self.demo_page, layout = surface()
        introduction = QHBoxLayout()
        introduction.addWidget(label("Prueba un operador sobre copias. La ejecución completa conserva su población y sus ajustes.", "Muted", True), 1)
        introduction.addWidget(label("Nivel máximo", "Muted"))
        self.demo_depth = spin(0, 7, self.initial_generation.max_height - 1, "Nivel máximo de los árboles de demostración")
        self.demo_depth.setFixedWidth(70)
        introduction.addWidget(self.demo_depth)
        layout.addLayout(introduction)
        self.demo_error = label("", "Error", True)
        self.demo_error.hide()
        layout.addWidget(self.demo_error)
        self._build_lab()
        layout.addWidget(self.lab, 1)
        self.workspace.addTab(self.demo_page, "Demostraciones")

    def _build_population(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.population_table = table(["Individuo", "Pérdida ↓", "Origen", "Ecuación (fenotipo)"])
        self.population_table.setAccessibleName("Población ordenada por adaptación")
        self.population_table.itemSelectionChanged.connect(self._inspect_population)
        layout.addWidget(self.population_table, 1)
        self.population_tree = TreePane("Individuo seleccionado")
        self.population_tree.open.clicked.connect(lambda: self._open_tree(self.population_tree.root))
        layout.addWidget(self.population_tree, 2)
        self.individual_note = label("Selecciona una fila para ver genotipo, fenotipo y adaptación.", "Muted", True)
        layout.addWidget(self.individual_note)
        self.tabs.addTab(page, "Población")

    def _pane(self, title: str) -> TreePane:
        pane = TreePane(title)
        pane.open.clicked.connect(lambda: self._open_tree(pane.root))
        return pane

    def _build_lab(self) -> None:
        self.lab = QTabWidget()
        self.lab.setDocumentMode(True)
        select_page = QWidget()
        selection_layout = QVBoxLayout(select_page)
        selection_layout.addWidget(label("¿Quién se reproduce?", "PanelTitle"))
        self.selection_explanation = label("Torneo: gana la menor pérdida entre k candidatos. Ruleta: peso = 1 / (1 + pérdida). SUS: un inicio aleatorio y punteros equidistantes sobre los mismos pesos.", "Muted", True)
        selection_layout.addWidget(self.selection_explanation)
        source_row = QHBoxLayout()
        source_row.addWidget(label("Población de prueba", "Muted"))
        self.demo_source = QComboBox()
        self.demo_source.addItem("Ejemplo de clase", "example")
        self.demo_source.addItem("Copia de la ejecución", "run")
        self.demo_source.setAccessibleName("Origen de la población de demostración")
        self.demo_source.model().item(1).setEnabled(False)
        source_row.addWidget(self.demo_source)
        self.refresh_demo = button("Actualizar copia", self._demo_source_changed)
        self.refresh_demo.hide()
        source_row.addWidget(self.refresh_demo)
        source_row.addStretch()
        selection_layout.addLayout(source_row)
        self.demo_population_note = label("", "Muted", True)
        selection_layout.addWidget(self.demo_population_note)
        selection_row = QHBoxLayout()
        self.demo_selection = QComboBox()
        for key, value in SELECTIONS.items():
            self.demo_selection.addItem(value, key)
        self.demo_selection.setAccessibleName("Método de selección de la demostración")
        selection_row.addWidget(self.demo_selection)
        selection_row.addWidget(label("Torneo (k)", "Muted"))
        self.demo_tournament = spin(2, 6, 3, "Participantes en el torneo de demostración")
        selection_row.addWidget(self.demo_tournament)
        self.select = button("Seleccionar pareja", self.select_pair, name="Primary")
        selection_row.addWidget(self.select)
        selection_row.addStretch()
        selection_layout.addLayout(selection_row)
        self.selection_chart = SelectionChart()
        selection_layout.addWidget(self.selection_chart)
        self.selection_table = table(["Individuo", "Pérdida", "Probabilidad", "Veces elegido"])
        self.selection_table.setAccessibleName("Probabilidades y frecuencia de selección")
        selection_layout.addWidget(self.selection_table, 1)
        self.selection_note = label("Se permite seleccionar al mismo individuo varias veces. Si toda la población es inválida, ruleta y SUS usan pesos uniformes.", "Muted", True)
        selection_layout.addWidget(self.selection_note)
        self.lab.addTab(select_page, "Selección")
        self.demo_source.currentIndexChanged.connect(self._demo_source_changed)
        self.demo_selection.currentIndexChanged.connect(self._clear_demo_selection)
        self.demo_tournament.valueChanged.connect(self._clear_demo_selection)
        cross_page = QWidget()
        cross_layout = QVBoxLayout(cross_page)
        row = QHBoxLayout()
        self.parent_a, self.parent_b = QComboBox(), QComboBox()
        for widget, text in ((self.parent_a, "Padre A"), (self.parent_b, "Padre B")):
            widget.setMinimumWidth(90)
            widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            widget.setAccessibleName(text + " de la cruza manual")
            row.addWidget(label(text, "Muted"))
            row.addWidget(widget, 1)
        self.cross = button("Cruzar", self.cross_parents, name="Primary")
        row.addWidget(self.cross)
        row.addWidget(button("Ejemplo de clase", self._example_cross))
        cross_layout.addLayout(row)
        cross_layout.addWidget(label("Elige un nodo de cada padre para cortar su arista, o deja ambos cortes al azar. La raíz no es un corte válido.", "Muted", True))
        self.cut_paths = [None, None]
        self.cross_panes = [self._pane(title) for title in ("Padre A · antes", "Padre B · antes", "Hijo A · después", "Hijo B · después")]
        grid = QGridLayout()
        for i, pane in enumerate(self.cross_panes):
            grid.addWidget(pane, i % 2, i // 2)
        for i in range(2):
            self.cross_panes[i].canvas.nodeSelected.connect(lambda node, side=i: self._cut_selected(side, node))
        cross_layout.addLayout(grid, 1)
        self.cross_note = label("Azul: rama de A · verde: rama de B · naranja: operando que repara una poda.", "Muted", True)
        cross_layout.addWidget(self.cross_note)
        cross_scroll = QScrollArea()
        cross_scroll.setWidgetResizable(True)
        cross_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cross_scroll.setWidget(cross_page)
        self.lab.addTab(cross_scroll, "Cruza")
        self.parent_a.currentIndexChanged.connect(self._parent_changed)
        self.parent_b.currentIndexChanged.connect(self._parent_changed)
        mutation_page = QWidget()
        mutation_layout = QVBoxLayout(mutation_page)
        row = QHBoxLayout()
        row.addWidget(label("Árbol de prueba", "Muted"))
        self.mutation_source = QComboBox()
        self.mutation_source.setAccessibleName("Origen del árbol de la demostración de mutación")
        row.addWidget(self.mutation_source, 1)
        row.addStretch()
        mutation_layout.addLayout(row)
        row = QHBoxLayout()
        self.lab_method = QComboBox()
        for key, title in MUTATIONS.items():
            self.lab_method.addItem(title, key)
        self.lab_method.setAccessibleName("Método de mutación manual")
        self.target = QComboBox()
        self.target.setMinimumWidth(120)
        self.target.setAccessibleName("Nodo de la mutación; incluye la raíz para subrama aleatoria")
        self.replacement = QLineEdit()
        self.replacement.setPlaceholderText("Operando al azar")
        self.replacement.setMaximumWidth(140)
        self.replacement.setAccessibleName("Nuevo operando u operador; vacío elige al azar")
        self.mutate_button = button("Mutar", self.mutate_tree, name="Primary")
        for widget in (self.lab_method, self.target, self.replacement, self.mutate_button):
            row.addWidget(widget)
        mutation_layout.addLayout(row)
        self.method_note = label("", "Muted", True)
        mutation_layout.addWidget(self.method_note)
        self.mutation_before, self.mutation_after = self._pane("Antes · genotipo"), self._pane("Después · genotipo")
        row = QHBoxLayout()
        row.addWidget(self.mutation_before, 1)
        row.addWidget(self.mutation_after, 1)
        mutation_layout.addLayout(row, 1)
        self.mutation_note = label("Borde punteado: gen recesivo. Un operador unario siempre evalúa la izquierda.", "Muted", True)
        mutation_layout.addWidget(self.mutation_note)
        self.continue_mutation = button("Continuar desde el resultado", self._continue_mutation)
        self.continue_mutation.setEnabled(False)
        mutation_layout.addWidget(self.continue_mutation, alignment=Qt.AlignmentFlag.AlignRight)
        mutation_layout.addWidget(label("Esta demostración aplica siempre la mutación elegida. Sus resultados solo cambian al enviarlos al explorador.", "Muted", True))
        self.lab.addTab(mutation_page, "Mutación")
        self.mutation_source.currentIndexChanged.connect(self._mutation_source_changed)
        self.lab_method.currentIndexChanged.connect(self._mutation_targets)
        self.mutation_before.canvas.nodeSelected.connect(self._mutation_node_selected)

    def _build_archive(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Las mejores soluciones de toda la ejecución", "PanelTitle"))
        layout.addWidget(label("El Hall of Fame conserva genotipos distintos y sus métricas, aunque desaparezcan de la población. El elitismo copia los mejores individuos a la siguiente generación. El archivo no se reinserta automáticamente.", "Muted", True))
        self.archive_table = table(["Individuo", "Generación", "Pérdida ↓", "MSE", "NMSE", "R²", "Ecuación"])
        self.archive_table.setAccessibleName("Hall of Fame de soluciones históricas")
        self.archive_table.itemSelectionChanged.connect(self._inspect_archive)
        layout.addWidget(self.archive_table, 1)
        self.archive_tree = self._pane("Solución del archivo")
        layout.addWidget(self.archive_tree, 2)
        self.archive_note = label("Inicia una ejecución para llenar el archivo. Capacidad 0 lo desactiva.", "Muted", True)
        layout.addWidget(self.archive_note)
        self.tabs.addTab(page, "Hall of Fame")

    def _build_progress(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("Adaptación por generación", "PanelTitle"))
        layout.addWidget(label("Azul: mejor pérdida de la población · naranja: media de individuos válidos. Los inválidos no entran en la media y siguen contados en la tabla.", "Muted", True))
        self.progress = ProgressChart()
        layout.addWidget(self.progress, 2)
        self.history_table = table(["Generación", "Mejor ↓", "Media", "Válidos", "Cruzas", "Mutaciones", "Podas"])
        layout.addWidget(self.history_table, 2)
        self.event_picker = QComboBox()
        self.event_picker.setAccessibleName("Operación real de la última generación para inspeccionar")
        self.event_picker.addItem("Los detalles de operaciones aparecerán durante la ejecución.", None)
        self.event_picker.currentIndexChanged.connect(self._inspect_event)
        layout.addWidget(self.event_picker)
        self.tabs.addTab(page, "Progreso")

    def _demo_source_changed(self, *_args) -> None:
        from_run = self.demo_source.currentData() == "run"
        self.refresh_demo.setVisible(from_run)
        if from_run:
            if not self.displayed:
                self.demo_error.setText("Inicia primero una ejecución para copiar su población.")
                self.demo_error.show()
                return
            self.demo_population = [ind.copy() for ind in self.displayed]
            self.demo_population_note.setText(f"Copia de la generación {self.displayed[0].generation} · {len(self.demo_population)} individuos. "
                                              "Actualizar copia importa la última generación terminada.")
        else:
            reference = tuple(SamplePoint(i / 10, (i / 10)**2 + i / 10 + 1) for i in range(-10, 11))
            self.demo_population = []
            for i, expression in enumerate(("x", "2*x", "x^2", "x^2+1", "x^2+x+1", "3"), 1):
                ind = Individual(i, detect_and_parse(expression, "infix", False)[0], 0)
                evaluate_individual(ind, reference, {}, "x", RepairConfig(enabled=False), "mse")
                self.demo_population.append(ind)
            self.demo_population_note.setText("Ejemplo de clase · 6 ecuaciones comparadas con x² + x + 1 en 21 puntos de [−1, 1]. Adaptación: MSE.")
        self.demo_tournament.setMaximum(len(self.demo_population))
        self._clear_demo_selection()
        self._populate_demo_parents()
        self.mutation_source.blockSignals(True)
        self.mutation_source.clear()
        self.mutation_source.addItem("Árbol del explorador", "explorer")
        self.mutation_source.addItem("Ejemplo switching · genes recesivos", "switch")
        for ind in self.demo_population:
            self.mutation_source.addItem(f"#{ind.id} · {ind.expression[:70]}", f"ind:{ind.id}")
        self.mutation_source.blockSignals(False)
        self._mutation_source_changed()
        self.demo_error.hide()

    def _clear_demo_selection(self, *_args) -> None:
        self.selection_chart.clear()
        self._fill(self.selection_table, [[f"#{ind.id}", self._value(ind.loss), "—", "0"] for ind in self.demo_population])
        self.demo_tournament.setEnabled(self.demo_selection.currentData() == "tournament")
        self.selection_note.setText("Selecciona una pareja para ver los candidatos o los punteros. Los padres elegidos quedan disponibles en Cruza.")

    def _populate_demo_parents(self) -> None:
        self.manual_parents = None
        for combo in (self.parent_a, self.parent_b):
            combo.blockSignals(True)
            combo.clear()
            for ind in self.demo_population:
                combo.addItem(f"#{ind.id} · {ind.expression[:45]}", ind.id)
            combo.blockSignals(False)
        self.parent_b.blockSignals(True)
        self.parent_b.setCurrentIndex(min(1, len(self.demo_population) - 1))
        self.parent_b.blockSignals(False)
        self._parent_changed()

    def _mutation_source_changed(self, *_args) -> None:
        source = self.mutation_source.currentData()
        if source == "switch":
            self._example_switch()
        elif source == "explorer":
            self._set_mutation_source(self.explorer_root)
        elif source == "result":
            if self.previous_mutation_root is not None:
                self._set_mutation_source(self.previous_mutation_root)
        elif source:
            ind = next(ind for ind in self.demo_population if f"ind:{ind.id}" == source)
            self._set_mutation_source(ind.root)

    def demo_generation_config(self) -> GenerationConfig:
        return GenerationConfig(self.demo_depth.value() + 1,
            self.initial_generation.operators or GENERATOR_OPERATORS,
            variable=self.initial_generation.variable)

    def generation_config(self) -> GenerationConfig:
        seed = self.seed.text().strip()
        try:
            seed_value = int(seed) if seed else None
        except ValueError:
            raise ValueError("La semilla debe ser un entero o quedar vacía.") from None
        return GenerationConfig(self.depth.value() + 1, tuple(t for t, c in self.operators.items() if c.isChecked()),
                                seed_value, self.variable.text().strip(), 63)

    def configuration(self) -> EvolutionConfig:
        return EvolutionConfig(
            generation=self.generation_config(), population_size=self.population_size.value(),
            selection=self.selection.currentData(), tournament_size=self.tournament.value(),
            crossover_probability=self.cross_probability.value() / 100,
            mutation_probability=self.mutation_probability.value() / 100,
            mutations=tuple(key for key, control in self.mutation_types.items() if control.isChecked()),
            elite_count=self.elite.value(), hall_of_fame_size=self.archive_size.value(),
            metric=self.fitness_metric.currentData(), max_generations=self.generations.value(),
            tolerance=self.tolerance.value())

    def _size_changed(self) -> None:
        self.elite.setMaximum(self.population_size.value() - 1)
        self.tournament.setMaximum(self.population_size.value())

    def _source_changed(self) -> None:
        csv = self.source.currentIndex() == 1
        self.reference.setVisible(not csv)
        self.csv_button.setVisible(csv)
        for control in (self.minimum, self.maximum, self.samples):
            control.setEnabled(not csv)
        self.data_note.setText("El CSV aporta todos sus valores x,y exactos." if csv else
                              f"{self.samples.value()} puntos entre {self.minimum.value():g} y {self.maximum.value():g}. Ajustes en Opciones avanzadas.")

    def invalidate(self, *_args) -> None:
        if self.source.currentIndex() == 0:
            self.data_note.setText(f"{self.samples.value()} puntos entre {self.minimum.value():g} y {self.maximum.value():g}. "
                                   "Ajustes en Opciones avanzadas.")
        if self.run:
            self.stale = True
            self.running = False
            self.timer.stop()
            self.status.setText("Ajustes modificados. Inicia una nueva ejecución para aplicarlos; los resultados visibles pertenecen a la anterior.")
            self._buttons()

    def load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Referencia de evolución", "", "CSV (*.csv);;Todos (*)")
        if not path:
            return
        try:
            points = read_points_csv(path)
            if any(p.y is None for p in points):
                raise ValueError("La evolución requiere una y en cada fila; completa las celdas vacías del CSV.")
            self.csv_points = points
            self.csv_button.setText(FilePath(path).name)
            self.csv_button.setToolTip(path)
            self.data_note.setText(f"{len(points)} puntos exactos del CSV. El intervalo no los filtra.")
            self.error.hide()
            self.invalidate()
        except (OSError, ValueError) as exc:
            self._error(str(exc))

    def _reference_points(self, cfg: EvolutionConfig) -> tuple[SamplePoint, ...]:
        if self.source.currentIndex() == 1:
            if self.csv_points is None:
                raise ValueError("Carga un CSV de referencia con columnas x,y.")
            return self.csv_points
        if self.minimum.value() >= self.maximum.value():
            raise ValueError("El inicio del intervalo debe ser menor que el final.")
        text = self.reference.text().strip()
        if text.startswith("y") and "=" in text:
            text = text.split("=", 1)[1].strip()
        root = detect_and_parse(text, "infix", False)[0]
        xs = tuple(self.minimum.value() + (self.maximum.value() - self.minimum.value()) * i / (self.samples.value() - 1)
                   for i in range(self.samples.value()))
        return sample_points(root, self.variables, xs, variable=cfg.generation.variable,
                             repair_config=replace(self.repairs, enabled=self.protected.isChecked()))

    def start_run(self) -> None:
        """The main action prepares G0, then runs every evolutionary phase."""
        self.initialize()
        if self.busy:
            self.tabs.setCurrentIndex(0)
            self.running = True
            self._buttons()

    def initialize(self) -> None:
        if self.busy:
            return
        self.running = False
        self.timer.stop()
        try:
            cfg = self.configuration()
            cfg.validate()
            run = EvolutionRun(cfg, self._reference_points(cfg), variables=self.variables,
                               repairs=replace(self.repairs, enabled=self.protected.isChecked()))
        except (ValueError, ParseError) as exc:
            self._error(str(exc))
            return
        def work():
            run.initialize()
            return run
        self._work(work, "Generando y evaluando la población…")

    def advance(self) -> None:
        if self.busy or not self.run or self.stale or self.run.stop_reason:
            return
        run = self.run
        def work():
            run.advance()
            return run
        self._work(work, f"Evaluando generación {run.generation + 1}…")

    def _work(self, work, status: str) -> None:
        self.error.hide()
        self.busy = True
        self.status.setText(status)
        self._buttons()
        worker = EvolutionWorker(work, self)
        self.worker = worker
        worker.succeeded.connect(self._received)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def _received(self, run: EvolutionRun) -> None:
        self.run, self.stale = run, False

    def _failed(self, message: str) -> None:
        self.running = False
        self._error(message)

    def _finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self.busy = False
        if self.run:
            self._refresh_run()
        self._buttons()
        if self.close_pending:
            self.close_pending = False
            self.close()
        elif self.running and self.run and not self.run.stop_reason:
            self.timer.start()

    def toggle_running(self) -> None:
        self.running = not self.running
        if self.running:
            self.advance()
        else:
            self.timer.stop()
            self.status.setText("Evolución pausada. Se conserva la ejecución." + (" Terminando la generación en curso…" if self.busy else ""))
        self._buttons()

    def _buttons(self) -> None:
        ready = self.run is not None and not self.stale and not self.run.stop_reason
        self.create.setVisible(not self.running)
        self.create.setEnabled(not self.busy)
        self.create.setText("Iniciar nueva ejecución" if self.run else "Iniciar ejecución")
        self.next.setVisible(bool(ready and not self.running and not self.busy))
        self.next.setEnabled(bool(ready and not self.busy))
        self.play.setVisible(bool(self.running or ready))
        self.play.setEnabled(bool(self.running or ready and not self.busy))
        self.play.setText("Pausar" if self.running else "Continuar ejecución")
        for control, primary in ((self.create, not ready), (self.play, bool(ready and not self.running))):
            name = "Primary" if primary else "Quiet"
            if control.objectName() != name:
                control.setObjectName(name)
                control.style().unpolish(control)
                control.style().polish(control)
        self.settings.setEnabled(not self.busy and not self.running)
        self.demo_source.model().item(1).setEnabled(bool(self.displayed))
        self.workspace.setTabText(0, "Algoritmo completo · en curso" if self.running else "Algoritmo completo")

    def _error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()

    @staticmethod
    def _fill(widget: QTableWidget, rows: list[list[str]]) -> None:
        widget.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                widget.setItem(r, c, item)

    @staticmethod
    def _value(value) -> str:
        return "—" if value is None or not math.isfinite(value) else format_number(value)

    def _refresh_run(self) -> None:
        run = self.run
        cfg = run.config
        stats = run.history[-1]
        self.comparison.set_run(run)
        self.displayed = sorted(run.population, key=lambda ind: ind.loss)
        self._fill(self.population_table, [[f"#{i.id}", self._value(i.loss), i.origin, i.expression] for i in self.displayed])
        self.population_table.selectRow(0)
        self._inspect_population()
        self.summary.setText(f"Generación {run.generation} / {cfg.max_generations}   ·   Mejor {cfg.metric.upper().replace('R2', 'R²')}: "
                             f"{self._value(run.best.metrics.get(cfg.metric))}   ·   {stats.valid}/{cfg.population_size} válidos   ·   "
                             f"{cfg.elite_count} élites   ·   {len(run.reference)} puntos")
        self.archive_displayed = list(run.hall_of_fame)
        self._fill(self.archive_table, [[f"#{i.id}", str(i.generation), self._value(i.loss), self._value(i.metrics.get("mse")),
                    self._value(i.metrics.get("nmse")), self._value(i.metrics.get("r2")), i.expression] for i in self.archive_displayed])
        if self.archive_displayed:
            self.archive_table.selectRow(0)
            self._inspect_archive()
        else:
            self.archive_tree.clear()
        self.progress.history = list(run.history)
        self.progress.update()
        self._fill(self.history_table, [[str(s.generation), self._value(s.best), self._value(s.mean), f"{s.valid}/{cfg.population_size}",
                    str(s.crossovers), str(s.mutations), str(s.repairs)] for s in run.history])
        self.history_table.scrollToBottom()
        self.event_picker.blockSignals(True)
        self.event_picker.clear()
        self.event_picker.addItem("Inspeccionar una operación real de esta generación…", None)
        for event in run.events:
            if event.crossover:
                self.event_picker.addItem(f"Cruza: padres #{event.parents[0]}, #{event.parents[1]} → " + ", ".join(f"#{i}" for i in event.children), event.crossover)
            for mutation in event.mutations:
                self.event_picker.addItem(f"Mutación {mutation.name}: pareja #{event.parents[0]}, #{event.parents[1]}", mutation)
        self.event_picker.blockSignals(False)
        self.status.setText(run.stop_reason or ("Evolucionando…" if self.running else "Ejecución pausada. Continúa el ciclo o avanza una generación completa."))
        if not stats.valid:
            self.status.setText("Todos los individuos son inválidos. Puedes evolucionar para buscar soluciones o revisar el dominio y los operadores.")
        if run.stop_reason:
            self.running = False

    def _inspect_population(self) -> None:
        row = self.population_table.currentRow()
        if 0 <= row < len(self.displayed):
            ind = self.displayed[row]
            self.population_tree.title.setText(f"Genotipo · #{ind.id}")
            self.population_tree.set_tree(ind.root)
            self.individual_note.setText(ind.error or f"MSE {self._value(ind.metrics.get('mse'))} · NMSE {self._value(ind.metrics.get('nmse'))} · "
                f"R² {self._value(ind.metrics.get('r2'))} · {len(traverse_preorder(ind.root))} nodos · "
                f"nivel máximo {tree_height(ind.root) - 1} · {ind.repaired_samples} puntos reparados")
        else:
            self.population_tree.clear()
            self.individual_note.setText("Selecciona una fila para ver genotipo, fenotipo y adaptación.")

    def _inspect_archive(self) -> None:
        row = self.archive_table.currentRow()
        if 0 <= row < len(self.archive_displayed):
            self.archive_tree.set_tree(self.archive_displayed[row].root)

    def select_pair(self) -> None:
        if not self.demo_population:
            return
        method = self.demo_selection.currentData()
        result = select_parents(self.demo_population, 2, method, self.lab_rng, self.demo_tournament.value())
        self.selection_chart.set_selection(result, [ind.id for ind in self.demo_population])
        counts = Counter(result.indices)
        self._fill(self.selection_table, [[f"#{ind.id}", self._value(ind.loss),
                f"{result.probabilities[i]:.2%}" if result.probabilities else "Depende del torneo", str(counts[i])]
                for i, ind in enumerate(self.demo_population)])
        selected = [self.demo_population[i] for i in result.indices]
        self.manual_parents = None
        if any(combo.findData(ind.id) < 0 for combo, ind in zip((self.parent_a, self.parent_b), selected)):
            self._populate_demo_parents()
        for combo, ind in zip((self.parent_a, self.parent_b), selected):
            combo.setCurrentIndex(combo.findData(ind.id))
        self.selection_note.setText(f"{SELECTIONS[method]} eligió #{selected[0].id} y #{selected[1].id}. " +
            ("SUS usa un inicio aleatorio y dos punteros separados por 0.5. " if method == "sus" else "") +
            "Puedes probar su cruza en la siguiente pestaña. La ejecución completa no cambia.")

    def _parents(self) -> tuple[ExprNode, ExprNode]:
        if self.manual_parents:
            return self.manual_parents
        by_id = {ind.id: ind.root for ind in self.demo_population}
        return by_id[self.parent_a.currentData()], by_id[self.parent_b.currentData()]

    def _parent_changed(self, *_args) -> None:
        if self.parent_a.currentData() is None or self.parent_b.currentData() is None:
            return
        self.cut_paths = [None, None]
        for pane, root in zip(self.cross_panes[:2], self._parents()):
            pane.set_tree(root)
        for pane in self.cross_panes[2:]:
            pane.clear()
        self.cross_note.setText("Cruza estos padres para comparar sus hijos. Azul: rama A · verde: rama B · naranja: reparación.")

    def _example_cross(self) -> None:
        self.manual_parents = tuple(detect_and_parse(t, "infix", False)[0] for t in ("2 + 3*x", "5 - x/2"))
        for i, combo in enumerate((self.parent_a, self.parent_b)):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(f"Ejemplo {'A' if i == 0 else 'B'}", "example")
            combo.blockSignals(False)
        self.cut_paths = [(1,), (0,)]
        for pane, root, path, color in zip(self.cross_panes, self.manual_parents, self.cut_paths, (BLUE, GREEN)):
            pane.set_tree(root, path, color)
        for pane in self.cross_panes[2:]:
            pane.clear()

    def _cut_selected(self, side: int, node: ExprNode) -> None:
        root = self.cross_panes[side].root
        path = next(p for p in tree_paths(root) if at_path(root, p).id == node.id)
        if not path:
            self.cut_paths[side] = None
            self.cross_note.setText("La raíz no tiene arista de entrada. El corte de este padre será aleatorio.")
            return
        self.cut_paths[side] = path
        self.cross_panes[side].set_tree(root, path, BLUE if side == 0 else GREEN)
        self.cross_note.setText("Corte fijado. Al cruzar se intercambiarán los subárboles marcados; el otro corte puede quedar al azar.")

    def cross_parents(self) -> None:
        try:
            a, b = self._parents()
            self._show_cross(crossover(a, b, self.demo_generation_config(), self.lab_rng, *self.cut_paths))
            self.demo_error.hide()
        except (ValueError, ParseError, KeyError) as exc:
            self.demo_error.setText(str(exc))
            self.demo_error.show()

    def _show_cross(self, change: GeneticChange) -> None:
        self.last_change = change
        for i in range(2):
            path = change.paths[i]
            self.cross_panes[i].set_tree(change.before[i], path, BLUE if i == 0 else GREEN)
            repairs = change.repairs[i] if change.repairs else ()
            self.cross_panes[i + 2].set_tree(change.after[i], path, GREEN if i == 0 else BLUE, repairs)
        self.cross_note.setText(" ".join(change.notes) + " Azul: A · verde: B · naranja: reparación.")
        if change.raw:
            self.cross_note.setToolTip("Antes de reparar: " + " | ".join(to_infix_string(r) for r in change.raw))

    def _set_mutation_source(self, root: ExprNode) -> None:
        self.mutation_root = clone_tree(root)
        self.mutation_before.set_tree(root)
        self.mutation_after.clear()
        self.continue_mutation.setEnabled(False)
        self._mutation_targets()

    def _mutation_targets(self, *_args) -> None:
        method = self.lab_method.currentData()
        self.target.clear()
        self.target.addItem("Nodo al azar", None)
        for path in tree_paths(self.mutation_root):
            node = at_path(self.mutation_root, path)
            if ((method == "leaf" and node.is_leaf) or (method == "operator" and node.children) or
                (method == "switch" and len(node.children) == 2) or method == "subtree"):
                route = "raíz" if not path else "/".join("izq" if i == 0 else "der" for i in path)
                self.target.addItem(f"{route} · {node.value}", path)
        self.replacement.setVisible(method in ("leaf", "operator"))
        self.replacement.setPlaceholderText("Operador al azar" if method == "operator" else "Operando al azar")
        self.replacement.clear()
        descriptions = {
            "leaf": "Cambia una hoja por una constante o variable. Puedes escribir 3.2, pi o x.",
            "operator": "Cambia un operador. Puedes escribir sqrt, log, +… La rama derecha de un unario queda recesiva.",
            "switch": "Intercambia dos ramas. En unarios, la derecha recesiva pasa a dominar.",
            "subtree": "Reemplaza cualquier subrama, incluida la raíz, por un árbol aleatorio dentro de la altura máxima."}
        self.method_note.setText(descriptions[method])

    def _mutation_node_selected(self, node: ExprNode) -> None:
        root = self.mutation_before.root
        path = next(p for p in tree_paths(root) if at_path(root, p).id == node.id)
        for i in range(1, self.target.count()):
            if self.target.itemData(i) == path:
                self.target.setCurrentIndex(i)
                return
        self.mutation_note.setText("Este nodo no es compatible con el método elegido. Cambia el método o selecciona otro nodo.")

    def mutate_tree(self) -> None:
        try:
            cfg = self.demo_generation_config()
            method = self.lab_method.currentData()
            replacement = self.replacement.text().strip() or None
            change = mutate(self.mutation_root, method, cfg, self.lab_rng, self.target.currentData(),
                            operator=replacement if method == "operator" else None,
                            operand=replacement if method == "leaf" else None)
            self._show_mutation(change)
            self.demo_error.hide()
        except (ValueError, ParseError, KeyError) as exc:
            self.demo_error.setText(str(exc))
            self.demo_error.show()

    def _show_mutation(self, change: GeneticChange) -> None:
        self.last_change = change
        self.mutation_before.set_tree(change.before[0], change.paths[0], BLUE)
        self.mutation_after.set_tree(change.after[0], change.paths[0], GREEN, change.repairs[0] if change.repairs else ())
        self.mutation_note.setText(" ".join(change.notes) + (" Se podaron ramas para respetar los límites." if any(change.repairs) else ""))
        self.continue_mutation.setEnabled(change.applied)

    def _continue_mutation(self) -> None:
        if self.mutation_after.root:
            self.previous_mutation_root = clone_tree(self.mutation_after.root)
            self.mutation_source.blockSignals(True)
            if self.mutation_source.findData("result") < 0:
                self.mutation_source.addItem("Resultado de la última mutación", "result")
            self.mutation_source.setCurrentIndex(self.mutation_source.findData("result"))
            self.mutation_source.blockSignals(False)
            self._set_mutation_source(self.previous_mutation_root)
            self.continue_mutation.setEnabled(False)

    def _example_switch(self) -> None:
        self.mutation_source.blockSignals(True)
        self.mutation_source.setCurrentIndex(self.mutation_source.findData("switch"))
        self.mutation_source.blockSignals(False)
        root = detect_and_parse("2*x + x/5", "infix", False)[0]
        root.value, root.kind = "sqrt", "func"
        self.lab_method.setCurrentIndex(self.lab_method.findData("switch"))
        self._set_mutation_source(root)
        for i in range(1, self.target.count()):
            if self.target.itemData(i) == ():
                self.target.setCurrentIndex(i)
        self.mutation_note.setText("√(2·x) tiene x/5 como rama recesiva. Muta para activar esa rama y obtener √(x/5).")

    def _inspect_event(self) -> None:
        change = self.event_picker.currentData()
        if not isinstance(change, GeneticChange):
            return
        if self.operation_window is not None:
            self.operation_window.close()
            self.operation_window.deleteLater()
        title = f"Generación {self.run.generation} · {self.event_picker.currentText()}"
        self.operation_window = OperationPreview(change, title, self)
        self.operation_window.treeRequested.connect(self.treeRequested.emit)
        self.operation_window.show()
        self.event_picker.blockSignals(True)
        self.event_picker.setCurrentIndex(0)
        self.event_picker.blockSignals(False)

    def _open_tree(self, root: ExprNode | None) -> None:
        if root:
            self.treeRequested.emit(clone_tree(root))

    def closeEvent(self, event) -> None:
        self.running = False
        self.timer.stop()
        if self.busy:
            self.close_pending = True
            event.ignore()
            return
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        for pane in self.findChildren(TreePane):
            QTimer.singleShot(0, pane.canvas.fit_tree_in_view)
