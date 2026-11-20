from dataclasses import FrozenInstanceError, replace
from math import inf, nan
from typing import cast

import pytest

from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Individual,
    Interval,
    Population,
    RealGenotype,
)


def test_interval_includes_endpoints() -> None:
    domain = Interval(0, 1)
    assert domain.contains(0) and domain.contains(1)
    assert not domain.contains(-0.001) and not domain.contains(1.001)


@pytest.mark.parametrize(
    ("lower", "upper"), [(1, 1), (1, 0), (nan, 1), (0, inf), (-1e308, 1e308)]
)
def test_invalid_intervals_are_rejected(lower: float, upper: float) -> None:
    with pytest.raises(ValueError):
        Interval(lower, upper)


@pytest.mark.parametrize("bits", [(), (0, 2), (0, True)])
def test_binary_genotype_rejects_invalid_bits(bits: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        BinaryGenotype(bits)


def test_models_are_immutable_and_repeated_genotypes_are_valid() -> None:
    source = [0]
    genotype = BinaryGenotype(cast(tuple[int, ...], source))
    source[0] = 1
    assert genotype.bits == (0,)
    first = Individual(0, genotype, (0.0,), objective_value=0.0)
    second = replace(first, identifier=1)
    members = [first, second]
    population = Population(cast(tuple[Individual, ...], members))
    members.clear()
    assert tuple(population) == (first, second)
    assert len(population) == 2 and population.generation_index == 0
    with pytest.raises(FrozenInstanceError):
        first.identifier = 2


def test_objective_and_selection_fitness_remain_distinct() -> None:
    point = (0.2, 0.3)
    individual = Individual(0, RealGenotype(point), point, objective_value=-3)
    assert individual.selection_fitness is None
    weighted = replace(individual, selection_fitness=1.5)
    assert weighted.objective_value == -3 and weighted.selection_fitness == 1.5
    assert individual.selection_fitness is None


@pytest.mark.parametrize(
    ("objective", "fitness"), [(inf, None), (-1, nan), (-1, -0.01), (None, 1)]
)
def test_invalid_evaluation_states_are_rejected(
    objective: float | None, fitness: float | None
) -> None:
    with pytest.raises(ValueError):
        Individual(0, BinaryGenotype((0,)), (0.0,), objective, fitness)


def test_real_values_and_phenotype_dimensions_are_validated() -> None:
    for values in ((), (nan,), (inf,)):
        with pytest.raises(ValueError):
            RealGenotype(values)
    with pytest.raises(ValueError, match="dimensions"):
        Individual(0, RealGenotype((0.0, 1.0)), (0.0,))
    with pytest.raises(ValueError, match="phenotype"):
        Individual(0, BinaryGenotype((0,)), ())


def test_population_rejects_conflicting_identity_or_shape() -> None:
    first = Individual(0, BinaryGenotype((0,)), (0.0,))
    invalid_members = (
        (first, first),
        (first, Individual(1, RealGenotype((0.0,)), (0.0,))),
        (first, Individual(1, BinaryGenotype((0, 0)), (0.0,))),
    )
    for members in invalid_members:
        with pytest.raises(ValueError):
            Population(members)
    with pytest.raises(ValueError):
        Population(())
    with pytest.raises(ValueError):
        Population((first,), generation_index=-1)
