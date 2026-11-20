"""The main window: editing and search controls around a QGraphicsView of the scenario."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QPainter, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QToolBar,
    QWidget,
)

from ant_pathfinding.generation.scenario_generator import GenerationRequest
from ant_pathfinding.presentation.qt.editor import (
    MIN_SIDE,
    EditTool,
    ScenarioEditor,
    starter_scenario,
)
from ant_pathfinding.presentation.qt.grid_scene import GridScene
from ant_pathfinding.presentation.qt.search_view import SearchPanel

_MAX_SIDE = 100
_MAX_FOODS = 9
"""The search explores ``cells * 2 ** food_count`` states, so only single digits are practical."""
_MAX_OBSTACLE_RATIO = 0.4
"""Above this a small grid is regularly split into components too small to hold the scenario."""
_MAX_SEARCH_STATES = 200_000
"""Ceiling on ``rows * columns * 2 ** food_count``, the size of the search space to run."""
_STATUS_MS = 5000
"""How long a transient status message stays before the bar goes back to idle."""
_PRESETS = (10, 20)
_INITIAL_SIDE = 10


class MainWindow(QMainWindow):
    """Editor for one scenario; the current one is always ``editor.scenario``."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ant Pathfinding")
        self.editor = ScenarioEditor(starter_scenario(_INITIAL_SIDE, _INITIAL_SIDE))
        self.scene = GridScene(self.editor)
        self.view = _FittingView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setCentralWidget(self.view)

        tool_bar = QToolBar("Editing", self)
        tool_bar.setMovable(False)
        self.addToolBar(tool_bar)

        tool_bar.addWidget(QLabel(" Tool "))
        self.tool_combo = QComboBox()
        for tool in EditTool:
            self.tool_combo.addItem(tool.value.capitalize(), tool)
        tool_bar.addWidget(self.tool_combo)

        tool_bar.addSeparator()
        tool_bar.addWidget(QLabel(" Grid "))
        self.preset_combo = QComboBox()
        for side in _PRESETS:
            self.preset_combo.addItem(f"{side} x {side}", side)
        self.preset_combo.setToolTip("Reset the grid to this size")
        tool_bar.addWidget(self.preset_combo)
        tool_bar.addWidget(QLabel(" Rows "))
        self.rows_spin = _spin(MIN_SIDE, _MAX_SIDE, _INITIAL_SIDE)
        tool_bar.addWidget(self.rows_spin)
        tool_bar.addWidget(QLabel(" Columns "))
        self.columns_spin = _spin(MIN_SIDE, _MAX_SIDE, _INITIAL_SIDE)
        tool_bar.addWidget(self.columns_spin)

        dock = QDockWidget("Generate", self)
        panel = QWidget()
        form = QFormLayout(panel)
        self.foods_spin = QSpinBox(panel)
        self.foods_spin.setRange(0, _MAX_FOODS)
        form.addRow("Foods", self.foods_spin)
        self.ratio_spin = QDoubleSpinBox(panel)
        self.ratio_spin.setRange(0.0, _MAX_OBSTACLE_RATIO)
        self.ratio_spin.setSingleStep(0.05)
        self.ratio_spin.setDecimals(2)
        self.ratio_spin.setValue(0.2)
        self.ratio_spin.setToolTip("Share of the grid filled with obstacles")
        form.addRow("Obstacle ratio", self.ratio_spin)
        self.seed_spin = QSpinBox(panel)
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setToolTip("The same seed always generates the same map")
        form.addRow("Seed", self.seed_spin)
        self.generate_button = QPushButton("Generate", panel)
        form.addRow(self.generate_button)
        dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        search_dock = QDockWidget("Search", self)
        self.search_panel = SearchPanel(self.editor, self.scene)
        search_dock.setWidget(self.search_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, search_dock)

        self.tool_combo.currentIndexChanged.connect(self._tool_selected)
        self.preset_combo.currentIndexChanged.connect(self._preset_selected)
        self.rows_spin.valueChanged.connect(self._size_changed)
        self.columns_spin.valueChanged.connect(self._size_changed)
        self.generate_button.clicked.connect(self.generate)
        self.editor.scenarioChanged.connect(self._scenario_changed)
        self.editor.statusMessage.connect(self._show_status)

        self._scenario_changed()

    def generate(self) -> None:
        """Fill the grid with a random solvable scenario built from the panel values."""
        rows = self.rows_spin.value()
        columns = self.columns_spin.value()
        foods = self.foods_spin.value()
        if rows * columns * 2**foods > _MAX_SEARCH_STATES:
            self._show_status(
                f"too large to search: {rows}x{columns} with {foods} foods is over "
                f"{_MAX_SEARCH_STATES} states, so lower the grid size or the food count"
            )
            return
        self.editor.generate(
            GenerationRequest(
                rows=rows,
                columns=columns,
                food_count=foods,
                obstacle_ratio=self.ratio_spin.value(),
                seed=self.seed_spin.value(),
            )
        )

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, _STATUS_MS)

    def _scenario_changed(self) -> None:
        """Rebuild the grid drawing first: it deletes the search overlay, so it goes after."""
        self.scene.set_scenario(self.editor.scenario)
        self.search_panel.on_scenario_changed()

    def _tool_selected(self, index: int) -> None:
        tool = self.tool_combo.itemData(index)
        assert isinstance(tool, str), "the tool combo only holds tool values"
        self.editor.tool = EditTool(tool)

    def _preset_selected(self, index: int) -> None:
        """Apply a preset in one resize rather than one per spin box."""
        side = self.preset_combo.itemData(index)
        assert isinstance(side, int), "the preset combo only holds side lengths"
        _rows = QSignalBlocker(self.rows_spin)
        _columns = QSignalBlocker(self.columns_spin)
        self.rows_spin.setValue(side)
        self.columns_spin.setValue(side)
        self._size_changed()

    def _size_changed(self) -> None:
        self.editor.resize(self.columns_spin.value(), self.rows_spin.value())
        self.view.fit()


class _FittingView(QGraphicsView):
    """Keeps the whole grid visible and its cells square."""

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fit()

    def fit(self) -> None:
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    return spin
