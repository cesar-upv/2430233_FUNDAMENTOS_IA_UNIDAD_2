from dataclasses import replace
from random import Random

from evolutionary_lab.domain.models import BinaryGenotype, Genotype
from evolutionary_lab.domain.validation import probability, require_integer
from evolutionary_lab.domain.variation import CrossoverResult
from evolutionary_lab.evolution.encoding.binary import combine_chromosomes


def _binary_parents(
    first: Genotype, second: Genotype
) -> tuple[BinaryGenotype, BinaryGenotype]:
    if not isinstance(first, BinaryGenotype) or not isinstance(second, BinaryGenotype):
        raise ValueError("One-point crossover requires binary genotypes")
    if first.variable_lengths != second.variable_lengths:
        raise ValueError("Crossover requires equal chromosome lengths")
    return first, second


def cross_at_point(
    first: Genotype,
    second: Genotype,
    cut_point: int,
    *,
    allow_endpoints: bool = False,
) -> CrossoverResult:
    """Cut positions count genes from the LSB-first start of each chromosome."""
    parent_a, parent_b = _binary_parents(first, second)
    if len(parent_a.variable_lengths) != 1:
        raise ValueError("Multivariable crossover requires per-variable cut points")
    length = len(parent_a.bits)
    require_integer(cut_point, "cut point")
    minimum, maximum = (0, length) if allow_endpoints else (1, length - 1)
    if not minimum <= cut_point <= maximum:
        raise ValueError("Cut point is outside the permitted chromosome boundaries")
    return CrossoverResult(
        parents=(parent_a, parent_b),
        offspring=(
            BinaryGenotype(parent_a.bits[:cut_point] + parent_b.bits[cut_point:]),
            BinaryGenotype(parent_b.bits[:cut_point] + parent_a.bits[cut_point:]),
        ),
        cut_point=cut_point,
    )


def cross_at_points(
    first: Genotype,
    second: Genotype,
    cut_points: tuple[int, ...],
    *,
    allow_endpoints: bool = False,
) -> CrossoverResult:
    parents = _binary_parents(first, second)
    if len(cut_points) != len(parents[0].variable_lengths):
        raise ValueError("Crossover needs one cut point per variable")
    results = tuple(
        cross_at_point(a, b, cut, allow_endpoints=allow_endpoints)
        for a, b, cut in zip(
            parents[0].chromosomes, parents[1].chromosomes, cut_points, strict=True
        )
    )
    if len(results) == 1:
        return results[0]
    return CrossoverResult(
        parents,
        (
            combine_chromosomes(tuple(item.offspring[0] for item in results)),
            combine_chromosomes(tuple(item.offspring[1] for item in results)),
        ),
        None,
        cut_points=cut_points,
    )


def one_point_crossover(
    first: Genotype,
    second: Genotype,
    rng: Random,
    *,
    crossover_probability: float,
) -> CrossoverResult:
    parents = _binary_parents(first, second)
    rate = probability(crossover_probability, "crossover probability")
    lengths = parents[0].variable_lengths
    if min(lengths) < 2 and rate > 0:
        raise ValueError("Active one-point crossover requires at least two genes")
    draw = rng.random()
    if draw >= rate:
        return CrossoverResult(parents, parents, None, draw)
    result = cross_at_points(
        *parents, tuple(rng.randrange(1, length) for length in lengths)
    )
    return replace(result, random_value=draw)
