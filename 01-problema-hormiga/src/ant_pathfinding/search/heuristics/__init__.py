"""Estimates of the remaining cost, and the alias that makes them interchangeable.

A heuristic is a plain function of a problem instance and a search state returning
an estimated number of remaining moves. Keeping it a function - no class, no
protocol, no registry - is the whole composition mechanism: a caller hands one to
:meth:`ant_pathfinding.search.runner.SearchRunner.__init__` and the engine never
learns which estimate it was given. That is what lets breadth-first search, uniform
cost search and A* share one engine, and what lets the quality of an estimate be
tested without running a search at all.
"""

from __future__ import annotations

from collections.abc import Callable

from ant_pathfinding.domain.scenario import AntScenario
from ant_pathfinding.search.heuristics.lower_bounds import manhattan_mst, uniform_cost
from ant_pathfinding.search.state import SearchState

type Heuristic = Callable[[AntScenario, SearchState], int]

__all__ = ["Heuristic", "manhattan_mst", "uniform_cost"]
