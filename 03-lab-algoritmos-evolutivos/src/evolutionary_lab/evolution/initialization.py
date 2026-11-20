from random import Random

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import (
    Individual,
    Population,
    RealGenotype,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.evolution.encoding.binary import (
    BinaryVectorEncoding,
    combine_chromosomes,
    genotype_from_integer,
)
from evolutionary_lab.evolution.encoding.real import uniform_real_value


def initialize_population(
    config: ExperimentConfig,
    problem: OptimizationProblem,
    rng: Random,
) -> Population:
    config.validate_for(problem)
    if config.representation == Representation.REAL:
        return Population(
            tuple(
                Individual(identifier, genotype, genotype.values)
                for identifier in range(config.population_size)
                for genotype in (
                    RealGenotype(
                        tuple(
                            uniform_real_value(domain, rng)[0]
                            for domain in config.domains
                        )
                    ),
                )
            )
        )
    encoding = BinaryVectorEncoding.from_parameters(config.domains, config.precision)

    individuals: list[Individual] = []
    for identifier in range(config.population_size):
        genotype = combine_chromosomes(
            tuple(
                genotype_from_integer(rng.getrandbits(variable.length), variable.length)
                for variable in encoding.variables
            )
        )
        individuals.append(
            Individual(
                identifier=identifier,
                genotype=genotype,
                phenotype=encoding.decode(genotype),
            )
        )
    return Population(tuple(individuals))
