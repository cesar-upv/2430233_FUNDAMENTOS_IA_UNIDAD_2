"""Editing tools and the scenario draft the window drives.

The editor never decides whether an edit is legal: it builds the draft, asks
:class:`~ant_pathfinding.domain.scenario.AntScenario` to validate it and keeps the
previous scenario when the domain refuses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Signal

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.generation.scenario_generator import (
    GenerationRequest,
    generate_scenario,
)

MIN_SIDE = 5
"""Smallest grid side the editor offers; the domain allows one cell, which is not worth drawing."""


class EditTool(StrEnum):
    """What a click on a cell does."""

    SELECT = "select"
    START = "start"
    GOAL = "goal"
    FOOD = "food"
    OBSTACLE = "obstacle"
    ERASE = "erase"


@dataclass(slots=True)
class _Draft:
    """Editable state; only the domain decides whether it is a valid scenario."""

    width: int
    height: int
    blocked: set[Position]
    start: Position
    goal: Position
    foods: set[Position]

    def copy(self) -> _Draft:
        return _Draft(
            self.width,
            self.height,
            set(self.blocked),
            self.start,
            self.goal,
            set(self.foods),
        )

    def place(self, tool: EditTool, position: Position) -> None:
        match tool:
            case EditTool.START:
                self.start = position
            case EditTool.GOAL:
                self.goal = position
            case EditTool.FOOD:
                self.foods.add(position)
            case EditTool.OBSTACLE:
                self.blocked.add(position)
            case EditTool.ERASE:
                self.blocked.discard(position)
                self.foods.discard(position)
            case EditTool.SELECT:
                pass

    def lift(self, tool: EditTool, position: Position) -> None:
        """Take the dragged element of ``tool`` kind out of ``position``."""
        match tool:
            case EditTool.FOOD:
                self.foods.discard(position)
            case EditTool.OBSTACLE:
                self.blocked.discard(position)
            case EditTool.SELECT | EditTool.START | EditTool.GOAL | EditTool.ERASE:
                pass


def starter_scenario(width: int, height: int) -> AntScenario:
    """An empty map with walkable corners and one food in the middle."""
    return AntScenario(
        grid=Grid(width, height, ()),
        start=Position(0, 0),
        goal=Position(width - 1, height - 1),
        foods=(Position(width // 2, height // 2),),
    )


class ScenarioEditor(QObject):
    """The scenario being edited, with the tool selected for the next click."""

    scenarioChanged = Signal()
    statusMessage = Signal(str)

    def __init__(self, scenario: AntScenario) -> None:
        super().__init__()
        self._scenario = scenario
        self.tool = EditTool.SELECT

    @property
    def scenario(self) -> AntScenario:
        return self._scenario

    def edit(self, tool: EditTool, position: Position) -> bool:
        """Apply one click; return whether the scenario now reflects it."""
        draft = self._draft().copy()
        draft.place(tool, position)
        return self._commit(draft)

    def move(self, tool: EditTool, source: Position, target: Position) -> bool:
        """Move the element of kind ``tool`` from ``source`` to ``target``."""
        if source == target:
            return True
        draft = self._draft().copy()
        draft.lift(tool, source)
        draft.place(tool, target)
        return self._commit(draft)

    def generate(self, request: GenerationRequest) -> bool:
        """Replace the scenario with a random one, reporting unsatisfiable requests."""
        try:
            scenario = generate_scenario(request)
        except ValueError as error:
            self.statusMessage.emit(str(error))
            return False
        self._adopt(scenario)
        return True

    def resize(self, width: int, height: int) -> None:
        """Fit the draft to a new grid size, keeping whatever still fits."""
        frame = Grid(max(width, MIN_SIDE), max(height, MIN_SIDE), ())
        previous = self._scenario.grid
        draft = _Draft(
            frame.width,
            frame.height,
            {position for position in previous.blocked if frame.contains(position)},
            _clamp(self._scenario.start, frame),
            _clamp(self._scenario.goal, frame),
            {position for position in self._scenario.foods if frame.contains(position)},
        )
        if not self._commit(draft):
            self._adopt(starter_scenario(frame.width, frame.height))
            self.statusMessage.emit("the map did not fit the new grid; showing an empty one")

    def _draft(self) -> _Draft:
        scenario = self._scenario
        return _Draft(
            scenario.grid.width,
            scenario.grid.height,
            set(scenario.grid.blocked),
            scenario.start,
            scenario.goal,
            set(scenario.foods),
        )

    def _commit(self, draft: _Draft) -> bool:
        """Adopt ``draft`` when the domain accepts it, otherwise report and keep the scenario."""
        try:
            scenario = AntScenario(
                grid=Grid(draft.width, draft.height, draft.blocked),
                start=draft.start,
                goal=draft.goal,
                foods=draft.foods,
            )
        except ValueError as error:
            self.statusMessage.emit(str(error))
            return False
        self._adopt(scenario)
        return True

    def _adopt(self, scenario: AntScenario) -> None:
        self._scenario = scenario
        self.scenarioChanged.emit()


def _clamp(position: Position, frame: Grid) -> Position:
    return Position(min(position.x, frame.width - 1), min(position.y, frame.height - 1))
