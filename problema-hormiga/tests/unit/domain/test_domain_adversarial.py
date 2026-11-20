"""Adversarial checks on the domain value objects.

The objects are frozen dataclasses, so "immutable" has two separate meanings that
both have to hold: the attributes cannot be reassigned, and nothing that was
handed to the constructor can still change the object afterwards. The second one
is easy to get wrong when the constructor accepts a collection, so every test
below builds the object from a mutable container and then mutates that container.
"""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError, replace
from operator import setitem
from random import Random

import pytest

from ant_pathfinding.domain.grid import Grid
from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.state import SearchState

OPEN = Grid(width=3, height=3, blocked=frozenset())


# --------------------------------------------------------------------------
# Position
# --------------------------------------------------------------------------


def test_neighbors_are_east_south_west_north_in_that_order() -> None:
    assert Position(1, 1).neighbors() == (
        Position(2, 1),
        Position(1, 2),
        Position(0, 1),
        Position(1, 0),
    )


def test_neighbors_of_a_corner_are_the_raw_offsets() -> None:
    assert Position(0, 0).neighbors() == (
        Position(1, 0),
        Position(0, 1),
        Position(-1, 0),
        Position(0, -1),
    )


def test_neighbors_never_step_diagonally() -> None:
    origin = Position(3, 4)
    for neighbor in origin.neighbors():
        dx = neighbor.x - origin.x
        dy = neighbor.y - origin.y
        assert abs(dx) + abs(dy) == 1
        assert dx == 0 or dy == 0


def test_neighbors_are_distinct_and_exactly_four() -> None:
    for cell in (Position(-4, -4), Position(0, 0), Position(9, 9)):
        neighbors = cell.neighbors()
        assert len(neighbors) == 4
        assert len(set(neighbors)) == 4
        assert cell not in neighbors


def test_each_call_returns_a_fresh_tuple() -> None:
    cell = Position(2, 3)
    first = cell.neighbors()
    second = cell.neighbors()

    assert first == second
    assert first is not second
    assert isinstance(first, tuple)


def test_neighbor_results_cannot_be_written_to() -> None:
    neighbors = Position(0, 0).neighbors()

    with pytest.raises(TypeError):
        setitem(neighbors, 0, Position(9, 9))


def test_position_equality_survives_being_used_as_a_mapping_key() -> None:
    mapping = {Position(1, 2): "food", Position(3, 4): "goal"}

    assert mapping[Position(1, 2)] == "food"
    assert len({Position(1, 2), Position(1, 2), Position(2, 1)}) == 2


def test_positions_with_the_same_value_are_interchangeable() -> None:
    built = Position(2, 5)

    assert built == Position(2, 5)
    assert hash(built) == hash(Position(2, 5))
    assert built.x == 2
    assert built.y == 5


def test_position_attributes_cannot_be_reassigned() -> None:
    for attribute, value in (("x", 9), ("y", 9)):
        with pytest.raises(FrozenInstanceError):
            setattr(Position(1, 1), attribute, value)


# --------------------------------------------------------------------------
# Grid bounds and neighbourhood
# --------------------------------------------------------------------------


@pytest.mark.parametrize("width, height", [(0, 1), (1, 0), (0, 0), (-1, 4), (4, -1), (-2, -2)])
def test_rejects_non_positive_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="dimensions must be positive"):
        Grid(width=width, height=height, blocked=frozenset())


@pytest.mark.parametrize(
    "outside",
    [
        Position(3, 0),
        Position(0, 3),
        Position(-1, 0),
        Position(0, -1),
        Position(3, 3),
        Position(-1, -1),
        Position(4, 2),
        Position(2, 4),
    ],
)
def test_rejects_a_single_blocked_cell_outside_the_grid(outside: Position) -> None:
    with pytest.raises(ValueError, match="outside the grid"):
        Grid(width=3, height=3, blocked=frozenset({outside}))


def test_reports_every_blocked_cell_outside_the_grid() -> None:
    with pytest.raises(ValueError, match=r"Position\(x=0, y=4\).*Position\(x=4, y=0\)"):
        Grid(width=3, height=3, blocked=frozenset({Position(4, 0), Position(0, 4)}))


def test_a_grid_of_a_single_cell_has_no_neighbors() -> None:
    grid = Grid(width=1, height=1, blocked=frozenset())

    assert grid.neighbors(Position(0, 0)) == ()


