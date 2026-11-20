"""Grid cell coordinates.

``x`` is the column index in ``[0, width)`` and ``y`` is the row index in
``[0, height)``. Columns increase to the right and rows increase downwards, so
``Position(x, y)`` names a cell without reference to any drawing geometry; mapping
a cell onto pixels is left to the presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class Position:
    """Immutable cell coordinate, comparable and hashable by value."""

    x: int
    y: int

    def neighbors(self) -> tuple[Position, ...]:
        """Return the four orthogonal offsets: east, south, west, north."""
        return (
            Position(self.x + 1, self.y),
            Position(self.x, self.y + 1),
            Position(self.x - 1, self.y),
            Position(self.x, self.y - 1),
        )
