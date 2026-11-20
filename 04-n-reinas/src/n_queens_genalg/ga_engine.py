from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

FitnessMode = Literal["Crawford [CRA92] (Penalización)", "Homaifar [HOM92] (Recompensa)"]
CrossoverMode = Literal["PMX (Permutación)", "OX (Orden)", "Cruce 1-Punto + Reparación", "Cruce 2-Puntos + Reparación"]
SelectionMode = Literal["Torneo", "Ruleta / Proporcional"]


@dataclass
class ConflictEdge:
    col_i: int  # 1-indexed column (1..N)
    row_i: int  # 1-indexed row (1..N)
    col_j: int  # 1-indexed column (1..N)
    row_j: int  # 1-indexed row (1..N)
    kind: str   # "diagonal" or "fila"


@dataclass
class Individual:
    genes: list[int]  # 1-indexed permutation of [1..N] where index+1 is column, value is row
    conflicts: int = 0
    homaifar_score: float = 0.0
    conflict_edges: list[ConflictEdge] = field(default_factory=list)
    origin: str = "Inicial"
    parents_info: str = ""
    mutation_swap: tuple[int, int] | None = None  # 0-indexed positions swapped if mutated

    @property
    def n(self) -> int:
        return len(self.genes)

    @property
    def is_solution(self) -> bool:
        return self.conflicts == 0 and len(set(self.genes)) == self.n


@dataclass
class EvolutionMoveLog:
    generation: int
    action: str
    parent1: list[int]
    parent2: list[int] | None
    child_before_mut: list[int]
    child_after_mut: list[int]
    cut_points: tuple[int, ...]
    swapped_positions: tuple[int, int] | None
    child_conflicts: int
    child_homaifar: float


@dataclass
class GenerationRecord:
    generation: int
    population: list[Individual]
    best: Individual
    avg_conflicts: float
    worst_conflicts: int
    best_homaifar: float
    avg_homaifar: float
    unique_solutions: list[list[int]]
    logs: list[EvolutionMoveLog]


def evaluate_individual(genes: list[int], origin: str = "Inicial", parents_info: str = "", mutation_swap: tuple[int, int] | None = None) -> Individual:
    n = len(genes)
    conflicts = 0
    edges: list[ConflictEdge] = []

    # Check all pairs (i, j) with i < j (Crawford [CRA92]: |q_i - q_j| == |i - j| or q_i == q_j)
    for i in range(n):
        for j in range(i + 1, n):
            qi = genes[i]
            qj = genes[j]
            col_dist = j - i
            row_dist = abs(qi - qj)
            if qi == qj:
                conflicts += 1
                edges.append(ConflictEdge(i + 1, qi, j + 1, qj, "fila"))
            elif row_dist == col_dist:
                conflicts += 1
                edges.append(ConflictEdge(i + 1, qi, j + 1, qj, "diagonal"))

    # Homaifar [HOM92]: Por cada reina y para cada diagonal (principal y secundaria)
    # se añade 1/(2*N) si no es atacada en esa diagonal. Max score = 1.0 (o 2*N / (2*N))
    unattacked_diagonals = 0
    for i in range(n):
        qi = genes[i]
        attacked_main = False  # q_i - i == q_j - j
        attacked_sec = False   # q_i + i == q_j + j
        for j in range(n):
            if i == j:
                continue
            qj = genes[j]
            if (qi - i) == (qj - j):
                attacked_main = True
            if (qi + i) == (qj + j):
                attacked_sec = True
        if not attacked_main:
            unattacked_diagonals += 1
        if not attacked_sec:
            unattacked_diagonals += 1

    homaifar_score = unattacked_diagonals / (2.0 * n) if n > 0 else 0.0

    return Individual(
        genes=list(genes),
        conflicts=conflicts,
        homaifar_score=homaifar_score,
        conflict_edges=edges,
        origin=origin,
        parents_info=parents_info,
        mutation_swap=mutation_swap,
    )


def crossover_pmx(p1: list[int], p2: list[int], rng: random.Random) -> tuple[list[int], tuple[int, int]]:
    n = len(p1)
    if n < 2:
        return list(p1), (0, 0)
    c1, c2 = sorted(rng.sample(range(n), 2))
    child = [0] * n
    child[c1:c2 + 1] = p1[c1:c2 + 1]

    for idx in range(c1, c2 + 1):
        val = p2[idx]
        if val not in child:
            pos = idx
            while c1 <= pos <= c2:
                mapped_val = p1[pos]
                pos = p2.index(mapped_val)
            child[pos] = val

    for idx in range(n):
        if child[idx] == 0:
            child[idx] = p2[idx]

    return child, (c1 + 1, c2 + 1)


