"""Admissible lower bounds on the number of moves a state still needs.

Both functions here are pure: they read a scenario and a state and return an
integer. Neither of them touches a frontier, a cost table or a result, so the
same estimate can be reused by any search that asks for it, and it can be tested
on its own - see ``tests/unit/search/test_heuristics.py``, where the estimates are
checked against an independently written breadth-first walk rather than against
another heuristic.

The strategy is composed by function, not by class: a caller passes one of these
functions to :class:`ant_pathfinding.search.runner.SearchRunner`, and the search
layer never learns which one it got.
"""

from __future__ import annotations

from collections.abc import Sequence

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.state import SearchState


def uniform_cost(scenario: AntScenario, state: SearchState) -> int:
    """Return the trivial estimate ``0`` for every state.

    Zero is the trivial admissible and consistent estimate: it never overestimates,
    so the search stays optimal, and it never changes, so the consistency condition
    ``h(s) <= 1 + h(s')`` holds with room to spare. A search that uses it ignores
    the estimate entirely and orders states by accumulated cost alone, which is
    uniform-cost search. On a grid where every move costs 1 that *is* breadth-first
    search, so this heuristic is how the engine is asked for BFS or Dijkstra
    behaviour, and it is also the special case that makes
    :func:`ant_pathfinding.search.astar.solve_astar` degrade to uniform-cost search
    on demand.

    The arguments are part of the signature and are deliberately unused: the alias
    :data:`ant_pathfinding.search.heuristics.Heuristic` requires every heuristic to
    accept them.
    """
    return 0


