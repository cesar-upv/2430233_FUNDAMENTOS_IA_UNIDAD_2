"""The observable progress contract of a search run.

A search is driven one expansion at a time and reports what it did as a stream of
:class:`SearchStep` values, each carrying a :class:`SearchStatistics` snapshot. A
consumer - a test, or later an animation - therefore never has to poll a counter or
ask a search object what it is doing: it iterates, it stops when it wants to stop,
and everything it needs to draw is already in the stream.

What the stream carries, and what it does not. It carries every expansion, every
first-time discovery, the four counters and the final outcome. It does not carry the
finished path, which arrives separately from
:meth:`~ant_pathfinding.search.runner.SearchRunner.result` once the outcome is
``FOUND``, and it does not carry the exact frontier of a reopening A* run: there
``discovered - expanded`` is contained in the frontier rather than equal to it, so the
frontier can only be bounded, never read off.

Nothing in this module knows how a run is implemented. It is a leaf of the search
layer: it imports only the state it reports on, and never the runner, so the progress
vocabulary stays readable on its own and the dependency direction stays
``runner -> progress -> state``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ant_pathfinding.search.state import SearchState


class SearchOutcome(StrEnum):
    """How far a run has come, and how it ended.

    ``RUNNING`` is the only value that means "call me again". The other three are
    final, and a run that reached one of them will never expand another state.
    """

    RUNNING = "running"
    """The run is live: there is either work left or nothing left to discover."""

    FOUND = "found"
    """A terminal state was expanded and the run stopped on the first such state."""

    EXHAUSTED = "exhausted"
    """The frontier ran empty, which proves that no solution exists."""

    STOPPED = "stopped"
    """A consumer called
    :meth:`~ant_pathfinding.search.runner.SearchRunner.stop` before the run finished."""


@dataclass(frozen=True, slots=True)
class SearchStatistics:
    """An immutable snapshot of a run's four counters at one observation point."""

    expanded_states: int
    """Number of states the run has expanded so far.

    A state counts as expanded when it was popped from the frontier *and not
    superseded* *and* processed - goal test included, successor generation
    excluded. The initial state counts, and on success the terminal state counts.
    A pop of an entry whose recorded cost has since been improved is not an
    expansion and is not counted here; it is discarded without producing a step.

    This is not the number of discovered states and it is not an ant-step count. For
    a uniform-cost search - every move costing 1, so the first discovery of a state is
    already the optimal one - a state is inserted once and expanded once, which gives
    the identity ``discovered_states == expanded_states + frontier_size`` at every
    observation point. A* re-inserts a state whose cost it improves, so there it
    holds only as ``discovered_states - expanded_states <= frontier_size``, with one
    extra frontier entry per improvement; and because the engine reopens such a state
    instead of closing it, a state may be expanded more than once, in which case this
    count exceeds the number of distinct expanded states.

    A failed run empties the frontier and so expands every discovered state. For a
    successful run the two counts are settled by how often a state was improved after
    discovery. When it never was - uniform cost, the case in which a state is inserted
    once and expanded once - the run stops as soon as the terminal goal state leaves
    the frontier and so expands exactly as many states as it discovered if it returns
    with an empty frontier, and strictly fewer otherwise; the two counts are equal
    precisely when the goal state was the last state inserted, as when the start is
    already the goal or the goal is the start's only walkable neighbour and there is
    no food to collect. That reading does not survive a state improved after
    discovery, even a state still waiting in the frontier, because the improvement
    adds a queued entry without adding a discovered state. Only
    ``expanded_states >= discovered_states - frontier_size`` is guaranteed in general,
    and a reopening search can be less tidy even than that: it can find the optimal
    path while reporting *more* expanded states than discovered ones, since every
    reopening is an expansion with no matching discovery.
    """

    discovered_states: int
    """Number of distinct states ever inserted into the frontier.

    Counting a state once per *insertion* would make the counter an artefact of the
    re-insertion strategy rather than of the problem, so a state improved and pushed
    again is still one discovered state. The start state is discovered at
    construction, so this is at least 1, and it is at least the number of *distinct*
    expanded states, because a state is expanded only after it was inserted - but not
    at least ``expanded_states`` itself, which a reopening search can exceed, one
    expansion per reopening and no matching discovery.
    """

    frontier_size: int
    """Number of entries currently queued, superseded entries included.

    "Entries" rather than "states": with A* an improved state can be queued twice.
    The identity with the counters above is therefore exact for uniform-cost search
    only, and the weaker form above holds in general.
    """

    frontier_peak_size: int
    """The largest number of frontier entries ever held simultaneously.

    Measured immediately after an insertion, so it is the high-water mark of the
    queue occupancy rather than of anything the search decided to count. It is at
    least 1 because the start state is queued before the first step.
    """


@dataclass(frozen=True, slots=True)
class SearchStep:
    """One expansion, reported as it happens.

    A consumer can derive everything a visualization needs from the step stream
    alone, with no further accessor on the run: ``discovered`` is the union of every
    ``step.discovered``, ``expanded`` is the set of every ``step.state``, and for a
    uniform-cost search ``frontier == discovered - expanded``. That last identity is
    exact for every state of a uniform-cost search, which never reopens one. Under A*,
    the direction that survives is ``discovered - expanded`` contained in the frontier
    - the count form of it being
    ``discovered_states - expanded_states <= frontier_size`` - and the reverse
    inclusion is the one that fails: a reopened state is already in ``expanded`` and is
    queued again for its better cost, so it contributes nothing to
    ``discovered - expanded`` while it still occupies the frontier. No consumer can
    therefore read the exact frontier of a reopening run out of this stream; the stream
    gives it the containment, and the counters above give it the bound.

    One exception to the derivation, and it is bookkeeping rather than behaviour: the
    start state is inserted before the first step and therefore appears in no step's
    ``discovered``, so the complete discovered set is that union plus the first step's
    ``state``. The frontier relation is unaffected - the start state is always the
    first state popped, so it is always expanded, and a state that is expanded
    contributes nothing to ``discovered - expanded``.

    ``discovered`` is annotated as a tuple of states, which is what typed callers
    pass. ``__post_init__`` additionally normalizes it through :func:`tuple`, mirroring
    :class:`ant_pathfinding.search.state.SearchState` and
    :class:`ant_pathfinding.search.result.SearchResult`, so a step assembled
    dynamically from untyped or deserialized input never aliases the object it was
    handed and the statistics stay exactly as measured.
    """

    state: SearchState
    """The state this expansion processed."""

    discovered: tuple[SearchState, ...]
    """States this expansion added to the frontier, in the order they were inserted.

    Empty when the expansion found nothing new, which is the normal case for a
    uniform-cost search late in a run. A state appears in exactly one step's
    ``discovered``: the step at which it was first inserted. The start state is the one
    exception, because it is inserted before the run is first stepped.
    """

    statistics: SearchStatistics
    """Counters taken *after* this expansion, insertions included."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "discovered", tuple(self.discovered))
