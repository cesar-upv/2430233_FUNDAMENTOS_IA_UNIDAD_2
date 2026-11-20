from dataclasses import replace
from math import isfinite

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import FitnessPolicy
from evolutionary_lab.domain.models import BinaryGenotype, Individual, Population
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod, ZeroWeightPolicy
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.evolution.evaluation import revise_minimization_fitness
from evolutionary_lab.problems.registry import (
    PROJECT_01_MIN1,
    PROJECT_01_MIN2,
    PROJECT_01_MIN3,
)


def population(values: tuple[float, ...]) -> Population:
    return Population(
        tuple(
            Individual(i, BinaryGenotype((0,)), (0,), v) for i, v in enumerate(values)
        )
    )


@pytest.mark.parametrize(
    "policy, objectives, expected",
    [
        (FitnessPolicy.MINIMIZATION_BOOK, (1.0, 2.0, 3.0), (2.15, 1.15, 0.15)),
        (FitnessPolicy.MINIMIZATION_SIGNED, (-5.0, -4.0, -2.0), (3.1, 2.1, 0.1)),
        (FitnessPolicy.MINIMIZATION_SIGNED, (-2.0, 0.0, 3.0), (5.15, 3.15, 0.15)),
        (FitnessPolicy.MINIMIZATION_SIGNED, (-2.0, -2.0), (0.1, 0.1)),
        (FitnessPolicy.MINIMIZATION_BOOK, (0.0, 0.0), (0.0, 0.0)),
    ],
)
def test_explicit_population_weights(policy, objectives, expected) -> None:
    original = population(objectives)
    revised = revise_minimization_fitness(original, policy)
    assert tuple(i.selection_fitness for i in revised) == pytest.approx(expected)
    assert tuple(i.objective_value for i in revised) == objectives
    assert all(i.selection_fitness is None for i in original)


def test_literal_book_policy_rejects_negative_maximum_and_nonfinite_offsets() -> None:
    with pytest.raises(ValueError, match="nonnegative cmax"):
        revise_minimization_fitness(
            population((-5.0, -2.0)), FitnessPolicy.MINIMIZATION_BOOK
        )
    with pytest.raises(ValueError, match="finite"):
        revise_minimization_fitness(
            population((1.79e308,)), FitnessPolicy.MINIMIZATION_BOOK
        )


@pytest.mark.parametrize("selection", list(SelectionMethod))
@pytest.mark.parametrize("replacement", list(ReplacementStrategy))
def test_negative_minimization_runs_reproducibly_with_all_operators(
    selection, replacement
) -> None:
    problem = PROJECT_01_MIN2
    config = ExperimentConfig(
        problem.identifier,
        problem.domains,
        (0.01,),
        10,
        30,
        42,
        direction=problem.direction,
        fitness_policy=FitnessPolicy.MINIMIZATION_SIGNED,
        selection_method=selection,
        replacement_strategy=replacement,
    )
    first = run_evolution(config, problem)
    assert first == run_evolution(config, problem)
    best = float("inf")
    for snapshot in first.generations:
        assert len(snapshot.population) == 10
        assert (
            snapshot.statistics.best_individual.objective_value
            == snapshot.statistics.objective_min
        )
        cmax = snapshot.statistics.objective_max
        offset = cmax + 0.05 * abs(cmax)
        for individual in snapshot.population:
            assert individual.objective_value == problem.evaluate(individual.phenotype)
            assert individual.selection_fitness == pytest.approx(
                offset - individual.objective_value
            )
            assert (
                isfinite(individual.selection_fitness)
                and individual.selection_fitness >= 0
            )
        assert snapshot.best_so_far.objective_value <= best
        best = snapshot.best_so_far.objective_value
        if (
            snapshot.trace is not None
            and replacement == ReplacementStrategy.CLASSROOM_CONDITIONAL
        ):
            for parent, child, accepted in zip(
                snapshot.trace.selection.selected,
                snapshot.trace.evaluated_offspring,
                snapshot.trace.replacement.accepted,
                strict=True,
            ):
                assert accepted == (child.objective_value < parent.objective_value)


def test_zero_weight_population_keeps_explicit_selection_policy() -> None:
    problem = replace(PROJECT_01_MIN1, objective=lambda point: 0.0)
    config = ExperimentConfig(
        problem.identifier,
        problem.domains,
        (0.001,),
        10,
        1,
        42,
        direction=problem.direction,
        fitness_policy=FitnessPolicy.MINIMIZATION_BOOK,
    )
    with pytest.raises(ValueError, match="zero total"):
        run_evolution(config, problem)
    assert (
        len(
            run_evolution(
                replace(config, zero_weight_policy=ZeroWeightPolicy.UNIFORM), problem
            ).generations
        )
        == 2
    )


@pytest.mark.parametrize("problem", [PROJECT_01_MIN1, PROJECT_01_MIN2, PROJECT_01_MIN3])
def test_verified_univariate_minima_match_printed_approximations(problem) -> None:
    optimum = problem.reference_optimum
    assert abs(problem.evaluate(optimum.phenotype) - optimum.objective_value) < 0.001
