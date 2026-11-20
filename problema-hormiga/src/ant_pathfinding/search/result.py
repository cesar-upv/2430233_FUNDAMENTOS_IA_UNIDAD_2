"""Outcome of a search run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ant_pathfinding.domain.position import Position


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Immutable search outcome.

    ``path`` holds the ant positions from start to goal without repeating the
    food bookkeeping, so a successful result satisfies
    ``cost == len(path) - 1`` while a failed result has an empty path and cost
    ``0``. ``expanded_states`` is the number of search states the run expanded.

    ``path`` is annotated as a tuple of positions, which is what typed callers
    pass. ``__post_init__`` additionally normalizes it through :func:`tuple`, so a
    result assembled dynamically from untyped or deserialized input never aliases
    the object it was handed and the cost invariant checked there holds for the
    whole lifetime of the result.
    """

    found: bool
    path: tuple[Position, ...]
    cost: int
    expanded_states: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))
        if self.found and not self.path:
            raise ValueError("a successful result requires a non-empty path")
        if not self.found and self.path:
            raise ValueError("a failed result cannot carry a path")
        expected_cost = len(self.path) - 1 if self.found else 0
        if self.cost != expected_cost:
            raise ValueError(
                f"cost {self.cost} does not match a path of {len(self.path)} positions"
            )
        if self.expanded_states < 0:
            raise ValueError(f"expanded_states cannot be negative: {self.expanded_states}")

    @classmethod
    def success(cls, path: Sequence[Position], expanded_states: int) -> SearchResult:
        """Build a successful result from a start-to-goal path."""
        positions = tuple(path)
        return cls(
            found=True,
            path=positions,
            cost=len(positions) - 1,
            expanded_states=expanded_states,
        )

    @classmethod
    def failure(cls, expanded_states: int) -> SearchResult:
        """Build a failed result: no path and no movement cost."""
        return cls(found=False, path=(), cost=0, expanded_states=expanded_states)