def crossover_ox(p1: list[int], p2: list[int], rng: random.Random) -> tuple[list[int], tuple[int, int]]:
    n = len(p1)
    if n < 2:
        return list(p1), (0, 0)
    c1, c2 = sorted(rng.sample(range(n), 2))
    child = [0] * n
    child[c1:c2 + 1] = p1[c1:c2 + 1]
    used = set(child[c1:c2 + 1])

    remaining = [gene for gene in p2 if gene not in used]
    rem_idx = 0
    for i in range(n):
        pos = (c2 + 1 + i) % n
        if child[pos] == 0:
            child[pos] = remaining[rem_idx]
            rem_idx += 1

    return child, (c1 + 1, c2 + 1)


def repair_permutation(genes: list[int], n: int) -> list[int]:
    """Repairs a 1-point or 2-point crossover child so it remains a valid permutation of 1..N without repetitions."""
    seen: set[int] = set()
    missing = [v for v in range(1, n + 1) if v not in genes]
    missing_idx = 0
    repaired = list(genes)
    for i, val in enumerate(repaired):
        if val in seen or val < 1 or val > n:
            repaired[i] = missing[missing_idx]
            missing_idx += 1
        else:
            seen.add(val)
    return repaired


def crossover_one_point(p1: list[int], p2: list[int], rng: random.Random) -> tuple[list[int], tuple[int]]:
    n = len(p1)
    if n < 2:
        return list(p1), (1,)
    cut = rng.randint(1, n - 1)
    raw = p1[:cut] + p2[cut:]
    return repair_permutation(raw, n), (cut,)


def crossover_two_point(p1: list[int], p2: list[int], rng: random.Random) -> tuple[list[int], tuple[int, int]]:
    n = len(p1)
    if n < 2:
        return list(p1), (1, 1)
    c1, c2 = sorted(rng.sample(range(n), 2))
    raw = p1[:c1] + p2[c1:c2 + 1] + p1[c2 + 1:]
    return repair_permutation(raw, n), (c1 + 1, c2 + 1)


