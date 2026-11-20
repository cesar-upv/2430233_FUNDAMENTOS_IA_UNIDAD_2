"""The multi-goal problem instance."""

from collections.abc import Collection
from dataclasses import dataclass

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position


@dataclass(frozen=True, slots=True)
class AntScenario:
    """One ant that must collect every food item and finish on the goal.

    ``foods`` accepts any collection of positions and is normalized to a
    :class:`frozenset`: duplicated entries collapse into a single food item and
    the collection order carries no meaning.
    """

    grid: Grid
    start: Position
    goal: Position
    foods: Collection[Position]

    def __post_init__(self) -> None:
        object.__setattr__(self, "foods", frozenset(self.foods))
        self._require_walkable("start", self.start)
        self._require_walkable("goal", self.goal)
        for position in sorted(self.foods):
            self._require_walkable("food", position)

    def _require_walkable(self, role: str, position: Position) -> None:
        if not self.grid.is_walkable(position):
            raise ValueError(f"{role} position {position} is not a walkable grid cell")
