from math import exp, log, pi, sin

from evolutionary_lab.domain.models import Phenotype


def evaluate_f1(phenotype: Phenotype) -> float:
    # Verified visually: printed p. 151, PDF p. 149 of the local reference book.
    (x,) = phenotype
    return sin(5 * pi * x) ** 6 * exp(-2 * log(2) * ((x - 0.1) / 0.8) ** 2)
