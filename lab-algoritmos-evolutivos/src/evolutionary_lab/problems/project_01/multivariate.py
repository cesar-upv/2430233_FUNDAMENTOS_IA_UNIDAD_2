from math import cos, fsum, pi, sin, sqrt

from evolutionary_lab.domain.models import Phenotype


def evaluate_schaffer(phenotype: Phenotype) -> float:
    x, y = phenotype
    radius_squared = x * x + y * y
    return 0.5 - (sin(sqrt(radius_squared)) ** 2 - 0.5) / (
        1 + 0.001 * radius_squared**2
    )


def evaluate_rastrigin(phenotype: Phenotype) -> float:
    return fsum(x * x + 10 * (1 - cos(2 * pi * x)) for x in phenotype)


def evaluate_sine_power(phenotype: Phenotype) -> float:
    # The scan uses (i+1), with i starting at 1, unlike the usual Michalewicz form.
    return -fsum(
        sin(x) * sin(index * x * x / pi) ** 20
        for index, x in enumerate(phenotype, start=2)
    )


def evaluate_schwefel(phenotype: Phenotype) -> float:
    return -fsum(x * sin(sqrt(abs(x))) for x in phenotype)
