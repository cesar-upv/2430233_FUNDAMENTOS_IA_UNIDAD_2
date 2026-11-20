from math import inf, nan, nextafter, ulp

import pytest

from evolutionary_lab.domain.models import BinaryGenotype, Interval, RealGenotype
from evolutionary_lab.evolution.encoding.binary import (
    BinaryEncoding,
    chromosome_length,
    genotype_from_integer,
    genotype_from_string,
    genotype_to_integer,
    genotype_to_string,
)


def test_unit_interval_uses_ten_bits_and_exact_endpoints() -> None:
    domain = Interval(0, 1)
    length = chromosome_length(domain, 0.001)
    encoding = BinaryEncoding(domain, length)
    assert length == 10 and encoding.max_integer == 1023
    assert encoding.resolution == pytest.approx(1 / 1023)
    assert encoding.resolution <= 0.001 < 1 / 511
    assert encoding.decode_integer(0) == domain.lower
    assert encoding.decode_integer(1023) == domain.upper
    assert encoding.encode_integer(domain.lower) == 0
    assert encoding.encode_integer(domain.upper) == 1023
    assert encoding.encode_integer(0.1) == 102
    assert abs(encoding.decode(encoding.encode(0.1)) - 0.1) <= encoding.resolution / 2


def test_book_bit_order_and_msb_first_strings_preserve_leading_zeros() -> None:
    genotype = genotype_from_string("00101100")
    assert genotype.bits == (0, 0, 1, 1, 0, 1, 0, 0)
    assert genotype_to_integer(genotype) == 44
    assert genotype_from_integer(44, 8) == genotype
    assert genotype_to_string(genotype) == "00101100"
    assert genotype_to_string(genotype_from_integer(0, 10)) == "0000000000"


@pytest.mark.parametrize("value", [0, 1, 102, 511, 512, 1023])
def test_genotype_and_phenotype_round_trips_preserve_length(value: int) -> None:
    encoding = BinaryEncoding(Interval(0, 1), 10)
    genotype = genotype_from_integer(value, 10)
    phenotype = encoding.decode(genotype)
    assert len(genotype.bits) == 10 and 0 <= phenotype <= 1
    assert genotype_to_integer(genotype) == value
    assert genotype_from_string(genotype_to_string(genotype)) == genotype
    assert encoding.encode(phenotype) == genotype


def test_nearest_quantization_breaks_exact_ties_upward() -> None:
    encoding = BinaryEncoding(Interval(0, 1), 10)
    assert encoding.encode_integer(0.5) == 512
    assert encoding.encode_integer(nextafter(0.5, -inf)) == 511
    assert encoding.encode_integer(nextafter(0.5, inf)) == 512


def test_shifted_domain_quantization_error_is_bounded() -> None:
    encoding = BinaryEncoding(Interval(-2, 4), chromosome_length(Interval(-2, 4), 0.1))
    for value in (-2.0, -1.99, -0.5, 0.0, 2.4, 3.99999, 4.0):
        decoded = encoding.decode(encoding.encode(value))
        assert encoding.domain.contains(decoded)
        assert abs(decoded - value) <= encoding.resolution / 2 + ulp(value)
    assert encoding.decode_integer(0) == -2
    assert encoding.decode_integer(encoding.max_integer) == 4


def test_length_calculation_handles_boundaries_without_log_rounding() -> None:
    domain = Interval(0, 3)
    assert chromosome_length(domain, 1.0) == 2
    assert chromosome_length(domain, nextafter(1.0, 0.0)) == 3
    assert chromosome_length(domain, nextafter(1.0, inf)) == 2
    assert chromosome_length(Interval(0, 1), 2.0) == 1
    assert chromosome_length(Interval(0, 1), nextafter(0.0, inf)) == 1075


@pytest.mark.parametrize("precision", [0, -0.001, nan, inf, True])
def test_invalid_precision_is_rejected(precision: float) -> None:
    with pytest.raises(ValueError):
        chromosome_length(Interval(0, 1), precision)


@pytest.mark.parametrize("text", ["", "2", "10 1"])
def test_invalid_binary_strings_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        genotype_from_string(text)


@pytest.mark.parametrize("length", [0, -1, True])
def test_invalid_lengths_are_rejected(length: int) -> None:
    with pytest.raises(ValueError):
        genotype_from_integer(0, length)
    with pytest.raises(ValueError):
        BinaryEncoding(Interval(0, 1), length)


@pytest.mark.parametrize("value", [-1, 1024, True])
def test_invalid_integers_are_rejected(value: int) -> None:
    with pytest.raises(ValueError):
        genotype_from_integer(value, 10)
    with pytest.raises(ValueError):
        BinaryEncoding(Interval(0, 1), 10).decode_integer(value)


@pytest.mark.parametrize("value", [nextafter(0.0, -inf), nextafter(1.0, inf), nan])
def test_invalid_phenotypes_are_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        BinaryEncoding(Interval(0, 1), 10).encode(value)


def test_decoding_rejects_a_different_chromosome_length() -> None:
    with pytest.raises(ValueError, match="length"):
        BinaryEncoding(Interval(0, 1), 10).decode(BinaryGenotype((0,)))


def test_decoding_rejects_an_incompatible_representation() -> None:
    with pytest.raises(ValueError, match="binary genotype"):
        BinaryEncoding(Interval(0, 1), 10).decode(RealGenotype((0.1,)))


def test_unrepresentable_grids_fail_and_adjacent_endpoints_still_work() -> None:
    with pytest.raises(ValueError, match="floating-point"):
        BinaryEncoding(Interval(0, 1), 54)
    domain = Interval(1, nextafter(1.0, inf))
    encoding = BinaryEncoding(domain, 1)
    assert encoding.decode_integer(0) == domain.lower
    assert encoding.decode_integer(1) == domain.upper
    with pytest.raises(ValueError, match="floating-point"):
        BinaryEncoding(domain, 2)


def test_large_domain_conversion_avoids_intermediate_float_overflow() -> None:
    domain = Interval(0, 1e308)
    encoding = BinaryEncoding(domain, chromosome_length(domain, 1e300))
    value = encoding.max_integer // 2
    decoded = encoding.decode_integer(value)
    assert domain.contains(decoded)
    assert encoding.encode_integer(decoded) == value
