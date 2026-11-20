# 0001 - One search engine, three settings, instead of three algorithms

Status: accepted.

## Context

BFS, Dijkstra and A* must all run over the same multi-goal state space: the ant
position together with the collected food set. What distinguishes them is only what
they add to the accumulated cost before choosing the next state - nothing, or an
estimate. Written as three algorithms, the multi-goal goal test, the successor
generation, the parent bookkeeping, the four progress counters and the incremental
`step()` loop would exist three times, and each copy would drift.

## Decision

One expansion loop, `SearchRunner`, parameterised by a `Heuristic` function
(`Callable[[AntScenario, SearchState], int]`). `solve_bfs`, `solve_dijkstra` and
`solve_astar` are thin delegations that build a runner with the right estimate.
Selection from outside the layer is the `SearchAlgorithm` enum plus `new_runner`, and
that function is a `match` ending in `assert_never` - no registry.

## Consequences

- One implementation of the multi-goal goal test and of the progress contract to keep
  correct, and one place where the counters are defined.
- A fourth search is a new estimate rather than a new module.
- The cost is that BFS and Dijkstra no longer have an independent implementation to be
  compared against, so their equivalence to a hand-written FIFO loop is a documented
  argument plus tests rather than a second implementation. That argument needs two
  conditions to be honest: the same successor order as `Grid.neighbors`, and a parent
  map that keeps the parent recorded at first discovery. Both are documented on the
  modules.
- `expanded_states` and the returned `path` are therefore determined only once a
  successor order is fixed. They are pinned by tests, not promised by an interface.

## Rejected

- Three separate algorithms, one loop each: triplicated bookkeeping and three places to
  be wrong.
- A `Solver` protocol or abstract base class over the entry points. Nothing varies an
  algorithm by interface yet. Revisit when a consumer must treat all algorithms
  generically without naming them - a benchmark harness, or a persistence codec that
  turns an encoded algorithm name back into a runner.
