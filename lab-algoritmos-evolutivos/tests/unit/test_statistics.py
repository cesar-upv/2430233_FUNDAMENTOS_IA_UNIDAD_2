from dataclasses import FrozenInstanceError

import pytest

from evolutionary_lab.domain.models import (
    Individual,
    OptimizationDirection,
    Population,
    RealGenotype,
)
from evolutionary_lab.evolution.encoding.binary import genotype_from_string
from evolutionary_lab.evolution.statistics import (
    calculate_population_statistics,
    hamming_distance,
    mean_normalized_hamming_distance,
)


def _population(
    objectives: tuple[float | None, ...],
    fitness: tuple[float | None, ...],
    genotypes: tuple[str, ...] | None = None,
) -> Population:
    if genotypes is None:
        genotypes = ("00",) * len(objectives)
    return Population(
        tuple(
            Individual(index, genotype_from_string(bits), (0.0,), objective, weight)
            for index, (objective, weight, bits) in enumerate(
                zip(objectives, fitness, genotypes, strict=True)
            )
        ),
        generation_index=7,
    )


def test_statistics_keep_objective_ranking_separate_from_selection_fitness() -> None:
    population = _population((2.0, -1.0, 2.0), (5.0, 8.0, 5.0), ("00", "01", "11"))
    stats = calculate_population_statistics(population, OptimizationDirection.MAXIMIZE)
    assert stats.population_size == 3 and stats.generation_index == 7
    assert stats.direction == OptimizationDirection.MAXIMIZE
    assert stats.best_individual is population.individuals[0]
    assert stats.worst_individual is population.individuals[1]
    assert (stats.objective_min, stats.objective_max, stats.objective_mean) == (
        -1.0,
        2.0,
        1.0,
    )
    assert stats.selection_fitness_min == 5.0
    assert stats.selection_fitness_max == 8.0
    assert stats.selection_fitness_mean == 6.0
    assert stats.mean_normalized_hamming_distance == pytest.approx(2 / 3)
    with pytest.raises(FrozenInstanceError):
        stats.objective_mean = 0.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        stats.best_individual.objective_value = 0.0  # type: ignore[misc]


def test_tied_objectives_and_fitness_keep_first_individual_without_deduplication() -> (
    None
):
    population = _population((3.0, 3.0, 3.0), (3.0, 3.0, 3.0))
    stats = calculate_population_statistics(population, OptimizationDirection.MAXIMIZE)
    assert stats.population_size == 3
    assert stats.best_individual is stats.worst_individual is population.individuals[0]
    assert stats.objective_mean == stats.selection_fitness_mean == 3.0
    assert stats.mean_normalized_hamming_distance == 0.0


def test_singleton_statistics_and_diversity_are_defined() -> None:
    population = _population((-4.0,), (None,))
    stats = calculate_population_statistics(population, OptimizationDirection.MAXIMIZE)
    assert stats.best_individual is stats.worst_individual is population.individuals[0]
    assert stats.objective_min == stats.objective_max == stats.objective_mean == -4.0
    assert stats.selection_fitness_min is None
    assert stats.selection_fitness_max is None
    assert stats.selection_fitness_mean is None
    assert stats.mean_normalized_hamming_distance == 0.0


def test_negative_objectives_are_ranked_without_modification() -> None:
    population = _population((-4.0, -2.0, -3.0), (None, None, None))
    maximum = calculate_population_statistics(
        population, OptimizationDirection.MAXIMIZE
    )
    minimum = calculate_population_statistics(
        population, OptimizationDirection.MINIMIZE
    )
    assert (
        maximum.best_individual is minimum.worst_individual is population.individuals[1]
    )
    assert (
        maximum.worst_individual is minimum.best_individual is population.individuals[0]
    )
    assert maximum.objective_mean == minimum.objective_mean == -3.0
    assert maximum.selection_fitness_mean is minimum.selection_fitness_mean is None


@pytest.mark.parametrize("objectives", [(None, None), (1.0, None)])
def test_statistics_reject_incomplete_objective_evaluation(
    objectives: tuple[float | None, ...],
) -> None:
    with pytest.raises(ValueError, match="evaluated"):
        calculate_population_statistics(
            _population(objectives, (None, None)), OptimizationDirection.MAXIMIZE
        )


def test_statistics_reject_partial_fitness() -> None:
    with pytest.raises(ValueError, match="all or no individuals"):
        calculate_population_statistics(
            _population((1.0, 2.0), (1.0, None)), OptimizationDirection.MAXIMIZE
        )


def test_statistics_reject_unknown_direction() -> None:
    with pytest.raises(ValueError, match="direction"):
        calculate_population_statistics(
            _population((1.0,), (1.0,)),
            "unsupported",  # type: ignore[arg-type]
        )


def test_means_stay_finite_when_the_intermediate_sum_would_overflow() -> None:
    positive = _population((1e308, 1e308), (1e308, 1e308))
    stats = calculate_population_statistics(positive, OptimizationDirection.MAXIMIZE)
    assert stats.objective_mean == stats.selection_fitness_mean == 1e308
    signed = _population((1e308, 1e308, -1e308), (None, None, None))
    assert calculate_population_statistics(
        signed, OptimizationDirection.MAXIMIZE
    ).objective_mean == pytest.approx(1e308 / 3)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [("000", "000", 0), ("000", "111", 3), ("1010", "1001", 2)],
)
def test_hamming_distance(first: str, second: str, expected: int) -> None:
    a, b = genotype_from_string(first), genotype_from_string(second)
    assert hamming_distance(a, b) == hamming_distance(b, a) == expected


def test_hamming_distance_rejects_different_chromosome_lengths() -> None:
    with pytest.raises(ValueError, match="equal chromosome lengths"):
        hamming_distance(genotype_from_string("0"), genotype_from_string("00"))


@pytest.mark.parametrize(
    ("genes", "expected"),
    [
        (("00",), 0.0),
        (("00", "00", "00"), 0.0),
        (("0000", "1111"), 1.0),
        (("00", "01", "11"), 2 / 3),
        (("00", "00", "11"), 2 / 3),
        (("000", "001", "010", "100"), 0.5),
    ],
)
def test_mean_hamming_distance_uses_all_distinct_pairs_including_duplicate_genotypes(
    genes: tuple[str, ...], expected: float
) -> None:
    population = _population((None,) * len(genes), (None,) * len(genes), genes)
    assert mean_normalized_hamming_distance(population) == pytest.approx(expected)


def test_hamming_is_binary_only_and_real_statistics_do_not_invent_diversity() -> None:
    real = RealGenotype((0.5,))
    population = Population((Individual(0, real, (0.5,), objective_value=2.0),))
    with pytest.raises(ValueError, match="binary genotypes"):
        hamming_distance(real, real)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="binary genotypes"):
        mean_normalized_hamming_distance(population)
    stats = calculate_population_statistics(population, OptimizationDirection.MAXIMIZE)
    assert stats.objective_mean == 2.0
    assert stats.mean_normalized_hamming_distance is None
