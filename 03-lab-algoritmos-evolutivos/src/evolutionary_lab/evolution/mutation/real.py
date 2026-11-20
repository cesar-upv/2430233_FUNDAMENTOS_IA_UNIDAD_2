from random import Random

from evolutionary_lab.domain.models import Genotype, Interval, RealGenotype
from evolutionary_lab.domain.validation import probability
from evolutionary_lab.domain.variation import RealMutationResult
from evolutionary_lab.evolution.encoding.real import (
    uniform_real_value,
    validate_real_genotype,
)


def uniform_reset_mutation(
    genotype: Genotype,
    domains: tuple[Interval, ...],
    rng: Random,
    *,
    mutation_probability: float,
) -> RealMutationResult:
    original = validate_real_genotype(genotype, domains)
    rate = probability(mutation_probability, "per-gene mutation probability")
    draws = tuple(rng.random() for _ in original.values)
    positions = tuple(i for i, draw in enumerate(draws) if draw < rate)
    values = list(original.values)
    replacements: list[float | None] = [None] * len(values)
    for position in positions:
        values[position], replacements[position] = uniform_real_value(
            domains[position], rng
        )
    mutated = RealGenotype(tuple(values))
    return RealMutationResult(original, mutated, draws, positions, tuple(replacements))
