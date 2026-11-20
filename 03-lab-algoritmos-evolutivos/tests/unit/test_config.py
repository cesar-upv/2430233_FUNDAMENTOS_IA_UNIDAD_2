from dataclasses import replace
from math import nan

import pytest

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.models import (
    Interval,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.problems.registry import PROJECT_01_F1


@pytest.fixture
def config() -> ExperimentConfig:
    return ExperimentConfig(
        problem_id=PROJECT_01_F1.identifier,
        domains=PROJECT_01_F1.domains,
        precision=(0.001,),
        population_size=10,
        generation_limit=100,
        seed=42,
    )


def test_config_accepts_verified_problem_and_restricted_search(
    config: ExperimentConfig,
) -> None:
    config.validate_for(PROJECT_01_F1)
    restricted = replace(config, domains=(Interval(0.2, 0.7),))
    restricted.validate_for(PROJECT_01_F1)
    coarse = replace(config, precision=(2.0,), generation_limit=0, seed=-42)
    coarse.validate_for(PROJECT_01_F1)
    assert config.precision == (0.001,) and config.seed == 42


@pytest.mark.parametrize(
    "changes",
    [
        {"precision": (0.0,)},
        {"precision": (nan,)},
        {"precision": (0.001, 0.001)},
        {"population_size": 0},
        {"population_size": True},
        {"generation_limit": -1},
        {"seed": 0.5},
        {"problem_id": ""},
        {"crossover_probability": -0.1},
        {"crossover_probability": 1.1},
        {"crossover_probability": nan},
        {"mutation_probability": True},
        {"mutation_probability": -0.01},
        {"mutation_probability": 1.01},
        {"selection_method": "unknown"},
        {"reproduction_policy": "unknown"},
        {"replacement_strategy": "unknown"},
        {"fitness_policy": "unknown"},
        {"zero_weight_policy": "unknown"},
        {"tournament_tie_policy": "unknown"},
    ],
)
def test_invalid_configuration_fields_are_rejected(
    config: ExperimentConfig, changes: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        replace(config, **changes)


def test_configuration_rejects_incompatible_problem_settings(
    config: ExperimentConfig,
) -> None:
    incompatible = (
        replace(config, problem_id="unknown"),
        replace(config, direction=OptimizationDirection.MINIMIZE),
        replace(config, representation=Representation.REAL, precision=()),
        replace(config, domains=(Interval(-0.1, 1.0),)),
        replace(config, domains=(Interval(0.0, 1.1),)),
        replace(
            config,
            domains=(Interval(0.0, 1.0), Interval(0.0, 1.0)),
            precision=(0.001, 0.001),
        ),
    )
    for candidate in incompatible:
        with pytest.raises(ValueError):
            candidate.validate_for(PROJECT_01_F1)