def test_neighbor_count_depends_only_on_the_cell_degree() -> None:
    for width, height in ((1, 1), (1, 4), (4, 1), (2, 3), (4, 3), (5, 5), (7, 2)):
        grid = Grid(width=width, height=height, blocked=frozenset())
        for y in range(height):
            for x in range(width):
                cell = Position(x, y)
                expected = (
                    (1 if x > 0 else 0)
                    + (1 if x + 1 < width else 0)
                    + (1 if y > 0 else 0)
                    + (1 if y + 1 < height else 0)
                )
                neighbors = grid.neighbors(cell)
                assert len(neighbors) == expected, f"{cell} of {width}x{height}"
                assert len(set(neighbors)) == expected
                assert cell not in neighbors
                assert all(grid.contains(neighbor) for neighbor in neighbors)
                for neighbor in neighbors:
                    assert abs(neighbor.x - x) + abs(neighbor.y - y) == 1


def test_neighbors_of_a_corner_and_of_an_edge_cell() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())

    assert grid.neighbors(Position(0, 0)) == (Position(1, 0), Position(0, 1))
    assert grid.neighbors(Position(2, 2)) == (Position(1, 2), Position(2, 1))
    assert grid.neighbors(Position(1, 0)) == (Position(2, 0), Position(1, 1), Position(0, 0))
    assert grid.neighbors(Position(1, 1)) == (
        Position(2, 1),
        Position(1, 2),
        Position(0, 1),
        Position(1, 0),
    )


@pytest.mark.parametrize(
    "outside",
    [Position(-1, 0), Position(0, -1), Position(3, 0), Position(0, 3), Position(3, 3)],
)
def test_rejects_neighbors_of_a_position_outside_the_grid(outside: Position) -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())

    with pytest.raises(ValueError, match="outside the grid"):
        grid.neighbors(outside)


def test_blocked_neighbors_are_still_listed() -> None:
    """The documented contract: ``neighbors`` is geometric, walkability is separate."""
    grid = Grid(width=3, height=3, blocked=frozenset({Position(2, 1), Position(0, 0)}))

    neighbors = grid.neighbors(Position(1, 1))

    assert set(neighbors) == {Position(2, 1), Position(1, 2), Position(0, 1), Position(1, 0)}
    assert [neighbor for neighbor in neighbors if grid.is_walkable(neighbor)] == [
        Position(1, 2),
        Position(0, 1),
        Position(1, 0),
    ]


def test_contains_and_is_walkable_agree_on_the_blocked_cell() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))

    assert grid.contains(Position(1, 1)) is True
    assert grid.is_walkable(Position(1, 1)) is False
    assert grid.contains(Position(9, 9)) is False
    assert grid.is_walkable(Position(9, 9)) is False


# --------------------------------------------------------------------------
# Grid input aliasing
# --------------------------------------------------------------------------


def test_a_list_of_blocked_cells_cannot_change_the_grid_afterwards() -> None:
    blocked: list[Position] = [Position(1, 1)]
    grid = Grid(width=3, height=3, blocked=blocked)

    blocked.append(Position(2, 2))
    blocked.clear()

    assert grid.blocked == frozenset({Position(1, 1)})
    assert grid.is_walkable(Position(2, 2)) is True


def test_a_mutable_set_of_blocked_cells_cannot_change_the_grid_afterwards() -> None:
    blocked = {Position(1, 1)}
    grid = Grid(width=3, height=3, blocked=blocked)

    blocked |= {Position(0, 0)}

    assert grid.blocked == frozenset({Position(1, 1)})
    assert grid.is_walkable(Position(0, 0)) is True


def test_a_mapping_passed_as_blocked_cells_is_snapshotted() -> None:
    mapping = {Position(1, 1): "wall"}
    grid = Grid(width=3, height=3, blocked=mapping)

    mapping[Position(2, 2)] = "wall"

    assert grid.blocked == frozenset({Position(1, 1)})
    assert grid.is_walkable(Position(2, 2)) is True


def test_a_lazily_produced_collection_of_blocked_cells_is_snapshotted() -> None:
    def cells() -> Iterator[Position]:
        yield Position(1, 1)

    grid = Grid(width=3, height=3, blocked=cells())

    assert grid.blocked == frozenset({Position(1, 1)})


