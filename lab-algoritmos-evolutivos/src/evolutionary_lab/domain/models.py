from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from evolutionary_lab.domain.validation import finite_float, require_integer

type Phenotype = tuple[float, ...]


class Representation(StrEnum):
    BINARY = "binary"
    REAL = "real"


class OptimizationDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


def finite_vector(values: Phenotype, name: str) -> Phenotype:
    vector = tuple(finite_float(value, name) for value in values)
    if not vector:
        raise ValueError(f"{name} must not be empty")
    return vector


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        lower = finite_float(self.lower, "lower")
        upper = finite_float(self.upper, "upper")
        if lower >= upper or not isfinite(upper - lower):
            raise ValueError("Interval must have a positive finite width")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    def contains(self, value: float) -> bool:
        return self.lower <= finite_float(value, "coordinate") <= self.upper


@dataclass(frozen=True)
class BinaryGenotype:
    # Index 0 is the least significant bit, matching the book's bin_dec function.
    bits: tuple[int, ...]
    variable_lengths: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        bits = tuple(self.bits)
        if not bits or any(type(bit) is not int or bit not in (0, 1) for bit in bits):
            raise ValueError(
                "Binary genotype must contain a nonempty sequence of 0/1 bits"
            )
        object.__setattr__(self, "bits", bits)
        lengths = tuple(self.variable_lengths) or (len(bits),)
        for length in lengths:
            require_integer(length, "variable chromosome length", minimum=1)
        if sum(lengths) != len(bits):
            raise ValueError("Variable chromosome lengths must cover all genes")
        object.__setattr__(self, "variable_lengths", lengths)

    @property
    def chromosomes(self) -> tuple[BinaryGenotype, ...]:
        start = 0
        result = []
        for length in self.variable_lengths:
            result.append(BinaryGenotype(self.bits[start : start + length]))
            start += length
        return tuple(result)


@dataclass(frozen=True)
class RealGenotype:
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", finite_vector(self.values, "real genes"))


type Genotype = BinaryGenotype | RealGenotype


@dataclass(frozen=True)
class Individual:
    identifier: int
    genotype: Genotype
    phenotype: Phenotype
    objective_value: float | None = None
    selection_fitness: float | None = None

    def __post_init__(self) -> None:
        require_integer(self.identifier, "identifier", minimum=0)
        if not isinstance(self.genotype, (BinaryGenotype, RealGenotype)):
            raise ValueError("Unsupported genotype representation")
        phenotype = finite_vector(self.phenotype, "phenotype")
        if isinstance(self.genotype, BinaryGenotype) and len(
            self.genotype.variable_lengths
        ) != len(phenotype):
            raise ValueError("Binary genotype and phenotype dimensions must match")
        if isinstance(self.genotype, RealGenotype) and len(self.genotype.values) != len(
            phenotype
        ):
            raise ValueError("Real genotype and phenotype dimensions must match")
        object.__setattr__(self, "phenotype", phenotype)
        if self.objective_value is not None:
            object.__setattr__(
                self, "objective_value", finite_float(self.objective_value, "objective")
            )
        if self.selection_fitness is not None:
            fitness = finite_float(self.selection_fitness, "selection fitness")
            if self.objective_value is None or fitness < 0:
                raise ValueError(
                    "Selection fitness needs an objective and must be nonnegative"
                )
            object.__setattr__(self, "selection_fitness", fitness)


@dataclass(frozen=True)
class Population:
    individuals: tuple[Individual, ...]
    generation_index: int = 0

    def __post_init__(self) -> None:
        require_integer(self.generation_index, "generation index", minimum=0)
        individuals = tuple(self.individuals)
        if not individuals or not all(
            isinstance(item, Individual) for item in individuals
        ):
            raise ValueError("Population must contain individuals")
        if len({item.identifier for item in individuals}) != len(individuals):
            raise ValueError(
                "Individual identifiers must be unique within a population"
            )
        first = individuals[0]
        genotype_size = (
            len(first.genotype.bits)
            if isinstance(first.genotype, BinaryGenotype)
            else len(first.genotype.values)
        )
        for individual in individuals:
            size = (
                len(individual.genotype.bits)
                if isinstance(individual.genotype, BinaryGenotype)
                else len(individual.genotype.values)
            )
            if (
                type(individual.genotype) is not type(first.genotype)
                or size != genotype_size
                or len(individual.phenotype) != len(first.phenotype)
                or (
                    isinstance(first.genotype, BinaryGenotype)
                    and isinstance(individual.genotype, BinaryGenotype)
                    and individual.genotype.variable_lengths
                    != first.genotype.variable_lengths
                )
            ):
                raise ValueError("Population representations and dimensions must match")
        object.__setattr__(self, "individuals", individuals)

    def __len__(self) -> int:
        return len(self.individuals)

    def __iter__(self) -> Iterator[Individual]:
        return iter(self.individuals)
