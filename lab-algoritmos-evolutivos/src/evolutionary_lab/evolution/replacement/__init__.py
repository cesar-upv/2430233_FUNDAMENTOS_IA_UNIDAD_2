from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Individual,
    OptimizationDirection,
    Population,
)
from evolutionary_lab.domain.replacement import ReplacementResult, ReplacementStrategy


def is_better(
    candidate: Individual, incumbent: Individual, direction: OptimizationDirection
) -> bool:
    if not isinstance(direction, OptimizationDirection):
        raise ValueError("Unsupported optimization direction")
    if candidate.objective_value is None or incumbent.objective_value is None:
        raise ValueError("Comparison requires evaluated individuals")
    if direction == OptimizationDirection.MAXIMIZE:
        return candidate.objective_value > incumbent.objective_value
    return candidate.objective_value < incumbent.objective_value


def replace_population(
    parents: Population,
    offspring: Population,
    *,
    strategy: ReplacementStrategy,
    direction: OptimizationDirection,
) -> ReplacementResult:
    if not isinstance(strategy, ReplacementStrategy):
        raise ValueError("Unsupported replacement strategy")
    if not isinstance(direction, OptimizationDirection):
        raise ValueError("Unsupported optimization direction")
    if len(parents) != len(offspring):
        raise ValueError("Replacement requires one offspring per parent slot")
    if offspring.generation_index != parents.generation_index + 1:
        raise ValueError("Offspring must belong to the next generation")
    accepted: list[bool] = []
    survivors: list[Individual] = []
    for parent, child in zip(parents, offspring, strict=True):
        if parent.identifier != child.identifier:
            raise ValueError("Parent and offspring slot identifiers must match")
        parent_size = (
            len(parent.genotype.bits)
            if isinstance(parent.genotype, BinaryGenotype)
            else len(parent.genotype.values)
        )
        child_size = (
            len(child.genotype.bits)
            if isinstance(child.genotype, BinaryGenotype)
            else len(child.genotype.values)
        )
        if (
            type(parent.genotype) is not type(child.genotype)
            or parent_size != child_size
            or len(parent.phenotype) != len(child.phenotype)
            or (
                isinstance(parent.genotype, BinaryGenotype)
                and isinstance(child.genotype, BinaryGenotype)
                and parent.genotype.variable_lengths != child.genotype.variable_lengths
            )
        ):
            raise ValueError("Parent and offspring representations must match")
        better = is_better(child, parent, direction)
        adopt = strategy == ReplacementStrategy.BOOK_REFERENCE or better
        accepted.append(adopt)
        survivors.append(child if adopt else parent)
    return ReplacementResult(
        Population(tuple(survivors), offspring.generation_index), tuple(accepted)
    )