def test_the_stored_blocked_cells_are_a_frozenset() -> None:
    grid = Grid(width=3, height=3, blocked=[Position(1, 1)])

    assert isinstance(grid.blocked, frozenset)
    with pytest.raises(AttributeError):
        grid.blocked.add(Position(0, 0))


def test_duplicate_blocked_entries_collapse() -> None:
    grid = Grid(width=3, height=3, blocked=[Position(1, 1), Position(1, 1)])

    assert grid.blocked == frozenset({Position(1, 1)})


def test_a_grid_is_hashable_by_value() -> None:
    first = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))
    second = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))

    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_grid_attributes_cannot_be_reassigned() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())

    for attribute, value in (("width", 5), ("height", 5), ("blocked", frozenset())):
        with pytest.raises(FrozenInstanceError):
            setattr(grid, attribute, value)


# --------------------------------------------------------------------------
# AntScenario validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, goal, role",
    [
        (Position(3, 3), Position(2, 2), "start"),
        (Position(-1, 0), Position(2, 2), "start"),
        (Position(0, 0), Position(3, 0), "goal"),
        (Position(0, 0), Position(0, -1), "goal"),
        (Position(0, 0), Position(3, 3), "goal"),
    ],
)
def test_rejects_start_or_goal_outside_the_grid(start: Position, goal: Position, role: str) -> None:
    with pytest.raises(ValueError, match=f"{role} position"):
        AntScenario(grid=OPEN, start=start, goal=goal, foods=frozenset())


def test_rejects_every_food_outside_the_grid() -> None:
    with pytest.raises(ValueError, match="food position"):
        AntScenario(
            grid=OPEN,
            start=Position(0, 0),
            goal=Position(2, 2),
            foods=frozenset({Position(3, 3)}),
        )
    with pytest.raises(ValueError, match="food position"):
        AntScenario(
            grid=OPEN,
            start=Position(0, 0),
            goal=Position(2, 2),
            foods=frozenset({Position(1, 1), Position(0, 5)}),
        )


@pytest.mark.parametrize("role", ["start", "goal", "food"])
def test_rejects_a_blocked_cell_for_every_role(role: str) -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))
    target = Position(1, 1)

    fields: dict[str, Position] = {"start": Position(0, 0), "goal": Position(2, 2)}
    foods: frozenset[Position] = frozenset()
    if role == "start":
        fields["start"] = target
    elif role == "goal":
        fields["goal"] = target
    else:
        foods = frozenset({target})

    with pytest.raises(ValueError, match=f"{role} position Position"):
        AntScenario(grid=grid, start=fields["start"], goal=fields["goal"], foods=foods)


def test_accepts_food_on_the_start_and_on_the_goal_cell() -> None:
    scenario = AntScenario(
        grid=OPEN,
        start=Position(0, 0),
        goal=Position(2, 2),
        foods=[Position(0, 0), Position(2, 2)],
    )

    assert scenario.foods == frozenset({Position(0, 0), Position(2, 2)})


def test_accepts_start_equal_to_goal() -> None:
    scenario = AntScenario(grid=OPEN, start=Position(1, 1), goal=Position(1, 1), foods=frozenset())

    assert scenario.start == scenario.goal


def test_duplicate_foods_collapse_and_the_result_is_a_frozenset() -> None:
    scenario = AntScenario(
        grid=OPEN,
        start=Position(0, 0),
        goal=Position(2, 2),
        foods=[Position(1, 1), Position(1, 1), Position(0, 0), Position(1, 1)],
    )

    assert scenario.foods == frozenset({Position(1, 1), Position(0, 0)})
    assert isinstance(scenario.foods, frozenset)
    with pytest.raises(AttributeError):
        scenario.foods.add(Position(2, 2))


def test_the_food_collection_order_is_irrelevant() -> None:
    forward = AntScenario(
        grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=[Position(0, 1), Position(1, 2)]
    )
    backward = AntScenario(
        grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=[Position(1, 2), Position(0, 1)]
    )

    assert forward == backward
    assert hash(forward) == hash(backward)


def test_a_food_list_cannot_change_the_scenario_afterwards() -> None:
    foods = [Position(1, 1)]
    scenario = AntScenario(grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=foods)

    foods.append(Position(0, 1))
    foods.clear()

    assert scenario.foods == frozenset({Position(1, 1)})


