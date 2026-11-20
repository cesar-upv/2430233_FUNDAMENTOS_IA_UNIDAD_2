from __future__ import annotations

from dataclasses import dataclass, field

from .evaluation import evaluate_tree
from .generation import GenerationConfig, generate_tree
from .models import EvalStep, ExprNode, ParseError, RepairConfig
from .operators import CONSTANTS, OPERATORS
from .parsing import detect_and_parse
from .tree import extract_variables, to_infix_string


@dataclass
class ExpressionSession:
    root: ExprNode | None = None
    variables: dict[str, float] = field(default_factory=lambda: {"x": 1.0})
    repairs: RepairConfig = field(default_factory=RepairConfig)
    syntax_repairs: list[str] = field(default_factory=list)
    runtime_repairs: list[str] = field(default_factory=list)
    steps: list[EvalStep] = field(default_factory=list)
    mode: str = "infix"
    result: float | None = None
    error: str | None = None

    def parse(self, expression: str, mode: str = "auto") -> None:
        root, detected, notes = detect_and_parse(expression, mode, self.repairs.enabled and self.repairs.syntax_repair)
        self.root, self.mode, self.syntax_repairs = root, detected, notes
        self.recalculate()

    def recalculate(self) -> None:
        if self.root is None:
            return
        for variable in extract_variables(self.root):
            self.variables.setdefault(variable, 1.0)
        self.result, self.steps, self.error, self.runtime_repairs = evaluate_tree(self.root, self.variables, self.repairs)

    def generate(self, config: GenerationConfig) -> str:
        self.root = generate_tree(config)
        self.mode, self.syntax_repairs = "infix", []
        self.recalculate()
        return to_infix_string(self.root)

    def execute(self, command: str) -> tuple[str | None, float]:
        target, expression = None, command.strip()
        if "=" in expression:
            target, expression = (part.strip() for part in expression.split("=", 1))
            if not target.isidentifier() or target.lower() in CONSTANTS or target.lower() in OPERATORS or target.lower() == "sen":
                raise ParseError("Usa un nombre de variable distinto de una función o constante.")
        root, _, _ = detect_and_parse(expression, "auto", self.repairs.enabled and self.repairs.syntax_repair)
        result, _, error, _ = evaluate_tree(root, self.variables, self.repairs)
        if error or result is None:
            raise ParseError(error or "No se pudo evaluar la expresión.")
        if target:
            self.variables[target] = result
            self.recalculate()
        else:
            self.parse(expression)
        return target, result
