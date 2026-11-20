from collections.abc import Mapping
from dataclasses import replace
from math import pi
from types import MappingProxyType

from evolutionary_lab.domain.models import (
    Interval,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem, ReferenceOptimum
from evolutionary_lab.domain.validation import require_integer
from evolutionary_lab.problems.project_01.f1 import evaluate_f1
from evolutionary_lab.problems.project_01.multivariate import (
    evaluate_rastrigin,
    evaluate_schaffer,
    evaluate_schwefel,
    evaluate_sine_power,
)
from evolutionary_lab.problems.project_01.univariate import (
    evaluate_f2,
    evaluate_f3,
    evaluate_f4,
    evaluate_min1,
    evaluate_min2,
    evaluate_min3,
)

PROJECT_01_F1 = OptimizationProblem(
    identifier="project_01.f1",
    title="f1 · Primera función de maximización",
    formula=r"\sin^6(5\pi x)\exp\left[-2\ln(2)\left(\frac{x-0.1}{0.8}\right)^2\right]",
    domains=(Interval(0.0, 1.0),),
    direction=OptimizationDirection.MAXIMIZE,
    objective=evaluate_f1,
    supported_representations=(Representation.BINARY, Representation.REAL),
    reference_optimum=ReferenceOptimum(phenotype=(0.1,), objective_value=1.0),
    source_reference=(
        "Araujo and Cervigón (2009), Project 1, section 1; "
        "printed page 151, local PDF page 149 (one-based)."
    ),
)

PROJECT_01_MIN1 = OptimizationProblem(
    "project_01.min1",
    "Mínimo 1 · Coseno amortiguado",
    "1 + cos(x) / (1 + 0.01 x²)",
    (Interval(0, 50),),
    OptimizationDirection.MINIMIZE,
    evaluate_min1,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((3.08531,), 0.0883634),
    "Project 1 §2, printed p.153 / PDF p.151; verified visually.",
)
PROJECT_01_MIN2 = OptimizationProblem(
    "project_01.min2",
    "Mínimo 2 · Seno con raíz",
    "−|x sen(√|x|)|",
    (Interval(-250, 250),),
    OptimizationDirection.MINIMIZE,
    evaluate_min2,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((203.814,), -201.843),
    "Project 1 §2, printed p.153 / PDF p.151; verified visually.",
)
PROJECT_01_MIN3 = OptimizationProblem(
    "project_01.min3",
    "Mínimo 3 · Seno amortiguado",
    "sen(x) / (1 + √x + cos(x)/(1+x))",
    (Interval(0, 25),),
    OptimizationDirection.MINIMIZE,
    evaluate_min3,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((4.5798,), -0.318071),
    "Project 1 §2, printed p.153 / PDF p.151; verified visually.",
)

PROJECT_01_F2 = OptimizationProblem(
    "project_01.f2",
    "Máximo 2 · Exponenciales y coseno",
    "20 + e − 20 exp(−0.2 |x|) − exp(cos(2πx))",
    (Interval(0, 32),),
    OptimizationDirection.MAXIMIZE,
    evaluate_f2,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((31.5005,), 22.3136),
    "Project 1 §1, printed p.151 / PDF p.149; verified visually.",
)
PROJECT_01_F3 = OptimizationProblem(
    "project_01.f3",
    "Máximo 3 · Seno absoluto",
    "x + |sen(32πx)|",
    (Interval(0, 1),),
    OptimizationDirection.MAXIMIZE,
    evaluate_f3,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((0.98447395,), 1.98442447),
    "Project 1 §1, printed p.152 / PDF p.150; verified visually.",
)
PROJECT_01_F4 = OptimizationProblem(
    "project_01.f4",
    "Máximo 4 · Seno cuadrático",
    "0.5 − (sen²(x) − 0.5)/(1 + 0.001 x⁴)",
    (Interval(0, 10),),
    OptimizationDirection.MAXIMIZE,
    evaluate_f4,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((0.0,), 1.0),
    "Project 1 §1, printed p.152 / PDF p.150; verified visually.",
)
PROJECT_01_SCHAFFER = OptimizationProblem(
    "project_01.schaffer",
    "Dos variables · Seno radial",
    "0.5 − (sen²(√(x₁²+x₂²)) − 0.5)/(1 + 0.001 (x₁²+x₂²)²)",
    (Interval(-40, 40),) * 2,
    OptimizationDirection.MAXIMIZE,
    evaluate_schaffer,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((0.0, 0.0), 1.0),
    "Project 1 §3, printed p.154 / PDF p.152; verified visually.",
)
PROJECT_01_RASTRIGIN = OptimizationProblem(
    "project_01.rastrigin",
    "Varias variables · Rastrigin",
    "10n + Σᵢ [xᵢ² − 10 cos(2πxᵢ)]",
    (Interval(-5.12, 5.12),) * 2,
    OptimizationDirection.MINIMIZE,
    evaluate_rastrigin,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((0.0, 0.0), 0.0),
    "Project 1 §3, printed p.155 / PDF p.153; verified visually.",
)
PROJECT_01_SINE_POWER = OptimizationProblem(
    "project_01.sine_power",
    "Varias variables · Potencia del seno",
    "−Σᵢ sen(xᵢ) sen²⁰((i+1)xᵢ²/π), i = 1…n",
    (Interval(0, pi),) * 2,
    OptimizationDirection.MINIMIZE,
    evaluate_sine_power,
    (Representation.BINARY, Representation.REAL),
    source_reference="Project 1 §3, printed p.155 / PDF p.153; verified visually.",
)
PROJECT_01_SCHWEFEL = OptimizationProblem(
    "project_01.schwefel",
    "Varias variables · Seno con raíz",
    "−Σᵢ xᵢ sen(√|xᵢ|)",
    (Interval(0, 100),) * 2,
    OptimizationDirection.MINIMIZE,
    evaluate_schwefel,
    (Representation.BINARY, Representation.REAL),
    ReferenceOptimum((65.54785,) * 2, -2 * 63.63498),
    "Project 1 §3, printed p.155 / PDF p.153; verified visually.",
)
VARIABLE_DIMENSION_PROBLEMS = frozenset(
    (
        PROJECT_01_RASTRIGIN.identifier,
        PROJECT_01_SINE_POWER.identifier,
        PROJECT_01_SCHWEFEL.identifier,
    )
)

PROBLEMS: Mapping[str, OptimizationProblem] = MappingProxyType(
    {
        problem.identifier: problem
        for problem in (
            PROJECT_01_F1,
            PROJECT_01_F2,
            PROJECT_01_F3,
            PROJECT_01_F4,
            PROJECT_01_MIN1,
            PROJECT_01_MIN2,
            PROJECT_01_MIN3,
            PROJECT_01_SCHAFFER,
            PROJECT_01_RASTRIGIN,
            PROJECT_01_SINE_POWER,
            PROJECT_01_SCHWEFEL,
        )
    }
)


def get_problem(identifier: str, dimensions: int | None = None) -> OptimizationProblem:
    try:
        problem = PROBLEMS[identifier]
    except KeyError as error:
        raise ValueError(f"Unknown problem: {identifier!r}") from error
    if dimensions is not None:
        require_integer(dimensions, "dimensions", minimum=1)
    if dimensions is None or dimensions == len(problem.domains):
        return problem
    if identifier not in VARIABLE_DIMENSION_PROBLEMS:
        raise ValueError("Problem has a fixed number of variables")
    optimum = problem.reference_optimum
    if optimum is not None:
        optimum = ReferenceOptimum(
            (optimum.phenotype[0],) * dimensions,
            optimum.objective_value * dimensions / len(problem.domains),
        )
    return replace(
        problem, domains=(problem.domains[0],) * dimensions, reference_optimum=optimum
    )
