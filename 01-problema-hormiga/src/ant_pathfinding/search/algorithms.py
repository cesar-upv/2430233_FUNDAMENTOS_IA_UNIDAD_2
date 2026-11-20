"""Choosing a search by name.

The one thing a caller above this layer needs from the algorithms is the ability to
turn a user selection into a run. :class:`SearchAlgorithm` is that selection - a
closed set of the three names the application may offer - and :func:`new_runner` maps
one onto a :class:`~ant_pathfinding.search.runner.SearchRunner` configured for it.

That mapping is the entire concrete responsibility of this module, and it is
deliberately a plain ``match``: it is three lines of configuration, and the behaviour
behind them already lives in one engine, so there is nothing here to abstract. No
protocol, no abstract base class, no registry and no solver alias are introduced,
because nothing varies an algorithm by interface yet - every entry point takes the
scenario and nothing else, the one optional argument in the family being A*'s
keyword-only ``heuristic``, and that is a choice of estimate rather than a second kind
of call.

What would justify upgrading to a protocol is a consumer that has to treat all
algorithms generically without knowing their names: a benchmark harness that loops
over "every algorithm, on this scenario", or a persistence codec that encodes an
algorithm and needs to decode any value of this enum back into a runner. The moment
such a consumer appears it can enumerate ``SearchAlgorithm`` and switch on it itself,
and the abstraction will have a caller to justify it. Until then an enum plus a
``match`` is the smaller honest thing.
"""

from enum import StrEnum
from typing import assert_never

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import manhattan_mst, uniform_cost
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.runner import SearchRunner


class SearchAlgorithm(StrEnum):
    """The searches a caller may select by name."""

    BFS = "bfs"
    """Unit-cost breadth-first search; see :func:`ant_pathfinding.search.bfs.solve_bfs`."""

    DIJKSTRA = "dijkstra"
    """Uniform-cost search; on a unit-cost grid the same answer as ``BFS``; see
    :func:`ant_pathfinding.search.dijkstra.solve_dijkstra`."""

    ASTAR = "astar"
    """Cost plus estimate search, optimal for an admissible estimate: consistency is
    not required, because the engine reopens a state whose cost it improves, and it
    only bounds the work by allowing one expansion per state. The default
    :func:`~ant_pathfinding.search.heuristics.lower_bounds.manhattan_mst` is
    admissible but deliberately not consistent; see
    :func:`ant_pathfinding.search.astar.solve_astar`."""


def new_runner(algorithm: SearchAlgorithm, scenario: AntScenario) -> SearchRunner:
    """Return a fresh runner configured for ``algorithm``.

    Each call builds an independent run: two runners over one scenario share nothing
    but the immutable scenario, so their frontiers, counters and results cannot
    interfere. The runner is expanded through
    :meth:`~ant_pathfinding.search.runner.SearchRunner.step`; a caller that only wants
    the answer should use :func:`solve`.
    """
    match algorithm:
        case SearchAlgorithm.BFS | SearchAlgorithm.DIJKSTRA:
            # The two differ in name and in intent only: both order the frontier by
            # accumulated cost alone, which is what makes them agree on this grid.
            return SearchRunner(scenario, heuristic=uniform_cost)
        case SearchAlgorithm.ASTAR:
            return SearchRunner(scenario, heuristic=manhattan_mst)
    assert_never(algorithm)


def solve(algorithm: SearchAlgorithm, scenario: AntScenario) -> SearchResult:
    """Return the result of running ``algorithm`` to completion."""
    return new_runner(algorithm, scenario).run_to_completion()