def test_a_mutable_food_set_cannot_change_the_scenario_afterwards() -> None:
    foods = {Position(1, 1)}
    scenario = AntScenario(grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=foods)

    foods.add(Position(0, 1))

    assert scenario.foods == frozenset({Position(1, 1)})


def test_a_mapping_passed_as_foods_is_snapshotted() -> None:
    mapping = {Position(1, 1): 3}
    scenario = AntScenario(grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=mapping)

    mapping[Position(0, 1)] = 1

    assert scenario.foods == frozenset({Position(1, 1)})


def test_a_lazily_produced_food_collection_is_snapshotted() -> None:
    def cells() -> Iterator[Position]:
        yield Position(1, 1)
        yield Position(0, 1)

    scenario = AntScenario(grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=cells())

    assert scenario.foods == frozenset({Position(1, 1), Position(0, 1)})


def test_the_scenario_keeps_the_grid_it_was_given() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset({Position(1, 1)}))
    scenario = AntScenario(grid=grid, start=Position(0, 0), goal=Position(2, 2), foods=frozenset())

    assert scenario.grid is grid


def test_the_grid_holds_a_snapshot_not_a_view_of_its_input() -> None:
    """``Grid`` is immutable, so a live view of the input could only go wrong."""
    blocked: set[Position] = {Position(1, 1)}
    grid = Grid(width=3, height=3, blocked=blocked)
    scenario = AntScenario(grid=grid, start=Position(0, 0), goal=Position(2, 2), foods=frozenset())
    blocked.add(Position(1, 0))

    assert scenario.grid.is_walkable(Position(1, 0)) is True
    assert scenario.foods == frozenset()


def test_scenario_attributes_cannot_be_reassigned() -> None:
    scenario = AntScenario(grid=OPEN, start=Position(0, 0), goal=Position(2, 2), foods=frozenset())

    changes = (
        ("start", Position(1, 1)),
        ("goal", Position(0, 1)),
        ("foods", {Position(1, 1)}),
        ("grid", OPEN),
    )
    for attribute, value in changes:
        with pytest.raises(FrozenInstanceError):
            setattr(scenario, attribute, value)


# --------------------------------------------------------------------------
# SearchState
# --------------------------------------------------------------------------


def test_states_with_different_collected_food_are_different_states() -> None:
    base = SearchState(Position(1, 1), frozenset())
    with_food = SearchState(Position(1, 1), frozenset({Position(0, 0)}))

    assert base != with_food
    assert hash(base) != hash(with_food)
    assert len({base, with_food}) == 2
    assert base == SearchState(Position(1, 1), frozenset())


def test_state_equality_ignores_the_identity_of_the_food_set() -> None:
    state = SearchState(Position(1, 1), frozenset({Position(0, 0)}))

    assert state == SearchState(Position(1, 1), {Position(0, 0)})


