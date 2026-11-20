from collections.abc import Iterator
from dataclasses import replace
from random import Random

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import MINIMIZATION_POLICIES
from evolutionary_lab.domain.models import (
    Genotype,
    Individual,
    Population,
    RealGenotype,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.variation import (
    CrossoverResult,
    MutationResult,
    RealCrossoverMethod,
    RealMutationResult,
    ReproductionPolicy,
)
from evolutionary_lab.evolution.crossover import cross_at_points, one_point_crossover
from evolutionary_lab.evolution.crossover.real import real_crossover
from evolutionary_lab.evolution.encoding.binary import BinaryVectorEncoding
from evolutionary_lab.evolution.evaluation import (
    evaluate_individual,
    evaluate_population,
    revise_minimization_fitness,
)
from evolutionary_lab.evolution.initialization import initialize_population
from evolutionary_lab.evolution.mutation import bit_flip_mutation
from evolutionary_lab.evolution.mutation.real import uniform_reset_mutation
from evolutionary_lab.evolution.replacement import is_better, replace_population
from evolutionary_lab.evolution.selection import select
from evolutionary_lab.evolution.statistics import calculate_population_statistics
from evolutionary_lab.simulation.events import (
    GenerationTrace,
    PairCrossover,
    ReproductionTrace,
)
from evolutionary_lab.simulation.snapshots import EvolutionResult, GenerationSnapshot

IMPLEMENTATION_VERSION = "genetic-ga-v4"


def validate_configuration(
    config: ExperimentConfig, problem: OptimizationProblem
) -> None:
    _encoding(config, problem)


def _encoding(
    config: ExperimentConfig, problem: OptimizationProblem
) -> BinaryVectorEncoding | None:
    config.validate_for(problem)
    if config.representation == Representation.REAL:
        if config.real_crossover_method is None:
            raise ValueError("Real crossover method is required")
        if config.reproduction_policy != ReproductionPolicy.PAIRWISE:
            raise ValueError("Real crossover requires pairwise scheduling")
        if (
            config.real_crossover_method == RealCrossoverMethod.ONE_POINT
            and len(config.domains) < 2
            and config.crossover_probability > 0
        ):
            raise ValueError("Real one-point crossover requires at least two variables")
        return None
    if config.real_crossover_method is not None:
        raise ValueError("Real crossover is incompatible with binary representation")
    encoding = BinaryVectorEncoding.from_parameters(config.domains, config.precision)
    if min(encoding.lengths) < 2 and config.crossover_probability > 0:
        raise ValueError("Active one-point crossover requires at least two genes")
    return encoding


def _evaluated_child(
    identifier: int,
    genotype: Genotype,
    encoding: BinaryVectorEncoding | None,
    config: ExperimentConfig,
    problem: OptimizationProblem,
) -> Individual:
    if isinstance(genotype, RealGenotype):
        phenotype = genotype.values
    else:
        assert encoding is not None
        phenotype = encoding.decode(genotype)
    child = Individual(identifier, genotype, phenotype)
    return evaluate_individual(child, problem, fitness_policy=config.fitness_policy)


def _reproduce_real(
    parents: Population,
    config: ExperimentConfig,
    problem: OptimizationProblem,
    rng: Random,
) -> tuple[Population, ReproductionTrace]:
    assert config.real_crossover_method is not None
    children = list(parents.individuals)
    pairs = []
    for first in range(0, len(parents) - 1, 2):
        second = first + 1
        result = real_crossover(
            parents.individuals[first].genotype,
            parents.individuals[second].genotype,
            config.domains,
            rng,
            method=config.real_crossover_method,
            crossover_probability=config.crossover_probability,
            swap_probability=config.real_uniform_swap_probability,
            arithmetic_alpha=config.arithmetic_alpha,
            distribution_index=config.sbx_distribution_index,
            sbx_formula=config.sbx_formula,
            bounds_policy=config.real_bounds_policy,
        )
        pairs.append(PairCrossover((first, second), result))
        if result.applied:
            for slot, genotype in zip((first, second), result.offspring, strict=True):
                children[slot] = _evaluated_child(slot, genotype, None, config, problem)
    return Population(tuple(children), parents.generation_index + 1), ReproductionTrace(
        config.reproduction_policy, (), (), None, None, tuple(pairs)
    )


def _reproduce(
    parents: Population,
    encoding: BinaryVectorEncoding | None,
    config: ExperimentConfig,
    problem: OptimizationProblem,
    rng: Random,
) -> tuple[Population, ReproductionTrace]:
    if config.representation == Representation.REAL:
        return _reproduce_real(parents, config, problem, rng)
    assert encoding is not None
    pairs: list[PairCrossover] = []
    candidate_draws: tuple[float, ...] = ()
    candidate_slots: tuple[int, ...] = ()
    dropped_slot = None
    common_cut = None
    common_cuts: tuple[int, ...] = ()
    if config.reproduction_policy == ReproductionPolicy.BOOK_REFERENCE:
        candidate_draws = tuple(rng.random() for _ in parents)
        candidate_slots = tuple(
            slot
            for slot, draw in enumerate(candidate_draws)
            if draw < config.crossover_probability
        )
        eligible = candidate_slots
        if len(eligible) % 2:
            dropped_slot, eligible = eligible[-1], eligible[:-1]
        # Chapter 2 pp.44–45: one shared cut, drawn even without eligible pairs.
        cuts = tuple(rng.randrange(length + 1) for length in encoding.lengths)
        if len(cuts) == 1:
            common_cut = cuts[0]
        else:
            common_cuts = cuts
        for index in range(0, len(eligible), 2):
            first, second = eligible[index : index + 2]
            result = cross_at_points(
                parents.individuals[first].genotype,
                parents.individuals[second].genotype,
                cuts,
                allow_endpoints=True,
            )
            pairs.append(PairCrossover((first, second), result))
    else:
        for first in range(0, len(parents) - 1, 2):
            second = first + 1
            result = one_point_crossover(
                parents.individuals[first].genotype,
                parents.individuals[second].genotype,
                rng,
                crossover_probability=config.crossover_probability,
            )
            pairs.append(PairCrossover((first, second), result))

    children = list(parents.individuals)
    for pair in pairs:
        assert isinstance(pair.result, CrossoverResult)
        if pair.result.cut_point is None and not pair.result.cut_points:
            continue
        for slot, genotype in zip(
            pair.parent_slots, pair.result.offspring, strict=True
        ):
            children[slot] = _evaluated_child(slot, genotype, encoding, config, problem)
    trace = ReproductionTrace(
        config.reproduction_policy,
        candidate_draws,
        candidate_slots,
        dropped_slot,
        common_cut,
        tuple(pairs),
        common_cuts,
    )
    return Population(tuple(children), parents.generation_index + 1), trace


def _mutate(
    population: Population,
    encoding: BinaryVectorEncoding | None,
    config: ExperimentConfig,
    problem: OptimizationProblem,
    rng: Random,
) -> tuple[Population, tuple[MutationResult | RealMutationResult, ...]]:
    children: list[Individual] = []
    traces: list[MutationResult | RealMutationResult] = []
    for individual in population:
        result: MutationResult | RealMutationResult
        if isinstance(individual.genotype, RealGenotype):
            result = uniform_reset_mutation(
                individual.genotype,
                config.domains,
                rng,
                mutation_probability=config.mutation_probability,
            )
        else:
            result = bit_flip_mutation(
                individual.genotype,
                rng,
                mutation_probability=config.mutation_probability,
            )
        traces.append(result)
        children.append(
            _evaluated_child(
                individual.identifier, result.genotype, encoding, config, problem
            )
            if result.mutated_positions
            else individual
        )
    return Population(tuple(children), population.generation_index), tuple(traces)


def iterate_generations(
    config: ExperimentConfig, problem: OptimizationProblem
) -> Iterator[GenerationSnapshot]:
    encoding = _encoding(config, problem)
    rng = Random(config.seed)
    population = evaluate_population(
        initialize_population(config, problem, rng),
        problem,
        fitness_policy=config.fitness_policy,
    )
    statistics = calculate_population_statistics(
        population, config.direction, config.domains
    )
    best, best_generation = statistics.best_individual, 0
    yield GenerationSnapshot(
        config, IMPLEMENTATION_VERSION, population, statistics, best, best_generation
    )
    for generation in range(1, config.generation_limit + 1):
        selection = select(
            population,
            config.population_size,
            rng,
            method=config.selection_method,
            zero_weight_policy=config.zero_weight_policy,
            direction=config.direction,
            tie_policy=config.tournament_tie_policy,
        )
        # IDs name generation-local slots; source identities remain in selection traces.
        parents = Population(
            tuple(
                replace(item, identifier=slot)
                for slot, item in enumerate(selection.selected)
            ),
            population.generation_index,
        )
        crossed, reproduction = _reproduce(parents, encoding, config, problem, rng)
        before_mutation = (
            config.replacement_strategy == ReplacementStrategy.BOOK_REFERENCE
        )
        if before_mutation:
            replacement = replace_population(
                parents,
                crossed,
                strategy=config.replacement_strategy,
                direction=config.direction,
            )
            crossed = replacement.population
        offspring, mutations = _mutate(crossed, encoding, config, problem, rng)
        if before_mutation:
            population = offspring
        else:
            replacement = replace_population(
                parents,
                offspring,
                strategy=config.replacement_strategy,
                direction=config.direction,
            )
            population = replacement.population
        if config.fitness_policy in MINIMIZATION_POLICIES:
            population = revise_minimization_fitness(population, config.fitness_policy)
        statistics = calculate_population_statistics(
            population, config.direction, config.domains
        )
        if is_better(statistics.best_individual, best, config.direction):
            best, best_generation = statistics.best_individual, generation
        trace = GenerationTrace(
            selection, reproduction, mutations, offspring, replacement, before_mutation
        )
        yield GenerationSnapshot(
            config,
            IMPLEMENTATION_VERSION,
            population,
            statistics,
            best,
            best_generation,
            trace,
        )


def run_evolution(
    config: ExperimentConfig, problem: OptimizationProblem
) -> EvolutionResult:
    return EvolutionResult(
        config, IMPLEMENTATION_VERSION, tuple(iterate_generations(config, problem))
    )
