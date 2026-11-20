from dataclasses import FrozenInstanceError, replace
from random import Random

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import FitnessPolicy
from evolutionary_lab.domain.models import (
    BinaryGenotype,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod, ZeroWeightPolicy
from evolutionary_lab.domain.variation import ReproductionPolicy
from evolutionary_lab.evolution import engine
from evolutionary_lab.evolution.encoding.binary import genotype_to_integer
from evolutionary_lab.evolution.engine import iterate_generations, run_evolution
from evolutionary_lab.evolution.evaluation import evaluate_population
from evolutionary_lab.evolution.initialization import initialize_population
from evolutionary_lab.problems.registry import PROJECT_01_F1


@pytest.fixture
def config() -> ExperimentConfig:
    return ExperimentConfig(
        PROJECT_01_F1.identifier, PROJECT_01_F1.domains, (0.001,), 10, 5, 42
    )


def test_zero_generation_limit_is_only_the_evaluated_initial_population(
    config: ExperimentConfig,
) -> None:
    config = replace(config, generation_limit=0)
    result = run_evolution(config, PROJECT_01_F1)
    expected = evaluate_population(
        initialize_population(config, PROJECT_01_F1, Random(42)), PROJECT_01_F1
    )
    assert len(result.generations) == 1
    assert result.final_population == expected
    assert result.generations[0].trace is None
    assert result.generations[0].best_so_far_generation == 0
    assert result.effective_seed == 42


def test_iterator_and_complete_run_agree_and_snapshots_stay_immutable(
    config: ExperimentConfig,
) -> None:
    iterator = iterate_generations(config, PROJECT_01_F1)
    first = next(iterator)
    saved = first.population
    remaining = tuple(iterator)
    result = run_evolution(config, PROJECT_01_F1)
    assert (first,) + remaining == result.generations
    assert first.population == saved
    with pytest.raises(FrozenInstanceError):
        first.best_so_far_generation = 9  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.population.individuals[0].objective_value = 9  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.config.seed = 9  # type: ignore[misc]
    assert result != run_evolution(replace(config, seed=43), PROJECT_01_F1)


class ScriptedRandom(Random):
    def __init__(self) -> None:
        super().__init__(42)
        self.genes = iter((0, 1, 2, 3, 0))
        self.draws = iter(
            (0.1, 0.3, 0.5, 0.7, 0.9, 0.1, 0.8, 0.2, 0.4, 0.9) + (0.9,) * 10
        )

    def getrandbits(self, k: int) -> int:
        assert k == 2
        return next(self.genes)

    def random(self) -> float:
        return next(self.draws)

    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        assert (start, stop, step) == (3, None, 1)
        return 1


def test_book_schedule_drops_last_odd_candidate_uses_common_cut_and_mutates_all(
    config: ExperimentConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem = replace(PROJECT_01_F1, objective=lambda point: 1.0)
    config = replace(
        config,
        precision=(0.4,),
        population_size=5,
        generation_limit=1,
        crossover_probability=0.5,
        mutation_probability=1,
    )
    rng = ScriptedRandom()
    monkeypatch.setattr(engine, "Random", lambda seed: rng)
    result = run_evolution(config, problem)
    trace = result.generations[1].trace
    assert trace is not None
    assert trace.selection.indices == (0, 1, 2, 3, 4)
    reproduction = trace.reproduction
    assert reproduction.candidate_slots == (0, 2, 3)
    assert reproduction.dropped_slot == 3
    assert reproduction.common_cut == 1
    assert tuple(pair.parent_slots for pair in reproduction.pairs) == ((0, 2),)
    assert all(
        pair.result.cut_point == reproduction.common_cut for pair in reproduction.pairs
    )
    assert trace.replacement_before_mutation
    assert trace.replacement.accepted == (True,) * 5
    before_mutation = trace.replacement.population
    assert tuple(genotype_to_integer(item.genotype) for item in before_mutation) == (
        2,
        1,
        0,
        3,
        0,
    )
    assert tuple(
        genotype_to_integer(item.genotype) for item in result.final_population
    ) == (1, 2, 3, 0, 3)
    assert all(mutation.mutated_positions == (0, 1) for mutation in trace.mutations)


@pytest.mark.parametrize("strategy", list(ReplacementStrategy))
def test_conditional_compares_after_mutation_while_reference_accepts_worse(
    config: ExperimentConfig, strategy: ReplacementStrategy
) -> None:
    problem = replace(PROJECT_01_F1, objective=lambda point: point[0])
    config = replace(
        config,
        population_size=1,
        generation_limit=1,
        crossover_probability=0,
        mutation_probability=1,
        replacement_strategy=strategy,
    )
    result = run_evolution(config, problem)
    initial, final = result.generations
    parent = initial.population.individuals[0]
    trace = final.trace
    assert trace is not None
    child = trace.evaluated_offspring.individuals[0]
    assert child.objective_value < parent.objective_value
    assert child.genotype.bits == tuple(1 - bit for bit in parent.genotype.bits)
    expected = child if strategy == ReplacementStrategy.BOOK_REFERENCE else parent
    assert final.population.individuals[0] == expected
    assert final.best_so_far == parent
    assert trace.replacement_before_mutation == (
        strategy == ReplacementStrategy.BOOK_REFERENCE
    )


@pytest.mark.parametrize("policy", list(ReproductionPolicy))
def test_all_pair_cuts_and_odd_unpaired_slot_are_recorded(
    config: ExperimentConfig, policy: ReproductionPolicy
) -> None:
    config = replace(
        config,
        population_size=5,
        reproduction_policy=policy,
        crossover_probability=1,
        mutation_probability=0,
    )
    result = run_evolution(config, PROJECT_01_F1)
    for generation in result.generations[1:]:
        trace = generation.trace
        assert trace is not None
        assert tuple(pair.parent_slots for pair in trace.reproduction.pairs) == (
            (0, 1),
            (2, 3),
        )
        unpaired = trace.selection.selected[4]
        assert generation.population.individuals[4] == replace(unpaired, identifier=4)
        if policy == ReproductionPolicy.BOOK_REFERENCE:
            assert trace.reproduction.dropped_slot == 4
            assert trace.reproduction.candidate_slots == (0, 1, 2, 3, 4)
            assert all(
                pair.result.cut_point == trace.reproduction.common_cut
                for pair in trace.reproduction.pairs
            )
        else:
            assert trace.reproduction.common_cut is None
            assert all(
                pair.result.cut_point is not None
                and 1 <= pair.result.cut_point <= 9
                and pair.result.random_value is not None
                for pair in trace.reproduction.pairs
            )


def test_zero_total_error_or_explicit_uniform_and_tournament(
    config: ExperimentConfig,
) -> None:
    problem = replace(PROJECT_01_F1, objective=lambda point: 0.0)
    with pytest.raises(ValueError, match="zero total"):
        run_evolution(config, problem)
    for method in (SelectionMethod.ROULETTE, SelectionMethod.SUS):
        result = run_evolution(
            replace(
                config,
                selection_method=method,
                zero_weight_policy=ZeroWeightPolicy.UNIFORM,
            ),
            problem,
        )
        for generation in result.generations[1:]:
            assert generation.trace is not None
            assert generation.trace.selection.distribution.used_uniform_fallback
    tournament = run_evolution(
        replace(config, selection_method=SelectionMethod.BINARY_TOURNAMENT), problem
    )
    assert len(tournament.generations) == 6


def test_objective_only_minimization_uses_tournament_without_weight_transform(
    config: ExperimentConfig,
) -> None:
    problem = replace(
        PROJECT_01_F1,
        direction=OptimizationDirection.MINIMIZE,
        objective=lambda point: -point[0],
        reference_optimum=None,
    )
    config = replace(
        config,
        direction=problem.direction,
        fitness_policy=FitnessPolicy.OBJECTIVE_ONLY,
        selection_method=SelectionMethod.BINARY_TOURNAMENT,
        replacement_strategy=ReplacementStrategy.CLASSROOM_CONDITIONAL,
    )
    result = run_evolution(config, problem)
    values = [
        generation.best_so_far.objective_value for generation in result.generations
    ]
    assert values == sorted(values, reverse=True)
    assert all(
        item.selection_fitness is None and item.objective_value <= 0
        for generation in result.generations
        for item in generation.population
    )


def test_invalid_engine_compatibility_fails_before_rng_creation(
    config: ExperimentConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_rng(seed: int) -> Random:
        pytest.fail("Invalid configuration must fail before RNG creation")

    monkeypatch.setattr(engine, "Random", unexpected_rng)
    for invalid in (
        replace(config, precision=(2.0,)),
        replace(config, fitness_policy=FitnessPolicy.OBJECTIVE_ONLY),
        replace(config, problem_id="unknown"),
        replace(config, representation=Representation.REAL, precision=()),
    ):
        with pytest.raises(ValueError):
            run_evolution(invalid, PROJECT_01_F1)
    real_problem = replace(
        PROJECT_01_F1, supported_representations=(Representation.REAL,)
    )
    with pytest.raises(ValueError, match="Mutation method"):
        run_evolution(
            replace(config, representation=Representation.REAL, precision=()),
            real_problem,
        )


def test_single_bit_engine_requires_disabled_crossover(
    config: ExperimentConfig,
) -> None:
    problem = replace(PROJECT_01_F1, objective=lambda point: 1.0)
    result = run_evolution(
        replace(config, precision=(2.0,), crossover_probability=0), problem
    )
    assert all(
        isinstance(item.genotype, BinaryGenotype) and len(item.genotype.bits) == 1
        for generation in result.generations
        for item in generation.population
    )
