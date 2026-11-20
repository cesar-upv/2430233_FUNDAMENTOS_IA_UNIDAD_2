import subprocess
import sys


def test_core_packages_import_without_qt() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import evolutionary_lab; "
            "from evolutionary_lab import domain, evolution, problems, "
            "simulation, application, persistence; "
            "from evolutionary_lab.domain.config import ExperimentConfig; "
            "from evolutionary_lab.domain.models import Individual, Population; "
            "from evolutionary_lab.problems.registry import get_problem; "
            "from evolutionary_lab.evolution.encoding.binary import "
            "BinaryEncoding, chromosome_length; "
            "from evolutionary_lab.evolution.initialization import "
            "initialize_population; "
            "from evolutionary_lab.domain.evaluation import "
            "FitnessPolicy, PopulationStatistics; "
            "from evolutionary_lab.evolution.evaluation import "
            "evaluate_individual, evaluate_population; "
            "from evolutionary_lab.evolution.statistics import "
            "calculate_population_statistics, mean_normalized_hamming_distance; "
            "from random import Random; "
            "from evolutionary_lab.evolution.engine import run_evolution; "
            "problem = get_problem('project_01.f1'); "
            "config = ExperimentConfig(problem.identifier, problem.domains, "
            "(0.001,), 10, 0, 42); "
            "population = evaluate_population(initialize_population("
            "config, problem, Random(config.seed)), problem); "
            "stats = calculate_population_statistics(population, problem.direction); "
            "assert stats.population_size == 10; "
            "run_config = ExperimentConfig(problem.identifier, problem.domains, "
            "(0.001,), 10, 100, 42); "
            "result = run_evolution(run_config, problem); "
            "assert len(result.generations) == 101; "
            "assert len(result.final_population) == 10; "
            "assert get_problem('project_01.f1').evaluate((0.1,)) == 1.0; "
            "assert not any(name.startswith(('PySide6', 'pyqtgraph')) "
            "for name in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
