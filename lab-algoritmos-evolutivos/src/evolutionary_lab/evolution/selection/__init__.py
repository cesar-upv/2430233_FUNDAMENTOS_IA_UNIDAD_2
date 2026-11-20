from bisect import bisect_right
from collections.abc import Sequence
from math import fsum, nextafter
from random import Random

from evolutionary_lab.domain.models import OptimizationDirection, Population
from evolutionary_lab.domain.selection import (
    SelectionDistribution,
    SelectionMethod,
    SelectionResult,
    TournamentDraw,
    TournamentTiePolicy,
    ZeroWeightPolicy,
)
from evolutionary_lab.domain.validation import finite_float, require_integer


def selection_distribution(
    weights: Sequence[float],
    *,
    zero_weight_policy: ZeroWeightPolicy = ZeroWeightPolicy.ERROR,
) -> SelectionDistribution:
    if not isinstance(zero_weight_policy, ZeroWeightPolicy):
        raise ValueError("Unsupported zero-weight policy")
    values = tuple(finite_float(value, "selection weight") for value in weights)
    if not values or any(value < 0 for value in values):
        raise ValueError("Selection weights must be nonempty and nonnegative")
    maximum = max(values)
    fallback = maximum == 0
    if fallback:
        if zero_weight_policy == ZeroWeightPolicy.ERROR:
            raise ValueError("Selection weights have zero total")
        probabilities = (1.0 / len(values),) * len(values)
    else:
        # Proportional rescaling prevents overflow without changing relative weights.
        scaled = tuple(value / maximum for value in values)
        total = fsum(scaled)
        probabilities = tuple(value / total for value in scaled)

    last_positive = max(i for i, value in enumerate(probabilities) if value > 0)
    cumulative = [0.0]
    for index, probability in enumerate(probabilities):
        # Close at the last positive weight, leaving trailing zero intervals empty.
        boundary = (
            1.0 if index >= last_positive else min(1.0, cumulative[-1] + probability)
        )
        cumulative.append(boundary)
    return SelectionDistribution(
        probabilities, tuple(cumulative), zero_weight_policy, fallback
    )


def _distribution(
    population: Population, zero_weight_policy: ZeroWeightPolicy
) -> SelectionDistribution:
    weights: list[float] = []
    for individual in population:
        if individual.selection_fitness is None:
            raise ValueError("Proportional selection requires explicit fitness weights")
        weights.append(individual.selection_fitness)
    return selection_distribution(weights, zero_weight_policy=zero_weight_policy)


def _sample(
    population: Population,
    method: SelectionMethod,
    distribution: SelectionDistribution,
    random_values: tuple[float, ...],
    positions: tuple[float, ...],
) -> SelectionResult:
    # Half-open intervals [q_i, q_(i+1)) skip every zero-width interval.
    indices = tuple(bisect_right(distribution.cumulative, u) - 1 for u in positions)
    return SelectionResult(
        method=method,
        selected=tuple(population.individuals[index] for index in indices),
        indices=indices,
        distribution=distribution,
        random_values=random_values,
        positions=positions,
    )


def roulette(
    population: Population,
    count: int,
    rng: Random,
    *,
    zero_weight_policy: ZeroWeightPolicy = ZeroWeightPolicy.ERROR,
) -> SelectionResult:
    require_integer(count, "selection count", minimum=0)
    distribution = _distribution(population, zero_weight_policy)
    draws = tuple(rng.random() for _ in range(count))
    return _sample(population, SelectionMethod.ROULETTE, distribution, draws, draws)


def stochastic_universal_sampling(
    population: Population,
    count: int,
    rng: Random,
    *,
    zero_weight_policy: ZeroWeightPolicy = ZeroWeightPolicy.ERROR,
) -> SelectionResult:
    require_integer(count, "selection count", minimum=0)
    distribution = _distribution(population, zero_weight_policy)
    draws: tuple[float, ...] = (rng.random(),) if count else ()
    # Rounding a final pointer to 1 must not create an out-of-range index.
    positions = tuple(
        min((draws[0] + index) / count, nextafter(1.0, 0.0)) for index in range(count)
    )
    return _sample(population, SelectionMethod.SUS, distribution, draws, positions)


def binary_tournament(
    population: Population,
    count: int,
    rng: Random,
    *,
    direction: OptimizationDirection = OptimizationDirection.MAXIMIZE,
    tie_policy: TournamentTiePolicy = TournamentTiePolicy.RANDOM,
) -> SelectionResult:
    require_integer(count, "selection count", minimum=0)
    if not isinstance(direction, OptimizationDirection):
        raise ValueError("Unsupported optimization direction")
    if not isinstance(tie_policy, TournamentTiePolicy):
        raise ValueError("Unsupported tournament tie policy")
    if any(individual.objective_value is None for individual in population):
        raise ValueError("Tournament selection requires evaluated individuals")
    weighted = all(item.selection_fitness is not None for item in population)
    if not weighted and any(item.selection_fitness is not None for item in population):
        raise ValueError(
            "Selection fitness must be available for all or no individuals"
        )
    scores: list[float] = []
    for item in population:
        value = item.selection_fitness if weighted else item.objective_value
        assert value is not None
        scores.append(value)
    maximize = weighted or direction == OptimizationDirection.MAXIMIZE
    tournaments: list[TournamentDraw] = []
    for _ in range(count):
        # Competitors are sampled with replacement, including singleton populations.
        first, second = rng.randrange(len(population)), rng.randrange(len(population))
        tie_draw = None
        if scores[first] == scores[second]:
            if tie_policy == TournamentTiePolicy.RANDOM:
                tie_draw = rng.random()
            winner = first if tie_draw is None or tie_draw < 0.5 else second
        else:
            first_better = scores[first] > scores[second]
            winner = first if first_better == maximize else second
        tournaments.append(TournamentDraw((first, second), winner, tie_draw))
    indices = tuple(draw.winner_index for draw in tournaments)
    return SelectionResult(
        method=SelectionMethod.BINARY_TOURNAMENT,
        selected=tuple(population.individuals[index] for index in indices),
        indices=indices,
        tournaments=tuple(tournaments),
    )


def select(
    population: Population,
    count: int,
    rng: Random,
    *,
    method: SelectionMethod = SelectionMethod.ROULETTE,
    zero_weight_policy: ZeroWeightPolicy = ZeroWeightPolicy.ERROR,
    direction: OptimizationDirection = OptimizationDirection.MAXIMIZE,
    tie_policy: TournamentTiePolicy = TournamentTiePolicy.RANDOM,
) -> SelectionResult:
    if not isinstance(method, SelectionMethod):
        raise ValueError("Unsupported selection method")
    if method == SelectionMethod.ROULETTE:
        return roulette(population, count, rng, zero_weight_policy=zero_weight_policy)
    if method == SelectionMethod.SUS:
        return stochastic_universal_sampling(
            population, count, rng, zero_weight_policy=zero_weight_policy
        )
    return binary_tournament(
        population, count, rng, direction=direction, tie_policy=tie_policy
    )
