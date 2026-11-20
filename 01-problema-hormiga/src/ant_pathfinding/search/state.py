"""Search state of the multi-goal problem."""

from dataclasses import dataclass

from ant_pathfinding.domain.position import Position


@dataclass(frozen=True, slots=True)
class SearchState:
    """Ant position together with the food collected so far.

    Reaching the same cell with a different collected food is a different state,
    so both are expanded. Equality and hashing are by value, which makes the
    state usable as a mapping key or set member; ordering is not defined because
    ``collected`` is a set.

    ``collected`` is annotated as a :class:`frozenset`, which is what typed
    callers pass. ``__post_init__`` additionally normalizes it through
    :func:`frozenset`, so a state assembled dynamically from untyped or
    deserialized input still ends up hashable and immutable instead of aliasing
    the object it was handed.
    """

    position: Position
    collected: frozenset[Position]

    def __post_init__(self) -> None:
        object.__setattr__(self, "collected", frozenset(self.collected))
