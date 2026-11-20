from dataclasses import dataclass
from typing import Protocol

from evolutionary_lab.domain.models import (
    Interval,
    OptimizationDirection,
    Phenotype,
    Representation,
    finite_vector,
)
from evolutionary_lab.domain.validation import finite_float


class ObjectiveFunction(Protocol):
    def __call__(self, phenotype: Phenotype, /) -> float: ...


@dataclass(frozen=True)
class ReferenceOptimum:
    phenotype: Phenotype
    objective_value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "phenotype", finite_vector(self.phenotype, "optimum"))
        object.__setattr__(
            self,
            "objective_value",
            finite_float(self.objective_value, "reference value"),
        )


@dataclass(frozen=True)
class OptimizationProblem:
    identifier: str
    title: str
    formula: str
    domains: tuple[Interval, ...]
    direction: OptimizationDirection
    objective: ObjectiveFunction
    supported_representations: tuple[Representation, ...]
    reference_optimum: ReferenceOptimum | None = None
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("Problem identifier must not be empty")
        domains = tuple(self.domains)
        if not domains or not all(isinstance(domain, Interval) for domain in domains):
            raise ValueError("Problem must declare valid domains")
        if not isinstance(self.direction, OptimizationDirection):
            raise ValueError("Unsupported optimization direction")
        representations = tuple(self.supported_representations)
        if not representations or not all(
            isinstance(item, Representation) for item in representations
        ):
            raise ValueError("Problem must declare supported representations")
        if not callable(self.objective):
            raise ValueError("Objective must be callable")
        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "supported_representations", representations)
        if self.reference_optimum is not None:
            self.validate_phenotype(self.reference_optimum.phenotype)

    def validate_phenotype(self, phenotype: Phenotype) -> Phenotype:
        point = finite_vector(phenotype, "phenotype")
        if len(point) != len(self.domains):
            raise ValueError("Phenotype dimension does not match the problem")
        if not all(
            domain.contains(value)
            for domain, value in zip(self.domains, point, strict=True)
        ):
            raise ValueError("Phenotype is outside the problem domain")
        return point

    def evaluate(self, phenotype: Phenotype) -> float:
        point = self.validate_phenotype(phenotype)
        return finite_float(self.objective(point), "objective result")
