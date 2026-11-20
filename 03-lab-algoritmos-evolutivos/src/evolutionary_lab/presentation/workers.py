from dataclasses import dataclass
from time import monotonic

from PySide6.QtCore import QObject, QThread, Signal, Slot

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.evolution.engine import iterate_generations
from evolutionary_lab.simulation.snapshots import GenerationSnapshot


@dataclass(frozen=True)
class FunctionCurve:
    x: tuple[float, ...]
    y: tuple[float, ...]


@dataclass(frozen=True)
class FunctionSurface:
    x: tuple[float, ...]
    y: tuple[float, ...]
    values: tuple[tuple[float, ...], ...]


def sample_landscape(
    config: ExperimentConfig, problem: OptimizationProblem
) -> FunctionCurve | FunctionSurface | None:
    dimensions = len(config.domains)
    if dimensions > 2:
        return None
    count = 601 if dimensions == 1 else 161
    axes = tuple(
        tuple(
            domain.lower
            if i == 0
            else domain.upper
            if i == count - 1
            else domain.lower + (domain.upper - domain.lower) * i / (count - 1)
            for i in range(count)
        )
        for domain in config.domains
    )
    if dimensions == 1:
        return FunctionCurve(axes[0], tuple(problem.evaluate((x,)) for x in axes[0]))
    return FunctionSurface(
        axes[0],
        axes[1],
        tuple(tuple(problem.evaluate((x, y)) for y in axes[1]) for x in axes[0]),
    )


class SimulationWorker(QObject):
    curve_ready = Signal(object)
    snapshots_ready = Signal(object)
    failed = Signal(str)
    finished = Signal(str)

    def __init__(self, config: ExperimentConfig, problem: OptimizationProblem) -> None:
        super().__init__()
        self.config = config
        self.problem = problem

    @Slot()
    def run(self) -> None:
        outcome = "completed"
        failure = None
        batch: list[GenerationSnapshot] = []
        try:
            self.config.validate_for(self.problem)
            landscape = sample_landscape(self.config, self.problem)
            if landscape is not None:
                self.curve_ready.emit(landscape)
            last_delivery = monotonic()
            iterator = iterate_generations(self.config, self.problem)
            while not QThread.currentThread().isInterruptionRequested():
                try:
                    snapshot = next(iterator)
                except StopIteration:
                    break
                batch.append(snapshot)
                if len(batch) >= 32 or monotonic() - last_delivery >= 0.04:
                    self.snapshots_ready.emit(tuple(batch))
                    batch.clear()
                    last_delivery = monotonic()
            else:
                outcome = "cancelled"
        except Exception as error:
            failure = str(error)
            outcome = "failed"
        if batch:
            self.snapshots_ready.emit(tuple(batch))
        if failure is not None:
            self.failed.emit(failure)
        self.finished.emit(outcome)


class SimulationController(QObject):
    curve_ready = Signal(object)
    snapshots_ready = Signal(object)
    failed = Signal(str)
    finished = Signal(str)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: SimulationWorker | None = None
        self._outcome = "completed"

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    def start(self, config: ExperimentConfig, problem: OptimizationProblem) -> None:
        if self.is_running:
            raise RuntimeError("A simulation is already running")
        thread = QThread(self)
        worker = SimulationWorker(config, problem)
        worker.moveToThread(thread)
        self._thread, self._worker = thread, worker
        thread.started.connect(worker.run)
        worker.curve_ready.connect(self._receive_curve)
        worker.snapshots_ready.connect(self._receive_snapshots)
        worker.failed.connect(self._receive_error)
        worker.finished.connect(self._record_outcome)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        thread.start()

    @Slot(object)
    def _receive_curve(self, curve: FunctionCurve | FunctionSurface) -> None:
        self.curve_ready.emit(curve)

    @Slot(object)
    def _receive_snapshots(self, snapshots: object) -> None:
        self.snapshots_ready.emit(snapshots)

    @Slot(str)
    def _receive_error(self, message: str) -> None:
        self.failed.emit(message)

    @Slot(str)
    def _record_outcome(self, outcome: str) -> None:
        self._outcome = outcome

    @Slot()
    def _thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None:
            thread.deleteLater()
        self.finished.emit(self._outcome)

    def cancel(self) -> None:
        if self._thread is not None:
            self._thread.requestInterruption()

    def shutdown(self) -> None:
        if self._thread is not None:
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait()
