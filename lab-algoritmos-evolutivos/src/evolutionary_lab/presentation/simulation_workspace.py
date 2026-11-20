from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import Representation
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.evolution.engine import validate_configuration
from evolutionary_lab.presentation.errors import ConfigurationInputError, explain_error
from evolutionary_lab.presentation.generation_summary import GenerationSummary
from evolutionary_lab.presentation.inspector import IndividualInspector
from evolutionary_lab.presentation.plotting import PopulationPlot
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.presentation.theme import ThemeColors
from evolutionary_lab.presentation.workers import (
    FunctionCurve,
    FunctionSurface,
    SimulationController,
)
from evolutionary_lab.problems.registry import PROJECT_01_F1
from evolutionary_lab.simulation.snapshots import GenerationSnapshot


def demo_config(generation_limit: int = 100) -> ExperimentConfig:
    return ExperimentConfig(
        PROJECT_01_F1.identifier,
        PROJECT_01_F1.domains,
        (0.001,),
        10,
        generation_limit,
        42,
    )


class SimulationWorkspace(QWidget):
    history_changed = Signal(object)
    generation_changed = Signal(int)
    computation_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.controller = SimulationController(self)
        self.snapshot: GenerationSnapshot | None = None
        self.history: list[GenerationSnapshot] = []
        self.current_index = -1
        self.problem = PROJECT_01_F1
        self.problem_provider: Callable[[], OptimizationProblem] = lambda: self.problem
        self.config_provider: Callable[[], ExperimentConfig] = demo_config
        self._reset_pending = False
        self._cancel_requested = False
        self._auto_show_final = True
        self._playback_paused = False
        self.replay_timer = QTimer(self)
        self.replay_timer.setInterval(250)
        self.replay_timer.timeout.connect(self._replay_step)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        toolbar = QHBoxLayout()
        title = self.problem_title = QLabel(text("simulation_problem_title"))
        title.setObjectName("panelTitle")
        title.setWordWrap(True)
        toolbar.addWidget(title, 1)
        self.start_button = QPushButton(text("start_simulation"))
        self.start_button.setObjectName("startSimulation")
        self.start_button.setProperty("primary", True)
        self.start_button.clicked.connect(self.start_simulation)
        self.cancel_button = QPushButton(text("cancel_computation"))
        self.cancel_button.setObjectName("cancelSimulation")
        self.cancel_button.clicked.connect(self.cancel_computation)
        self.reset_button = QPushButton(text("reset_simulation"))
        self.reset_button.setObjectName("resetSimulation")
        self.reset_button.setToolTip(text("reset_simulation_help"))
        self.reset_button.clicked.connect(self.reset_simulation)
        for button in (self.start_button, self.cancel_button, self.reset_button):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.status = QLabel(text("plot_ready"))
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        layout.addWidget(self.status)
        self.metrics = GenerationSummary()
        layout.addWidget(self.metrics)
        self.computation_status = QLabel(text("computation_idle"))
        self.computation_status.setWordWrap(True)
        layout.addWidget(self.computation_status)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.plot = PopulationPlot()
        self.inspector = IndividualInspector()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("simulationSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.addWidget(self.plot)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 240])
        layout.addWidget(splitter, 1)
        replay = QHBoxLayout()
        self.previous_button = QPushButton(text("previous_generation"))
        self.previous_button.clicked.connect(lambda: self.seek(self.current_index - 1))
        self.play_button = QPushButton(text("play_history"))
        self.play_button.setObjectName("playHistory")
        self.play_button.setCheckable(True)
        self.play_button.clicked.connect(self.toggle_playback)
        self.next_button = QPushButton(text("next_generation"))
        self.next_button.clicked.connect(lambda: self.seek(self.current_index + 1))
        self.stop_button = QPushButton(text("stop_playback"))
        self.stop_button.clicked.connect(self.stop_playback)
        for button in (
            self.previous_button,
            self.play_button,
            self.next_button,
            self.stop_button,
        ):
            replay.addWidget(button)
        self.replay_status = QLabel(text("replay_idle"))
        self.replay_status.setObjectName("muted")
        self.replay_status.setWordWrap(True)
        replay.addWidget(self.replay_status, 1)
        layout.addLayout(replay)
        navigation = QHBoxLayout()
        self.generation_slider = QSlider(Qt.Orientation.Horizontal)
        self.generation_slider.setAccessibleName(text("generation"))
        self.generation_slider.valueChanged.connect(self.seek)
        navigation.addWidget(self.generation_slider, 1)
        jump_label = QLabel(text("jump_generation"))
        self.generation_spin = QSpinBox()
        self.generation_spin.setAccessibleName(text("jump_generation"))
        self.generation_spin.valueChanged.connect(self.seek)
        jump_label.setBuddy(self.generation_spin)
        navigation.addWidget(jump_label)
        navigation.addWidget(self.generation_spin)
        layout.addLayout(navigation)
        playback_options = QHBoxLayout()
        speed_label = QLabel(text("playback_speed"))
        self.speed = QComboBox()
        for rate in (1, 2, 4, 10, 30):
            self.speed.addItem(text("generations_per_second").format(rate=rate), rate)
        self.speed.setCurrentIndex(2)
        speed_label.setBuddy(self.speed)
        self.speed.currentIndexChanged.connect(self._change_speed)
        playback_options.addWidget(speed_label)
        playback_options.addWidget(self.speed)
        self.animate = QCheckBox(text("animate_history"))
        self.animate.setChecked(True)
        self.animate.toggled.connect(self._change_animation)
        playback_options.addWidget(self.animate)
        playback_options.addStretch()
        layout.addLayout(playback_options)
        self.inspector.individual_selected.connect(self.plot.select_individual)
        self.plot.individual_selected.connect(self.inspector.select_individual)
        self.controller.curve_ready.connect(self.set_curve)
        self.controller.snapshots_ready.connect(self.receive_snapshots)
        self.controller.finished.connect(self.finished)
        self.controller.failed.connect(self.failed)
        self._update_controls()

    @Slot()
    def start_simulation(self) -> None:
        if self.controller.is_running:
            return
        try:
            config = self.config_provider()
            problem = self.problem_provider()
            validate_configuration(config, problem)
        except ValueError as error:
            self.error_label.setText(
                str(error)
                if isinstance(error, ConfigurationInputError)
                else explain_error(str(error))
            )
            self.error_label.show()
            self._update_controls()
            return
        self.error_label.hide()
        self._clear_history()
        self.problem = problem
        self.problem_title.setText(
            text("project_problem_title").format(
                project=2 if config.representation == Representation.REAL else 1,
                problem=problem.title,
            )
        )
        self.plot.set_problem(config)
        self._cancel_requested = False
        self._auto_show_final = True
        self.computation_status.setText(text("computing"))
        self.controller.start(config, self.problem)
        self.computation_changed.emit(True)
        self._update_controls()

    @Slot(object)
    def set_curve(self, curve: FunctionCurve | FunctionSurface) -> None:
        if isinstance(curve, FunctionSurface):
            self.plot.set_surface(curve)
        else:
            self.plot.set_curve(curve)

    @Slot(object)
    def receive_snapshots(self, snapshots: tuple[GenerationSnapshot, ...]) -> None:
        if self._reset_pending:
            return
        self.history.extend(snapshots)
        if not self._cancel_requested:
            self.computation_status.setText(
                text("computation_progress").format(count=len(self.history))
            )
        if self.snapshot is None:
            self._display(0)
        self.history_changed.emit(tuple(self.history))
        self._update_controls()

    def show_snapshot(self, snapshot: GenerationSnapshot) -> None:
        self.snapshot = snapshot
        self.plot.set_snapshot(snapshot)
        self.inspector.set_snapshot(snapshot)
        self.status.setText(
            text("generation_meta").format(
                generation=snapshot.generation_index,
                size=len(snapshot.population),
            )
        )
        self.metrics.set_snapshot(snapshot)
        self.status.hide()

    def _display(self, index: int) -> None:
        self.current_index = index
        self.show_snapshot(self.history[index])
        for control in (self.generation_slider, self.generation_spin):
            control.blockSignals(True)
            control.setRange(0, len(self.history) - 1)
            control.setValue(index)
            control.blockSignals(False)
        self.generation_changed.emit(index)
        self._update_controls()

    @Slot(int)
    def seek(self, index: int) -> None:
        if not 0 <= index < len(self.history):
            return
        self._auto_show_final = False
        self.stop_playback()
        self._display(index)

    @Slot()
    def toggle_playback(self) -> None:
        if not self.animate.isChecked():
            if self.history:
                self.seek(len(self.history) - 1)
            return
        if self.replay_timer.isActive():
            self.stop_playback()
            self._playback_paused = True
            self.play_button.setText(text("resume_history"))
            self.replay_status.setText(text("replay_paused"))
            self._update_controls()
            return
        if len(self.history) < 2:
            return
        self._auto_show_final = False
        if self.current_index == len(self.history) - 1:
            self._display(0)
        self.replay_timer.start()
        self._playback_paused = False
        self.play_button.setText(text("pause_history"))
        self.replay_status.setText(text("replay_playing"))
        self._update_controls()

    @Slot()
    def stop_playback(self) -> None:
        self.replay_timer.stop()
        self._playback_paused = False
        self.play_button.setText(
            text("play_history" if self.animate.isChecked() else "show_final")
        )
        self.replay_status.setText(text("replay_idle"))
        self._update_controls()

    @Slot()
    def _replay_step(self) -> None:
        if self.current_index + 1 >= len(self.history):
            self.stop_playback()
            self.replay_status.setText(text("replay_finished"))
        else:
            self._display(self.current_index + 1)

    @Slot()
    def cancel_computation(self) -> None:
        self._cancel_requested = True
        self.controller.cancel()
        self.computation_status.setText(text("computation_cancelling"))
        self.cancel_button.setEnabled(False)

    @Slot()
    def reset_simulation(self) -> None:
        self._reset_pending = self.controller.is_running
        self._cancel_requested = self._reset_pending
        self.controller.cancel()
        self._clear_history()
        self.error_label.hide()
        self.computation_status.setText(
            text(
                "computation_cancelling" if self._reset_pending else "computation_idle"
            )
        )
        self._update_controls()

    def _clear_history(self) -> None:
        self.stop_playback()
        self.history.clear()
        self.snapshot = None
        self.current_index = -1
        self.plot.clear()
        self.inspector.clear()
        self.metrics.clear()
        self.status.setText(text("plot_ready"))
        self.status.show()
        for control in (self.generation_slider, self.generation_spin):
            control.blockSignals(True)
            control.setRange(0, 0)
            control.blockSignals(False)
        self.history_changed.emit(())

    def _update_controls(self) -> None:
        running = self.controller.is_running
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running and not self._cancel_requested)
        self.reset_button.setEnabled(
            not self._reset_pending
            and (running or bool(self.history) or self.error_label.isVisible())
        )
        self.previous_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(0 <= self.current_index < len(self.history) - 1)
        self.play_button.setEnabled(len(self.history) > 1)
        self.play_button.setChecked(self.replay_timer.isActive())
        self.stop_button.setEnabled(
            self.replay_timer.isActive() or self._playback_paused
        )
        for control in (self.generation_slider, self.generation_spin):
            control.setEnabled(bool(self.history))
            control.blockSignals(True)
            control.setMaximum(max(0, len(self.history) - 1))
            control.blockSignals(False)

    @Slot(str)
    def finished(self, outcome: str) -> None:
        self._cancel_requested = False
        if self._reset_pending:
            self._reset_pending = False
            self._clear_history()
            self.computation_status.setText(text("computation_idle"))
        else:
            self.computation_status.setText(
                text(f"computation_{outcome}").format(count=len(self.history))
            )
            if self.history and self._auto_show_final:
                self._display(len(self.history) - 1)
        self._update_controls()
        self.computation_changed.emit(False)

    @Slot(str)
    def failed(self, message: str) -> None:
        self.computation_status.setText(text("run_error"))
        self.error_label.setText(explain_error(message))
        self.error_label.show()

    @Slot(int)
    def _change_speed(self, _index: int) -> None:
        self.replay_timer.setInterval(round(1000 / int(self.speed.currentData())))

    @Slot(bool)
    def _change_animation(self, enabled: bool) -> None:
        self.stop_playback()
        self.speed.setEnabled(enabled)
        if not enabled:
            self.replay_status.setText(text("replay_manual"))

    def apply_theme(self, colors: ThemeColors) -> None:
        self.plot.apply_theme(colors)