def test_state_attributes_cannot_be_reassigned() -> None:
    state = SearchState(Position(1, 1), frozenset())

    for attribute, value in (
        ("position", Position(0, 0)),
        ("collected", frozenset({Position(0, 0)})),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(state, attribute, value)


def test_a_state_is_usable_as_a_dict_key() -> None:
    table = {SearchState(Position(0, 0), frozenset()): "start"}

    assert table[SearchState(Position(0, 0), frozenset())] == "start"


# --------------------------------------------------------------------------
# SearchResult invariants
# --------------------------------------------------------------------------


PATH = (Position(0, 0), Position(1, 0), Position(2, 0))


def test_successful_result_requires_a_path() -> None:
    with pytest.raises(ValueError, match="non-empty path"):
        SearchResult(found=True, path=(), cost=0, expanded_states=1)
    with pytest.raises(ValueError, match="non-empty path"):
        SearchResult.success((), expanded_states=1)


def test_failed_result_rejects_any_path() -> None:
    with pytest.raises(ValueError, match="cannot carry a path"):
        SearchResult(found=False, path=PATH, cost=0, expanded_states=1)
    with pytest.raises(ValueError, match="cannot carry a path"):
        SearchResult(found=False, path=PATH, cost=2, expanded_states=1)


@pytest.mark.parametrize("cost", [-1, 0, 1, 3, 4])
def test_cost_that_contradicts_the_path_length_is_rejected(cost: int) -> None:
    with pytest.raises(ValueError, match="does not match"):
        SearchResult(found=True, path=PATH, cost=cost, expanded_states=1)


@pytest.mark.parametrize("cost", [-1, 1, 2])
def test_failed_result_rejects_a_nonzero_cost(cost: int) -> None:
    with pytest.raises(ValueError, match="does not match"):
        SearchResult(found=False, path=(), cost=cost, expanded_states=1)


@pytest.mark.parametrize("expanded", [-1, -7])
def test_negative_expanded_states_are_rejected(expanded: int) -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        SearchResult.failure(expanded_states=expanded)
    with pytest.raises(ValueError, match="cannot be negative"):
        SearchResult.success(PATH, expanded_states=expanded)


def test_zero_expanded_states_is_accepted_but_suspicious() -> None:
    result = SearchResult.success(PATH, expanded_states=0)

    assert result.expanded_states == 0
    assert result.cost == 2


def test_the_constructors_normalize_the_path_to_a_tuple() -> None:
    from_list = SearchResult.success(list(PATH), expanded_states=3)
    from_iterator = SearchResult.success(iter(PATH), expanded_states=3)

    assert from_list.path == PATH
    assert isinstance(from_list.path, tuple)
    assert from_iterator.path == PATH
    assert isinstance(from_iterator.path, tuple)


def test_success_derives_the_cost_of_a_single_cell_path_as_zero() -> None:
    result = SearchResult.success([Position(2, 2)], expanded_states=1)

    assert result.found is True
    assert result.cost == 0


def test_failure_always_reports_zero_cost_and_an_empty_path() -> None:
    for expanded in (0, 1, 99):
        result = SearchResult.failure(expanded_states=expanded)
        assert (result.found, result.path, result.cost) == (False, (), 0)


def test_results_are_immutable_and_compare_by_value() -> None:
    first = SearchResult.success(PATH, expanded_states=3)
    second = SearchResult.success(PATH, expanded_states=3)

    assert first == second
    assert hash(first) == hash(second)
    for attribute, value in (("cost", 0), ("found", False), ("expanded_states", 0)):
        with pytest.raises(FrozenInstanceError):
            setattr(first, attribute, value)


def test_the_result_does_not_validate_the_path_it_is_given() -> None:
    """A gap worth knowing about: only the length of the path is checked.

    Nothing in ``SearchResult`` looks at the grid, so a non-walkable step or a
    path that does not start at the scenario start is accepted. The search is
    responsible for that, which is why the behaviour tests assert the path shape
    against the scenario instead of trusting the value object.
    """
    result = SearchResult.success((Position(0, 0), Position(5, 5)), expanded_states=2)

    assert result.found is True
    assert result.cost == 1


# --------------------------------------------------------------------------
# Grid neighbours swept over many shapes
# --------------------------------------------------------------------------


def test_neighbours_of_every_cell_of_many_grid_shapes() -> None:
    """Randomised geometry check over thin, square and rectangular grids.

    Only the geometric contract is asserted: four offsets, no duplicates, never
    the cell itself, never outside the grid, and exactly the cells that share an
    edge with it.
    """
    generator = Random(4_815)
    for _ in range(40):
        width = generator.randint(1, 9)
        height = generator.randint(1, 9)
        grid = Grid(width=width, height=height, blocked=frozenset())
        for y in range(height):
            for x in range(width):
                cell = Position(x, y)
                neighbours = grid.neighbors(cell)
                expected = {
                    Position(x + dx, y + dy)
                    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))
                    if 0 <= x + dx < width and 0 <= y + dy < height
                }
                assert len(neighbours) == len(set(neighbours))
                assert cell not in neighbours
                assert set(neighbours) == expected, (width, height, cell)
                assert all(grid.contains(neighbour) for neighbour in neighbours)


@pytest.mark.parametrize("width, height", [(1, 1), (1, 5), (5, 1), (1, 40), (40, 1)])
def test_a_one_cell_thin_grid_has_at_most_two_neighbours(width: int, height: int) -> None:
    grid = Grid(width=width, height=height, blocked=frozenset())
    degrees = [len(grid.neighbors(Position(x, y))) for y in range(height) for x in range(width)]

    assert max(degrees) <= 2
    assert sum(degrees) == 2 * max(width, height) - 2


def test_the_far_corner_is_inside_the_grid_and_walkable() -> None:
    grid = Grid(width=4, height=7, blocked=frozenset())
    corner = Position(3, 6)

    assert grid.contains(corner) is True
    assert grid.is_walkable(corner) is True
    assert grid.neighbors(corner) == (Position(2, 6), Position(3, 5))


