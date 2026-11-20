from dataclasses import replace
from math import fsum, inf, nan, nextafter
from random import Random

import pytest

from evolutionary_lab.domain.models import (
    BinaryGenotype,
    Individual,
    OptimizationDirection,
    Population,
    RealGenotype,
)
from evolutionary_lab.domain.selection import (
    SelectionMethod,
    SelectionOperator,
    TournamentTiePolicy,
    ZeroWeightPolicy,
)
from evolutionary_lab.evolution.selection import (
    binary_tournament,
    roulette,
    select,
    selection_distribution,
    stochastic_universal_sampling,
)


class DrawRandom(Random):
    def __init__(self, draws: tuple[float, ...]) -> None:
        super().__init__(0)
        self.draws = iter(draws)

    def random(self) -> float:
        return next(self.draws)


def population(*weights: float) -> Population:
    return Population(
        tuple(
            Individual(index, BinaryGenotype((0, 1)), (0.1,), weight, weight)
            for index, weight in enumerate(weights)
        )
    )


def test_distribution_and_half_open_intervals_skip_zero_weights() -> None:
    original = population(0.0, 1.0, 0.0, 3.0, 0.0)
    draws = (0.0, nextafter(0.25, 0.0), 0.25, nextafter(1.0, 0.0))
    result = roulette(original, 4, DrawRandom(draws))
    assert result.distribution is not None
    assert result.distribution.probabilities == (0, 0.25, 0, 0.75, 0)
    assert result.distribution.cumulative == (0, 0, 0.25, 0.25, 1, 1)
    assert not result.distribution.used_uniform_fallback
    assert result.indices == (1, 1, 3, 3)
    assert result.selected == tuple(original.individuals[i] for i in result.indices)
    assert result.random_values == result.positions == draws
    assert original.individuals[0].selection_fitness == 0


@pytest.mark.parametrize("weights", [(), (-1.0, 2.0), (nan,), (inf,), (-inf,), (True,)])
def test_invalid_weights_are_rejected_even_with_uniform_policy(
    weights: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError):
        selection_distribution(weights, zero_weight_policy=ZeroWeightPolicy.UNIFORM)


@pytest.mark.parametrize("operator", [roulette, stochastic_universal_sampling])
def test_zero_total_policy_is_explicit_and_validates_before_drawing(
    operator: SelectionOperator,
) -> None:
    rng = Random(42)
    state = rng.getstate()
    with pytest.raises(ValueError, match="zero total"):
        operator(population(0, 0), 3, rng)
    assert rng.getstate() == state
    result = select(
        population(0, 0),
        3,
        rng,
        method=SelectionMethod.ROULETTE
        if operator is roulette
        else SelectionMethod.SUS,
        zero_weight_policy=ZeroWeightPolicy.UNIFORM,
    )
    assert result.distribution is not None
    assert result.distribution.used_uniform_fallback
    assert result.distribution.probabilities == (0.5, 0.5)
    assert len(result.selected) == 3


def test_normalization_handles_overflowing_finite_sum_and_tiny_weights() -> None:
    assert selection_distribution((1e308, 1e308)).probabilities == (0.5, 0.5)
    assert selection_distribution((5e-324, 5e-324)).probabilities == (0.5, 0.5)
    distribution = selection_distribution((1.0,) * 10 + (0.0,))
    assert fsum(distribution.probabilities) == pytest.approx(1)
    assert distribution.cumulative[-2:] == (1, 1)
    assert all(
        a <= b
        for a, b in zip(
            distribution.cumulative, distribution.cumulative[1:], strict=False
        )
    )


def test_sus_spacing_and_single_draw() -> None:
    result = stochastic_universal_sampling(
        population(1, 1, 1, 1), 4, DrawRandom((0.4,))
    )
    assert result.random_values == (0.4,)
    assert result.positions == pytest.approx((0.1, 0.35, 0.6, 0.85))
    assert result.indices == (0, 1, 2, 3)