def manhattan_mst(scenario: AntScenario, state: SearchState) -> int:
    """Estimate the remaining moves as the weight of a minimum spanning tree.

    **What it estimates.** A lower bound on the moves still needed to collect every
    food that is not in ``state.collected`` and then finish on the goal. The
    estimate is the weight of a minimum spanning tree (MST) over the ant position,
    the pending foods and the goal, all measured with the static Manhattan metric
    ``|dx| + |dy|``.

    **Admissible.** Take an optimal completion walk from this state and list the
    positions where it first touches each of the pending foods and the goal. Read
    as a sequence of cells that starts on the ant, that list visits every vertex
    exactly once, so it is a Hamiltonian path of the vertex set; each hop of the
    path is bounded by the Manhattan distance between the two cells, so the path
    length is at most the walk cost; and a Hamiltonian path is itself a spanning
    tree, so ``MST <= OPT``. When the vertex set holds a single cell nothing is
    left to visit, the MST has no edges and the estimate is ``0``. If no completion
    walk exists at all the bound is vacuously true.

    **Not consistent, and knowingly so.** Consistency would need
    ``MST(vertices_before) <= MST(vertices_after) + 1`` across a move, resting on "a
    minimum spanning tree cannot change much when one vertex is swapped for a
    neighbouring one". It can change a lot, because the vertex that leaves is the
    ant's own cell and the vertex that arrives can become a junction for the targets:
    the tree is rebuilt around a new cell, not merely extended. The smallest violation
    found so far needs six cells and no wall at all - a ``2 x 3`` grid with start
    ``(0, 2)``, goal ``(0, 1)`` and the two foods ``(0, 0)`` and ``(1, 0)``::

        F F
        G .
        S .

    From ``(1, 2)``, with ``(0, 0)`` already collected, the vertices are
    ``{(1, 2), (1, 0), (0, 1)}`` and weigh ``2 + 2 = 4``; one move later, at
    ``(1, 1)``, they are ``{(1, 1), (1, 0), (0, 1)}`` and weigh ``1 + 1 = 2``, so
    ``h(s) = 4 > 1 + 2 = 1 + h(s')``. Both states stay admissible - four and three
    moves really are left - and sweeping every grid of up to five cells, every wall
    pattern on it and every food placement finds no violation at all, so six cells is
    the smallest grid this estimate is known to break on; on sampled larger grids a
    few percent of the reachable one-move transitions violate it.

    A violation need not run one way only, so there is no one-sided bound to fall back
    on. On a ``3 x 3`` grid with ``(1, 0)`` and ``(1, 1)`` blocked, start ``(2, 2)``,
    goal ``(2, 1)`` and the single food at ``(0, 0)``, nothing collected::

        F # .
        . # G
        . . S

    The vertex that leaves is the one that sat between the food and the goal and the
    one that arrives does not, so on ``(0, 2)`` the vertices ``{(0, 2), (0, 0),
    (2, 1)}`` weigh ``2 + 3 = 5`` while on ``(0, 1)`` the vertices ``{(0, 1), (0, 0),
    (2, 1)}`` weigh ``1 + 2 = 3``: ``5 > 1 + 3`` in that direction, and the step back
    from ``(0, 1)`` to ``(0, 2)`` raises the estimate by two for a single move. Neither
    ``h(s') <= 1 + h(s)`` nor its converse holds in general.

    The consequence is mechanical, not fatal. Optimality of A* needs *admissibility*
    plus a runner that reopens a state whose cost is improved after it was expanded,
    which is exactly what
    :class:`ant_pathfinding.search.runner.SearchRunner` does; consistency is only
    what bounds the *work*, because it rules out a state being expanded twice. So an
    inconsistent estimate costs expansions here, not optimality, and the runner is
    built to absorb it.

    **Quality, inside the metric relaxation.** The MST bound is the standard
    approximation for a metric travelling-salesman bound: for a metric, the optimal
    completion cost satisfies ``MST <= OPT <= 2 * MST``, the upper half being the
    double-tree argument and holding for an open path as well as for a tour. That
    ``OPT`` is the completion walk length of the *relaxed* problem - the same
    collect-and-finish objective with every cell reachable and every pair measured by
    Manhattan distance - so within the relaxation the estimate is never short of the
    truth by more than a factor of two.

    It is not a bound on what the real grid costs. Walls are exactly what the relaxed
    metric cannot see, and they push the true remaining cost arbitrarily far above
    ``2 * MST``: on this ``4 x 4`` grid, start ``(0, 0)``, goal ``(0, 1)``, one food::

        S # F .
        G . . .
        . . . .
        . . . .

    the three vertices weigh ``1 + 2 = 3`` while ``7`` moves are really left, and
    there is no constant factor to rescue the claim - a serpentine corridor on a
    ``9 x 39`` grid estimates ``46`` for ``190`` moves. Only the one-sided half
    survives for the grid, ``MST <= OPT``, which is the half admissibility needs; the
    looseness costs this search expansions, not optimality.

    **Cost and scope.** One call is ``O(k^2)`` for ``k`` pending foods plus the goal.
    That is affordable next to the state space this problem already pays for - a
    search over ``cells x 2^foods`` states with a heap and a parent map per state -
    and memoization is deliberately not done yet, because no measurement has shown
    the estimate to be a bottleneck (premature optimization).

    **Obstacles are ignored on purpose.** The metric is the static Manhattan distance
    even where a wall stands between two cells. Ignoring them can only *under*
    estimate, because the true walk is at least as long as the straight-line
    distance, which is the direction admissibility needs. Walls are also the main
    reason the bound is loose in practice: over the seeded sample of solvable states
    that ``tests/unit/search/test_heuristics.py`` measures, at least a quarter of the
    estimates are exactly the true remaining cost, and the rest are smaller.

    **A state invariant is assumed, not hidden.** Food is collected on entry, so a
    state standing on a food cell always has that food in ``collected``. The estimate
    relies on this: it is what makes ``h(s) == 0`` hold exactly at the terminal
    states, namely a state on the goal cell with every food collected, whose vertex
    set has collapsed to the single cell the ant stands on. Without the invariant a
    food left pending under the ant would be counted as a vertex at distance 0,
    which would not change the value but would no longer mean "terminal".

    **Why a spanning tree and not the nearest target.** Both this estimate and the
    weaker ``max(d(pos, nearest food), d(pos, goal))`` are admissible; the latter is
    also consistent, and is simply too weak: it never grows as more targets remain,
    so A* driven by it degenerates towards uniform-cost search. This estimate covers
    both objectives at once - the multiobjective "collect the pending food *and* end
    on the goal" - and it dominates the weaker one. In a spanning tree the unique
    path from the ant to a target weighs at least that target's Manhattan distance,
    and the whole tree weighs at least each of those path weights, so the total is at
    least the largest of them: ``h >= max(d(pos, t) for t in targets) >=
    max(d(pos, nearest food), d(pos, goal))``.
    """
    pending = frozenset(scenario.foods) - state.collected
    targets = pending | {scenario.goal}
    vertices = sorted({state.position} | targets)
    return _mst_weight(vertices)


def _mst_weight(vertices: Sequence[Position]) -> int:
    """Weight of a minimum spanning tree over ``vertices`` under Manhattan distance.

    Dense Prim: ``vertices`` is the complete graph, so every edge exists and only the
    weights have to be compared. A single vertex has no edge and weighs ``0``.
    """
    total = 0
    if len(vertices) < 2:
        return total
    connected = [False] * len(vertices)
    connected[0] = True
    # cheapest[k] is the lightest edge from the growing tree to vertex k.
    cheapest = [_manhattan(vertices[0], vertex) for vertex in vertices]
    for _ in range(len(vertices) - 1):
        outside = [index for index in range(len(vertices)) if not connected[index]]
        pick = min(outside, key=cheapest.__getitem__)
        total += cheapest[pick]
        connected[pick] = True
        for index in outside:
            if index == pick:
                continue
            distance = _manhattan(vertices[pick], vertices[index])
            if distance < cheapest[index]:
                cheapest[index] = distance
    return total


def _manhattan(origin: Position, target: Position) -> int:
    """Return the static grid distance between two cells."""
    return abs(origin.x - target.x) + abs(origin.y - target.y)
