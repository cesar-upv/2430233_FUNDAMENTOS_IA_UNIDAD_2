"""Optimal multi-goal A*.

A* differs from uniform-cost search only in what it adds to the accumulated cost
before choosing the next state: an estimate of the moves still needed. Ordered by
``cost + estimate``, a state whose estimate says "far from what is left" is left
waiting, while a state that is cheap and nearly finished is taken early. The engine,
the frontier and the bookkeeping are the shared ones in
:mod:`ant_pathfinding.search.runner`.

**The optimality claim is a claim about the estimate.** The default estimate,
:func:`~ant_pathfinding.search.heuristics.manhattan_mst`, is admissible: it never
overestimates the moves that are left, which is what makes the path this function
returns optimal - the runner reopens a state whose cost is improved, so admissibility
alone is enough. That estimate is deliberately *not* consistent, so a state can be
expanded more than once; consistency would only buy the guarantee of a single
expansion per state. A caller-supplied estimate that is inadmissible can return a
suboptimal path - that is a property of the estimate, not a bug in the engine. On a
unit-cost grid, uniform-cost search is the special case reachable by passing
:func:`~ant_pathfinding.search.heuristics.uniform_cost`.
"""

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import Heuristic, manhattan_mst
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.runner import SearchRunner


def solve_astar(scenario: AntScenario, *, heuristic: Heuristic = manhattan_mst) -> SearchResult:
    """Return the optimal start-to-goal path that collects all food.

    The search stops only on a state that stands on the goal cell with every
    food collected; passing through the goal earlier does not end the search.

    ``heuristic`` defaults to
    :func:`~ant_pathfinding.search.heuristics.manhattan_mst`, the admissible estimate
    under which the returned path is optimal. Passing
    :func:`~ant_pathfinding.search.heuristics.uniform_cost` turns this into
    uniform-cost search on the same grid; passing anything else is the caller's
    responsibility to keep admissible.

    Use :class:`ant_pathfinding.search.runner.SearchRunner` with the same
    ``heuristic`` to watch an A* run step by step.
    """
    return SearchRunner(scenario, heuristic=heuristic).run_to_completion()
