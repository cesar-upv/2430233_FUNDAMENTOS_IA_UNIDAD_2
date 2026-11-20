"""Invariants of the grid value object."""

from dataclasses import FrozenInstanceError

import pytest

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position


def test_rejects_non_positive_width() -> None:
    with pytest.raises(ValueError, match="dimensions must be positive"):
        Grid(width=0, height=3, blocked=frozenset())


def test_rejects_non_positive_height() -> None:
    with pytest.raises(ValueError, match="dimensions must be positive"):
        Grid(width=3, height=-1, blocked=frozenset())


@pytest.mark.parametrize("outside", [Position(3, 0), Position(0, 3), Position(-1, 0)])
def test_rejects_blocked_positions_outside_the_grid(outside: Position) -> None:
    with pytest.raises(ValueError, match="outside the grid"):
        Grid(width=3, height=3, blocked=frozenset({outside}))


def test_contains_only_accepts_positions_inside_the_grid() -> None:
    grid = Grid(width=3, height=2, blocked=frozenset())

    assert grid.contains(Position(2, 1)) is True
    assert grid.contains(Position(3, 1)) is False
    assert grid.contains(Position(2, 2)) is False
    assert grid.contains(Position(-1, 0)) is False


def test_blocked_cells_are_inside_the_grid_but_not_walkable() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))

    assert grid.contains(Position(1, 1)) is True
    assert grid.is_walkable(Position(1, 1)) is False
    assert grid.is_walkable(Position(1, 0)) is True
    assert grid.is_walkable(Position(3, 3)) is False


def test_neighbors_of_an_interior_cell_are_the_four_orthogonal_cells() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())

    assert grid.neighbors(Position(1, 1)) == (
        Position(2, 1),
        Position(1, 2),
        Position(0, 1),
        Position(1, 0),
    )


def test_neighbors_exclude_out_of_bounds_cells_but_keep_blocked_ones() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 0)}))

    assert grid.neighbors(Position(0, 0)) == (Position(1, 0), Position(0, 1))
    assert grid.is_walkable(grid.neighbors(Position(0, 0))[0]) is False


def test_neighbors_of_an_out_of_grid_position_is_rejected() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())

    with pytest.raises(ValueError, match="outside the grid"):
        grid.neighbors(Position(3, 0))


def test_blocked_cells_are_copied_so_the_grid_cannot_change_afterwards() -> None:
    blocked = {Position(1, 1)}
    grid = Grid(width=3, height=3, blocked=blocked)

    blocked.add(Position(2, 2))

    assert grid.blocked == frozenset({Position(1, 1)})
    assert grid.is_walkable(Position(2, 2)) is True


def test_grid_attributes_cannot_be_reassigned() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())
    attribute = "width"

    with pytest.raises(FrozenInstanceError):
        setattr(grid, attribute, 5)