class GeneticQueensSolver:
    def __init__(
        self,
        n: int = 8,
        pop_size: int = 60,
        crossover_rate: float = 0.35,  # Crawford [CRA92] recommends reduced crossover rate, higher swap mutation
        mutation_rate: float = 0.65,
        tournament_k: int = 3,
        elitism_count: int = 2,
        fitness_mode: FitnessMode = "Crawford [CRA92] (Penalización)",
        crossover_mode: CrossoverMode = "OX (Orden)",
        selection_mode: SelectionMode = "Torneo",
        seed: int | None = None,
    ) -> None:
        self.n = n
        self.pop_size = pop_size
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.tournament_k = tournament_k
        self.elitism_count = elitism_count
        self.fitness_mode: FitnessMode = fitness_mode
        self.crossover_mode: CrossoverMode = crossover_mode
        self.selection_mode: SelectionMode = selection_mode
        self.rng = random.Random(seed)

        self.generation = 0
        self.population: list[Individual] = []
        self.history: list[GenerationRecord] = []
        self.found_solutions: list[list[int]] = []
        self.reset()

    def reset(self) -> None:
        self.generation = 0
        self.population = []
        self.history = []
        self.found_solutions = []

        base = list(range(1, self.n + 1))
        for idx in range(self.pop_size):
            genes = list(base)
            self.rng.shuffle(genes)
            ind = evaluate_individual(genes, origin="Población Inicial", parents_info=f"Semilla #{idx + 1}")
            self.population.append(ind)

        self._sort_population()
        self._record_generation(logs=[])

    def _better_key(self, ind: Individual) -> tuple[float, float]:
        if self.fitness_mode.startswith("Crawford"):
            # Minimize conflicts, tie-break with Homaifar maximization
            return (float(ind.conflicts), -ind.homaifar_score)
        else:
            # Maximize Homaifar score, tie-break with fewer conflicts
            return (-ind.homaifar_score, float(ind.conflicts))

    def _sort_population(self) -> None:
        self.population.sort(key=self._better_key)
        for ind in self.population:
            if ind.is_solution and ind.genes not in self.found_solutions:
                self.found_solutions.append(list(ind.genes))

    def _record_generation(self, logs: list[EvolutionMoveLog]) -> None:
        avg_c = sum(ind.conflicts for ind in self.population) / len(self.population)
        worst_c = max(ind.conflicts for ind in self.population)
        best_h = max(ind.homaifar_score for ind in self.population)
        avg_h = sum(ind.homaifar_score for ind in self.population) / len(self.population)

        rec = GenerationRecord(
            generation=self.generation,
            population=list(self.population),
            best=self.population[0],
            avg_conflicts=avg_c,
            worst_conflicts=worst_c,
            best_homaifar=best_h,
            avg_homaifar=avg_h,
            unique_solutions=[list(s) for s in self.found_solutions],
            logs=logs,
        )
        self.history.append(rec)

    def _select_parent(self) -> Individual:
        if self.selection_mode == "Torneo":
            k = min(self.tournament_k, len(self.population))
            contenders = self.rng.sample(self.population, k)
            contenders.sort(key=self._better_key)
            return contenders[0]
        else:
            # Roulette / Proportional selection
            weights: list[float] = []
            for ind in self.population:
                if self.fitness_mode.startswith("Crawford"):
                    w = 1.0 / (1.0 + ind.conflicts)
                else:
                    w = max(0.01, ind.homaifar_score ** 2)
                weights.append(w)
            return self.rng.choices(self.population, weights=weights, k=1)[0]

    def _apply_crossover(self, p1: list[int], p2: list[int]) -> tuple[list[int], tuple[int, ...]]:
        if self.crossover_mode == "PMX (Permutación)":
            return crossover_pmx(p1, p2, self.rng)
        elif self.crossover_mode == "OX (Orden)":
            return crossover_ox(p1, p2, self.rng)
        elif self.crossover_mode == "Cruce 1-Punto + Reparación":
            return crossover_one_point(p1, p2, self.rng)
        else:
            return crossover_two_point(p1, p2, self.rng)

    def step_generation(self) -> GenerationRecord:
        self.generation += 1
        next_pop: list[Individual] = []
        logs: list[EvolutionMoveLog] = []

        # Elitism
        elite_n = max(0, min(self.elitism_count, self.pop_size))
        for i in range(elite_n):
            elite = self.population[i]
            copied = evaluate_individual(
                elite.genes,
                origin="Elitismo",
                parents_info=f"Élite #{i + 1} de Gen {self.generation - 1}",
                mutation_swap=None,
            )
            next_pop.append(copied)

        while len(next_pop) < self.pop_size:
            p1 = self._select_parent()
            p2 = self._select_parent()

            did_crossover = False
            cut_pts: tuple[int, ...] = ()
            if self.rng.random() < self.crossover_rate and self.n >= 2:
                child_genes, cut_pts = self._apply_crossover(p1.genes, p2.genes)
                did_crossover = True
            else:
                child_genes = list(p1.genes)

            before_mut = list(child_genes)
            swap_pos: tuple[int, int] | None = None

            # Swap mutation as described in Crawford [CRA92]:
            # "intercambio de los valores de dos posiciones"
            if self.rng.random() < self.mutation_rate and self.n >= 2:
                idx1, idx2 = sorted(self.rng.sample(range(self.n), 2))
                child_genes[idx1], child_genes[idx2] = child_genes[idx2], child_genes[idx1]
                swap_pos = (idx1, idx2)

            if did_crossover and swap_pos is not None:
                origin_str = "Cruce + Mutación (Swap)"
                p_info = f"P1:{p1.genes} x P2:{p2.genes} | Cortes:{cut_pts} | Swap col {swap_pos[0]+1}<->{swap_pos[1]+1}"
            elif did_crossover:
                origin_str = f"Cruce ({self.crossover_mode.split()[0]})"
                p_info = f"P1:{p1.genes} x P2:{p2.genes} | Cortes:{cut_pts}"
            elif swap_pos is not None:
                origin_str = "Mutación (Swap)"
                p_info = f"Padre:{p1.genes} | Intercambio col {swap_pos[0]+1} <-> col {swap_pos[1]+1}"
            else:
                origin_str = "Reproducción Directa"
                p_info = f"Clon de {p1.genes}"

            ind = evaluate_individual(
                child_genes,
                origin=origin_str,
                parents_info=p_info,
                mutation_swap=swap_pos,
            )
            next_pop.append(ind)

            if len(logs) < 25:
                logs.append(
                    EvolutionMoveLog(
                        generation=self.generation,
                        action=origin_str,
                        parent1=list(p1.genes),
                        parent2=list(p2.genes) if did_crossover else None,
                        child_before_mut=before_mut,
                        child_after_mut=list(child_genes),
                        cut_points=cut_pts,
                        swapped_positions=swap_pos,
                        child_conflicts=ind.conflicts,
                        child_homaifar=ind.homaifar_score,
                    )
                )

        self.population = next_pop
        self._sort_population()
        self._record_generation(logs=logs)
        return self.history[-1]
