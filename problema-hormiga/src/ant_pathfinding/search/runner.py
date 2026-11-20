"""The one search engine behind breadth-first search, Dijkstra and A*.

There is a single expansion loop here, and the three algorithms are three settings
of it: which estimate is added to the accumulated cost, and nothing else. Priority
is ``(accumulated cost + estimate, insertion sequence)``. A state is popped, its
estimate is recomputed from the scenario, and its not-yet-discovered or improved
successors are pushed; the first terminal state popped ends the run.

Two properties make that setting-based approach safe rather than merely convenient:

* **Uniform cost is the uninformative case.** With a zero estimate the priority is
  ``(cost, sequence)``. On a unit-cost grid every move adds exactly 1, so states are
  inserted in non-decreasing cost order and, within a cost layer, insertion sequence
  *is* FIFO order. Ordering the same states by ``(cost, sequence)`` therefore pops
  them in exactly the order a FIFO queue would. Breadth-first search and Dijkstra are
  this loop with different names, and ``solve_bfs`` keeps answering bit for bit what
  a hand-written breadth-first loop over these states answers - given that such a loop
  enumerates successors in :meth:`~ant_pathfinding.domain.grid.Grid.neighbors` order
  and keeps the parent it recorded at first discovery, as this engine does when no
  cost ever improves.
* **The answer is optimal whenever the estimate is admissible.** Optimality does not
  come from the estimate being monotone: a state whose cost improves after it was
  expanded is pushed again and expanded again here - nothing is closed permanently -
  which is precisely the reopening A* needs to stay optimal under an admissible but
  inconsistent estimate. Consistency is what bounds the *work*: it rules out a state
  being expanded twice, so with a consistent estimate no frontier entry is ever
  superseded and every state is expanded exactly once. The default estimate of this
  package is admissible but not consistent, so A* does reopen states; it still
  returns an optimal path, at the price of the occasional extra expansion. An
  inadmissible estimate is the caller's responsibility and may return a longer path.

The engine is incremental by design. ``step()`` performs exactly one expansion and
reports it, so a consumer drives the run at its own pace - a test can step through a
map, and a later animation can play it back - without threads, without callbacks and
without this module knowing that anything is watching. The layer above this file owns
policy (which algorithm, which estimate) and the layer that will eventually draw owns
rendering; this file knows only the grid, the scenario and the state.
"""

from __future__ import annotations

from collections.abc import Iterator
from heapq import heappop, heappush

from ant_pathfinding.domain.position import Position
from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics import Heuristic
from ant_pathfinding.search.progress import SearchOutcome, SearchStatistics, SearchStep
from ant_pathfinding.search.result import SearchResult
from ant_pathfinding.search.state import SearchState

# (priority, insertion sequence, accumulated cost, state). The sequence is unique
# within a run, so the tuple comparison never reaches the cost or the state, which
# keeps the heap free of any ordering requirement on SearchState.
type _FrontierEntry = tuple[int, int, int, SearchState]


