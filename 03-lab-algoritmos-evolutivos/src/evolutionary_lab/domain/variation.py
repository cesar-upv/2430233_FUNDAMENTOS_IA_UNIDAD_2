from dataclasses import dataclass
from enum import StrEnum

from evolutionary_lab.domain.models import BinaryGenotype, Phenotype, RealGenotype


class MutationMethod(StrEnum):
    BIT_FLIP = "bit_flip"
    UNIFORM_RESET = "uniform_reset"


class RealBoundsPolicy(StrEnum):
    REJECT = "reject"
    CLIP = "clip"


class RealCrossoverMethod(StrEnum):
    ONE_POINT = "one_point"
    UNIFORM = "uniform"
    ARITHMETIC = "arithmetic"
    SBX = "sbx"


class SbxFormula(StrEnum):
    BOOK_LITERAL = "book_literal"
    CONTINUOUS = "continuous"


class ReproductionPolicy(StrEnum):
    BOOK_REFERENCE = "book_reference"
    PAIRWISE = "pairwise"


@dataclass(frozen=True)
class CrossoverResult:
    parents: tuple[BinaryGenotype, BinaryGenotype]
    offspring: tuple[BinaryGenotype, BinaryGenotype]
    cut_point: int | None
    random_value: float | None = None
    cut_points: tuple[int, ...] = ()


@dataclass(frozen=True)
class MutationResult:
    original: BinaryGenotype
    genotype: BinaryGenotype
    random_values: tuple[float, ...]
    mutated_positions: tuple[int, ...]


@dataclass(frozen=True)
class RealMutationResult:
    original: RealGenotype
    genotype: RealGenotype
    random_values: tuple[float, ...]
    mutated_positions: tuple[int, ...]
    replacement_draws: tuple[float | None, ...]


@dataclass(frozen=True)
class RealCrossoverResult:
    parents: tuple[RealGenotype, RealGenotype]
    offspring: tuple[RealGenotype, RealGenotype]
    method: RealCrossoverMethod
    applied: bool
    random_value: float
    raw_offspring: tuple[Phenotype, Phenotype]
    repaired_positions: tuple[tuple[int, ...], tuple[int, ...]] = ((), ())
    cut_point: int | None = None
    gene_draws: tuple[float, ...] = ()
    swapped_positions: tuple[int, ...] = ()
    alpha: float | None = None
    sbx_draw: float | None = None
    beta: float | None = None
