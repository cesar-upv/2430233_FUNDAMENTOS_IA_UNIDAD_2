from math import fsum
from statistics import mean

from evolutionary_lab.domain.evaluation import PopulationStatistics
from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Interval,
    OptimizationDirection,
    Population,
)
from evolutionary_lab.evolution.encoding.real import validate_real_genotype


def hamming_distance(first: BinaryGenotype, second: BinaryGenotype) -> int:
    if not isinstance(first, BinaryGenotype) or not isinstance(second, BinaryGenotype):
        raise ValueError("Hamming distance requires binary genotypes")
    if first.variable_lengths != second.variable_lengths:
        raise ValueError("Hamming distance requires equal chromosome lengths")
    return sum(a != b for a, b in zip(first.bits, second.bits, strict=True))


def mean_normalized_hamming_distance(population: Population) -> float:
    """Average over unordered distinct pairs; a singleton has zero diversity."""
    first = population.individuals[0].genotype
    if not isinstance(first, BinaryGenotype):
        raise ValueError("Hamming diversity requires binary genotypes")
    length = len(first.bits)
    ones = [0] * length
    for individual in population:
        genotype = individual.genotype
        if not isinstance(genotype, BinaryGenotype):
            raise ValueError("Hamming diversity requires binary genotypes")
        for position, bit in enumerate(genotype.bits):
            ones[position] += bit
    size = len(population)
    if size == 1:
        return 0.0
    # Each locus contributes k*(N-k) differing pairs, without enumerating N² pairs.
    differences = sum(count * (size - count) for count in ones)
    pairs = size * (size - 1) // 2
    return differences / (pairs * length)


def mean_normalized_real_distance(
    population: Population, domains: tuple[Interval, ...]
) -> float:
    """Mean pairwise L1 distance normalized by domains; O(D N log N)."""
    vectors = [
        validate_real_genotype(item.genotype, domains).values for item in population
    ]
    size = len(vectors)
    if size == 1:
        return 0.0
    distances = []
    for coordinate, domain in enumerate(domains):
        values = sorted(
            (v[coordinate] - domain.lower) / (domain.upper - domain.lower)
            for v in vectors
        )
        # Each adjacent gap occurs in (i+1)*(N-i-1) unordered pair distances.
        distances.append(
            fsum(
                (values[i + 1] - values[i]) * (i + 1) * (size - i - 1)
                for i in range(size - 1)
            )
        )
    pairs = size * (size - 1) // 2
    return min(1.0, max(0.0, fsum(distances) / (len(domains) * pairs)))


def calculate_population_statistics(
    population: Population,
    direction: OptimizationDirection,
    domains: tuple[Interval, ...] | None = None,
) -> PopulationStatistics:
    """Rank raw objectives by direction, retaining the first individual on ties."""
    if not isinstance(direction, OptimizationDirection):
        raise ValueError("Unsupported optimization direction")
    objectives: list[float] = []
    fitness: list[float] = []
    for individual in population:
        if individual.objective_value is None:
            raise ValueError("Statistics require every individual to be evaluated")
        objectives.append(individual.objective_value)
        if individual.selection_fitness is not None:
            fitness.append(individual.selection_fitness)
    if fitness and len(fitness) != len(population):
        raise ValueError(
            "Selection fitness must be available for all or no individuals"
        )

    minimum_index = min(range(len(population)), key=objectives.__getitem__)
    maximum_index = max(range(len(population)), key=objectives.__getitem__)
    best_index, worst_index = (
        (maximum_index, minimum_index)
        if direction == OptimizationDirection.MAXIMIZE
        else (minimum_index, maximum_index)
    )
    diversity = (
        mean_normalized_hamming_distance(population)
        if isinstance(population.individuals[0].genotype, BinaryGenotype)
        else None
    )
    return PopulationStatistics(
        population_size=len(population),
        generation_index=population.generation_index,
        direction=direction,
        best_individual=population.individuals[best_index],
        worst_individual=population.individuals[worst_index],
        objective_min=objectives[minimum_index],
        objective_max=objectives[maximum_index],
        # The standard-library mean avoids overflow of intermediate finite sums.
        objective_mean=mean(objectives),
        selection_fitness_min=min(fitness) if fitness else None,
        selection_fitness_max=max(fitness) if fitness else None,
        selection_fitness_mean=mean(fitness) if fitness else None,
        mean_normalized_hamming_distance=diversity,
        mean_normalized_real_distance=(
            mean_normalized_real_distance(population, domains)
            if diversity is None and domains is not None
            else None
        ),
    )
