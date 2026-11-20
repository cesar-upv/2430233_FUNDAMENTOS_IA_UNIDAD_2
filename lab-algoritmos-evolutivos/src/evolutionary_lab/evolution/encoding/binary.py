from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import ceil, nextafter, ulp

from evolutionary_lab.domain.models import BinaryGenotype, Interval
from evolutionary_lab.domain.validation import finite_float, require_integer


def chromosome_length(domain: Interval, precision: float) -> int:
    precision = finite_float(precision, "precision")
    if precision <= 0:
        raise ValueError("Precision must be positive")
    width = Fraction(domain.upper) - Fraction(domain.lower)
    intervals = ceil(width / Fraction(precision))
    # Integer arithmetic avoids log rounding and overflow at precision boundaries.
    return intervals.bit_length()


def genotype_to_integer(genotype: BinaryGenotype) -> int:
    return sum(bit << position for position, bit in enumerate(genotype.bits))


def genotype_from_integer(value: int, length: int) -> BinaryGenotype:
    require_integer(length, "chromosome length", minimum=1)
    require_integer(value, "genotype integer", minimum=0)
    if value.bit_length() > length:
        raise ValueError("Integer does not fit the chromosome length")
    return BinaryGenotype(tuple((value >> position) & 1 for position in range(length)))


def genotype_from_string(value: str) -> BinaryGenotype:
    if not isinstance(value, str) or not value or any(bit not in "01" for bit in value):
        raise ValueError("Binary string must contain only 0/1 digits and not be empty")
    return BinaryGenotype(tuple(int(bit) for bit in reversed(value)))


def genotype_to_string(genotype: BinaryGenotype) -> str:
    return "".join(str(bit) for bit in reversed(genotype.bits))


@dataclass(frozen=True)
class BinaryEncoding:
    domain: Interval
    length: int

    def __post_init__(self) -> None:
        if not isinstance(self.domain, Interval):
            raise ValueError("Encoding requires a validated interval")
        require_integer(self.length, "chromosome length", minimum=1)
        spacing = max(
            ulp(nextafter(self.domain.lower, self.domain.upper)),
            ulp(nextafter(self.domain.upper, self.domain.lower)),
        )
        max_intervals = int(self._width / Fraction(spacing))
        max_length = max(1, (max_intervals + 1).bit_length() - 1)
        if self.length > max_length:
            raise ValueError(
                "Encoding grid is finer than floating-point domain spacing"
            )

    @property
    def _width(self) -> Fraction:
        return Fraction(self.domain.upper) - Fraction(self.domain.lower)

    @property
    def max_integer(self) -> int:
        return (1 << self.length) - 1

    @property
    def resolution(self) -> float:
        return float(self._width / self.max_integer)

    def decode_integer(self, value: int) -> float:
        require_integer(value, "genotype integer", minimum=0)
        if value > self.max_integer:
            raise ValueError("Integer does not fit the chromosome length")
        if value == 0:
            return self.domain.lower
        if value == self.max_integer:
            return self.domain.upper
        return float(
            Fraction(self.domain.lower) + self._width * value / self.max_integer
        )

    def encode_integer(self, value: float) -> int:
        value = finite_float(value, "phenotype")
        if not self.domain.contains(value):
            raise ValueError("Phenotype is outside the encoding domain")
        position = (
            (Fraction(value) - Fraction(self.domain.lower))
            * self.max_integer
            / self._width
        )
        # Nearest grid point; exact halfway ties go toward the larger integer.
        return (2 * position.numerator + position.denominator) // (
            2 * position.denominator
        )

    def decode(self, genotype: BinaryGenotype) -> float:
        if not isinstance(genotype, BinaryGenotype):
            raise ValueError("Encoding requires a binary genotype")
        if genotype.variable_lengths != (self.length,):
            raise ValueError("Genotype length does not match the encoding")
        return self.decode_integer(genotype_to_integer(genotype))

    def encode(self, value: float) -> BinaryGenotype:
        return genotype_from_integer(self.encode_integer(value), self.length)


def combine_chromosomes(chromosomes: tuple[BinaryGenotype, ...]) -> BinaryGenotype:
    if not chromosomes or any(len(item.variable_lengths) != 1 for item in chromosomes):
        raise ValueError("Expected one binary chromosome per variable")
    return BinaryGenotype(
        tuple(bit for item in chromosomes for bit in item.bits),
        tuple(len(item.bits) for item in chromosomes),
    )


@dataclass(frozen=True)
class BinaryVectorEncoding:
    variables: tuple[BinaryEncoding, ...]

    def __post_init__(self) -> None:
        variables = tuple(self.variables)
        if not variables or not all(
            isinstance(item, BinaryEncoding) for item in variables
        ):
            raise ValueError("Vector encoding requires binary variable encodings")
        object.__setattr__(self, "variables", variables)

    @classmethod
    def from_parameters(
        cls, domains: tuple[Interval, ...], precision: tuple[float, ...]
    ) -> BinaryVectorEncoding:
        if len(domains) != len(precision):
            raise ValueError("Each domain needs a precision")
        return cls(
            tuple(
                BinaryEncoding(d, chromosome_length(d, p))
                for d, p in zip(domains, precision, strict=True)
            )
        )

    @property
    def lengths(self) -> tuple[int, ...]:
        return tuple(item.length for item in self.variables)

    def decode(self, genotype: BinaryGenotype) -> tuple[float, ...]:
        if genotype.variable_lengths != self.lengths:
            raise ValueError("Genotype variable lengths do not match the encoding")
        return tuple(
            encoding.decode(chromosome)
            for encoding, chromosome in zip(
                self.variables, genotype.chromosomes, strict=True
            )
        )

    def encode(self, phenotype: tuple[float, ...]) -> BinaryGenotype:
        if len(phenotype) != len(self.variables):
            raise ValueError("Phenotype dimension does not match the encoding")
        return combine_chromosomes(
            tuple(
                encoding.encode(value)
                for encoding, value in zip(self.variables, phenotype, strict=True)
            )
        )
