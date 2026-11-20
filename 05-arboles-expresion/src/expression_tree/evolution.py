"""Reproducible generational GP: selection, variation, elitism and an archive."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .generation import GenerationConfig, generate_tree
from .genetics import MUTATIONS, GeneticChange, clone_tree, crossover, mutate
from .metrics import calculate_metrics
from .models import ExprNode, RepairConfig
from .sampling import SamplePoint, sample_points
from .tree import to_infix_string

SELECTIONS = {"tournament": "Torneo", "roulette": "Ruleta", "sus": "Estocástico universal (SUS)"}


@dataclass(frozen=True)
class EvolutionConfig:
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    population_size: int = 100
    selection: str = "tournament"
    tournament_size: int = 3
    crossover_probability: float = .9
    mutation_probability: float = .05
    mutations: tuple[str, ...] = tuple(MUTATIONS)
    elite_count: int = 1
    hall_of_fame_size: int = 10
    metric: str = "mse"
    max_generations: int = 50
    tolerance: float = 1e-6

    def validate(self) -> None:
        # Reuse generation's contract, even when the caller supplies an initial population.
        generate_tree(self.generation)
        if not 2 <= self.population_size <= 500:
            raise ValueError("La población debe contener entre 2 y 500 individuos.")
        if self.selection not in SELECTIONS:
            raise ValueError("El método de selección no es válido.")
        if not isinstance(self.mutations, tuple) or any(not isinstance(method, str) or method not in MUTATIONS
                                                       for method in self.mutations):
            raise ValueError("Elige tipos de mutación válidos o una tupla vacía para desactivarlos.")
        if len(set(self.mutations)) != len(self.mutations):
            raise ValueError("Los tipos de mutación no deben repetirse.")
        if not 2 <= self.tournament_size <= self.population_size:
            raise ValueError("El tamaño del torneo debe estar entre 2 y el tamaño de la población.")
        if not 0 <= self.elite_count < self.population_size:
            raise ValueError("El elitismo debe ser menor que la población; usa 0 para desactivarlo.")
        if not 0 <= self.hall_of_fame_size <= 100:
            raise ValueError("El Hall of Fame admite entre 0 y 100 soluciones.")
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in (self.crossover_probability, self.mutation_probability)):
            raise ValueError("Las probabilidades deben estar entre 0 y 1.")
        if self.metric not in ("mse", "nmse", "r2"):
            raise ValueError("Elige MSE, NMSE o R².")
        if not 1 <= self.max_generations <= 10000 or not math.isfinite(self.tolerance) or self.tolerance < 0:
            raise ValueError("Revisa el límite de generaciones y la tolerancia de paro.")


@dataclass
class Individual:
    id: int
    root: ExprNode
    generation: int
    origin: str = "Aleatorio"
    parents: tuple[int, ...] = ()
    loss: float = math.inf
    metrics: dict[str, float | None] = field(default_factory=dict)
    error: str | None = None
    repaired_samples: int = 0

    @property
    def expression(self) -> str:
        return to_infix_string(self.root)

    def copy(self) -> Individual:
        return Individual(self.id, clone_tree(self.root), self.generation, self.origin, self.parents,
                          self.loss, dict(self.metrics), self.error, self.repaired_samples)


@dataclass(frozen=True)
class GenerationElites:
    """Independent snapshots of the best evaluated individuals of one generation."""
    generation: int
    individuals: tuple[Individual, ...]


def evaluate_individual(individual: Individual, reference: tuple[SamplePoint, ...], variables: dict[str, float],
                        variable: str, repairs: RepairConfig, metric: str) -> None:
    predictions = sample_points(individual.root, variables, (p.x for p in reference), variable=variable, repair_config=repairs)
    individual.repaired_samples = sum(p.repaired for p in predictions)
    individual.metrics, individual.loss, individual.error = {}, math.inf, None
    invalid = sum(p.y is None for p in predictions)
    if invalid:
        individual.error = f"Sin adaptación: {invalid} de {len(reference)} predicciones fuera de dominio."
        return
    try:
        values = calculate_metrics([p.y for p in reference], [p.y for p in predictions]).values
        value = values[metric]
        if value is None:
            raise ValueError("NMSE y R² requieren al menos dos referencias con distinta y.")
        individual.metrics = values
        individual.loss = max(0.0, 1 - value) if metric == "r2" else value
    except ValueError as exc:
        individual.error = str(exc)


@dataclass(frozen=True)
class SelectionResult:
    indices: tuple[int, ...]
    probabilities: tuple[float, ...]
    pointers: tuple[float, ...] = ()
    contestants: tuple[tuple[int, ...], ...] = ()


def select_parents(population: list[Individual], count: int, method: str, rng: random.Random,
                   tournament_size: int = 3) -> SelectionResult:
    if not population or count < 1 or method not in SELECTIONS:
        raise ValueError("Se necesita una población y un método de selección válido.")
    if method == "tournament":
        if not 2 <= tournament_size <= len(population):
            raise ValueError("El torneo debe tener entre 2 y N participantes.")
        rounds = tuple(tuple(rng.sample(range(len(population)), tournament_size)) for _ in range(count))
        return SelectionResult(tuple(min(group, key=lambda i: population[i].loss) for group in rounds), (), contestants=rounds)
    weights = [1 / (1 + ind.loss) if math.isfinite(ind.loss) else 0.0 for ind in population]
    total = math.fsum(weights)
    probabilities = tuple(w / total for w in weights) if total > 0 else tuple(1 / len(population) for _ in population)
    if method == "sus":
        start = rng.random() / count
        pointers = tuple(start + i / count for i in range(count))
    else:
        pointers = tuple(rng.random() for _ in range(count))
    cumulative, running = [], 0.0
    for p in probabilities:
        running += p
        cumulative.append(running)
    # Scan only positive intervals: an exact zero pointer cannot pick a zero-weight individual.
    positive = [i for i, p in enumerate(probabilities) if p > 0]
    indices = tuple(next((i for i in positive if point < cumulative[i]), positive[-1]) for point in pointers)
    return SelectionResult(indices, probabilities, pointers)


@dataclass
class BreedingEvent:
    parents: tuple[int, int]
    children: tuple[int, ...]
    crossover: GeneticChange | None
    mutations: tuple[GeneticChange, ...]


@dataclass(frozen=True)
class GenerationStats:
    generation: int
    best: float
    mean: float
    valid: int
    crossovers: int = 0
    mutations: int = 0
    repairs: int = 0


class EvolutionRun:
    def __init__(self, config: EvolutionConfig, reference: tuple[SamplePoint, ...], *,
                 variables: dict[str, float] | None = None, repairs: RepairConfig | None = None) -> None:
        config.validate()
        if not reference or any(p.y is None or not math.isfinite(p.x) or not math.isfinite(p.y) for p in reference):
            raise ValueError("La referencia debe tener un valor x,y finito en cada punto. Revisa el dominio o el CSV.")
        if config.metric != "mse" and (len(reference) < 2 or len({p.y for p in reference}) < 2):
            raise ValueError("NMSE y R² requieren al menos dos referencias con distinta y; usa MSE para referencias constantes.")
        self.config, self.reference = config, tuple(reference)
        self.variables, self.repairs = dict(variables or {}), repairs or RepairConfig(enabled=False)
        self.rng = random.Random(config.generation.seed)
        self.population: list[Individual] = []
        self.hall_of_fame: list[Individual] = []
        self.history: list[GenerationStats] = []
        self.elite_history: list[GenerationElites] = []
        self.latest_elite_predictions: tuple[SamplePoint, ...] = ()
        self.events: list[BreedingEvent] = []
        self.selection: SelectionResult | None = None
        self.generation, self._next_id = 0, 1

    def _individual(self, root: ExprNode, origin: str = "Aleatorio", parents: tuple[int, ...] = ()) -> Individual:
        individual = Individual(self._next_id, root, self.generation, origin, parents)
        self._next_id += 1
        evaluate_individual(individual, self.reference, self.variables, self.config.generation.variable,
                            self.repairs, self.config.metric)
        return individual

    def initialize(self) -> None:
        if self.population:
            raise ValueError("Esta ejecución ya tiene una población. Crea otra para reiniciarla.")
        cfg = self.config.generation
        self.population = [self._individual(generate_tree(GenerationConfig(cfg.max_height, cfg.operators,
                           self.rng.getrandbits(64), cfg.variable, cfg.max_nodes))) for _ in range(self.config.population_size)]
        self._record()

    @property
    def best(self) -> Individual:
        return min(self.population, key=lambda ind: ind.loss)

    @property
    def stop_reason(self) -> str | None:
        if self.population and self.best.loss <= self.config.tolerance:
            return "Se alcanzó la adaptación objetivo."
        if self.generation >= self.config.max_generations:
            return "Se alcanzó el límite de generaciones."
        return None

    def _record(self, crossovers: int = 0, mutations: int = 0, repairs: int = 0) -> None:
        valid = [ind.loss for ind in self.population if math.isfinite(ind.loss)]
        self.history.append(GenerationStats(self.generation, self.best.loss, math.fsum(v / len(valid) for v in valid) if valid else math.inf,
                                            len(valid), crossovers, mutations, repairs))
        leaders = sorted(self.population, key=lambda ind: ind.loss)[:max(1, self.config.elite_count)]
        self.elite_history.append(GenerationElites(self.generation, tuple(ind.copy() for ind in leaders)))
        # Prepare the live curve in the generation worker. Only the latest prediction
        # vector is retained; historical curves can be reconstructed from the trees.
        self.latest_elite_predictions = sample_points(leaders[0].root, self.variables,
            (point.x for point in self.reference), variable=self.config.generation.variable, repair_config=self.repairs)
        candidates = sorted(self.hall_of_fame + [ind for ind in self.population if math.isfinite(ind.loss)], key=lambda ind: ind.loss)
        self.hall_of_fame = []
        seen = set()
        for ind in candidates:
            # Include dormant genes: identical phenotypes can carry distinct useful genotypes.
            def signature(node):
                return node.kind, node.value, tuple(signature(c) for c in node.children)
            key = signature(ind.root)
            if key not in seen and len(self.hall_of_fame) < self.config.hall_of_fame_size:
                self.hall_of_fame.append(ind.copy())
                seen.add(key)

    def advance(self) -> None:
        if not self.population:
            raise ValueError("Genera primero una población.")
        if self.stop_reason:
            return
        cfg = self.config
        previous = self.population
        self.generation += 1
        self.events = []
        self.population = [self._individual(clone_tree(ind.root), "Élite", (ind.id,))
                           for ind in sorted(previous, key=lambda ind: ind.loss)[:cfg.elite_count]]
        pair_count = math.ceil((cfg.population_size - len(self.population)) / 2)
        self.selection = select_parents(previous, pair_count * 2, cfg.selection, self.rng, cfg.tournament_size)
        cross_count = mutation_count = repair_count = 0
        for pair in range(pair_count):
            a, b = (previous[i] for i in self.selection.indices[pair * 2:pair * 2 + 2])
            change = crossover(a.root, b.root, cfg.generation, self.rng) if self.rng.random() < cfg.crossover_probability else None
            roots = change.after if change else (clone_tree(a.root), clone_tree(b.root))
            cross_count += bool(change and change.applied)
            repair_count += sum(len(p) for p in change.repairs) if change else 0
            mutations, children = [], []
            for root in roots:
                if len(self.population) >= cfg.population_size:
                    break
                mutation = None
                if cfg.mutations and self.rng.random() < cfg.mutation_probability:
                    method = self.rng.choice(cfg.mutations)
                    mutation = mutate(root, method, cfg.generation, self.rng)
                if mutation:
                    root = mutation.after[0]
                    mutations.append(mutation)
                    mutation_count += mutation.applied
                    repair_count += sum(len(p) for p in mutation.repairs)
                origin = "Cruza" if change and change.applied else "Copia"
                if mutation and mutation.applied:
                    origin += " + " + MUTATIONS[method].lower()
                child = self._individual(root, origin, (a.id, b.id))
                children.append(child.id)
                self.population.append(child)
            self.events.append(BreedingEvent((a.id, b.id), tuple(children), change, tuple(mutations)))
        self._record(cross_count, mutation_count, repair_count)
