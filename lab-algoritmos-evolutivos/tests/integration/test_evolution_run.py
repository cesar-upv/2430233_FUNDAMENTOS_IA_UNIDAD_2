from dataclasses import replace
from math import isfinite

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import BinaryGenotype
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod
from evolutionary_lab.domain.variation import ReproductionPolicy
from evolutionary_lab.evolution.encoding.binary import BinaryEncoding
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.problems.registry import PROJECT_01_F1


@pytest.mark.parametrize("method", list(SelectionMethod))
@pytest.mark.parametrize("strategy", list(ReplacementStrategy))
@pytest.mark.parametrize("policy", list(ReproductionPolicy))
def test_project_1_f1_100_generations_are_valid_and_reproducible(
    method: SelectionMethod, strategy: ReplacementStrategy, policy: ReproductionPolicy
) -> None:
    config = ExperimentConfig(
        problem_id=PROJECT_01_F1.identifier,
        domains=PROJECT_01_F1.domains,
        precision=(0.001,),
        population_size=10,
        generation_limit=100,
        seed=42,
        selection_method=method,
        replacement_strategy=strategy,
        reproduction_policy=policy,
    )
    result = run_evolution(config, PROJECT_01_F1)
    assert result == run_evolution(config, PROJECT_01_F1)
    assert result.effective_seed == 42
    assert len(result.generations) == 101
    assert result.final_population.generation_index == 100
    encoding = BinaryEncoding(config.domains[0], 10)
    best_values: list[float] = []
    for index, snapshot in enumerate(result.generations):
        assert snapshot.generation_index == index
        assert snapshot.config == config
        assert snapshot.implementation_version == result.implementation_version
        population = snapshot.population
        assert len(population) == 10
        assert {item.identifier for item in population} == set(range(10))
        for individual in population:
            assert isinstance(individual.genotype, BinaryGenotype)
            assert len(individual.genotype.bits) == 10
            assert all(bit in (0, 1) for bit in individual.genotype.bits)
            assert individual.phenotype == (encoding.decode(individual.genotype),)
            assert 0 <= individual.phenotype[0] <= 1
            value = individual.objective_value
            assert value is not None and isfinite(value) and 0 <= value <= 1
            assert value == PROJECT_01_F1.evaluate(individual.phenotype)
            assert individual.selection_fitness == value
        statistics = snapshot.statistics
        assert statistics.population_size == 10 and statistics.generation_index == index
        assert statistics.best_individual.objective_value == max(
            item.objective_value for item in population
        )
        assert (
            statistics.objective_min
            <= statistics.objective_mean
            <= statistics.objective_max
        )
        assert 0 <= statistics.mean_normalized_hamming_distance <= 1
        assert snapshot.best_so_far.objective_value is not None
        best_values.append(snapshot.best_so_far.objective_value)
        origin = result.generations[snapshot.best_so_far_generation]
        assert snapshot.best_so_far in origin.population.individuals
        if snapshot.trace is not None:
            trace = snapshot.trace
            assert len(trace.selection.selected) == len(trace.mutations) == 10
            assert len(trace.evaluated_offspring) == 10
            if strategy == ReplacementStrategy.CLASSROOM_CONDITIONAL:
                assert not trace.replacement_before_mutation
                for slot, (parent, child, survivor) in enumerate(
                    zip(
                        trace.selection.selected,
                        trace.evaluated_offspring,
                        population,
                        strict=True,
                    )
                ):
                    improve = child.objective_value > parent.objective_value
                    assert trace.replacement.accepted[slot] == improve
                    assert survivor == (
                        child if improve else replace(parent, identifier=slot)
                    )
            else:
                assert trace.replacement_before_mutation
                assert trace.replacement.accepted == (True,) * 10
    assert best_values == sorted(best_values)
    assert result.best_individual == result.generations[-1].best_so_far
