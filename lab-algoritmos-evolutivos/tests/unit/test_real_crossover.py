from dataclasses import replace
from math import isfinite, sqrt
from random import Random

import pytest
from test_real_representation import Draws

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import FitnessPolicy
from evolutionary_lab.domain.models import Interval, RealGenotype, Representation
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod
from evolutionary_lab.domain.variation import (
    MutationMethod,
    RealBoundsPolicy,
    RealCrossoverMethod,
    ReproductionPolicy,
    SbxFormula,
)
from evolutionary_lab.evolution.crossover.real import real_crossover, sbx_beta
from evolutionary_lab.evolution.engine import run_evolution, validate_configuration
from evolutionary_lab.problems.registry import get_problem

A = RealGenotype((0.2, 12.0, -2.0))
B = RealGenotype((0.8, 18.0, 2.0))
DOMAINS = (Interval(0, 1), Interval(10, 20), Interval(-3, 3))


def test_uniform_crossover_uses_complementary_per_gene_mask() -> None:
    result = real_crossover(
        A,
        B,
        DOMAINS,
        Draws((0.0, 0.1, 0.5, 0.9)),
        method=RealCrossoverMethod.UNIFORM,
        crossover_probability=1,
        swap_probability=0.5,
    )
    assert result.offspring == (
        RealGenotype((0.8, 12.0, -2.0)),
        RealGenotype((0.2, 18.0, 2.0)),
    )
    assert result.swapped_positions == (0,)
    assert result.gene_draws == (0.1, 0.5, 0.9)


def test_arithmetic_crossover_matches_book_complementary_formula() -> None:
    result = real_crossover(
        A,
        B,
        DOMAINS,
        Random(42),
        method=RealCrossoverMethod.ARITHMETIC,
        crossover_probability=1,
        arithmetic_alpha=0.25,
    )
    assert result.offspring[0].values == pytest.approx((0.65, 16.5, 1.0))
    assert result.offspring[1].values == pytest.approx((0.35, 13.5, -1.0))
    assert result.alpha == 0.25 and result.repaired_positions == ((), ())


def test_one_point_exchanges_whole_real_components() -> None:
    result = real_crossover(
        A,
        B,
        DOMAINS,
        Random(42),
        method=RealCrossoverMethod.ONE_POINT,
        crossover_probability=1,
    )
    cut = result.cut_point
    assert cut in (1, 2)
    assert result.offspring[0].values == A.values[:cut] + B.values[cut:]
    assert result.offspring[1].values == B.values[:cut] + A.values[cut:]


@pytest.mark.parametrize(
    "draw,book,continuous",
    [(0.0, 0.0, 0.0), (0.25, 1.0, sqrt(0.5)), (0.5, 1.0, 1.0), (0.875, 2.0, 2.0)],
)
def test_sbx_literal_and_explicit_continuous_variant(draw, book, continuous) -> None:
    assert sbx_beta(draw, 1, SbxFormula.BOOK_LITERAL) == pytest.approx(book)
    assert sbx_beta(draw, 1, SbxFormula.CONTINUOUS) == pytest.approx(continuous)


def test_sbx_reuses_one_draw_per_pair_and_records_raw_and_repaired_children() -> None:
    a, b = RealGenotype((0.0,)), RealGenotype((1.0,))
    domains = (Interval(0, 1),)
    result = real_crossover(
        a,
        b,
        domains,
        Draws((0.0, 0.875)),
        method=RealCrossoverMethod.SBX,
        crossover_probability=1,
    )
    assert result.raw_offspring == ((-0.5,), (1.5,))
    assert result.offspring == (a, b)
    assert result.repaired_positions == ((0,), (0,)) and result.beta == 2
    with pytest.raises(ValueError, match="outside"):
        real_crossover(
            a,
            b,
            domains,
            Draws((0.0, 0.875)),
            method=RealCrossoverMethod.SBX,
            crossover_probability=1,
            bounds_policy=RealBoundsPolicy.REJECT,
        )
    pair = real_crossover(
        A,
        B,
        DOMAINS,
        Draws((0.0, 0.25)),
        method=RealCrossoverMethod.SBX,
        crossover_probability=1,
    )
    assert pair.beta == 1 and pair.raw_offspring[0] == pytest.approx(A.values)


@pytest.mark.parametrize("method", list(RealCrossoverMethod))
def test_skipped_real_crossover_preserves_parents(method) -> None:
    result = real_crossover(
        A, B, DOMAINS, Draws((0.0,)), method=method, crossover_probability=0
    )
    assert not result.applied and result.offspring == (A, B)


def test_incompatible_dimensions_and_invalid_parameters_precede_random_draws() -> None:
    rng = Random(42)
    state = rng.getstate()
    for method, alpha in (
        (RealCrossoverMethod.ONE_POINT, 0.5),
        (RealCrossoverMethod.ARITHMETIC, 2.0),
    ):
        with pytest.raises(ValueError):
            real_crossover(
                RealGenotype((0.0,)),
                RealGenotype((1.0,)),
                (Interval(0, 1),),
                rng,
                method=method,
                crossover_probability=1,
                arithmetic_alpha=alpha,
            )
        assert rng.getstate() == state
    for draw in (1.0, -0.1, float("nan")):
        with pytest.raises(ValueError):
            sbx_beta(draw, 1, SbxFormula.BOOK_LITERAL)


@pytest.mark.parametrize("method", list(RealCrossoverMethod))
@pytest.mark.parametrize("replacement", list(ReplacementStrategy))
@pytest.mark.parametrize("selection", list(SelectionMethod))
def test_real_engine_reuses_cycle_and_preserves_invariants(
    method, replacement, selection
) -> None:
    base = get_problem("project_01.rastrigin", 3)
    problem = replace(base, supported_representations=(Representation.REAL,))
    config = ExperimentConfig(
        problem.identifier,
        problem.domains,
        (),
        7,
        8,
        42,
        representation=Representation.REAL,
        direction=problem.direction,
        fitness_policy=FitnessPolicy.MINIMIZATION_BOOK,
        mutation_method=MutationMethod.UNIFORM_RESET,
        real_crossover_method=method,
        reproduction_policy=ReproductionPolicy.PAIRWISE,
        replacement_strategy=replacement,
        selection_method=selection,
    )
    result = run_evolution(config, problem)
    assert result == run_evolution(config, problem)
    best = float("inf")
    for snapshot in result.generations:
        assert (
            len(snapshot.population) == 7
            and snapshot.best_so_far.objective_value <= best
        )
        best = snapshot.best_so_far.objective_value
        for individual in snapshot.population:
            assert individual.genotype.values == individual.phenotype
            assert individual.objective_value == problem.evaluate(individual.phenotype)
            assert (
                isfinite(individual.selection_fitness)
                and individual.selection_fitness >= 0
            )
        if snapshot.trace:
            assert len(snapshot.trace.mutations) == 7
            for parent, child, adopted in zip(
                snapshot.trace.selection.selected,
                snapshot.trace.evaluated_offspring,
                snapshot.trace.replacement.accepted,
                strict=True,
            ):
                if replacement == ReplacementStrategy.CLASSROOM_CONDITIONAL:
                    assert adopted == (child.objective_value < parent.objective_value)
    with pytest.raises(ValueError, match="pairwise"):
        validate_configuration(
            replace(config, reproduction_policy=ReproductionPolicy.BOOK_REFERENCE),
            problem,
        )
