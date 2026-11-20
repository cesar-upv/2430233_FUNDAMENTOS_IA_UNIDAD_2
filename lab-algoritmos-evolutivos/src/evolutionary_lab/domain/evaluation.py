from dataclasses import dataclass
from enum import StrEnum

from evolutionary_lab.domain.models import Individual, OptimizationDirection


class FitnessPolicy(StrEnum):
    NONNEGATIVE_IDENTITY = "nonnegative_identity"
    OBJECTIVE_ONLY = "objective_only"
    MINIMIZATION_BOOK = "minimization_book"
    MINIMIZATION_SIGNED = "minimization_signed"


def validate_fitness_policy(
    direction: OptimizationDirection, policy: FitnessPolicy
) -> None:
    if not isinstance(policy, FitnessPolicy):
        raise ValueError("Unsupported fitness policy")
    if (
        policy == FitnessPolicy.NONNEGATIVE_IDENTITY
        and direction != OptimizationDirection.MAXIMIZE
    ):
        raise ValueError("Identity fitness requires maximization")
    if policy in MINIMIZATION_POLICIES and direction != OptimizationDirection.MINIMIZE:
        raise ValueError("Minimization fitness requires minimization")


MINIMIZATION_POLICIES = (
    FitnessPolicy.MINIMIZATION_BOOK,
    FitnessPolicy.MINIMIZATION_SIGNED,
)


@dataclass(frozen=True)
class PopulationStatistics:
    population_size: int
    generation_index: int
    direction: OptimizationDirection
    best_individual: Individual
    worst_individual: Individual
    objective_min: float
    objective_max: float
    objective_mean: float
    selection_fitness_min: float | None
    selection_fitness_max: float | None
    selection_fitness_mean: float | None
    mean_normalized_hamming_distance: float | None
    mean_normalized_real_distance: float | None = None

    @property
    def normalized_diversity(self) -> float | None:
        return (
            self.mean_normalized_hamming_distance
            if self.mean_normalized_hamming_distance is not None
            else self.mean_normalized_real_distance
        )
