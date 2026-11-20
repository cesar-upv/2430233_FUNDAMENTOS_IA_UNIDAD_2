from dataclasses import replace

from evolutionary_lab.domain.evaluation import (
    MINIMIZATION_POLICIES,
    FitnessPolicy,
    validate_fitness_policy,
)
from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Individual,
    Population,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.domain.validation import finite_float


def evaluate_individual(
    individual: Individual,
    problem: OptimizationProblem,
    *,
    fitness_policy: FitnessPolicy = FitnessPolicy.NONNEGATIVE_IDENTITY,
) -> Individual:
    validate_fitness_policy(problem.direction, fitness_policy)
    representation = (
        Representation.BINARY
        if isinstance(individual.genotype, BinaryGenotype)
        else Representation.REAL
    )
    if representation not in problem.supported_representations:
        raise ValueError("Representation is incompatible with the problem")
    objective = problem.evaluate(individual.phenotype)
    fitness = None
    if fitness_policy == FitnessPolicy.NONNEGATIVE_IDENTITY:
        if objective < 0:
            raise ValueError("Identity fitness requires a nonnegative objective")
        fitness = objective
    return replace(individual, objective_value=objective, selection_fitness=fitness)


def revise_minimization_fitness(
    population: Population, policy: FitnessPolicy
) -> Population:
    """Recompute population-relative weights without reevaluating objectives."""
    if policy not in MINIMIZATION_POLICIES:
        raise ValueError("A minimization fitness policy is required")
    objectives = [item.objective_value for item in population]
    if any(value is None for value in objectives):
        raise ValueError("Fitness revision requires evaluated objectives")
    cmax = max(value for value in objectives if value is not None)
    if policy == FitnessPolicy.MINIMIZATION_BOOK:
        if cmax < 0:
            raise ValueError("Book minimization fitness requires nonnegative cmax")
        offset = cmax * 1.05
    else:
        # Named signed extension: retain the book's 5% margin for positive cmax.
        offset = cmax + 0.05 * abs(cmax)
    finite_float(offset, "fitness offset")
    return replace(
        population,
        individuals=tuple(
            replace(
                item,
                selection_fitness=finite_float(offset - value, "selection fitness"),
            )
            for item, value in zip(population, objectives, strict=True)
            if value is not None
        ),
    )


def evaluate_population(
    population: Population,
    problem: OptimizationProblem,
    *,
    fitness_policy: FitnessPolicy = FitnessPolicy.NONNEGATIVE_IDENTITY,
) -> Population:
    validate_fitness_policy(problem.direction, fitness_policy)
    individuals = tuple(
        evaluate_individual(individual, problem, fitness_policy=fitness_policy)
        for individual in population
    )
    result = replace(population, individuals=individuals)
    return (
        revise_minimization_fitness(result, fitness_policy)
        if fitness_policy in MINIMIZATION_POLICIES
        else result
    )
