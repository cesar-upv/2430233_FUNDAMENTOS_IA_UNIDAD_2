from dataclasses import replace
from math import inf, nan, nextafter, sqrt

import pytest

from evolutionary_lab.domain.models import (
    Interval,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.problems.registry import PROBLEMS, PROJECT_01_F1, get_problem


def test_registry_exposes_verified_book_problems() -> None:
    assert "project_01.f1" in PROBLEMS
    assert all(problem.source_reference for problem in PROBLEMS.values())
    problem = get_problem("project_01.f1")
    assert problem.direction == OptimizationDirection.MAXIMIZE
    assert problem.supported_representations == (
        Representation.BINARY,
        Representation.REAL,
    )
    assert problem.domains == (Interval(0.0, 1.0),)
    optimum = problem.reference_optimum
    assert optimum is not None and optimum.phenotype == (0.1,)
    assert problem.evaluate(optimum.phenotype) == optimum.objective_value == 1.0
    with pytest.raises(ValueError, match="Unknown problem"):
        get_problem("missing")


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        (0.0, 0.0),
        (0.05, 2 ** (-1 / 128) / 8),
        (0.1, 1.0),
        (0.3, 2 ** (-1 / 8)),
        (0.5, 1 / sqrt(2)),
        (0.9, 0.25),
        (1.0, 0.0),
    ],
)
def test_book_function_matches_independent_reference_values(
    x: float, expected: float
) -> None:
    assert PROJECT_01_F1.evaluate((x,)) == pytest.approx(expected, rel=1e-13, abs=1e-15)


@pytest.mark.parametrize(
    "point",
    [(), (0.1, 0.2), (nextafter(0.0, -inf),), (nextafter(1.0, inf),), (nan,), (inf,)],
)
def test_problem_rejects_wrong_dimensions_and_outside_domain(
    point: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError):
        PROJECT_01_F1.evaluate(point)


@pytest.mark.parametrize("result", [nan, inf])
def test_problem_rejects_nonfinite_objective_results(result: float) -> None:
    problem = replace(PROJECT_01_F1, objective=lambda point: result)
    with pytest.raises(ValueError, match="objective result"):
        problem.evaluate((0.1,))


def test_objective_contract_accepts_vectors_and_both_representations() -> None:
    problem = OptimizationProblem(
        identifier="test.sum",
        title="Test objective",
        formula="x + y",
        domains=(Interval(-1, 1), Interval(-1, 1)),
        direction=OptimizationDirection.MINIMIZE,
        objective=lambda point: sum(point),
        supported_representations=(Representation.BINARY, Representation.REAL),
    )
    assert problem.evaluate((-0.5, 0.25)) == -0.25
