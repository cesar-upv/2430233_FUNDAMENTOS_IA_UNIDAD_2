from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class OperatorSpec:
    token: str
    label: str
    arity: int
    function: Callable[..., float]
    precedence: int = 4
    associativity: str = "L"
    aliases: tuple[str, ...] = ()
    generate: bool = True


# This registry feeds the parser, evaluator, generator and operator picker.
OPERATORS = {
    spec.token: spec for spec in (
        OperatorSpec("+", "Suma", 2, operator.add, 1),
        OperatorSpec("-", "Resta", 2, operator.sub, 1),
        OperatorSpec("*", "Multiplicación", 2, operator.mul, 2),
        OperatorSpec("/", "División", 2, operator.truediv, 2),
        OperatorSpec("%", "Módulo", 2, operator.mod, 2, aliases=("mod",)),
        OperatorSpec("^", "Potencia", 2, math.pow, 3, "R"),
        OperatorSpec("sqrt", "Raíz cuadrada", 1, math.sqrt),
        OperatorSpec("log", "Logaritmo base 10", 1, math.log10),
        OperatorSpec("sin", "Seno", 1, math.sin, aliases=("sen",)),
        OperatorSpec("cos", "Coseno", 1, math.cos),
        OperatorSpec("tan", "Tangente", 1, math.tan),
        # Extra functions retained for interpreter compatibility and explicit repairs.
        OperatorSpec("abs", "Valor absoluto", 1, abs, generate=False),
        OperatorSpec("ln", "Logaritmo natural", 1, math.log, generate=False),
        OperatorSpec("log2", "Logaritmo base 2", 1, math.log2, generate=False),
        OperatorSpec("asin", "Arcoseno", 1, math.asin, generate=False),
        OperatorSpec("acos", "Arcocoseno", 1, math.acos, generate=False),
        OperatorSpec("atan", "Arcotangente", 1, math.atan, generate=False),
        OperatorSpec("exp", "Exponencial", 1, math.exp, generate=False),
        OperatorSpec("cbrt", "Raíz cúbica", 1, math.cbrt, generate=False),
        OperatorSpec("floor", "Piso", 1, math.floor, generate=False),
        OperatorSpec("ceil", "Techo", 1, math.ceil, generate=False),
        OperatorSpec("round", "Redondeo", 1, round, generate=False),
        OperatorSpec("min", "Mínimo", 2, min, generate=False),
        OperatorSpec("max", "Máximo", 2, max, generate=False),
        OperatorSpec("pow", "Potencia", 2, math.pow, generate=False),
    )
}
GENERATOR_OPERATORS = tuple(key for key, spec in OPERATORS.items() if spec.generate)
BINARY_OPS = {key: (s.precedence, s.associativity, s.function) for key, s in OPERATORS.items() if s.precedence < 4}
FUNCTIONS = {key: (s.arity, s.function) for key, s in OPERATORS.items() if s.precedence == 4}
CONSTANTS = {"pi": math.pi, "π": math.pi, "e": math.e, "tau": math.tau, "phi": (1 + math.sqrt(5)) / 2}
ALIASES = {alias: token for token, spec in OPERATORS.items() for alias in spec.aliases}


def canonical_token(token: str) -> str:
    low = token.lower()
    return ALIASES.get(low, low) if low in ALIASES or low in OPERATORS or low in CONSTANTS else token
