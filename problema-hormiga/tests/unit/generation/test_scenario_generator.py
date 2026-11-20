"""Generation guarantees: requested shape, reproducibility, and solvability."""

from collections import deque

import pytest

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.generation.scenario_generator import GenerationRequest, generate_scenario


def _reachable(grid: Grid, origin: Position) -> set[Position]:
    seen = {origin}
    queue = deque([origin])
    while queue:
        for neighbor in grid.neighbors(queue.popleft()):
            if neighbor not in seen and grid.is_walkable(neighbor):
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


@pytest.mark.parametrize(
    ("rows", "columns", "food_count"),
    [(5, 5, 0), (5, 5, 2), (10, 10, 3), (20, 20, 5)],
)
def test_generation_matches_the_request(rows: int, columns: int, food_count: int) -> None:
    scenario = generate_scenario(
        GenerationRequest(rows=rows, columns=columns, food_count=food_count, obstacle_ratio=0.2)
    )

    assert scenario.grid.width == columns
    assert scenario.grid.height == rows
    assert len(scenario.foods) == food_count
    assert scenario.grid.is_walkable(scenario.start)
    assert scenario.grid.is_walkable(scenario.goal)
    assert scenario.start != scenario.goal
    assert not scenario.foods & {scenario.start, scenario.goal}


@pytest.mark.parametrize("obstacle_ratio", [0.0, 0.2, 0.5])
def test_obstacles_are_inside_the_grid_and_blocked(obstacle_ratio: float) -> None:
    scenario = generate_scenario(
        GenerationRequest(rows=10, columns=10, food_count=2, obstacle_ratio=obstacle_ratio, seed=3)
    )

    assert len(scenario.grid.blocked) == round(100 * obstacle_ratio)
    for blocked in scenario.grid.blocked:
        assert scenario.grid.contains(blocked)
        assert not scenario.grid.is_walkable(blocked)


def test_the_same_seed_generates_the_same_scenario() -> None:
    request = GenerationRequest(rows=12, columns=9, food_count=3, obstacle_ratio=0.3, seed=17)

    first = generate_scenario(request)
    second = generate_scenario(request)

    assert first == second


@pytest.mark.parametrize(
    ("rows", "columns", "food_count", "obstacle_ratio"),
    [(5, 5, 2, 0.2), (8, 8, 3, 0.35)],
)
def test_every_generated_scenario_is_solvable(
    rows: int, columns: int, food_count: int, obstacle_ratio: float
) -> None:
    for seed in range(30):
        scenario = generate_scenario(
            GenerationRequest(
                rows=rows,
                columns=columns,
                food_count=food_count,
                obstacle_ratio=obstacle_ratio,
                seed=seed,
            )
        )
        reachable = _reachable(scenario.grid, scenario.start)

        assert scenario.goal in reachable
        assert scenario.foods <= reachable


@pytest.mark.parametrize(
    "invalid",
    [
        GenerationRequest(rows=0, columns=5, food_count=1, obstacle_ratio=0.2),
        GenerationRequest(rows=5, columns=5, food_count=-1, obstacle_ratio=0.2),
        GenerationRequest(rows=5, columns=5, food_count=1, obstacle_ratio=1.5),
        GenerationRequest(rows=3, columns=3, food_count=8, obstacle_ratio=0.2),
    ],
)
def test_invalid_requests_are_rejected(invalid: GenerationRequest) -> None:
    with pytest.raises(ValueError):
        generate_scenario(invalid)


@pytest.mark.parametrize(
    "unsatisfiable",
    [
        GenerationRequest(rows=6, columns=6, food_count=2, obstacle_ratio=1.0),
        GenerationRequest(rows=2, columns=2, food_count=2, obstacle_ratio=0.5),
    ],
)
def test_requests_that_cannot_be_satisfied_are_rejected(unsatisfiable: GenerationRequest) -> None:
    with pytest.raises(ValueError, match="no component of at least"):
        generate_scenario(unsatisfiable)
