from dataclasses import replace
from math import inf, nan
from random import Random

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import FitnessPolicy
from evolutionary_lab.domain.models import (
    Individual,
    OptimizationDirection,
    Population,
    RealGenotype,
    Representation,
)
from evolutionary_lab.evolution.encoding.binary import (
    BinaryEncoding,
    genotype_from_integer,
)
from evolutionary_lab.evolution.evaluation import (
    evaluate_individual,
    evaluate_population,
)
from evolutionary_lab.evolution.initialization import initialize_population
from evolutionary_lab.evolution.statistics import calculate_population_statistics
from evolutionary_lab.problems.registry import get_problem


def _population(*integers: int) -> Population:
    encoding = BinaryEncoding(get_problem("project_01.f1").domains[0], 10)
    return Population(
        tuple(
            Individual(
                identifier=index,
                genotype=genotype_from_integer(value, 10),
                phenotype=(encoding.decode_integer(value),),
            )
            for index, value in enumerate(integers)
        ),
        generation_index=4,
    )


def test_population_evaluation_preserves_decoding_order_and_repeated_genotypes() -> (
    None
):
    problem = get_problem("project_01.f1")
    original = _population(0, 102, 103, 1023, 102)
    evaluated = evaluate_population(original, problem)
    assert evaluated is not original
    assert evaluated.generation_index == original.generation_index
    assert len(evaluated) == len(original)
    for before, after in zip(original, evaluated, strict=True):
        assert (after.identifier, after.genotype, after.phenotype) == (
            before.identifier,
            before.genotype,
            before.phenotype,
        )
        assert before.objective_value is None and before.selection_fitness is None
        assert after.objective_value == problem.evaluate(before.phenotype)
        assert after.selection_fitness == after.objective_value
    stats = calculate_population_statistics(evaluated, problem.direction)
    assert stats.best_individual == evaluated.individuals[1]
    assert stats.worst_individual == evaluated.individuals[0]
    assert stats.best_individual.phenotype == (102 / 1023,)
    assert stats.objective_max < 1.0
    assert problem.reference_optimum is not None
    assert problem.reference_optimum.objective_value == 1.0
    assert stats.best_individual.phenotype != problem.reference_optimum.phenotype


def test_re_evaluation_replaces_stale_objective_and_fitness() -> None:
    problem = get_problem("project_01.f1")
    original = replace(
        _population(102).individuals[0], objective_value=9.0, selection_fitness=7.0
    )
    evaluated = evaluate_individual(original, problem)
    assert evaluated.objective_value == problem.evaluate(original.phenotype)
    assert evaluated.selection_fitness == evaluated.objective_value
    assert original.objective_value == 9.0 and original.selection_fitness == 7.0
    objective_only = evaluate_individual(
        evaluated, problem, fitness_policy=FitnessPolicy.OBJECTIVE_ONLY
    )
    assert objective_only.objective_value == evaluated.objective_value
    assert objective_only.selection_fitness is None


def test_negative_objective_is_preserved_without_implicit_weight_transform() -> None:
    problem = replace(get_problem("project_01.f1"), objective=lambda point: -2.0)
    original = _population(102)
    with pytest.raises(ValueError, match="nonnegative objective"):
        evaluate_population(original, problem)
    evaluated = evaluate_population(
        original, problem, fitness_policy=FitnessPolicy.OBJECTIVE_ONLY
    )
    assert evaluated.individuals[0].objective_value == -2.0
    assert evaluated.individuals[0].selection_fitness is None
    assert original.individuals[0].objective_value is None


def test_minimization_requires_objective_only_policy() -> None:
    problem = replace(
        get_problem("project_01.f1"),
        direction=OptimizationDirection.MINIMIZE,
        objective=lambda point: -point[0],
        reference_optimum=None,
    )
    with pytest.raises(ValueError, match="maximization"):
        evaluate_population(_population(0, 1023), problem)
    evaluated = evaluate_population(
        _population(0, 1023), problem, fitness_policy=FitnessPolicy.OBJECTIVE_ONLY
    )
    stats = calculate_population_statistics(evaluated, problem.direction)
    assert stats.best_individual == evaluated.individuals[1]
    assert stats.worst_individual == evaluated.individuals[0]
    assert stats.objective_mean == -0.5
    assert stats.selection_fitness_mean is None


def test_zero_fitness_population_needs_no_selection_fallback_during_evaluation() -> (
    None
):
    problem = get_problem("project_01.f1")
    evaluated = evaluate_population(_population(0, 0), problem)
    stats = calculate_population_statistics(evaluated, problem.direction)
    assert stats.selection_fitness_min == stats.selection_fitness_max == 0.0
    assert stats.selection_fitness_mean == 0.0
    assert stats.mean_normalized_hamming_distance == 0.0


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_nonfinite_evaluation_does_not_change_original_population(value: float) -> None:
    problem = replace(
        get_problem("project_01.f1"),
        objective=lambda point: 1.0 if point[0] == 0 else value,
    )
    original = _population(0, 102)
    with pytest.raises(ValueError, match="objective result"):
        evaluate_population(original, problem)
    assert all(item.objective_value is None for item in original)


@pytest.mark.parametrize("point", [(-0.1,), (1.1,), (0.1, 0.2)])
def test_evaluation_checks_problem_bounds_and_dimensions(
    point: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError):
        individual = replace(_population(102).individuals[0], phenotype=point)
        evaluate_individual(individual, get_problem("project_01.f1"))


def test_evaluation_checks_representation_compatibility() -> None:
    individual = Individual(0, RealGenotype((0.1,)), (0.1,))
    binary_only = replace(
        get_problem("project_01.f1"), supported_representations=(Representation.BINARY,)
    )
    with pytest.raises(ValueError, match="Representation"):
        evaluate_individual(individual, binary_only)


def test_unknown_fitness_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="fitness policy"):
        evaluate_individual(
            _population(102).individuals[0],
            get_problem("project_01.f1"),
            fitness_policy="unsupported",  # type: ignore[arg-type]
        )


def test_seeded_initialization_evaluation_and_statistics_are_reproducible() -> None:
    problem = get_problem("project_01.f1")
    config = ExperimentConfig(
        problem_id=problem.identifier,
        domains=problem.domains,
        precision=(0.001,),
        population_size=10,
        generation_limit=0,
        seed=42,
    )
    first = evaluate_population(
        initialize_population(config, problem, Random(config.seed)), problem
    )
    second = evaluate_population(
        initialize_population(config, problem, Random(config.seed)), problem
    )
    assert first == second
    assert calculate_population_statistics(
        first, problem.direction
    ) == calculate_population_statistics(second, problem.direction)
