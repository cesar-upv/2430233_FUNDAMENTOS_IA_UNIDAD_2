"""Genetic operators over expression genotypes, including dormant right branches.

All operators return independent trees. Paths address genotype branches (0 left,
1 right); the empty path denotes the root. Height uses the generator convention:
a leaf has one level, so the maximum depth is max_height - 1.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from .generation import GenerationConfig, generate_tree
from .models import ExprNode
from .operators import OPERATORS
from .parsing import NodeFactory
from .tree import traverse_preorder

Path = tuple[int, ...]
MUTATIONS = {"leaf": "Hojas", "operator": "Operadores", "switch": "Switching", "subtree": "Subrama aleatoria"}


def clone_tree(root: ExprNode) -> ExprNode:
    factory = NodeFactory()

    def copy(node: ExprNode) -> ExprNode:
        return factory.create(node.value, node.kind, [copy(c) for c in node.children], node.num_value)

    return copy(root)


def tree_paths(root: ExprNode) -> list[Path]:
    def walk(node: ExprNode, path: Path):
        yield path
        for i, child in enumerate(node.children):
            yield from walk(child, path + (i,))

    return list(walk(root, ()))


def at_path(root: ExprNode, path: Path) -> ExprNode:
    for index in path:
        if index < 0 or index >= len(root.children):
            raise ValueError("La rama seleccionada ya no existe.")
        root = root.children[index]
    return root


def replace_branch(root: ExprNode, path: Path, branch: ExprNode) -> ExprNode:
    if not path:
        return branch
    at_path(root, path[:-1]).children[path[-1]] = branch
    return root


def nearest_operand(root: ExprNode) -> ExprNode:
    """Nearest leaf by breadth first search; ties consistently prefer the left."""
    pending = deque([root])
    while pending:
        node = pending.popleft()
        if node.is_leaf and node.kind in ("number", "constant", "variable"):
            return clone_tree(node)
        pending.extend(node.children)
    raise ValueError("El árbol no contiene un operando válido para reparar.")


def repair_tree(root: ExprNode, max_height: int, max_nodes: int = 63) -> tuple[ExprNode, tuple[Path, ...]]:
    if not 1 <= max_height <= 8 or max_nodes < 1:
        raise ValueError("La altura debe ser de 1 a 8 niveles y el límite de nodos positivo.")
    root, repairs = clone_tree(root), []

    def prune(node: ExprNode, path: Path, budget: int) -> ExprNode:
        if node.children and (len(path) >= max_height - 1 or budget < len(node.children) + 1):
            repairs.append(path)
            return nearest_operand(node)
        remaining = budget - 1
        for i, child in enumerate(node.children):
            child_budget = remaining - (len(node.children) - i - 1)
            node.children[i] = prune(child, path + (i,), child_budget)
            remaining -= len(traverse_preorder(node.children[i]))
        return node

    return clone_tree(prune(root, (), max_nodes)), tuple(repairs)


@dataclass
class GeneticChange:
    name: str
    before: tuple[ExprNode, ...]
    after: tuple[ExprNode, ...]
    paths: tuple[Path | None, ...]
    repairs: tuple[tuple[Path, ...], ...] = ()
    notes: tuple[str, ...] = ()
    applied: bool = True
    raw: tuple[ExprNode, ...] = field(default_factory=tuple)


def crossover(first: ExprNode, second: ExprNode, config: GenerationConfig, rng: random.Random,
              first_path: Path | None = None, second_path: Path | None = None) -> GeneticChange:
    parents = (clone_tree(first), clone_tree(second))
    paths_a, paths_b = tree_paths(first)[1:], tree_paths(second)[1:]
    if not paths_a or not paths_b:
        return GeneticChange("Cruza monopunto", parents, (clone_tree(first), clone_tree(second)), (None, None),
                             notes=("Un padre es una hoja: no tiene aristas para cortar. Se copian ambos padres.",), applied=False)
    pa = rng.choice(paths_a) if first_path is None else first_path
    pb = rng.choice(paths_b) if second_path is None else second_path
    if pa not in paths_a or pb not in paths_b:
        raise ValueError("La cruza corta aristas; selecciona un nodo distinto de la raíz en cada padre.")
    a, b = clone_tree(first), clone_tree(second)
    a = replace_branch(a, pa, clone_tree(at_path(second, pb)))
    b = replace_branch(b, pb, clone_tree(at_path(first, pa)))
    raw = (clone_tree(a), clone_tree(b))
    a, repairs_a = repair_tree(a, config.max_height, config.max_nodes)
    b, repairs_b = repair_tree(b, config.max_height, config.max_nodes)
    count = len(repairs_a) + len(repairs_b)
    notes = ("Se intercambiaron los subárboles de las dos aristas marcadas.",)
    if count:
        notes += (f"Poda y reparación en {count} rama(s): sube el operando más cercano, con prioridad izquierda en empates.",)
    return GeneticChange("Cruza monopunto", parents, (a, b), (pa, pb), (repairs_a, repairs_b), notes, raw=raw)


def random_operand(rng: random.Random, variable: str, previous: str = "") -> ExprNode:
    values = [variable, "pi", "e", str(round(rng.uniform(-9, 9), 1))]
    return NodeFactory().create_atom(rng.choice([v for v in values if v != previous]))


def mutate(root: ExprNode, method: str, config: GenerationConfig, rng: random.Random,
           path: Path | None = None, *, operator: str | None = None, operand: str | None = None) -> GeneticChange:
    if method not in MUTATIONS:
        raise ValueError("Elige uno de los cuatro métodos de mutación.")
    before, result = clone_tree(root), clone_tree(root)
    eligible = [p for p in tree_paths(result) if
                (method == "leaf" and at_path(result, p).is_leaf) or
                (method == "operator" and bool(at_path(result, p).children)) or
                (method == "switch" and len(at_path(result, p).children) == 2) or method == "subtree"]
    if not eligible:
        return GeneticChange(MUTATIONS[method], (before,), (result,), (None,),
                             notes=("Este árbol no tiene nodos compatibles con la mutación elegida.",), applied=False)
    selected = rng.choice(eligible) if path is None else path
    if selected not in eligible:
        raise ValueError("El nodo seleccionado no es compatible con este método de mutación.")
    node = at_path(result, selected)
    note = ""
    if method == "leaf":
        replacement = NodeFactory().create_atom(operand) if operand is not None else random_operand(rng, config.variable, node.value)
        if replacement.kind not in ("number", "variable", "constant") or replacement.value == node.value:
            raise ValueError("El nuevo valor debe ser un operando distinto del actual.")
        note = f"Hoja: {node.value} → {replacement.value}."
        result = replace_branch(result, selected, replacement)
    elif method == "operator":
        choices = [t for t in config.operators if t != node.value]
        if operator is not None and operator not in choices:
            raise ValueError("Elige otro operador de los permitidos.")
        if not choices:
            return GeneticChange(MUTATIONS[method], (before,), (result,), (selected,),
                                 notes=("No hay otro operador permitido para sustituirlo.",), applied=False)
        token = operator if operator is not None else rng.choice(choices)
        spec = OPERATORS[token]
        note = f"Operador: {node.value} → {token}."
        node.value, node.kind = token, "op" if spec.precedence < 4 else "func"
        if spec.arity == 2 and len(node.children) == 1:
            node.children.append(random_operand(rng, config.variable))
            note += " Se generó el operando derecho que faltaba."
        if spec.arity == 1 and len(node.children) == 2:
            note += " La izquierda domina; la derecha se conserva como gen recesivo."
    elif method == "switch":
        node.children.reverse()
        note = "Se intercambiaron izquierda y derecha. En operadores unarios cambia la rama dominante."
    else:
        budget = config.max_nodes - len(traverse_preorder(result)) + len(traverse_preorder(node))
        replacement = generate_tree(GenerationConfig(config.max_height - len(selected), config.operators,
                                                    rng.getrandbits(64), config.variable, max(1, budget)))
        result = replace_branch(result, selected, replacement)
        note = "Se generó una subrama nueva dentro de la altura disponible." + (" Se reemplazó la raíz completa." if not selected else "")
    raw = clone_tree(result)
    result, repairs = repair_tree(result, config.max_height, config.max_nodes)
    return GeneticChange(MUTATIONS[method], (before,), (result,), (selected,), (repairs,), (note,), raw=(raw,))
