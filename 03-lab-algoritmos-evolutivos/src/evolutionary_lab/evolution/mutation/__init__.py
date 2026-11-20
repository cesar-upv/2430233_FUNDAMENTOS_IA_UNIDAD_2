from random import Random

from evolutionary_lab.domain.models import BinaryGenotype, Genotype
from evolutionary_lab.domain.validation import probability
from evolutionary_lab.domain.variation import MutationResult


def bit_flip_mutation(
    genotype: Genotype,
    rng: Random,
    *,
    mutation_probability: float,
) -> MutationResult:
    if not isinstance(genotype, BinaryGenotype):
        raise ValueError("Bit-flip mutation requires a binary genotype")
    rate = probability(mutation_probability, "per-bit mutation probability")
    draws = tuple(rng.random() for _ in genotype.bits)
    positions = tuple(index for index, draw in enumerate(draws) if draw < rate)
    mutated = BinaryGenotype(
        tuple(
            bit ^ int(draw < rate)
            for bit, draw in zip(genotype.bits, draws, strict=True)
        ),
        genotype.variable_lengths,
    )
    return MutationResult(genotype, mutated, draws, positions)
