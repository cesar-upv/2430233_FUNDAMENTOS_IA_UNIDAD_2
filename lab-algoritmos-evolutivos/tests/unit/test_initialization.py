import random
from dataclasses import replace
from random import Random

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Interval,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.evolution.encoding.binary import (
    BinaryEncoding,
    genotype_to_integer,
)
from evolutionary_lab.evolution.initialization import initialize_population
from evolutionary_lab.problems.registry import PROJECT_01_F1


@pytest.fixture
def config() -> ExperimentConfig:
    return ExperimentConfig(
        problem_id=PROJECT_01_F1.identifier,
        domains=PROJECT_01_F1.domains,
        precision=(0.001,),
        population_size=10,
        generation_limit=0,
        seed=42,
    )


def test_initialization_reproduces_seeded_population_without_global_randomness(
    config: ExperimentConfig,
) -> None:
    global_state = random.getstate()
    first = initialize_population(config, PROJECT_01_F1, Random(config.seed))
    second = initialize_population(replace(config), PROJECT_01_F1, Random(config.seed))
    assert first == second
    assert random.getstate() == global_state


def test_initial_population_integrates_domain_models_and_binary_decoding(
    config: ExperimentConfig,
) -> None:
    population = initialize_population(config, PROJECT_01_F1, Random(config.seed))
    encoding = BinaryEncoding(config.domains[0], 10)
    assert (
        len(population) == config.population_size and population.generation_index == 0
    )
    assert [individual.identifier for individual in population] == list(range(10))
    for individual in population:
        assert isinstance(individual.genotype, BinaryGenotype)
        assert len(individual.genotype.bits) == 10
        assert individual.phenotype == (encoding.decode(individual.genotype),)
        assert config.domains[0].contains(individual.phenotype[0])
        assert (
            individual.objective_value is None and individual.selection_fitness is None
        )


def test_repeated_genotypes_are_kept_at_the_configured_population_size(
    config: ExperimentConfig,
) -> None:
    coarse = replace(config, precision=(1.0,), population_size=8)
    population = initialize_population(coarse, PROJECT_01_F1, Random(coarse.seed))
    assert len(population) == 8
    assert len({individual.genotype for individual in population}) <= 2
    assert len({individual.identifier for individual in population}) == 8


def test_supplied_rng_state_is_consumed_without_reseeding(
    config: ExperimentConfig,
) -> None:
    rng = Random(config.seed)
    control = Random(config.seed)
    rng.getrandbits(10)
    control.getrandbits(10)
    expected_first = control.getrandbits(10)
    previous_state = rng.getstate()
    population = initialize_population(config, PROJECT_01_F1, rng)
    genotype = population.individuals[0].genotype
    assert isinstance(genotype, BinaryGenotype)
    assert genotype_to_integer(genotype) == expected_first
    assert rng.getstate() != previous_state


def test_invalid_initialization_does_not_consume_rng(config: ExperimentConfig) -> None:
    for invalid in (
        replace(config, representation=Representation.REAL, precision=()),
        replace(config, domains=(Interval(-1, 1),)),
        replace(config, precision=(1e-300,)),
    ):
        rng = Random(config.seed)
        state = rng.getstate()
        with pytest.raises(ValueError):
            initialize_population(invalid, PROJECT_01_F1, rng)
        assert rng.getstate() == state


def test_multivariable_initialization_decodes_each_variable(
    config: ExperimentConfig,
) -> None:
    domains = (Interval(0, 1), Interval(0, 1))
    problem = OptimizationProblem(
        identifier="test.sum",
        title="Test objective",
        formula="x + y",
        domains=domains,
        direction=OptimizationDirection.MAXIMIZE,
        objective=lambda point: sum(point),
        supported_representations=(Representation.BINARY,),
    )
    multiple = replace(
        config, problem_id=problem.identifier, domains=domains, precision=(0.1, 0.1)
    )
    population = initialize_population(multiple, problem, Random(multiple.seed))
    assert len(population) == multiple.population_size
    for individual in population:
        assert len(individual.phenotype) == 2
        assert individual.genotype.variable_lengths == (4, 4)
        assert all(0 <= value <= 1 for value in individual.phenotype)
