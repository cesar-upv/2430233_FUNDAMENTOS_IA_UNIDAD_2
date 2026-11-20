from __future__ import annotations

import random
from dataclasses import dataclass

from .models import ExprNode
from .operators import ALIASES, CONSTANTS, GENERATOR_OPERATORS, OPERATORS
from .parsing import NodeFactory


@dataclass(frozen=True)
class GenerationConfig:
    max_height: int = 4
    operators: tuple[str, ...] = GENERATOR_OPERATORS
    seed: int | None = None
    variable: str = "x"
    max_nodes: int = 63


def generate_tree(config: GenerationConfig | None = None) -> ExprNode:
    cfg = config or GenerationConfig()
    if not 1 <= cfg.max_height <= 8:
        raise ValueError("La altura debe estar entre 1 y 8 niveles.")
    if not cfg.operators or any(token not in GENERATOR_OPERATORS for token in cfg.operators):
        raise ValueError("Selecciona al menos un operador válido.")
    if not cfg.variable.isidentifier() or cfg.variable.lower() in OPERATORS or cfg.variable.lower() in CONSTANTS or cfg.variable.lower() in ALIASES:
        raise ValueError("El nombre de la variable no es válido.")
    if cfg.max_nodes < 1:
        raise ValueError("El límite de nodos debe ser positivo.")
    rng, factory = random.Random(cfg.seed), NodeFactory()

    def build(level: int, budget: int, needs_variable: bool = False) -> ExprNode:
        candidates = [OPERATORS[t] for t in cfg.operators if OPERATORS[t].arity + 1 <= budget]
        if level >= cfg.max_height or not candidates or (level > 1 and not needs_variable and rng.random() < 0.32):
            return factory.create_atom(cfg.variable if needs_variable or rng.random() < 0.42 else str(rng.randint(1, 9)))
        spec = rng.choice(candidates)
        if spec.arity == 1:
            children = [build(level + 1, budget - 1, needs_variable)]
        else:
            left_budget = rng.randint(1, budget - 2)
            variable_side = rng.randrange(2)
            children = [build(level + 1, left_budget, needs_variable and variable_side == 0), build(level + 1, budget - 1 - left_budget, needs_variable and variable_side == 1)]
        return factory.create(spec.token, "op" if spec.precedence < 4 else "func", children)

    return build(1, cfg.max_nodes, True)
