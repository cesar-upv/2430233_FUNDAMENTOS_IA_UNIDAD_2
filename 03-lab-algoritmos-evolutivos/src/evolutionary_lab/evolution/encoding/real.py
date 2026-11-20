from random import Random

from evolutionary_lab.domain.models import Genotype, Interval, RealGenotype
from evolutionary_lab.domain.validation import finite_float
from evolutionary_lab.domain.variation import RealBoundsPolicy


def validate_real_genotype(
    genotype: Genotype, domains: tuple[Interval, ...]
) -> RealGenotype:
    if not isinstance(genotype, RealGenotype):
        raise ValueError("Real operators require real genotypes")
    if not domains or not all(isinstance(d, Interval) for d in domains):
        raise ValueError("Real operators require validated domains")
    if len(genotype.values) != len(domains):
        raise ValueError("Real genotype dimension does not match domains")
    if not all(d.contains(v) for d, v in zip(domains, genotype.values, strict=True)):
        raise ValueError("Real genotype is outside configured domains")
    return genotype


def uniform_real_value(domain: Interval, rng: Random) -> tuple[float, float]:
    draw = rng.random()
    # Clip only endpoint rounding of an in-domain uniform sample.
    value = min(
        domain.upper,
        max(domain.lower, domain.lower + (domain.upper - domain.lower) * draw),
    )
    return value, draw


def bound_real_values(
    values: tuple[float, ...], domains: tuple[Interval, ...], policy: RealBoundsPolicy
) -> tuple[RealGenotype, tuple[int, ...]]:
    if not isinstance(policy, RealBoundsPolicy):
        raise ValueError("Unsupported real bounds policy")
    if len(values) != len(domains) or not domains:
        raise ValueError("Real genotype dimension does not match domains")
    finite = tuple(finite_float(value, "real offspring") for value in values)
    outside = tuple(
        i
        for i, (value, domain) in enumerate(zip(finite, domains, strict=True))
        if not domain.contains(value)
    )
    if outside and policy == RealBoundsPolicy.REJECT:
        raise ValueError("Real offspring is outside configured domains")
    repaired = tuple(
        min(d.upper, max(d.lower, v)) for v, d in zip(finite, domains, strict=True)
    )
    genotype = RealGenotype(repaired)
    validate_real_genotype(genotype, domains)
    return genotype, outside