def test_the_first_cell_past_every_edge_is_outside_the_grid() -> None:
    grid = Grid(width=4, height=7, blocked=frozenset())

    for outside in (
        Position(4, 0),
        Position(0, 7),
        Position(4, 6),
        Position(-1, 6),
        Position(3, 7),
        Position(4, 7),
    ):
        assert grid.contains(outside) is False
        assert grid.is_walkable(outside) is False


def test_blocking_every_cell_of_a_grid_is_allowed() -> None:
    """A grid with no walkable cell is well formed; only a scenario may not use it."""
    width = height = 3
    cells = [Position(x, y) for y in range(height) for x in range(width)]
    grid = Grid(width=width, height=height, blocked=frozenset(cells))

    assert len(grid.blocked) == 9
    assert all(not grid.is_walkable(cell) for cell in cells)


def test_replacing_a_grid_field_validates_again() -> None:
    grid = Grid(width=3, height=3, blocked=frozenset())

    widened = replace(grid, width=4)

    assert widened.width == 4
    assert len(grid.blocked) == 0
    with pytest.raises(ValueError, match="dimensions must be positive"):
        replace(grid, height=0)


# --------------------------------------------------------------------------
# AntScenario reports its failures in a fixed order
# --------------------------------------------------------------------------


def test_an_invalid_start_is_reported_before_an_invalid_goal() -> None:
    with pytest.raises(ValueError, match="start position"):
        AntScenario(grid=OPEN, start=Position(5, 5), goal=Position(6, 6), foods=frozenset())


def test_an_invalid_goal_is_reported_before_an_invalid_food() -> None:
    with pytest.raises(ValueError, match="goal position"):
        AntScenario(
            grid=OPEN,
            start=Position(0, 0),
            goal=Position(9, 9),
            foods=frozenset({Position(7, 7)}),
        )


def test_the_first_food_in_order_is_the_one_reported() -> None:
    """Foods are checked in grid order, so the message is reproducible."""
    with pytest.raises(ValueError, match=r"food position Position\(x=0, y=4\)"):
        AntScenario(
            grid=OPEN,
            start=Position(0, 0),
            goal=Position(2, 2),
            foods=frozenset({Position(4, 0), Position(0, 4)}),
        )


def test_a_single_cell_grid_accepts_a_start_that_is_also_the_goal_and_the_food() -> None:
    grid = Grid(width=1, height=1, blocked=frozenset())
    cell = Position(0, 0)

    scenario = AntScenario(grid=grid, start=cell, goal=cell, foods=[cell])

    assert scenario.foods == frozenset({cell})
    assert grid.neighbors(cell) == ()


def test_a_scenario_on_a_single_cell_grid_is_accepted_and_solved_at_no_cost() -> None:
    grid = Grid(width=1, height=1, blocked=frozenset())
    cell = Position(0, 0)

    result = solve_bfs(AntScenario(grid=grid, start=cell, goal=cell, foods=frozenset({cell})))

    assert (result.found, result.path, result.cost, result.expanded_states) == (
        True,
        (cell,),
        0,
        1,
    )


# --------------------------------------------------------------------------
# Defects this suite found, now fixed and kept as regressions
# --------------------------------------------------------------------------


def test_a_search_state_normalizes_collected_to_a_frozenset() -> None:
    state = SearchState(Position(0, 0), {Position(1, 1)})

    assert isinstance(state.collected, frozenset)
    assert hash(state) == hash(SearchState(Position(0, 0), {Position(1, 1)}))


def test_mutating_the_collected_set_cannot_change_an_existing_state() -> None:
    collected = {Position(1, 1)}
    state = SearchState(Position(0, 0), collected)

    collected.add(Position(2, 2))

    assert state.collected == frozenset({Position(1, 1)})


def test_a_directly_built_result_normalizes_its_path_to_a_tuple() -> None:
    result = SearchResult(
        found=True, path=[Position(0, 0), Position(1, 0)], cost=1, expanded_states=2
    )

    assert isinstance(result.path, tuple)


def test_mutating_the_path_cannot_break_the_cost_invariant() -> None:
    path = [Position(0, 0), Position(1, 0)]
    result = SearchResult(found=True, path=path, cost=1, expanded_states=2)

    path.append(Position(2, 0))

    assert result.cost == len(result.path) - 1
