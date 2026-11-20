"""Search execution controls, metrics and the overlay they draw, driven by two QTimers."""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGraphicsItem,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.presentation.qt.editor import ScenarioEditor
from ant_pathfinding.presentation.qt.grid_scene import CELL_PX, GridScene
from ant_pathfinding.search.algorithms import SearchAlgorithm, new_runner
from ant_pathfinding.search.progress import SearchOutcome, SearchStep
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.runner import SearchRunner

_ALGORITHM_LABELS = {
    SearchAlgorithm.BFS: "BFS",
    SearchAlgorithm.DIJKSTRA: "Dijkstra",
    SearchAlgorithm.ASTAR: "A*",
}
"""On-screen spelling of the three enum members; the selection itself is always the enum."""
_STEP_BURSTS = (1, 10, 100, 1000)
_TICK_MS = 20
"""Interval of the expansion timer; the burst control decides how much work a tick does."""
_PLAYBACK_MS = 150
_BLANK = "-"


def _wash(name: str, alpha: int) -> QBrush:
    color = QColor(name)
    color.setAlpha(alpha)
    return QBrush(color)


# The cell washes are translucent so the start, goal, food and obstacle markers drawn
# underneath stay readable once a cell has been explored.
_DISCOVERED_BRUSH = _wash("#4dabf7", 140)
_EXPANDED_BRUSH = _wash("#868e96", 150)
_COLLECTED_BRUSH = _wash("#212529", 120)
_PATH_PEN = QPen(QColor("#15a34a"), CELL_PX * 0.22)
_ANT_BRUSH = QBrush(QColor("#101418"))
_ANT_PEN = QPen(QColor("#ffffff"), 1.5)


