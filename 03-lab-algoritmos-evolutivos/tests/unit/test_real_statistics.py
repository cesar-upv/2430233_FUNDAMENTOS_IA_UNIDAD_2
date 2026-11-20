from itertools import combinations
from statistics import mean

import pytest

from evolutionary_lab.domain.models import (
    Individual,
    Interval,
    OptimizationDirection,
    Population,
    RealGenotype,
)
from evolutionary_lab.evolution.statistics import (
    calculate_population_statistics,
    mean_normalized_real_distance,
)


def population(vectors: tuple[tuple[float, ...], ...]) -> Population:
    return Population(
        tuple(
            Individual(i, RealGenotype(values), values, objective_value=sum(values))
            for i, values in enumerate(vectors)
        )
    )


@pytest.mark.parametrize(
    "vectors, expected",
    [
        (((0.5,),), 0),
        (((0.5,), (0.5,), (0.5,)), 0),
        (((0,), (1,)), 1),
        (((0,), (0.5,), (1,)), 2 / 3),
    ],
)
def test_real_diversity_is_distinct_from_hamming(vectors, expected) -> None:
    stats = calculate_population_statistics(
        population(vectors), OptimizationDirection.MAXIMIZE, (Interval(0, 1),)
    )
    assert stats.mean_normalized_hamming_distance is None
    assert stats.mean_normalized_real_distance == pytest.approx(expected)
    assert stats.normalized_diversity == stats.mean_normalized_real_distance


def test_real_diversity_matches_pairwise_definition_with_independent_domains() -> None:
    domains = (Interval(-1, 1), Interval(100, 200))
    vectors = ((-1, 100), (0, 120), (1, 150), (0, 120))
    expected = mean(
        mean(
            abs(x - y) / (d.upper - d.lower)
            for x, y, d in zip(a, b, domains, strict=True)
        )
        for a, b in combinations(vectors, 2)
    )
    assert mean_normalized_real_distance(population(vectors), domains) == pytest.approx(
        expected
    )
    with pytest.raises(ValueError, match="outside"):
        mean_normalized_real_distance(population(vectors), (Interval(0, 1), domains[1]))
