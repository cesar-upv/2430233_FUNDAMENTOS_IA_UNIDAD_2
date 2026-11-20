from dataclasses import replace

import pytest

from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Individual,
    OptimizationDirection,
    Population,
    RealGenotype,
)
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.evolution.replacement import is_better, replace_population


def population(values: tuple[float, ...], generation: int) -> Population:
    return Population(
        tuple(
            Individual(i, BinaryGenotype((0, 1)), (0.5,), value)
            for i, value in enumerate(values)
        ),
        generation,
    )


@pytest.mark.parametrize("direction", list(OptimizationDirection))
def test_reference_adopts_worse_equal_and_better_offspring(
    direction: OptimizationDirection,
) -> None:
    parents, offspring = population((1, 2, 3), 4), population((0, 2, 4), 5)
    result = replace_population(
        parents,
        offspring,
        strategy=ReplacementStrategy.BOOK_REFERENCE,
        direction=direction,
    )
    assert result.population == offspring
    assert result.accepted == (True, True, True)
    assert parents.individuals[0].objective_value == 1


@pytest.mark.parametrize(
    "direction, accepted",
    [
        (OptimizationDirection.MAXIMIZE, (False, False, True)),
        (OptimizationDirection.MINIMIZE, (True, False, False)),
    ],
)
def test_classroom_uses_strict_direction_aware_improvement_per_parent_slot(
    direction: OptimizationDirection, accepted: tuple[bool, ...]
) -> None:
    parents, offspring = population((-1, 0, 1), 4), population((-2, 0, 2), 5)
    result = replace_population(
        parents,
        offspring,
        strategy=ReplacementStrategy.CLASSROOM_CONDITIONAL,
        direction=direction,
    )
    assert result.accepted == accepted
    assert result.population.generation_index == 5
    assert len(result.population) == 3
    for parent, child, survivor, adopt in zip(
        parents, offspring, result.population, accepted, strict=True
    ):
        assert survivor is (child if adopt else parent)
    assert result.population.individuals[1] is parents.individuals[1]


def test_replacement_contract_also_accepts_real_genotype_values() -> None:
    parent = Individual(0, RealGenotype((0.1,)), (0.1,), 1)
    child = Individual(0, RealGenotype((0.2,)), (0.2,), 2)
    result = replace_population(
        Population((parent,)),
        Population((child,), 1),
        strategy=ReplacementStrategy.CLASSROOM_CONDITIONAL,
        direction=OptimizationDirection.MAXIMIZE,
    )
    assert result.population.individuals == (child,)


def test_malformed_replacement_pairings_are_rejected() -> None:
    parents, offspring = population((1, 2), 0), population((2, 3), 1)
    first, second = offspring.individuals
    invalid = (
        population((2,), 1),
        replace(offspring, generation_index=0),
        replace(offspring, individuals=(replace(first, identifier=8), second)),
        replace(
            offspring,
            individuals=tuple(
                replace(child, objective_value=None) for child in offspring
            ),
        ),
        Population(
            tuple(replace(child, genotype=BinaryGenotype((0,))) for child in offspring),
            1,
        ),
        Population(
            tuple(replace(child, genotype=RealGenotype((0.5,))) for child in offspring),
            1,
        ),
        Population(
            tuple(
                replace(
                    child, phenotype=(0.5, 0.5), genotype=BinaryGenotype((0, 1), (1, 1))
                )
                for child in offspring
            ),
            1,
        ),
    )
    for children in invalid:
        with pytest.raises(ValueError):
            replace_population(
                parents,
                children,
                strategy=ReplacementStrategy.BOOK_REFERENCE,
                direction=OptimizationDirection.MAXIMIZE,
            )


def test_comparison_and_strategy_validation() -> None:
    parents, offspring = population((1,), 0), population((2,), 1)
    with pytest.raises(ValueError, match="direction"):
        is_better(offspring.individuals[0], parents.individuals[0], "bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="strategy"):
        replace_population(
            parents, offspring, strategy="bad", direction=OptimizationDirection.MAXIMIZE
        )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="direction"):
        replace_population(
            parents,
            offspring,
            strategy=ReplacementStrategy.BOOK_REFERENCE,
            direction="bad",
        )  # type: ignore[arg-type]
