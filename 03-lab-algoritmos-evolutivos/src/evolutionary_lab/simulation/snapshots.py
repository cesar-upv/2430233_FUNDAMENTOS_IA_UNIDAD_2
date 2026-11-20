from dataclasses import dataclass

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import PopulationStatistics
from evolutionary_lab.domain.models import Individual, Population
from evolutionary_lab.simulation.events import GenerationTrace


@dataclass(frozen=True)
class GenerationSnapshot:
    config: ExperimentConfig
    implementation_version: str
    population: Population
    statistics: PopulationStatistics
    best_so_far: Individual
    best_so_far_generation: int
    trace: GenerationTrace | None = None

    @property
    def generation_index(self) -> int:
        return self.population.generation_index


@dataclass(frozen=True)
class EvolutionResult:
    config: ExperimentConfig
    implementation_version: str
    generations: tuple[GenerationSnapshot, ...]

    @property
    def effective_seed(self) -> int:
        return self.config.seed

    @property
    def final_population(self) -> Population:
        return self.generations[-1].population

    @property
    def best_individual(self) -> Individual:
        return self.generations[-1].best_so_far