class SearchPanel(QWidget):
    """Drives one search run with a timer and shows what the run reports."""

    def __init__(self, editor: ScenarioEditor, scene: GridScene) -> None:
        super().__init__()
        self._editor = editor
        self._scene = scene
        self._search_timer = QTimer(self)
        self._search_timer.setInterval(_TICK_MS)
        self._search_timer.timeout.connect(self._tick)
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(_PLAYBACK_MS)
        self._playback_timer.timeout.connect(self._step_playback)
        self._runner: SearchRunner | None = None
        self._result: SearchResult | None = None
        self._expanded_states = 0
        self._frontier_size = 0
        self._discovered: set[Position] = set()
        self._expanded: set[Position] = set()
        self._path: tuple[Position, ...] = ()
        self._playback_index = 0
        self._collected: frozenset[Position] = frozenset()
        self._elapsed = 0.0
        self._first_step = True
        self._layout = QVBoxLayout(self)
        self._overlay = self._new_overlay()
        self._build_controls()
        self._build_metrics()
        self.algorithm_combo.currentIndexChanged.connect(self.reset)
        self._report()

    def run(self) -> None:
        """Start a fresh run, or resume the live one this panel already holds."""
        if self._runner is None or self._runner.finished:
            self._begin_run()
        self._search_timer.start()
        self._report()

    def pause(self) -> None:
        """Stop the timer and keep the run, so ``run`` resumes it where it stopped."""
        self._search_timer.stop()
        self._report()

    def step(self) -> None:
        """Expand exactly one state, starting a fresh run when none is live."""
        self._search_timer.stop()
        if self._runner is None or self._runner.finished:
            self._begin_run()
        self._advance(1)
        self._report()

    def stop(self) -> None:
        """End the run early; a stopped run has no result and therefore no path."""
        if self._runner is None:
            return
        self._search_timer.stop()
        self._playback_timer.stop()
        self._runner.stop()
        if self._runner.outcome is SearchOutcome.STOPPED:
            self._settle()
        self._report()

    def reset(self) -> None:
        """Return to idle: no run, no drawn cells, no metrics but the scenario's."""
        self._search_timer.stop()
        self._runner = None
        self._clear_visuals()
        self._report()

    def on_scenario_changed(self) -> None:
        """Reset the run and draw a fresh overlay: an edit deletes every scene item."""
        self._overlay = self._new_overlay()
        self.reset()

    def _new_overlay(self) -> SearchOverlay:
        overlay = SearchOverlay(self._editor.scenario.grid)
        self._scene.addItem(overlay)
        return overlay

    def _begin_run(self) -> None:
        self._runner = new_runner(self._algorithm(), self._editor.scenario)
        self._clear_visuals()

    def _clear_visuals(self) -> None:
        # A fresh run owns the playback from here: leaving the timer running would let it
        # walk a path this run never found.
        self._playback_timer.stop()
        self._result = None
        self._expanded_states = 0
        self._frontier_size = 0
        self._discovered.clear()
        self._expanded.clear()
        self._path = ()
        self._playback_index = 0
        self._collected = frozenset()
        self._elapsed = 0.0
        self._first_step = True
        self._overlay.reset()

    def _tick(self) -> None:
        self._advance(self._burst())
        self._report()

    def _advance(self, steps: int) -> None:
        """Expand up to ``steps`` states, timing the whole batch into the search time."""
        runner = self._runner
        assert runner is not None, "a run is started before it is advanced"
        started = time.perf_counter()
        for _ in range(steps):
            step = runner.step()
            if step is None:
                break
            self._absorb(step)
        self._elapsed += time.perf_counter() - started
        statistics = runner.statistics
        self._expanded_states = statistics.expanded_states
        self._frontier_size = statistics.frontier_size
        # The cells discovered but not yet expanded stand in for the frontier: that
        # identity is exact for uniform-cost search, and under A* this set is only a
        # subset of the frontier, which the step stream cannot read off.
        self._overlay.show_progress(self._discovered, self._expanded)
        if runner.finished:
            self._search_timer.stop()
            self._settle()

    def _absorb(self, step: SearchStep) -> None:
        """Fold one expansion into the drawn cell sets."""
        if self._first_step:
            # The start state is inserted before the first step, so no step reports it.
            self._discovered.add(step.state.position)
            self._first_step = False
        self._expanded.add(step.state.position)
        self._discovered.update(state.position for state in step.discovered)

    def _settle(self) -> None:
        """Take what a finished run knows: only a found run has a path to walk."""
        runner = self._runner
        assert runner is not None
        if runner.outcome is SearchOutcome.STOPPED:
            self._result = None
            self._path = ()
        else:
            self._result = runner.result()
            self._path = self._result.path
        self._playback_index = 0
        self._overlay.show_path(self._path)
        self._show_ant()

    def _show_ant(self) -> None:
        """Put the ant on its playback cell and mark every food the walk has touched."""
        if not self._path:
            self._collected = frozenset()
            self._overlay.show_ant(None, ())
            return
        walked = frozenset(self._path[: self._playback_index + 1])
        self._collected = walked & frozenset(self._editor.scenario.foods)
        self._overlay.show_ant(self._path[self._playback_index], self._collected)

    def _toggle_playback(self, playing: bool) -> None:
        if playing:
            self._playback_timer.start()
        else:
            self._playback_timer.stop()
        self._report()

    def _step_playback(self) -> None:
        """Move the ant one cell along the found path, stopping on the goal."""
        if self._playback_index + 1 >= len(self._path):
            self._playback_timer.stop()
        else:
            self._playback_index += 1
            self._show_ant()
        self._report()

    def _algorithm(self) -> SearchAlgorithm:
        """Return the selected algorithm: a combo box hands a StrEnum member back as its value."""
        algorithm = self.algorithm_combo.currentData()
        assert isinstance(algorithm, str), "the combo only holds algorithm values"
        return SearchAlgorithm(algorithm)

    def _burst(self) -> int:
        burst = self.burst_combo.currentData()
        assert isinstance(burst, int), "the burst combo only holds step counts"
        return burst

    def _outcome_text(self) -> str:
        if self._runner is None:
            return "idle"
        match self._runner.outcome:
            case SearchOutcome.RUNNING:
                return "running" if self._search_timer.isActive() else "held"
            case SearchOutcome.FOUND:
                return "found"
            case SearchOutcome.EXHAUSTED:
                return "no solution"
            case SearchOutcome.STOPPED:
                return "stopped"

    def _report(self) -> None:
        """Push the run state into the metrics and into the states of the controls."""
        result = self._result
        running = self._search_timer.isActive()
        playing = self._playback_timer.isActive()
        live = self._runner is not None and not self._runner.finished
        can_walk = bool(self._path) and self._playback_index < len(self._path) - 1

        self.algorithm_label.setText(_ALGORITHM_LABELS[self._algorithm()])
        self.outcome_label.setText(self._outcome_text())
        self.cost_label.setText(_BLANK if result is None else str(result.cost))
        self.path_length_label.setText(_BLANK if result is None else str(len(result.path)))
        self.expanded_label.setText(str(self._expanded_states))
        self.frontier_label.setText(str(self._frontier_size))
        self.time_label.setText(f"{self._elapsed:.3f} s")
        self.foods_label.setText(f"{len(self._collected)} / {len(self._editor.scenario.foods)}")

        self.run_button.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.step_button.setEnabled(not running)
        self.stop_button.setEnabled(running or live)
        self.reset_button.setEnabled(running or self._runner is not None or result is not None)
        self.play_button.setEnabled(can_walk)
        self.play_button.setChecked(playing)
        self.play_button.setText("Pause" if playing else "Play")
        self.playback_step_button.setEnabled(can_walk and not playing)

    def _build_controls(self) -> None:
        self.algorithm_combo = QComboBox(self)
        for algorithm in SearchAlgorithm:
            self.algorithm_combo.addItem(_ALGORITHM_LABELS[algorithm], algorithm)
        self._layout.addWidget(self.algorithm_combo)

        burst_row = QHBoxLayout()
        self.burst_combo = QComboBox(self)
        for burst in _STEP_BURSTS:
            self.burst_combo.addItem(f"{burst} / tick", burst)
        self.burst_combo.setToolTip("Search expansions performed on each timer tick")
        burst_row.addWidget(self.burst_combo)
        self.run_button = self._button("Run", self.run)
        self.pause_button = self._button("Pause", self.pause)
        self.step_button = self._button("Step search", self.step)
        self.stop_button = self._button("Stop", self.stop)
        self.reset_button = self._button("Reset", self.reset)
        for button in (
            self.run_button,
            self.pause_button,
            self.step_button,
            self.stop_button,
            self.reset_button,
        ):
            burst_row.addWidget(button)
        self._layout.addLayout(burst_row)

        playback_row = QHBoxLayout()
        self.play_button = QPushButton("Play", self)
        self.play_button.setCheckable(True)
        self.play_button.setToolTip("Walk the ant along the path the search found")
        self.play_button.clicked.connect(self._toggle_playback)
        self.playback_step_button = self._button("Step walk", self._step_playback)
        playback_row.addWidget(self.play_button)
        playback_row.addWidget(self.playback_step_button)
        self._layout.addLayout(playback_row)

    def _build_metrics(self) -> None:
        form = QFormLayout()
        self.algorithm_label = QLabel(self)
        self.outcome_label = QLabel(self)
        self.cost_label = QLabel(self)
        self.path_length_label = QLabel(self)
        self.expanded_label = QLabel(self)
        self.frontier_label = QLabel(self)
        self.time_label = QLabel(self)
        self.foods_label = QLabel(self)
        rows = (
            ("Algorithm", self.algorithm_label),
            ("Result", self.outcome_label),
            ("Cost", self.cost_label),
            ("Path length", self.path_length_label),
            ("Expanded states", self.expanded_label),
            ("Frontier size", self.frontier_label),
            ("Search time", self.time_label),
            ("Foods collected", self.foods_label),
        )
        for name, label in rows:
            form.addRow(name, label)
        self._layout.addLayout(form)

    def _button(self, text: str, slot: Callable[[], None]) -> QPushButton:
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        return button


