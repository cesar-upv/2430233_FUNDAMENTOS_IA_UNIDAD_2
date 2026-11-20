from __future__ import annotations

import math
from dataclasses import dataclass, field

from .operators import OPERATORS

@dataclass
class RepairConfig:
    enabled: bool = True
    syntax_repair: bool = True
    # 'abs': sqrt(|x|), 'zero': 0.0
    neg_root_strategy: str = "abs"
    # 'zero': 0.0 (Protected Division GP), 'epsilon': a / 1e-6, 'numerator': a, 'one': 1.0
    div_zero_strategy: str = "zero"
    # 'abs_eps': ln(|x|) or ln(1e-6) if x==0
    log_strategy: str = "abs_eps"
    # 'clamp': asin/acos(clamp(x, -1, 1))
    trig_strategy: str = "clamp"
    epsilon: float = 1e-6
    overflow_cap: float = 1e12


@dataclass
class EvalStep:
    step_index: int
    node_id: int
    token: str
    description: str
    result: float
    stack_snapshot: list[str]
    is_operation: bool
    repaired: bool = False
    repair_note: str | None = None


@dataclass
class ExprNode:
    id: int
    value: str
    kind: str  # 'number' | 'variable' | 'constant' | 'op' | 'unary' | 'func'
    children: list[ExprNode] = field(default_factory=list)
    num_value: float | None = None
    evaluated: float | None = None
    error: str | None = None
    repaired: bool = False
    repair_note: str | None = None
    # Layout positions assigned by layout algorithm
    x: float = 0.0
    y: float = 0.0
    depth: int = 0

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def active_children(self) -> list[ExprNode]:
        """Unary genes always express the left branch; the right can remain dormant."""
        arity = 1 if self.kind == "unary" else OPERATORS[self.value].arity if self.kind in ("op", "func") else 0
        return self.children[:arity]

    @property
    def left(self) -> ExprNode | None:
        return self.children[0] if len(self.children) >= 1 else None

    @property
    def right(self) -> ExprNode | None:
        return self.children[1] if len(self.children) >= 2 else None

    @property
    def display_label(self) -> str:
        if self.kind == "unary" and self.value == "u-":
            return "−x"
        if self.kind == "unary" and self.value == "u+":
            return "+x"
        return self.value

    @property
    def token_label(self) -> str:
        if self.kind == "unary" and self.value == "u-":
            return "-u"
        if self.kind == "unary" and self.value == "u+":
            return "+u"
        return self.value


class ParseError(Exception):
    pass


def format_number(val: float | None) -> str:
    if val is None:
        return "?"
    if math.isnan(val):
        return "NaN"
    if math.isinf(val):
        return "∞" if val > 0 else "-∞"
    if abs(val - round(val)) < 1e-10 and abs(val) < 1e15:
        return str(int(round(val)))
    return f"{val:.6g}"
