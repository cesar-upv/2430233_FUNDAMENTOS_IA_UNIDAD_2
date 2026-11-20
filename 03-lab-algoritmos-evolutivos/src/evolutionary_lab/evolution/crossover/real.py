from math import pow
from random import Random

from evolutionary_lab.domain.models import Genotype, Interval
from evolutionary_lab.domain.validation import finite_float, probability
from evolutionary_lab.domain.variation import (
    RealBoundsPolicy,
    RealCrossoverMethod,
    RealCrossoverResult,
    SbxFormula,
)
from evolutionary_lab.evolution.encoding.real import (
    bound_real_values,
    validate_real_genotype,
)


def sbx_beta(draw: float, distribution_index: float, formula: SbxFormula) -> float:
    draw = finite_float(draw, "SBX draw")
    index = finite_float(distribution_index, "SBX distribution index")
    if not 0 <= draw < 1 or index < 0 or not isinstance(formula, SbxFormula):
        raise ValueError("Invalid SBX parameters")
    power = 1 / (index + 1)
    if draw < 0.5:
        # The scan prints 2*u**power, without parentheses around 2*u.
        return (
            2 * pow(draw, power)
            if formula == SbxFormula.BOOK_LITERAL
            else pow(2 * draw, power)
        )
    return pow(1 / (2 * (1 - draw)), power)


def real_crossover(
    first: Genotype,
    second: Genotype,
    domains: tuple[Interval, ...],
    rng: Random,
    *,
    method: RealCrossoverMethod,
    crossover_probability: float,
    swap_probability: float = 0.5,
    arithmetic_alpha: float = 0.5,
    distribution_index: float = 1.0,
    sbx_formula: SbxFormula = SbxFormula.BOOK_LITERAL,
    bounds_policy: RealBoundsPolicy = RealBoundsPolicy.CLIP,
) -> RealCrossoverResult:
    parents = (
        validate_real_genotype(first, domains),
        validate_real_genotype(second, domains),
    )
    if not isinstance(method, RealCrossoverMethod) or not isinstance(
        bounds_policy, RealBoundsPolicy
    ):
        raise ValueError("Unsupported real crossover settings")
    rate = probability(crossover_probability, "crossover probability")
    swap = probability(swap_probability, "uniform swap probability")
    alpha = probability(arithmetic_alpha, "arithmetic alpha")
    sbx_beta(0.0, distribution_index, sbx_formula)
    dimension = len(domains)
    if method == RealCrossoverMethod.ONE_POINT and dimension < 2 and rate > 0:
        raise ValueError("Real one-point crossover requires at least two variables")
    a, b = parents[0].values, parents[1].values
    draw = rng.random()
    if draw >= rate:
        return RealCrossoverResult(parents, parents, method, False, draw, (a, b))
    cut = None
    gene_draws: tuple[float, ...] = ()
    swapped: tuple[int, ...] = ()
    sbx_draw = beta = None
    if method == RealCrossoverMethod.ONE_POINT:
        cut = rng.randrange(1, dimension)
        raw = (a[:cut] + b[cut:], b[:cut] + a[cut:])
    elif method == RealCrossoverMethod.UNIFORM:
        gene_draws = tuple(rng.random() for _ in domains)
        swapped = tuple(i for i, u in enumerate(gene_draws) if u < swap)
        raw = (
            tuple(b[i] if u < swap else a[i] for i, u in enumerate(gene_draws)),
            tuple(a[i] if u < swap else b[i] for i, u in enumerate(gene_draws)),
        )
    elif method == RealCrossoverMethod.ARITHMETIC:
        raw = (
            tuple(alpha * x + (1 - alpha) * y for x, y in zip(a, b, strict=True)),
            tuple(alpha * y + (1 - alpha) * x for x, y in zip(a, b, strict=True)),
        )
    else:
        # Project 2 draws one alpha/beta for the entire pair, before the gene loop.
        sbx_draw = rng.random()
        beta = sbx_beta(sbx_draw, distribution_index, sbx_formula)
        centers = tuple(0.5 * x + 0.5 * y for x, y in zip(a, b, strict=True))
        spreads = tuple(0.5 * abs(x - y) * beta for x, y in zip(a, b, strict=True))
        raw = (
            tuple(c - s for c, s in zip(centers, spreads, strict=True)),
            tuple(c + s for c, s in zip(centers, spreads, strict=True)),
        )
    child_a, repaired_a = bound_real_values(raw[0], domains, bounds_policy)
    child_b, repaired_b = bound_real_values(raw[1], domains, bounds_policy)
    return RealCrossoverResult(
        parents,
        (child_a, child_b),
        method,
        True,
        draw,
        raw,
        (repaired_a, repaired_b),
        cut,
        gene_draws,
        swapped,
        alpha if method == RealCrossoverMethod.ARITHMETIC else None,
        sbx_draw,
        beta,
    )
