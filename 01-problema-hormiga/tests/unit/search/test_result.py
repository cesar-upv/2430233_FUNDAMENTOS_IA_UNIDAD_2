"""Invariants of the search result value object."""

import pytest

from ant_pathfinding.domain.position import Position
from ant_pathfinding.search.result import SearchResult

PATH = (Position(0, 0), Position(1, 0), Position(2, 0))


def test_success_derives_cost_from_the_path_length() -> None:
    result = SearchResult.success(PATH, expanded_states=3)

    assert result.found is True
    assert result.path == PATH
    assert result.cost == 2
    assert result.expanded_states == 3


def test_success_accepts_any_position_sequence() -> None:
    result = SearchResult.success(list(PATH), expanded_states=1)

    assert result.path == PATH


def test_failure_has_no_path_and_no_cost() -> None:
    result = SearchResult.failure(expanded_states=7)

    assert result.found is False
    assert result.path == ()
    assert result.cost == 0
    assert result.expanded_states == 7


def test_single_position_path_has_cost_zero() -> None:
    result = SearchResult.success((Position(1, 1),), expanded_states=1)

    assert result.found is True
    assert result.cost == 0


def test_success_without_a_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty path"):
        SearchResult.success((), expanded_states=1)


def test_failure_carrying_a_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot carry a path"):
        SearchResult(found=False, path=PATH, cost=0, expanded_states=1)


def test_cost_that_contradicts_the_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not match"):
        SearchResult(found=True, path=PATH, cost=3, expanded_states=3)


def test_negative_expanded_state_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        SearchResult.failure(expanded_states=-1)
