from dataclasses import dataclass

from evolutionary_lab.domain.models import Population
from evolutionary_lab.domain.replacement import ReplacementResult
from evolutionary_lab.domain.selection import SelectionResult
from evolutionary_lab.domain.variation import (
    CrossoverResult,
    MutationResult,
    RealCrossoverResult,
    RealMutationResult,
    ReproductionPolicy,
)


@dataclass(frozen=True)
class PairCrossover:
    parent_slots: tuple[int, int]
    result: CrossoverResult | RealCrossoverResult


@dataclass(frozen=True)
class ReproductionTrace:
    policy: ReproductionPolicy
    candidate_draws: tuple[float, ...]
    candidate_slots: tuple[int, ...]
    dropped_slot: int | None
    common_cut: int | None
    pairs: tuple[PairCrossover, ...]
    common_cuts: tuple[int, ...] = ()


@dataclass(frozen=True)
class GenerationTrace:
    selection: SelectionResult
    reproduction: ReproductionTrace
    mutations: tuple[MutationResult | RealMutationResult, ...]
    evaluated_offspring: Population
    replacement: ReplacementResult
    replacement_before_mutation: bool