def test_sus_rounded_last_pointer_stays_in_range() -> None:
    result = stochastic_universal_sampling(
        population(0, 1, 0), 3, DrawRandom((nextafter(1.0, 0.0),))
    )
    assert all(0 <= value < 1 for value in result.positions)
    assert result.indices == (1, 1, 1)


@pytest.mark.parametrize("method", list(SelectionMethod))
def test_selection_reproducibility_duplicates_and_rng_consumption(
    method: SelectionMethod,
) -> None:
    original = population(1)
    rng = Random(42)
    before = rng.getstate()
    result = select(original, 10, rng, method=method)
    assert result == select(original, 10, Random(42), method=method)
    assert result.indices == (0,) * 10
    assert result.selected == (original.individuals[0],) * 10
    assert rng.getstate() != before


@pytest.mark.parametrize(
    "operator", [roulette, stochastic_universal_sampling, binary_tournament]
)
def test_common_contract_zero_count_and_invalid_counts(
    operator: SelectionOperator,
) -> None:
    rng = Random(42)
    before = rng.getstate()
    result = operator(population(1, 2), 0, rng)
    assert result.selected == result.indices == ()
    assert rng.getstate() == before
    for count in (-1, True, 1.5):
        with pytest.raises(ValueError):
            operator(population(1), count, rng)  # type: ignore[arg-type]
    assert rng.getstate() == before


def test_tournaments_record_competitors_and_pick_better_fitness() -> None:
    result = binary_tournament(population(1, 9, 2), 20, Random(42))
    assert result.distribution is None
    assert len(result.tournaments) == 20
    for draw, selected in zip(result.tournaments, result.selected, strict=True):
        weights = (1, 9, 2)
        assert selected.selection_fitness == max(weights[i] for i in draw.participants)
        assert draw.winner_index in draw.participants


def test_tournament_objective_only_supports_signed_minimization_and_real_data() -> None:
    original = Population(
        tuple(
            Individual(i, RealGenotype((0.1,)), (0.1,), value)
            for i, value in enumerate((-2, 1, -7))
        )
    )
    result = binary_tournament(
        original, 20, Random(42), direction=OptimizationDirection.MINIMIZE
    )
    for draw, selected in zip(result.tournaments, result.selected, strict=True):
        assert selected.objective_value == min(
            original.individuals[i].objective_value for i in draw.participants
        )
    with pytest.raises(ValueError, match="explicit fitness"):
        roulette(original, 1, Random(42))


def test_tournament_ties_are_seeded_or_first_by_explicit_policy() -> None:
    original = population(0, 0, 0)
    result = binary_tournament(original, 20, Random(42))
    assert result == binary_tournament(original, 20, Random(42))
    for draw in result.tournaments:
        assert draw.tie_draw is not None
        assert draw.winner_index == draw.participants[0 if draw.tie_draw < 0.5 else 1]
    first = binary_tournament(
        original, 20, Random(42), tie_policy=TournamentTiePolicy.FIRST
    )
    assert all(
        draw.winner_index == draw.participants[0] and draw.tie_draw is None
        for draw in first.tournaments
    )


def test_tournament_rejects_unevaluated_or_mixed_fitness() -> None:
    original = population(1, 2)
    for invalid in (
        Population((Individual(0, BinaryGenotype((0,)), (0.0,)),)),
        replace(
            original,
            individuals=(
                original.individuals[0],
                replace(original.individuals[1], selection_fitness=None),
            ),
        ),
    ):
        with pytest.raises(ValueError):
            binary_tournament(invalid, 1, Random(42))


def test_invalid_policies_are_rejected() -> None:
    with pytest.raises(ValueError, match="selection method"):
        select(population(1), 1, Random(42), method="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="zero-weight"):
        selection_distribution((1,), zero_weight_policy="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="tie policy"):
        binary_tournament(population(1), 1, Random(42), tie_policy="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="direction"):
        binary_tournament(population(1), 1, Random(42), direction="unknown")  # type: ignore[arg-type]
