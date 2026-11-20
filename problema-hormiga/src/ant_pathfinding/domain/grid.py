"""Rectangular grid with blocked cells."""

from collections.abc import Collection
from dataclasses import dataclass

from ant_pathfinding.domain.position import Position


@dataclass(frozen=True, slots=True)
class Grid:
    """Immutable ``width`` x ``height`` grid that owns its blocked cells.

    ``blocked`` accepts any collection of positions and is normalized to a
    :class:`frozenset`, so neither the argument nor the grid can be modified
    afterwards.
    """

    width: int
    height: int
    blocked: Collection[Position]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"grid dimensions must be positive, got width={self.width}, height={self.height}"
            )
        blocked = frozenset(self.blocked)
        outside = sorted(position for position in blocked if not self._inside_bounds(position))
        if outside:
            raise ValueError(f"blocked positions outside the grid: {outside}")
        object.__setattr__(self, "blocked", blocked)

    def contains(self, position: Position) -> bool:
        """Return whether the position lies inside the grid bounds."""
        return self._inside_bounds(position)

    def is_walkable(self, position: Position) -> bool:
        """Return whether the position is inside the grid and not blocked."""
        return self._inside_bounds(position) and position not in self.blocked

    def neighbors(self, position: Position) -> tuple[Position, ...]:
        """Return the in-bounds orthogonal neighbors of an in-grid position.

        Blocked neighbors are included; filter with :meth:`is_walkable` when a
        walkable-only neighborhood is needed.
        """
        if not self._inside_bounds(position):
            raise ValueError(f"position {position} is outside the grid")
        return tuple(neighbor for neighbor in position.neighbors() if self._inside_bounds(neighbor))

    def _inside_bounds(self, position: Position) -> bool:
        return 0 <= position.x < self.width and 0 <= position.y < self.height
