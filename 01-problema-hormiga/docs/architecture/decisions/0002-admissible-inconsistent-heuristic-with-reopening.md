# 0002 - Admissible but inconsistent heuristic, with state reopening

Status: accepted.

## Context

A* over the multi-goal state space needs a lower bound on the moves still required to
collect every pending food and finish on the goal. The bound has to be cheap enough to
call on every successor of every expansion, and it has to grow with the number of
targets that are left, otherwise A* degenerates towards uniform-cost search.

## Decision

`manhattan_mst` estimates the remaining moves as the weight of a minimum spanning tree
over `{ant} ∪ pending foods ∪ {goal}`, all measured with the static Manhattan metric.
The bound is admissible because the first-visit order of any completion walk is a
Hamiltonian path over that vertex set, and a Hamiltonian path is a spanning tree, so
`MST <= OPT`.

It is deliberately **not** consistent. MST is not monotone under vertex-set inclusion,
and a move replaces the ant's own vertex: the newcomer can become a junction for the
targets, so the estimate can change by more than 1, in either direction. Smallest
verified violation: a 2x3 grid with no walls, goal `(0, 1)`, foods `{(0, 0), (1, 0)}`;
from `(1, 2)` with `(0, 0)` collected the estimate is 4, one move later at `(1, 1)` it
is 2. The engine therefore **reopens** a state whose cost improves instead of closing
it.

## Consequences

- Admissibility alone becomes sufficient for optimality, because no expansion is
  permanent. The independent suite pins it on every scenario it sweeps - 852 exhaustive
  small maps, 8,592 two-food maps, 1,600 random maps and the degenerate rules - against
  two references that do not share the engine's structure.
- Re-expansion is rare rather than absent: of 432 larger maps in the reopening suite,
  a dozen or so re-expand a state.
- The price is untidy counters. `expanded_states` counts expansions, so a re-expanded
  state is counted twice and can exceed `discovered_states` on a successful run, and
  the exact A* frontier is not derivable from the step stream. All of this is
  documented in `search/progress.py`.
- A* bounds its work no better than a consistent heuristic would; the extra expansions
  are what is paid for a bound that grows with the number of pending targets.

## Rejected

- `max(d(ant, nearest food), d(ant, goal))`: consistent, but never grows as more
  targets remain, so it drives A* towards uniform-cost search.
- An MST over the targets *excluding* the ant's cell: consistent, but not admissible for
  a collect-and-finish objective, because the ant still has to reach the first target.
- Obstacle-aware distances: admissible and tighter, deferred until a measurement shows
  the static bound is too weak to pay for the cost.
