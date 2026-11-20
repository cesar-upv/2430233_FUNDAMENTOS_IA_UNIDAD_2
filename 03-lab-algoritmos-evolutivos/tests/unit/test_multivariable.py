from math import pi
from random import Random

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import FitnessPolicy
from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Individual,
    Interval,
    OptimizationDirection,
    Population,
)
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod
from evolutionary_lab.domain.variation import ReproductionPolicy
from evolutionary_lab.evolution.crossover import cross_at_points, one_point_crossover
from evolutionary_lab.evolution.encoding.binary import (
    BinaryVectorEncoding,
    combine_chromosomes,
)
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.evolution.mutation import bit_flip_mutation
from evolutionary_lab.problems.registry import PROBLEMS, PROJECT_01_F1, get_problem


def test_independent_domains_lengths_and_endpoint_roundtrips() -> None:
    encoding = BinaryVectorEncoding.from_parameters(
        (Interval(-2, 2), Interval(10, 20)), (0.5, 0.01)
    )
    assert encoding.lengths == (4, 10)
    for point in ((-2.0, 10.0), (2.0, 20.0), (0.0, 15.0)):
        genotype = encoding.encode(point)
        assert genotype.variable_lengths == (4, 10)
        decoded = encoding.decode(genotype)
        for value, actual, step in zip(point, decoded, (0.5, 0.01), strict=True):
            assert abs(value - actual) <= step / 2
        assert encoding.encode(decoded) == genotype
    assert encoding.decode(encoding.encode((-2.0, 10.0))) == (-2.0, 10.0)
    assert encoding.decode(encoding.encode((2.0, 20.0))) == (2.0, 20.0)
    with pytest.raises(ValueError, match="variable lengths"):
        encoding.decode(BinaryGenotype((0,) * 14, (7, 7)))


def test_crossing_matches_variables_and_mutation_retains_segments() -> None:
    first = combine_chromosomes((BinaryGenotype((0,) * 3), BinaryGenotype((1,) * 5)))
    second = combine_chromosomes((BinaryGenotype((1,) * 3), BinaryGenotype((0,) * 5)))
    result = cross_at_points(first, second, (1, 4))
    assert result.cut_point is None and result.cut_points == (1, 4)
    assert result.offspring[0].chromosomes == (
        BinaryGenotype((0, 1, 1)),
        BinaryGenotype((1, 1, 1, 1, 0)),
    )
    assert result.offspring[1].chromosomes == (
        BinaryGenotype((1, 0, 0)),
        BinaryGenotype((0, 0, 0, 0, 1)),
    )
    mutated = bit_flip_mutation(first, Random(42), mutation_probability=1)
    assert mutated.genotype == second
    assert mutated.mutated_positions == tuple(range(8))
    crossed = one_point_crossover(first, second, Random(42), crossover_probability=1)
    assert crossed == one_point_crossover(
        first, second, Random(42), crossover_probability=1
    )
    assert len(crossed.cut_points) == 2
    assert crossed.offspring[0].variable_lengths == first.variable_lengths
    with pytest.raises(ValueError, match="equal chromosome lengths"):
        cross_at_points(first, BinaryGenotype(second.bits, (4, 4)), (1, 1))


def test_invalid_segments_and_population_layouts_are_rejected() -> None:
    for lengths in ((2, 0), (1,), (True, 1)):
        with pytest.raises(ValueError):
            BinaryGenotype((0, 0), lengths)
    first = Individual(0, BinaryGenotype((0,) * 6, (2, 4)), (0.0, 0.0))
    second = Individual(1, BinaryGenotype((0,) * 6, (3, 3)), (0.0, 0.0))
    with pytest.raises(ValueError, match="dimensions must match"):
        Population((first, second))


@pytest.mark.parametrize("selection", list(SelectionMethod))
@pytest.mark.parametrize("replacement", list(ReplacementStrategy))
@pytest.mark.parametrize("reproduction", list(ReproductionPolicy))
def test_five_variable_engine_preserves_each_encoding(
    selection, replacement, reproduction
) -> None:
    problem = get_problem("project_01.rastrigin", 5)
    config = ExperimentConfig(
        problem.identifier,
        (Interval(-1, 1),) + problem.domains[1:],
        (0.01, 0.02, 0.03, 0.04, 0.05),
        7,
        12,
        42,
        direction=problem.direction,
        fitness_policy=FitnessPolicy.MINIMIZATION_BOOK,
        selection_method=selection,
        replacement_strategy=replacement,
        reproduction_policy=reproduction,
    )
    encoding = BinaryVectorEncoding.from_parameters(config.domains, config.precision)
    result = run_evolution(config, problem)
    assert result == run_evolution(config, problem)
    previous = float("inf")
    for snapshot in result.generations:
        assert len(snapshot.population) == 7
        assert snapshot.best_so_far.objective_value <= previous
        previous = snapshot.best_so_far.objective_value
        for individual in snapshot.population:
            assert encoding.decode(individual.genotype) == individual.phenotype
            assert individual.objective_value == problem.evaluate(individual.phenotype)
            assert individual.selection_fitness >= 0
        if snapshot.trace:
            for pair in snapshot.trace.reproduction.pairs:
                if pair.result.cut_points:
                    assert len(pair.result.cut_points) == 5
                    for cut, length in zip(
                        pair.result.cut_points, encoding.lengths, strict=True
                    ):
                        assert (
                            0 <= cut <= length
                            if reproduction == ReproductionPolicy.BOOK_REFERENCE
                            else 1 <= cut < length
                        )
            if reproduction == ReproductionPolicy.BOOK_REFERENCE:
                assert len(snapshot.trace.reproduction.common_cuts) == 5


@pytest.mark.parametrize("identifier", list(PROBLEMS))
def test_all_registered_formulas_are_finite_and_match_available_reference_values(
    identifier,
) -> None:
    problem = get_problem(identifier)
    if problem.reference_optimum:
        reference = problem.reference_optimum
        assert problem.evaluate(reference.phenotype) == pytest.approx(
            reference.objective_value, abs=0.001
        )
    for point in (
        tuple(d.lower for d in problem.domains),
        tuple(d.upper for d in problem.domains),
    ):
        value = problem.evaluate(point)
        if problem.direction == OptimizationDirection.MAXIMIZE:
            assert value >= 0


def test_scanned_sine_power_uses_i_plus_one_and_dimension_validation() -> None:
    assert get_problem("project_01.sine_power", 1).evaluate((pi / 2,)) == pytest.approx(
        -1
    )
    assert get_problem("project_01.sine_power", 2).evaluate(
        (pi / 2, 0)
    ) == pytest.approx(-1)
    assert get_problem("project_01.rastrigin", 5).evaluate((0,) * 5) == 0
    assert get_problem("project_01.schaffer").evaluate((0, 0)) == 1
    with pytest.raises(ValueError):
        get_problem("project_01.schaffer", 3)
    with pytest.raises(ValueError):
        get_problem("project_01.rastrigin", 0)


def test_f1_keeps_approved_seeded_objective_results() -> None:
    problem = PROJECT_01_F1
    config = ExperimentConfig(
        problem.identifier, problem.domains, (0.001,), 10, 100, 42
    )
    result = run_evolution(config, problem)
    assert result.generations[-1].best_so_far.objective_value == 0.9999361576410012
    assert (
        result.generations[-1].statistics.best_individual.objective_value
        == 0.9923013444564796
    )
    assert result.generations[-1].best_so_far.phenotype == pytest.approx(
        (0.0997067448680352,), abs=1e-16
    )
