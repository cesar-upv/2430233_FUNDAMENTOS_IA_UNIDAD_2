from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QMainWindow, QScrollArea, QSlider, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget

from .canvas import ExpressionTreeCanvas
from .evaluation import rewrite_tree_with_structural_repairs
from .models import ExprNode, ParseError, format_number
from .generation import GenerationConfig
from .genetics import clone_tree
from .session import ExpressionSession
from .presets import PRESETS
from .tree import extract_variables, to_infix_string, traverse_inorder, traverse_preorder, traverse_postorder, tree_height
from .ui.curve import CurvePanel
from .ui.details import InterpreterPanel, RepairsPanel, StepsPanel, TraversalsPanel
from .ui.evaluation import EvaluationPanel
from .ui.generator import GeneratorPanel
from .ui.metrics import MetricsWindow
from .ui.evolution import EvolutionWindow
from .ui.theme import BLUE, PAPER, apply_theme
from .ui.widgets import button, icon, icon_button, label, rule, surface



class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        apply_theme(QApplication.instance())
        self.setWindowTitle("Expresiones · Árboles y curvas")
        self.setWindowIcon(icon("tree", BLUE))
        self.resize(1440, 960)
        self.setMinimumSize(1024, 740)
        self.session = ExpressionSession()
        self.metrics_window: MetricsWindow | None = None
        self.evolution_window: EvolutionWindow | None = None
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._advance_animation_step)
        self.anim_sequence: list[int] = []
        self.anim_index = -1
        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(550)
        self.live_timer.timeout.connect(self._parse_and_update)
        self._build_ui()
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._parse_and_update)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.generator.request)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.canvas.fit_tree_in_view)
        self._load_preset(PRESETS[0].expression, PRESETS[0].mode)

    @property
    def root_node(self) -> ExprNode | None:
        return self.session.root

    @property
    def repair_config(self):
        return self.session.repairs

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        mark = label("")
        mark.setPixmap(icon("tree", BLUE, 30).pixmap(30, 30))
        header.addWidget(mark)
        title = QVBoxLayout()
        title.setSpacing(1)
        title.addWidget(label("Expresiones", "Title"))
        title.addWidget(label("Una ecuación. Cada una de sus formas.", "Muted"))
        header.addLayout(title)
        header.addStretch()
        header.addWidget(button("Evolución", self._open_evolution, glyph="tree"))
        header.addWidget(button("Métricas de error", self._open_metrics))
        self.examples = QComboBox()
        self.examples.setAccessibleName("Cargar un ejemplo")
        self.examples.addItem("Explorar ejemplos")
        self.examples.addItems([preset.name for preset in PRESETS])
        self.examples.setMaximumWidth(250)
        self.examples.currentIndexChanged.connect(self._example_selected)
        header.addWidget(self.examples)
        header.addWidget(button("Exportar árbol", self._export_png, glyph="export"))
        layout.addLayout(header)

        editor, editor_layout = surface()
        editor_layout.setContentsMargins(12, 4, 10, 4)
        editor_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        for name, code in (("Automática", "auto"), ("Infija", "infix"), ("Prefija", "prefix"), ("Postfija", "postfix")):
            self.mode_combo.addItem(name, code)
        self.mode_combo.setFixedWidth(125)
        self.mode_combo.setAccessibleName("Notación de entrada")
        editor_row.addWidget(self.mode_combo)
        fx = label("f =", "PanelTitle")
        editor_row.addWidget(fx)
        self.expression_input = QLineEdit()
        self.expression_input.setObjectName("Expression")
        self.expression_input.setPlaceholderText("sen(x) + x ^ 2 / 6")
        self.expression_input.setAccessibleName("Expresión matemática")
        self.expression_input.setClearButtonEnabled(True)
        self.expression_input.returnPressed.connect(self._parse_and_update)
        self.expression_input.textChanged.connect(self._edited)
        editor_row.addWidget(self.expression_input, 1)
        editor_row.addWidget(button("Construir árbol", self._parse_and_update, name="Primary"))
        editor_layout.addLayout(editor_row)
        layout.addWidget(editor)
        self.error = label("", "Error", True)
        self.error.hide()
        layout.addWidget(self.error)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(12)
        self.main_splitter.setChildrenCollapsible(False)
        self.visual_splitter = QSplitter(Qt.Orientation.Vertical)
        self.visual_splitter.setHandleWidth(10)
        self.visual_splitter.setChildrenCollapsible(False)
        tree_frame, tree_layout = surface()
        tree_layout.setContentsMargins(14, 12, 14, 10)
        tree_layout.setSpacing(5)
        heading = QHBoxLayout()
        heading.addWidget(label("Árbol de expresión", "PanelTitle"))
        self.tree_meta = label("", "Muted")
        heading.addWidget(self.tree_meta)
        heading.addStretch()
        heading.addWidget(icon_button("minus", "Alejar el árbol", self.canvas_zoom_out))
        heading.addWidget(icon_button("plus", "Acercar el árbol", self.canvas_zoom_in))
        heading.addWidget(icon_button("fit", "Ajustar árbol a la vista · Ctrl+0", self._fit))
        tree_layout.addLayout(heading)
        tools = QHBoxLayout()
        for text, color in (("Operador", "#9D4310"), ("Función", "#1C6C66"), ("Variable", "#5E409D")):
            legend = label(text, "Muted")
            legend.setStyleSheet(f"color: {color}; font-size: 11px;")
            tools.addWidget(legend)
        tools.addStretch()
        self.show_values = QCheckBox("Valores")
        self.show_values.setChecked(True)
        tools.addWidget(self.show_values)
        tools.addSpacing(10)
        tools.addWidget(label("Niveles visibles", "Muted"))
        self.visible_levels = QSpinBox()
        self.visible_levels.setRange(1, 64)
        self.visible_levels.setValue(6)
        self.visible_levels.setFixedWidth(65)
        self.visible_levels.setAccessibleName("Niveles visibles del árbol. Pliega ramas sin modificar la ecuación.")
        self.visible_levels.setToolTip("Pliega las ramas que excedan este nivel. La expresión completa se conserva.")
        tools.addWidget(self.visible_levels)
        tree_layout.addLayout(tools)
        self.canvas = ExpressionTreeCanvas()
        self.canvas.nodeSelected.connect(self._inspect)
        self.show_values.toggled.connect(self.canvas.set_show_eval_badges)
        self.visible_levels.valueChanged.connect(self._fold_tree)
        tree_layout.addWidget(self.canvas, 1)
        self.inspector = label("Selecciona un nodo para explorar su subexpresión.", "Muted")
        self.inspector.setMinimumWidth(0)
        self.inspector.setWordWrap(True)
        self.inspector.setMaximumHeight(38)
        tree_layout.addWidget(self.inspector)
        tree_layout.addWidget(rule())
        animation = QHBoxLayout()
        self.traversal_mode = QComboBox()
        for name in ("Preorden", "Inorden", "Postorden", "Evaluación"):
            self.traversal_mode.addItem(name)
        self.traversal_mode.setAccessibleName("Orden de animación")
        self.traversal_mode.currentIndexChanged.connect(self._stop_animation)
        animation.addWidget(self.traversal_mode)
        self.play = icon_button("play", "Reproducir o pausar recorrido", self._toggle_play)
        animation.addWidget(self.play)
        animation.addWidget(icon_button("next", "Avanzar un nodo", self._step_animation_forward))
        animation.addWidget(icon_button("reset", "Reiniciar recorrido", self._stop_animation))
        self.animation_note = label("Explora el recorrido", "Muted")
        animation.addWidget(self.animation_note)
        animation.addStretch()
        animation.addWidget(label("Velocidad", "Muted"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1, 10)
        self.speed.setValue(5)
        self.speed.setFixedWidth(75)
        self.speed.setAccessibleName("Velocidad de animación")
        self.speed.valueChanged.connect(lambda value: self.anim_timer.setInterval(1300 - value * 110))
        animation.addWidget(self.speed)
        tree_layout.addLayout(animation)
        self.visual_splitter.addWidget(tree_frame)

        details_frame, details_layout = surface()
        details_layout.setContentsMargins(12, 0, 12, 8)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.setMinimumHeight(200)
        self.curve = CurvePanel()
        self.curve.settingsChanged.connect(self._update_metrics_context)
        self.curve.statusChanged.connect(lambda message: self.status.setText(message))
        self.traversals = TraversalsPanel()
        self.steps = StepsPanel()
        self.interpreter = InterpreterPanel()
        self.repairs = RepairsPanel(self.session.repairs)
        for panel, title in ((self.curve, "Curva"), (self.traversals, "Recorridos"), (self.steps, "Paso a paso"), (self.interpreter, "Intérprete"), (self.repairs, "Reparaciones")):
            self.tabs.addTab(panel, title)
        self.traversals.nodeSelected.connect(self._select_node)
        self.steps.nodeSelected.connect(self._select_node)
        self.interpreter.executeRequested.connect(self._execute)
        self.interpreter.expressionRequested.connect(lambda expr: self._load_preset(expr, "auto"))
        self.repairs.configChanged.connect(self._recalculate_repairs)
        self.repairs.rewriteRequested.connect(self._rewrite)
        details_layout.addWidget(self.tabs)
        self.visual_splitter.addWidget(details_frame)
        self.visual_splitter.setStretchFactor(0, 3)
        self.visual_splitter.setStretchFactor(1, 2)
        self.visual_splitter.setSizes([530, 230])
        self.main_splitter.addWidget(self.visual_splitter)

        side_frame, side_layout = surface()
        side_frame.setMinimumWidth(285)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)
        self.generator = GeneratorPanel()
        self.generator.generateRequested.connect(self._generate)
        content_layout.addWidget(self.generator)
        content_layout.addWidget(rule())
        self.evaluation = EvaluationPanel()
        self.evaluation.variableChanged.connect(self._variable_changed)
        self.evaluation.repairChanged.connect(self._repair_toggled)
        self.evaluation.detailsRequested.connect(lambda: self.tabs.setCurrentWidget(self.repairs))
        content_layout.addWidget(self.evaluation)
        content_layout.addStretch()
        scroller.setWidget(content)
        side_layout.addWidget(scroller)
        self.main_splitter.addWidget(side_frame)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setSizes([1050, 310])
        layout.addWidget(self.main_splitter, 1)
        footer = QHBoxLayout()
        self.status = label("Listo", "Muted")
        footer.addWidget(self.status)
        footer.addStretch()
        footer.addWidget(label("Arrastra para mover · Rueda para ampliar · Ctrl+G para generar", "Muted"))
        layout.addLayout(footer)
        self.mode_combo.currentIndexChanged.connect(self._parse_and_update)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.canvas.fit_tree_in_view)

    def canvas_zoom_in(self) -> None:
        self.canvas.zoom_in()

    def canvas_zoom_out(self) -> None:
        self.canvas.zoom_out()

    def _fit(self) -> None:
        self.canvas.fit_tree_in_view()

    def _example_selected(self, index: int) -> None:
        if index:
            preset = PRESETS[index - 1]
            self._load_preset(preset.expression, preset.mode)
            if preset.sampling:
                self.curve.set_sampling(preset.sampling)
            self.examples.blockSignals(True)
            self.examples.setCurrentIndex(0)
            self.examples.blockSignals(False)

    def _edited(self, _text: str) -> None:
        self._stop_animation()
        self.status.setText("Cambios pendientes…")
        self.live_timer.start()

    def _load_preset(self, expression: str, mode: str = "auto") -> None:
        self.live_timer.stop()
        self.expression_input.blockSignals(True)
        self.expression_input.setText(expression)
        self.expression_input.blockSignals(False)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(mode)))
        self.mode_combo.blockSignals(False)
        self._parse_and_update()

    def _parse_and_update(self, *_args, silent_errors: bool = False) -> None:
        self.live_timer.stop()
        try:
            self.session.parse(self.expression_input.text(), self.mode_combo.currentData())
        except (ParseError, ValueError) as exc:
            self._stop_animation()
            self.error.setText(f"{exc} Se conserva el último árbol válido.")
            self.error.show()
            self.status.setText("Revisa la expresión de entrada")
            return
        self.error.hide()
        self._refresh(new_tree=True)

    def _refresh(self, *, new_tree: bool = False) -> None:
        self._stop_animation()
        session, root = self.session, self.session.root
        if root is None:
            return
        if new_tree:
            self.canvas.set_tree(root)
            self.traversals.set_tree(root)
        else:
            self.canvas.refresh_evaluations()
        count = len(traverse_preorder(root))
        height = tree_height(root)
        hidden = count - len(self.canvas.node_items)
        self.tree_meta.setText(f"{count} nodos · {height} niveles" + (f" · {hidden} ocultos" if hidden else ""))
        self.evaluation.set_session(session)
        self.steps.set_steps(session.steps)
        self.repairs.set_notes(session.syntax_repairs + session.runtime_repairs, session.repairs.enabled)
        self.curve.set_expression(root, session.variables, session.repairs, extract_variables(root), session.result)
        self.inspector.setText("Selecciona un nodo para explorar su subexpresión.")
        mode = {"infix": "Infija", "prefix": "Prefija", "postfix": "Postfija"}[session.mode]
        self.status.setText(f"{mode} · árbol actualizado" + (" · revisa el dominio" if session.error else ""))

    def _generate(self, config) -> None:
        self.live_timer.stop()
        try:
            expression = self.session.generate(config)
        except ValueError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.error.hide()
        self.expression_input.blockSignals(True)
        self.expression_input.setText(expression)
        self.expression_input.blockSignals(False)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(self.mode_combo.findData("infix"))
        self.mode_combo.blockSignals(False)
        if self.visible_levels.value() < tree_height(self.root_node):
            self.visible_levels.blockSignals(True)
            self.visible_levels.setValue(tree_height(self.root_node))
            self.visible_levels.blockSignals(False)
            self.canvas.max_visible_levels = self.visible_levels.value()
        self._refresh(new_tree=True)
        self.status.setText(f"Árbol generado · altura máxima {config.max_height}" + (f" · semilla {config.seed}" if config.seed is not None else ""))

    def _variable_changed(self, name: str, value: float) -> None:
        self.session.variables[name] = value
        self.session.recalculate()
        self._refresh()

    def _repair_toggled(self, checked: bool) -> None:
        self.session.repairs.enabled = checked
        self._recalculate_repairs()

    def _recalculate_repairs(self) -> None:
        if self.live_timer.isActive() or self.session.root is None:
            self._parse_and_update()
        else:
            self.session.recalculate()
            self._refresh()

    def _fold_tree(self, levels: int) -> None:
        self.canvas.max_visible_levels = levels
        self._refresh(new_tree=True)

    def _inspect(self, node: ExprNode | None) -> None:
        if node:
            expression = to_infix_string(node)
            if len(expression) > 115:
                expression = expression[:112] + "…"
            state = "gen recesivo · no se evalúa" if node.id in self.canvas.recessive_ids else f"= {format_number(node.evaluated)}"
            self.inspector.setText(f"Nodo {node.id} · {expression} {state}" + (" · reparado" if node.repaired else ""))
            self.inspector.setToolTip(to_infix_string(node) + (f"\n{node.repair_note}" if node.repair_note else ""))

    def _select_node(self, node_id: int) -> None:
        node = next((node for node in traverse_preorder(self.root_node) if node.id == node_id), None)
        if node:
            if node.id not in self.canvas.node_items:
                level = self._node_level(self.root_node, node_id)
                self.visible_levels.setValue(level)
            self.canvas.select_node(node_id)
            if node_id in self.canvas.node_items:
                self.canvas.ensureVisible(self.canvas.node_items[node_id], 35, 35)
            self._inspect(node)

    @staticmethod
    def _node_level(root: ExprNode, node_id: int, level: int = 1) -> int:
        if root.id == node_id:
            return level
        return max((MainWindow._node_level(child, node_id, level + 1) for child in root.children), default=0)

    def _prepare_animation(self) -> None:
        root = self.root_node
        if root is None:
            return
        if self.traversal_mode.currentText() == "Evaluación":
            self.anim_sequence = [step.node_id for step in self.session.steps]
        else:
            traversal = {"Preorden": traverse_preorder, "Inorden": traverse_inorder, "Postorden": traverse_postorder}[self.traversal_mode.currentText()]
            self.anim_sequence = [node.id for node in traversal(root)]
        self.anim_index = -1

    def _toggle_play(self) -> None:
        if self.anim_timer.isActive():
            self.anim_timer.stop()
            self.play.setIcon(icon("play"))
            return
        if not self.anim_sequence or self.anim_index >= len(self.anim_sequence) - 1:
            self._prepare_animation()
        if not self.anim_sequence:
            return
        self.play.setIcon(icon("pause"))
        self._advance_animation_step()
        if self.anim_index < len(self.anim_sequence) - 1:
            self.anim_timer.start(1300 - self.speed.value() * 110)

    def _step_animation_forward(self) -> None:
        self.anim_timer.stop()
        self.play.setIcon(icon("play"))
        if not self.anim_sequence or self.anim_index >= len(self.anim_sequence) - 1:
            self._prepare_animation()
        self._advance_animation_step()

    def _advance_animation_step(self) -> None:
        if self.anim_index + 1 >= len(self.anim_sequence):
            self.anim_timer.stop()
            self.play.setIcon(icon("play"))
            return
        self.anim_index += 1
        node_id = self.anim_sequence[self.anim_index]
        visited = {key: i + 1 for i, key in enumerate(self.anim_sequence[:self.anim_index + 1])}
        self.canvas.apply_animation_state(visited, node_id, self.traversal_mode.currentText() == "Evaluación")
        self._inspect(next(node for node in traverse_preorder(self.root_node) if node.id == node_id))
        self.animation_note.setText(f"Nodo {self.anim_index + 1} de {len(self.anim_sequence)}")
        if self.anim_index == len(self.anim_sequence) - 1:
            self.anim_timer.stop()
            self.play.setIcon(icon("play"))

    def _stop_animation(self, *_args) -> None:
        self.anim_timer.stop()
        self.anim_sequence, self.anim_index = [], -1
        if hasattr(self, "canvas"):
            self.canvas.clear_animation_state()
        if hasattr(self, "play"):
            self.play.setIcon(icon("play"))
            self.animation_note.setText("Explora el recorrido")

    def _execute(self, command: str) -> None:
        try:
            target, value = self.session.execute(command)
        except (ParseError, ValueError) as exc:
            self.interpreter.record(command, str(exc), True)
            return
        self.interpreter.record(command, f"{target or 'f'} = {format_number(value)}")
        if target:
            self._refresh()
        else:
            self._load_preset(to_infix_string(self.root_node), "infix")

    def _rewrite(self) -> None:
        if self.root_node:
            expression, changes = rewrite_tree_with_structural_repairs(self.root_node, self.session.variables, self.session.repairs)
            if changes:
                self._load_preset(expression, "infix")
                self.repairs.log.addItems(changes)
                self.status.setText("Reparaciones aplicadas al árbol con los valores actuales")

    def _update_metrics_context(self) -> None:
        if self.metrics_window is not None and self.curve.root is not None:
            self.metrics_window.set_context(self.curve.root, self.curve.variables, self.curve.variable.currentText(), self.curve.sampling_config(), self.curve.curve_config())

    def _open_metrics(self) -> None:
        if self.metrics_window is None:
            self.metrics_window = MetricsWindow(self)
        self._update_metrics_context()
        self.metrics_window.show()
        self.metrics_window.raise_()
        self.metrics_window.activateWindow()
        if self.metrics_window.source.currentIndex() == 0 or self.metrics_window.csv_points is not None:
            self.metrics_window.calculate_metrics()

    def _open_evolution(self) -> None:
        if self.root_node is None:
            return
        if self.evolution_window is None:
            config = GenerationConfig(self.generator.height.value(),
                tuple(t for t, control in self.generator.operators.items() if control.isChecked()),
                variable=self.curve.variable.currentText() or "x")
            self.evolution_window = EvolutionWindow(self.root_node, self.session.variables, config, self.session.repairs, self)
            self.evolution_window.treeRequested.connect(self._accept_evolved_tree)
        else:
            self.evolution_window.explorer_root = clone_tree(self.root_node)
        self.evolution_window.show()
        self.evolution_window.raise_()
        self.evolution_window.activateWindow()

    def _accept_evolved_tree(self, root: ExprNode) -> None:
        self.live_timer.stop()
        self.session.root = clone_tree(root)
        self.session.mode, self.session.syntax_repairs = "infix", []
        self.session.recalculate()
        self.expression_input.blockSignals(True)
        self.expression_input.setText(to_infix_string(root))
        self.expression_input.blockSignals(False)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(self.mode_combo.findData("infix"))
        self.mode_combo.blockSignals(False)
        self.error.hide()
        self._refresh(new_tree=True)
        self.status.setText("Genotipo de evolución cargado. Las ramas recesivas se conservan y se muestran punteadas.")

    def closeEvent(self, event) -> None:
        if self.evolution_window:
            self.evolution_window.running = False
            self.evolution_window.timer.stop()
            worker = self.evolution_window.worker
            if worker:
                worker.wait()
        super().closeEvent(event)

    def _export_png(self) -> None:
        if self.root_node is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar árbol visible", "arbol.png", "Imagen PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        scene = self.canvas.scene()
        rect = scene.itemsBoundingRect().adjusted(-35, -35, 35, 35)
        scale = min(2.0, 6000 / max(rect.width(), rect.height()))
        image = QImage(max(1, int(rect.width() * scale)), max(1, int(rect.height() * scale)), QImage.Format.Format_ARGB32)
        image.fill(QColor(PAPER))
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        if image.save(path):
            self.status.setText(f"Árbol guardado en {path}")
        else:
            self.error.setText("No se pudo guardar la imagen. Elige una carpeta con permisos de escritura.")
            self.error.show()
