"""Value semantics of the grid coordinate."""

from dataclasses import FrozenInstanceError

import pytest

from ant_pathfinding.domain.position import Position


def test_position_is_immutable() -> None:
    position = Position(1, 2)
    attribute = "x"

    with pytest.raises(FrozenInstanceError):
        setattr(position, attribute, 7)


def test_equal_positions_share_value_equality_and_hash() -> None:
    position = Position(3, 4)

    assert position == Position(3, 4)
    assert hash(position) == hash(Position(3, 4))
    assert {position: "start"}[Position(3, 4)] == "start"


def test_positions_order_by_column_then_row() -> None:
    assert Position(0, 9) < Position(1, 0)
    assert Position(1, 0) < Position(1, 1)
    assert sorted([Position(1, 1), Position(0, 1), Position(1, 0)]) == [
        Position(0, 1),
        Position(1, 0),
        Position(1, 1),
    ]


def test_neighbors_are_the_four_orthogonal_offsets() -> None:
    assert Position(1, 1).neighbors() == (
        Position(2, 1),
        Position(1, 2),
        Position(0, 1),
        Position(1, 0),
    )


def test_neighbors_of_a_corner_still_returns_four_offsets() -> None:
    assert len(Position(0, 0).neighbors()) == 4
    assert Position(-1, 0) in Position(0, 0).neighbors()
    assert Position(0, -1) in Position(0, 0).neighbors()
