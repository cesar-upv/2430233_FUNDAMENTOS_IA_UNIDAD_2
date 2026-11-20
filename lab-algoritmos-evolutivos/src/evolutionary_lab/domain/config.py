from dataclasses import dataclass

from evolutionary_lab.domain.evaluation import FitnessPolicy, validate_fitness_policy
from evolutionary_lab.domain.models import (
    Interval,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import (
    SelectionMethod,
    TournamentTiePolicy,
    ZeroWeightPolicy,
)
from evolutionary_lab.domain.validation import (
    finite_float,
    probability,
    require_integer,
)
from evolutionary_lab.domain.variation import (
    MutationMethod,
    RealBoundsPolicy,
    RealCrossoverMethod,
    ReproductionPolicy,
    SbxFormula,
)


@dataclass(frozen=True)
class ExperimentConfig:
    problem_id: str
    domains: tuple[Interval, ...]
    precision: tuple[float, ...]
    population_size: int
    generation_limit: int
    seed: int
    representation: Representation = Representation.BINARY
    direction: OptimizationDirection = OptimizationDirection.MAXIMIZE
    selection_method: SelectionMethod = SelectionMethod.ROULETTE
    crossover_probability: float = 0.70
    mutation_probability: float = 0.01
    reproduction_policy: ReproductionPolicy = ReproductionPolicy.BOOK_REFERENCE
    replacement_strategy: ReplacementStrategy = ReplacementStrategy.BOOK_REFERENCE
    fitness_policy: FitnessPolicy = FitnessPolicy.NONNEGATIVE_IDENTITY
    zero_weight_policy: ZeroWeightPolicy = ZeroWeightPolicy.ERROR
    tournament_tie_policy: TournamentTiePolicy = TournamentTiePolicy.RANDOM
    mutation_method: MutationMethod = MutationMethod.BIT_FLIP
    real_crossover_method: RealCrossoverMethod | None = None
    real_uniform_swap_probability: float = 0.5
    arithmetic_alpha: float = 0.5
    sbx_distribution_index: float = 1.0
    sbx_formula: SbxFormula = SbxFormula.BOOK_LITERAL
    real_bounds_policy: RealBoundsPolicy = RealBoundsPolicy.CLIP

    def __post_init__(self) -> None:
        if not isinstance(self.problem_id, str) or not self.problem_id.strip():
            raise ValueError("Problem identifier must not be empty")
        domains = tuple(self.domains)
        if not domains or not all(isinstance(domain, Interval) for domain in domains):
            raise ValueError("Configuration must declare valid domains")
        precision = tuple(finite_float(value, "precision") for value in self.precision)
        if self.representation == Representation.REAL and precision:
            raise ValueError(
                "Real representation does not use discretization precision"
            )
        if self.representation != Representation.REAL and (
            len(precision) != len(domains) or any(value <= 0 for value in precision)
        ):
            raise ValueError("Each domain needs a positive finite precision")
        require_integer(self.population_size, "population size", minimum=1)
        require_integer(self.generation_limit, "generation limit", minimum=0)
        require_integer(self.seed, "seed")
        if not isinstance(self.representation, Representation):
            raise ValueError("Unsupported representation")
        if not isinstance(self.direction, OptimizationDirection):
            raise ValueError("Unsupported optimization direction")
        for value, enum_type in (
            (self.selection_method, SelectionMethod),
            (self.reproduction_policy, ReproductionPolicy),
            (self.replacement_strategy, ReplacementStrategy),
            (self.fitness_policy, FitnessPolicy),
            (self.zero_weight_policy, ZeroWeightPolicy),
            (self.tournament_tie_policy, TournamentTiePolicy),
            (self.mutation_method, MutationMethod),
            (self.sbx_formula, SbxFormula),
            (self.real_bounds_policy, RealBoundsPolicy),
        ):
            if not isinstance(value, enum_type):
                raise ValueError(f"Unsupported {enum_type.__name__}")
        if self.real_crossover_method is not None and not isinstance(
            self.real_crossover_method, RealCrossoverMethod
        ):
            raise ValueError("Unsupported real crossover method")
        object.__setattr__(
            self,
            "real_uniform_swap_probability",
            probability(self.real_uniform_swap_probability, "uniform swap probability"),
        )
        object.__setattr__(
            self,
            "arithmetic_alpha",
            probability(self.arithmetic_alpha, "arithmetic alpha"),
        )
        index = finite_float(self.sbx_distribution_index, "SBX distribution index")
        if index < 0:
            raise ValueError("SBX distribution index must be nonnegative")
        object.__setattr__(self, "sbx_distribution_index", index)
        object.__setattr__(
            self,
            "crossover_probability",
            probability(self.crossover_probability, "crossover probability"),
        )
        object.__setattr__(
            self,
            "mutation_probability",
            probability(self.mutation_probability, "per-bit mutation probability"),
        )
        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "precision", precision)

    def validate_for(self, problem: OptimizationProblem) -> None:
        if self.problem_id != problem.identifier:
            raise ValueError("Configuration and problem identifiers differ")
        if self.direction != problem.direction:
            raise ValueError("Configuration and problem directions differ")
        validate_fitness_policy(self.direction, self.fitness_policy)
        if (
            self.fitness_policy == FitnessPolicy.OBJECTIVE_ONLY
            and self.selection_method != SelectionMethod.BINARY_TOURNAMENT
        ):
            raise ValueError("Proportional selection requires explicit fitness weights")
        if self.representation not in problem.supported_representations:
            raise ValueError("Representation is incompatible with the problem")
        expected_mutation = (
            MutationMethod.BIT_FLIP
            if self.representation == Representation.BINARY
            else MutationMethod.UNIFORM_RESET
        )
        if self.mutation_method != expected_mutation:
            raise ValueError("Mutation method is incompatible with the representation")
        if len(self.domains) != len(problem.domains):
            raise ValueError("Configuration dimension does not match the problem")
        if any(
            domain.lower < allowed.lower or domain.upper > allowed.upper
            for domain, allowed in zip(self.domains, problem.domains, strict=True)
        ):
            raise ValueError("Configured domain extends outside the problem domain")
