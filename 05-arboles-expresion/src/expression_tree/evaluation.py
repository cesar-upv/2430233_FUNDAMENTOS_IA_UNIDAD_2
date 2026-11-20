from __future__ import annotations

import math

from .models import EvalStep, ExprNode, RepairConfig, format_number
from .operators import CONSTANTS, OPERATORS
from .tree import traverse_preorder


def evaluate_tree(
    root: ExprNode,
    variables: dict[str, float],
    repair_config: RepairConfig | None = None,
    *,
    annotate: bool = True,
    trace: bool = True,
) -> tuple[float | None, list[EvalStep], str | None, list[str]]:
    cfg = repair_config or RepairConfig()
    if not math.isfinite(cfg.epsilon) or cfg.epsilon <= 0 or not math.isfinite(cfg.overflow_cap) or cfg.overflow_cap <= 0:
        return None, [], "Épsilon y límite numérico deben ser positivos y finitos.", []
    steps: list[EvalStep] = []
    repairs: list[str] = []
    stack: list[str] = []
    if annotate:
        for node in traverse_preorder(root):
            node.evaluated, node.error = None, None
            node.repaired, node.repair_note = False, None

    def visit(node: ExprNode) -> float:
        notes: list[str] = []

        def repair(message: str) -> None:
            if not cfg.enabled:
                raise ValueError(message)
            notes.append(message)

        def zero_result(numerator: float, operation: str) -> float:
            repair(f"{operation}: denominador cero; política {cfg.div_zero_strategy}.")
            if cfg.div_zero_strategy == "numerator":
                return numerator
            if cfg.div_zero_strategy == "one":
                return 1.0
            if cfg.div_zero_strategy == "epsilon":
                if operation == "potencia":
                    return math.pow(cfg.epsilon, numerator)
                return numerator % cfg.epsilon if operation == "módulo" else numerator / cfg.epsilon
            return 0.0

        try:
            args = [visit(child) for child in node.active_children]
            if node.kind == "number":
                value = float(node.num_value if node.num_value is not None else node.value)
            elif node.kind == "constant":
                value = CONSTANTS[node.value.lower()]
            elif node.kind == "variable":
                if node.value not in variables:
                    raise ValueError(f"Asigna un valor a la variable '{node.value}'.")
                value = float(variables[node.value])
            elif node.kind == "unary":
                value = -args[0] if node.value == "u-" else args[0]
            else:
                token = node.value
                spec = OPERATORS[token]
                if len(args) != spec.arity:
                    raise ValueError(f"{token} necesita {spec.arity} argumentos.")
                if token in ("/", "%") and args[1] == 0:
                    value = zero_result(args[0], "módulo" if token == "%" else "división")
                elif token in ("^", "pow"):
                    base, exponent = args
                    if base == 0 and exponent < 0:
                        value = zero_result(exponent, "potencia")
                    else:
                        if base < 0 and not exponent.is_integer():
                            repair("Potencia fraccionaria de base negativa: se aplica valor absoluto." if cfg.neg_root_strategy == "abs" else "Potencia fraccionaria de base negativa: resultado 0.")
                            base = abs(base) if cfg.neg_root_strategy == "abs" else 0.0
                            if cfg.neg_root_strategy == "zero":
                                value = 0.0
                            else:
                                value = math.pow(base, exponent)
                        else:
                            value = math.pow(base, exponent)
                elif token == "sqrt" and args[0] < 0:
                    repair("Raíz de un negativo: se aplica valor absoluto." if cfg.neg_root_strategy == "abs" else "Raíz de un negativo: resultado 0.")
                    value = math.sqrt(abs(args[0])) if cfg.neg_root_strategy == "abs" else 0.0
                elif token in ("log", "ln", "log2") and args[0] <= 0:
                    repair(f"{token} fuera de dominio: se usa |argumento| o ε si es cero.")
                    value = spec.function(abs(args[0]) if args[0] < 0 else cfg.epsilon)
                elif token in ("asin", "acos") and abs(args[0]) > 1:
                    repair(f"{token}: argumento limitado al intervalo [-1, 1].")
                    value = spec.function(max(-1.0, min(1.0, args[0])))
                elif token == "tan" and abs(math.cos(args[0])) < 1e-12:
                    repair("Tangente indefinida: resultado protegido 0.")
                    value = 0.0
                else:
                    value = float(spec.function(*args))
            value = float(value)
            if not math.isfinite(value) or (cfg.enabled and abs(value) > cfg.overflow_cap):
                repair(f"Resultado fuera del límite numérico: acotado a {cfg.overflow_cap:g}.")
                value = math.copysign(cfg.overflow_cap, value) if not math.isnan(value) else 0.0
        except OverflowError:
            if not cfg.enabled:
                if annotate:
                    node.error = "Desbordamiento numérico."
                raise ValueError("Desbordamiento numérico.") from None
            notes.append("Desbordamiento numérico: resultado acotado.")
            sign = -1 if node.value in ("^", "pow") and args[0] < 0 and args[1].is_integer() and int(args[1]) % 2 else 1
            value = sign * cfg.overflow_cap
        except (ValueError, ZeroDivisionError, KeyError, TypeError) as exc:
            if annotate:
                node.error = str(exc)
            raise ValueError(str(exc)) from exc
        note = " ".join(notes) or None
        repairs.extend(notes)
        if annotate:
            node.evaluated, node.repaired, node.repair_note = value, bool(notes), note
        if trace:
            if args:
                del stack[-len(args):]
            stack.append(format_number(value))
            description = note or (f"{node.display_label}({', '.join(format_number(a) for a in args)}) = {format_number(value)}" if args else f"{node.value} = {format_number(value)}")
            steps.append(EvalStep(len(steps) + 1, node.id, node.token_label, description, value, list(stack), bool(args), bool(notes), note))
        return value

    try:
        return visit(root), steps, None, repairs
    except (ValueError, RecursionError) as exc:
        return None, steps, str(exc), repairs


