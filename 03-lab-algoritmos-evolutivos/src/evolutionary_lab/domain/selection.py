from dataclasses import dataclass
from enum import StrEnum
from random import Random
from typing import Protocol

from evolutionary_lab.domain.models import Individual, Population


class SelectionMethod(StrEnum):
    ROULETTE = "roulette"
    SUS = "sus"
    BINARY_TOURNAMENT = "binary_tournament"


class ZeroWeightPolicy(StrEnum):
    ERROR = "error"
    UNIFORM = "uniform"


class TournamentTiePolicy(StrEnum):
    RANDOM = "random"
    FIRST = "first"


@dataclass(frozen=True)
class SelectionDistribution:
    probabilities: tuple[float, ...]
    cumulative: tuple[float, ...]
    zero_weight_policy: ZeroWeightPolicy
    used_uniform_fallback: bool


@dataclass(frozen=True)
class TournamentDraw:
    participants: tuple[int, int]
    winner_index: int
    tie_draw: float | None


@dataclass(frozen=True)
class SelectionResult:
    method: SelectionMethod
    selected: tuple[Individual, ...]
    indices: tuple[int, ...]
    distribution: SelectionDistribution | None = None
    random_values: tuple[float, ...] = ()
    positions: tuple[float, ...] = ()
    tournaments: tuple[TournamentDraw, ...] = ()


class SelectionOperator(Protocol):
    def __call__(
        self, population: Population, count: int, rng: Random, /
    ) -> SelectionResult: ...
