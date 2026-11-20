from dataclasses import replace
from random import Random

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Interval,
    RealGenotype,
    Representation,
)
from evolutionary_lab.domain.variation import MutationMethod, RealBoundsPolicy
from evolutionary_lab.evolution.encoding.real import bound_real_values
from evolutionary_lab.evolution.initialization import initialize_population
from evolutionary_lab.evolution.mutation.real import uniform_reset_mutation
from evolutionary_lab.problems.registry import PROJECT_01_F1


class Draws(Random):
    def __init__(self, values: tuple[float, ...]) -> None:
        self.draws = iter(values)

    def random(self) -> float:
        return next(self.draws)


def test_real_initialization_preserves_each_domain_and_seed_without_quantization() -> (
    None
):
    domains = (Interval(-2, 3), Interval(10, 20))
    problem = replace(
        PROJECT_01_F1,
        domains=domains,
        supported_representations=(Representation.REAL,),
        reference_optimum=None,
        objective=lambda point: sum(x * x for x in point),
    )
    config = ExperimentConfig(
        problem.identifier,
        domains,
        (),
        10,
        0,
        42,
        representation=Representation.REAL,
        mutation_method=MutationMethod.UNIFORM_RESET,
    )
    population = initialize_population(config, problem, Random(42))
    assert population == initialize_population(config, problem, Random(42))
    control = Random(42)
    for member in population:
        assert isinstance(member.genotype, RealGenotype)
        assert member.genotype.values == member.phenotype
        assert member.phenotype == tuple(
            control.uniform(d.lower, d.upper) for d in domains
        )
        assert member.objective_value is None and member.selection_fitness is None
    with pytest.raises(ValueError, match="discretization"):
        replace(config, precision=(0.001, 0.001))
    with pytest.raises(ValueError, match="Mutation method"):
        replace(config, mutation_method=MutationMethod.BIT_FLIP).validate_for(problem)


def test_uniform_reset_uses_independent_gene_probability_and_records_draws() -> None:
    original = RealGenotype((0.75, 12.0, 0.3))
    domains = (Interval(-1, 1), Interval(10, 20), Interval(0, 1))
    result = uniform_reset_mutation(
        original, domains, Draws((0.0, 0.5, 0.9, 0.25)), mutation_probability=0.5
    )
    assert result.genotype.values == (-0.5, 12.0, 0.3)
    assert result.random_values == (0.0, 0.5, 0.9)
    assert result.replacement_draws == (0.25, None, None)
    assert result.mutated_positions == (0,)
    assert original.values == (0.75, 12.0, 0.3)


@pytest.mark.parametrize("rate", [0.0, 1.0])
def test_reset_probability_extremes_and_determinism(rate: float) -> None:
    original = RealGenotype((0.0, 15.0))
    domains = (Interval(-1, 1), Interval(10, 20))
    first = uniform_reset_mutation(
        original, domains, Random(42), mutation_probability=rate
    )
    assert first == uniform_reset_mutation(
        original, domains, Random(42), mutation_probability=rate
    )
    assert len(first.genotype.values) == 2
    assert first.mutated_positions == (() if rate == 0 else (0, 1))
    assert all(
        d.contains(v) for d, v in zip(domains, first.genotype.values, strict=True)
    )
    if rate == 0:
        assert first.genotype == original


@pytest.mark.parametrize(
    "genotype, domains",
    [
        (BinaryGenotype((0,)), (Interval(0, 1),)),
        (RealGenotype((2.0,)), (Interval(0, 1),)),
        (RealGenotype((0.5,)), (Interval(0, 1), Interval(0, 1))),
    ],
)
def test_invalid_real_mutation_fails_before_consuming_randomness(
    genotype, domains
) -> None:
    rng = Random(42)
    state = rng.getstate()
    with pytest.raises(ValueError):
        uniform_reset_mutation(genotype, domains, rng, mutation_probability=0.5)
    assert rng.getstate() == state


def test_bounds_policies_are_explicit_and_never_accept_nonfinite_values() -> None:
    domains = (Interval(-1, 1), Interval(10, 20))
    with pytest.raises(ValueError, match="outside"):
        bound_real_values((-2.0, 21.0), domains, RealBoundsPolicy.REJECT)
    clipped, positions = bound_real_values((-2.0, 21.0), domains, RealBoundsPolicy.CLIP)
    assert clipped.values == (-1.0, 20.0) and positions == (0, 1)
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            bound_real_values((value, 15.0), domains, RealBoundsPolicy.CLIP)
