from dataclasses import FrozenInstanceError
from math import inf, nan
from random import Random

import pytest

from evolutionary_lab.domain.models import BinaryGenotype, RealGenotype
from evolutionary_lab.evolution.crossover import cross_at_point, one_point_crossover
from evolutionary_lab.evolution.mutation import bit_flip_mutation


class DrawRandom(Random):
    def __init__(self, draws: tuple[float, ...]) -> None:
        super().__init__(0)
        self.draws = iter(draws)

    def random(self) -> float:
        return next(self.draws)


def test_one_point_exchange_is_complementary_and_preserves_lsb_order() -> None:
    first, second = BinaryGenotype((0, 0, 0, 0)), BinaryGenotype((1, 1, 1, 1))
    result = cross_at_point(first, second, 2)
    assert result.parents == (first, second)
    assert result.offspring == (
        BinaryGenotype((0, 0, 1, 1)),
        BinaryGenotype((1, 1, 0, 0)),
    )
    assert result.cut_point == 2 and result.random_value is None
    assert first.bits == (0, 0, 0, 0) and second.bits == (1, 1, 1, 1)
    with pytest.raises(FrozenInstanceError):
        result.cut_point = 1  # type: ignore[misc]


@pytest.mark.parametrize("rate", [0.0, 1.0, 0.7])
def test_pair_probability_and_reproducible_shared_cut(rate: float) -> None:
    first, second = BinaryGenotype((0,) * 10), BinaryGenotype((1,) * 10)
    rng = Random(42)
    before = rng.getstate()
    result = one_point_crossover(first, second, rng, crossover_probability=rate)
    assert result == one_point_crossover(
        first, second, Random(42), crossover_probability=rate
    )
    assert rng.getstate() != before
    assert result.random_value is not None
    if result.random_value < rate:
        assert result.cut_point is not None and 1 <= result.cut_point <= 9
        cut = result.cut_point
        assert result.offspring[0].bits == first.bits[:cut] + second.bits[cut:]
        assert result.offspring[1].bits == second.bits[:cut] + first.bits[cut:]
    else:
        assert result.offspring == result.parents and result.cut_point is None


def test_probability_gate_uses_strict_less_than() -> None:
    parents = (BinaryGenotype((0, 0)), BinaryGenotype((1, 1)))
    result = one_point_crossover(
        *parents, DrawRandom((0.5,)), crossover_probability=0.5
    )
    assert result.offspring == parents and result.cut_point is None
    mutation = bit_flip_mutation(
        BinaryGenotype((0, 0, 1)),
        DrawRandom((0.499, 0.5, 0.9)),
        mutation_probability=0.5,
    )
    assert mutation.mutated_positions == (0,)
    assert mutation.genotype.bits == (1, 0, 1)


@pytest.mark.parametrize("rate", [-0.1, 1.1, nan, inf, -inf, True])
def test_invalid_rates_fail_before_random_draws(rate: float) -> None:
    rng = Random(42)
    before = rng.getstate()
    genes = BinaryGenotype((0, 1))
    with pytest.raises(ValueError):
        one_point_crossover(genes, genes, rng, crossover_probability=rate)
    with pytest.raises(ValueError):
        bit_flip_mutation(genes, rng, mutation_probability=rate)
    assert rng.getstate() == before


def test_incompatible_chromosomes_and_active_short_crossover_are_rejected() -> None:
    rng = Random(42)
    before = rng.getstate()
    short, longer = BinaryGenotype((0,)), BinaryGenotype((0, 1))
    real = RealGenotype((0.1,))
    for first, second in ((short, longer), (short, short), (real, real), (real, short)):
        with pytest.raises(ValueError):
            one_point_crossover(first, second, rng, crossover_probability=1)
    with pytest.raises(ValueError, match="binary"):
        bit_flip_mutation(real, rng, mutation_probability=1)
    assert rng.getstate() == before
    skipped = one_point_crossover(short, short, rng, crossover_probability=0)
    assert skipped.offspring == (short, short) and skipped.cut_point is None


@pytest.mark.parametrize("cut", [-1, 0, 4, 5, True, 1.5])
def test_invalid_internal_cuts(cut: int) -> None:
    genes = BinaryGenotype((0,) * 4)
    with pytest.raises(ValueError):
        cross_at_point(genes, genes, cut)


def test_book_endpoint_cuts_require_explicit_opt_in() -> None:
    parents = (BinaryGenotype((0, 0)), BinaryGenotype((1, 1)))
    assert cross_at_point(*parents, 0, allow_endpoints=True).offspring == parents[::-1]
    assert cross_at_point(*parents, 2, allow_endpoints=True).offspring == parents
    with pytest.raises(ValueError):
        cross_at_point(*parents, 3, allow_endpoints=True)


@pytest.mark.parametrize("rate", [0, 1, 0.35])
def test_mutation_is_per_bit_reproducible_and_records_every_draw(rate: float) -> None:
    genes = BinaryGenotype((0, 1, 0, 1, 1, 0, 0, 1))
    rng = Random(42)
    result = bit_flip_mutation(genes, rng, mutation_probability=rate)
    assert result == bit_flip_mutation(genes, Random(42), mutation_probability=rate)
    expected_rng = Random(42)
    draws = tuple(expected_rng.random() for _ in genes.bits)
    assert result.random_values == draws
    assert rng.getstate() == expected_rng.getstate()
    assert result.mutated_positions == tuple(
        i for i, draw in enumerate(draws) if draw < rate
    )
    assert len(result.genotype.bits) == len(genes.bits)
    assert all(bit in (0, 1) for bit in result.genotype.bits)
    assert (
        tuple(
            i
            for i, (a, b) in enumerate(
                zip(genes.bits, result.genotype.bits, strict=True)
            )
            if a != b
        )
        == result.mutated_positions
    )
    if rate == 0:
        assert result.genotype == genes
    if rate == 1:
        assert result.genotype.bits == tuple(1 - bit for bit in genes.bits)
    with pytest.raises(FrozenInstanceError):
        result.mutated_positions = ()  # type: ignore[misc]


def test_single_bit_mutation_and_empty_representation_policy() -> None:
    genes = BinaryGenotype((1,))
    assert bit_flip_mutation(
        genes, Random(42), mutation_probability=1
    ).genotype.bits == (0,)
    with pytest.raises(ValueError, match="nonempty"):
        BinaryGenotype(())
