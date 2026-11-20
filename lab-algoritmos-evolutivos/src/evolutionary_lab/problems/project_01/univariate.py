from math import cos, e, expm1, pi, sin, sqrt

from evolutionary_lab.domain.models import Phenotype


def evaluate_min1(phenotype: Phenotype) -> float:
    (x,) = phenotype
    return 1 + cos(x) / (1 + 0.01 * x**2)


def evaluate_min2(phenotype: Phenotype) -> float:
    (x,) = phenotype
    return -abs(x * sin(sqrt(abs(x))))


def evaluate_min3(phenotype: Phenotype) -> float:
    (x,) = phenotype
    return sin(x) / (1 + sqrt(x) + cos(x) / (1 + x))


def evaluate_f2(phenotype: Phenotype) -> float:
    (x,) = phenotype
    # Equivalent form preserves the exact zero and nonnegativity at x=0.
    return -20 * expm1(-0.2 * abs(x)) - e * expm1(cos(2 * pi * x) - 1)


def evaluate_f3(phenotype: Phenotype) -> float:
    (x,) = phenotype
    return x + abs(sin(32 * pi * x))


def evaluate_f4(phenotype: Phenotype) -> float:
    (x,) = phenotype
    return 0.5 - (sin(x) ** 2 - 0.5) / (1 + 0.001 * x**4)
