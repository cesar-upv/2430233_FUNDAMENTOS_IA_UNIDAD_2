"""Optimal multi-goal uniform-cost search (Dijkstra).

**On this grid Dijkstra is breadth-first search, and that is not a bug.** Every move
costs 1, so the shortest-path problem has no edge-weight variation for Dijkstra's
``f = g`` ordering to exploit: it pops states in exactly the order a FIFO queue pops
them, expands exactly the same states, and returns exactly the same path as
:func:`ant_pathfinding.search.bfs.solve_bfs`. Running both and getting identical
answers is the correct result, and the equivalence is pinned by tests rather than
left as folklore.

The function exists as the named, general uniform-cost entry point. It is written
against the shared engine with a zero estimate, which is the general formulation of
the same algorithm: were a move ever to cost more than 1, or a cell to cost
something other than its neighbours, this entry point would already be the right
*name* and the right formulation. The change would not be confined to this file,
though - the engine accumulates ``cost + 1`` per move and offers no step-cost
parameter, so it would need a hook for the cost of a step before a weighted grid could
be searched at all.
"""

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import uniform_cost
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.runner import SearchRunner


def solve_dijkstra(scenario: AntScenario) -> SearchResult:
    """Return the optimal start-to-goal path that collects all food.

    The search stops only on a state that stands on the goal cell with every
    food collected; passing through the goal earlier does not end the search. On a
    unit-cost grid the answer - the path, the cost and ``expanded_states`` - is the
    one :func:`ant_pathfinding.search.bfs.solve_bfs` returns.

    Use :class:`ant_pathfinding.search.runner.SearchRunner` with
    :func:`uniform_cost` to watch a uniform-cost run step by step.
    """
    return SearchRunner(scenario, heuristic=uniform_cost).run_to_completion()