class SearchRunner:
    """An expandable search over the states of one scenario.

    The runner owns the frontier, the cost table, the parent map and the counters; it
    reports progress through :meth:`step` and the iterator protocol and never touches
    anything outside the search layer.
    """

    def __init__(self, scenario: AntScenario, *, heuristic: Heuristic) -> None:
        self._grid = scenario.grid
        self._foods = scenario.foods
        self._goal = scenario.goal
        self._scenario = scenario
        self._heuristic = heuristic
        self._outcome = SearchOutcome.RUNNING
        self._result: SearchResult | None = None
        self._expanded = 0
        start_state = SearchState(
            scenario.start, frozenset({scenario.start}).intersection(self._foods)
        )
        self._parents: dict[SearchState, SearchState | None] = {start_state: None}
        # The best-cost mapping doubles as the discovered set: a state is inserted the
        # first time an entry is written here.
        self._best_cost: dict[SearchState, int] = {start_state: 0}
        self._frontier: list[_FrontierEntry] = [
            (heuristic(scenario, start_state), 0, 0, start_state)
        ]
        self._sequence = 1
        self._discovered = 1
        self._peak = 1

    @property
    def statistics(self) -> SearchStatistics:
        """Return the counters as they stand right now."""
        return SearchStatistics(
            expanded_states=self._expanded,
            discovered_states=self._discovered,
            frontier_size=len(self._frontier),
            frontier_peak_size=self._peak,
        )

    @property
    def outcome(self) -> SearchOutcome:
        """Return how far the run has come; see :class:`SearchOutcome`."""
        return self._outcome

    @property
    def finished(self) -> bool:
        """Return whether the run will never expand another state."""
        return self._outcome is not SearchOutcome.RUNNING

    def step(self) -> SearchStep | None:
        """Expand at most one state and report it.

        Returns ``None`` once the run is over - either because it found a solution,
        because the frontier ran empty, or because it was stopped - and then keeps
        returning ``None`` without touching anything. Otherwise the returned step
        carries the expanded state, the states that expansion discovered and a
        statistics snapshot taken after it, so a terminal expansion is reported like
        any other.
        """
        if self._outcome is not SearchOutcome.RUNNING:
            return None
        while True:
            if not self._frontier:
                self._outcome = SearchOutcome.EXHAUSTED
                self._result = SearchResult.failure(self._expanded)
                return None
            _, _, cost, state = heappop(self._frontier)
            if cost > self._best_cost[state]:
                # A cheaper entry for this state was pushed after this one, so this
                # pop carries no information: it is not an expansion and not a step.
                continue
            self._expanded += 1
            if state.position == self._goal and state.collected == self._foods:
                self._outcome = SearchOutcome.FOUND
                self._result = SearchResult.success(
                    _rebuild_path(self._parents, state), self._expanded
                )
                return SearchStep(state, (), self.statistics)
            discovered = self._expand(state, cost)
            return SearchStep(state, discovered, self.statistics)

    def __iter__(self) -> Iterator[SearchStep]:
        """Iterate the expansions of this run; the runner *is* its own iterator."""
        return self

    def __next__(self) -> SearchStep:
        """Return the next expansion, or stop iterating once the run is over."""
        step = self.step()
        if step is None:
            raise StopIteration
        return step

    def stop(self) -> None:
        """End the run early; safe and idempotent at any point, finished or not.

        Stopping a run that already finished changes nothing: a ``FOUND`` or
        ``EXHAUSTED`` outcome is a fact about the scenario and is never overwritten.
        A stopped run keeps its statistics but has no result, because no path is
        known for it - see :meth:`result`.
        """
        if self._outcome is SearchOutcome.RUNNING:
            self._outcome = SearchOutcome.STOPPED

    def result(self) -> SearchResult:
        """Return the finished result, refusing to invent one.

        Raises ``RuntimeError`` while the run is live, and raises it for a stopped run
        as well: half a search knows no path, and reporting a failed result would
        claim that the scenario has no solution.
        """
        if self._outcome is SearchOutcome.STOPPED:
            raise RuntimeError("a stopped search has no result: no path is known")
        if self._result is None:
            raise RuntimeError("the search is still running")
        return self._result

    def run_to_completion(self) -> SearchResult:
        """Expand until the run finishes and return its result.

        Idempotent for a finished run - calling it again returns the same result -
        and raising ``RuntimeError`` for a stopped one, which never reaches a result.
        """
        while self._outcome is SearchOutcome.RUNNING:
            self.step()
        return self.result()

    def _expand(self, state: SearchState, cost: int) -> tuple[SearchState, ...]:
        """Push every walkable neighbour of ``state`` that the run can still use.

        Returns the states that were discovered for the first time, in insertion
        order. A neighbour whose cost is already known and no worse is dropped; a
        neighbour whose cost is improved is pushed again and leaves its parent
        pointing at ``state``, which keeps every parent edge worth exactly one move
        and therefore keeps a rebuilt path a real walk of the reported length.
        """
        scenario = self._scenario
        foods = self._foods
        heuristic = self._heuristic
        discovered: list[SearchState] = []
        for neighbor in self._grid.neighbors(state.position):
            if not self._grid.is_walkable(neighbor):
                continue
            collected = state.collected | {neighbor} if neighbor in foods else state.collected
            successor = SearchState(neighbor, collected)
            known = self._best_cost.get(successor)
            if known is not None and known <= cost + 1:
                continue
            # The cost and the parent are written together and unconditionally, and
            # that is what keeps a rebuilt path honest. Every parent edge was a real
            # move out of an expansion at the cost the child was recorded with, so for
            # every state X with parent P ``_best_cost[X] >= _best_cost[P] + 1``, and
            # when the run stops on a terminal state its chain back to the start is
            # the walk whose length ``SearchResult.cost`` reports. Writing the parent
            # only on first discovery instead leaves an improved state pointing at the
            # stale, longer route that first reached it - the rebuilt walk can then come
            # out longer than the optimal cost - and splitting the two writes breaks
            # the pairing at its root.
            self._best_cost[successor] = cost + 1
            self._parents[successor] = state
            sequence = self._sequence
            self._sequence += 1
            heappush(
                self._frontier,
                (cost + 1 + heuristic(scenario, successor), sequence, cost + 1, successor),
            )
            self._peak = max(self._peak, len(self._frontier))
            if known is None:
                self._discovered += 1
                discovered.append(successor)
        return tuple(discovered)


def _rebuild_path(
    parents: dict[SearchState, SearchState | None], goal_state: SearchState
) -> tuple[Position, ...]:
    """Walk the parent pointers from the terminal state back to the start."""
    path: list[Position] = []
    current: SearchState | None = goal_state
    while current is not None:
        path.append(current.position)
        current = parents[current]
    path.reverse()
    return tuple(path)
