"""The search state must carry the collected food, not only the position."""

from dataclasses import FrozenInstanceError

import pytest

from ant_pathfinding.domain.position import Position
from ant_pathfinding.search.state import SearchState

CELL = Position(2, 2)
OTHER_FOOD = Position(0, 0)


def test_same_cell_with_different_collected_food_is_a_different_state() -> None:
    without_food = SearchState(position=CELL, collected=frozenset())
    with_food = SearchState(position=CELL, collected=frozenset({OTHER_FOOD}))

    assert without_food != with_food
    assert hash(without_food) != hash(with_food)
    assert len({without_food, with_food}) == 2


def test_equal_states_are_interchangeable_as_mapping_keys() -> None:
    state = SearchState(position=CELL, collected=frozenset({OTHER_FOOD}))

    visited: dict[SearchState, str] = {state: "first"}
    visited[SearchState(position=CELL, collected=frozenset({OTHER_FOOD}))] = "second"

    assert visited == {state: "second"}


def test_state_is_immutable() -> None:
    state = SearchState(position=CELL, collected=frozenset())
    attribute = "position"

    with pytest.raises(FrozenInstanceError):
        setattr(state, attribute, Position(0, 0))