class SearchOverlay(QGraphicsItem):
    """Draws the discovered, expanded, path and ant marks of one run as a single item."""

    def __init__(self, grid: Grid) -> None:
        super().__init__()
        self._grid = grid
        self._discovered: set[Position] = set()
        self._expanded: set[Position] = set()
        self._path: tuple[Position, ...] = ()
        self._ant: Position | None = None
        self._collected: set[Position] = set()
        self.setZValue(2.0)

    def reset(self) -> None:
        self.show_progress((), ())
        self.show_path(())
        self.show_ant(None, ())

    def show_progress(
        self, discovered: Collection[Position], expanded: Collection[Position]
    ) -> None:
        self._discovered = set(discovered)
        self._expanded = set(expanded)
        self.update()

    def show_path(self, path: Sequence[Position]) -> None:
        self._path = tuple(path)
        self.update()

    def show_ant(self, position: Position | None, collected: Collection[Position]) -> None:
        self._ant = position
        self._collected = set(collected)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0.0, 0.0, self._grid.width * CELL_PX, self._grid.height * CELL_PX)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        for position in self._discovered - self._expanded:
            painter.fillRect(self._cell(position), _DISCOVERED_BRUSH)
        for position in self._expanded:
            painter.fillRect(self._cell(position), _EXPANDED_BRUSH)
        for position in self._collected:
            painter.fillRect(self._cell(position), _COLLECTED_BRUSH)
        if len(self._path) > 1:
            path_pen = QPen(_PATH_PEN)
            path_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            path_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(path_pen)
            painter.drawPolyline(QPolygonF([self._centre(p) for p in self._path]))
        if self._ant is not None:
            painter.setBrush(_ANT_BRUSH)
            painter.setPen(_ANT_PEN)
            radius = CELL_PX * 0.26
            centre = self._centre(self._ant)
            painter.drawEllipse(centre, radius, radius)

    def _cell(self, position: Position) -> QRectF:
        return QRectF(
            position.x * CELL_PX + 1.0,
            position.y * CELL_PX + 1.0,
            CELL_PX - 2.0,
            CELL_PX - 2.0,
        )

    def _centre(self, position: Position) -> QPointF:
        return QPointF(
            position.x * CELL_PX + CELL_PX / 2.0,
            position.y * CELL_PX + CELL_PX / 2.0,
        )
