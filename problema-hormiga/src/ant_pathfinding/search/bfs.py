"""Optimal multi-goal breadth-first search.

Every move costs 1, so breadth-first search expands states in non-decreasing
order of accumulated cost and the first goal state removed from the queue is
reached with minimum total movement. The state carries the collected food, so no
greedy "walk to the nearest food" assumption is made.

This module is the unit-cost special case of :mod:`ant_pathfinding.search.runner`,
the one engine shared with Dijkstra and A*: with a zero estimate the engine's
priority is the accumulated cost alone, which on a unit-cost grid *is*
breadth-first search.

Why the delegation cannot change a single answer. The engine orders the frontier by
``(cost, insertion sequence)``. Because every move costs exactly 1, a state
discovered while expanding one of cost ``c`` has cost ``c + 1``, so states are
inserted in non-decreasing cost order and, inside one cost layer, insertion sequence
reproduces FIFO order; across layers the cost already decides. Ordering the same
states by ``(cost, sequence)`` consequently pops the same state a FIFO queue would
pop at every step, so by induction over the pops the discovered set, the expanded
set, the pop order, the parent map, the returned path and every ``expanded_states``
count are exactly what a hand-written breadth-first loop over these states
produces - given that such a loop enumerates the successors in the same order, that is
:meth:`~ant_pathfinding.domain.grid.Grid.neighbors` order: east, south, west, north.
Enumerating them in another order still returns an optimal path, but a different one,
and a different ``expanded_states`` count.

The second condition is the parent map. This engine writes a parent only together
with a strictly better cost, so on a unit-cost grid - where a state is never improved
after discovery - it keeps the parent recorded at first discovery. A reference that
assigns the parent on every regeneration of a successor still reports the same cost,
but the parent chain it rebuilds is not this one: a later, deeper expansion takes
over as the parent of one of its own ancestors, and the chain can even close into a
cycle, so the rebuilt walk is not even guaranteed to terminate.
"""

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import uniform_cost
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.runner import SearchRunner


def solve_bfs(scenario: AntScenario) -> SearchResult:
    """Return the optimal start-to-goal path that collects all food.

    The search stops only on a state that stands on the goal cell with every
    food collected; passing through the goal earlier does not end the search. A
    successful run stops as soon as the terminal goal state leaves the frontier, so
    the expanded count falls short of the discovered count exactly when the run
    returns with a non-empty frontier - the two counts are equal when the goal state
    was the last state the run enqueued, as when the start is already the goal or the
    goal is the start's only walkable neighbour and there is no food to collect. The
    canonical definition of that count lives on
    :attr:`SearchStatistics.expanded_states
    <ant_pathfinding.search.progress.SearchStatistics.expanded_states>`.

    Use :class:`ant_pathfinding.search.runner.SearchRunner` with
    :func:`uniform_cost` to watch a breadth-first run step by step.
    """
    return SearchRunner(scenario, heuristic=uniform_cost).run_to_completion()
