"""Invariants of the multi-goal problem instance."""

from dataclasses import FrozenInstanceError

import pytest

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario

OPEN_GRID = Grid(width=3, height=3, blocked=frozenset())
BLOCKED_GRID = Grid(width=3, height=3, blocked=frozenset({Position(1, 1), Position(2, 0)}))


def test_scenario_without_food_is_valid() -> None:
    scenario = AntScenario(
        grid=OPEN_GRID, start=Position(0, 0), goal=Position(2, 2), foods=frozenset()
    )

    assert scenario.foods == frozenset()


def test_rejects_start_outside_the_grid() -> None:
    with pytest.raises(ValueError, match="start position"):
        AntScenario(grid=OPEN_GRID, start=Position(3, 3), goal=Position(2, 2), foods=frozenset())


def test_rejects_goal_outside_the_grid() -> None:
    with pytest.raises(ValueError, match="goal position"):
        AntScenario(grid=OPEN_GRID, start=Position(0, 0), goal=Position(0, 9), foods=frozenset())


def test_rejects_food_outside_the_grid() -> None:
    with pytest.raises(ValueError, match="food position"):
        AntScenario(
            grid=OPEN_GRID,
            start=Position(0, 0),
            goal=Position(2, 2),
            foods=frozenset({Position(1, 3)}),
        )


def test_rejects_start_on_a_blocked_cell() -> None:
    with pytest.raises(ValueError, match="start position"):
        AntScenario(
            grid=BLOCKED_GRID,
            start=Position(1, 1),
            goal=Position(0, 0),
            foods=frozenset(),
        )


def test_rejects_goal_on_a_blocked_cell() -> None:
    with pytest.raises(ValueError, match="goal position"):
        AntScenario(
            grid=BLOCKED_GRID,
            start=Position(0, 0),
            goal=Position(2, 0),
            foods=frozenset(),
        )


def test_rejects_food_on_a_blocked_cell() -> None:
    with pytest.raises(ValueError, match="food position"):
        AntScenario(
            grid=BLOCKED_GRID,
            start=Position(0, 0),
            goal=Position(2, 2),
            foods=frozenset({Position(1, 1)}),
        )


def test_duplicate_food_positions_collapse_into_a_single_item() -> None:
    scenario = AntScenario(
        grid=OPEN_GRID,
        start=Position(0, 0),
        goal=Position(2, 2),
        foods=[Position(1, 1), Position(1, 1), Position(0, 2)],
    )

    assert scenario.foods == frozenset({Position(0, 2), Position(1, 1)})


def test_food_argument_cannot_change_the_scenario_afterwards() -> None:
    foods = [Position(1, 1)]
    scenario = AntScenario(grid=OPEN_GRID, start=Position(0, 0), goal=Position(2, 2), foods=foods)

    foods.append(Position(0, 2))

    assert scenario.foods == frozenset({Position(1, 1)})


def test_scenario_attributes_cannot_be_reassigned() -> None:
    scenario = AntScenario(
        grid=OPEN_GRID, start=Position(0, 0), goal=Position(2, 2), foods=frozenset()
    )
    attribute = "goal"

    with pytest.raises(FrozenInstanceError):
        setattr(scenario, attribute, Position(0, 1))