def rewrite_tree_with_structural_repairs(root: ExprNode, variables: dict[str, float], repair_config: RepairConfig | None = None) -> tuple[str, list[str]]:
    """Make the repairs at the current variable values explicit in a new expression."""
    from .parsing import detect_and_parse
    from .tree import to_infix_string

    cfg = repair_config or RepairConfig()
    if not cfg.enabled:
        return to_infix_string(root), []
    _, _, error, _ = evaluate_tree(root, variables, cfg)
    if error:
        return to_infix_string(root), []
    changes: list[str] = []

    def rewrite(node: ExprNode) -> str:
        if node.is_leaf:
            return node.value
        children = [rewrite(child) for child in node.active_children]
        token = node.value
        if node.kind == "unary":
            return f"-({children[0]})"
        if node.repaired:
            old = to_infix_string(node)
            if token == "sqrt" and node.children[0].evaluated < 0 and cfg.neg_root_strategy == "abs":
                result = f"sqrt(abs({children[0]}))"
            elif token in ("ln", "log", "log2") and node.children[0].evaluated <= 0:
                arg = f"abs({children[0]})" if node.children[0].evaluated < 0 else f"{cfg.epsilon:.17g}"
                result = f"{token}({arg})"
            elif token in ("asin", "acos"):
                result = f"{token}(max(-1, min(1, {children[0]})))"
            elif token in ("^", "pow") and node.children[0].evaluated < 0 and cfg.neg_root_strategy == "abs":
                result = f"abs({children[0]}) ^ ({children[1]})"
            elif token in ("/", "%") and cfg.div_zero_strategy == "epsilon":
                result = f"({children[0]}) {token} {cfg.epsilon:.17g}"
            else:
                result = f"{node.evaluated:.17g}"
            changes.append(f"{old} → {result}")
            return result
        if node.kind == "op":
            return f"({children[0]}) {token} ({children[1]})"
        return f"{token}({', '.join(children)})"

    expression = rewrite(root)
    return to_infix_string(detect_and_parse(expression, "infix", False)[0]), changes
