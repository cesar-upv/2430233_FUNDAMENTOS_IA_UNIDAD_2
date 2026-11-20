from dataclasses import dataclass

from .sampling import SamplingConfig

COSINE_EXPRESSION = "6.87 + 11 * cos(7.23 * x^3)"


@dataclass(frozen=True)
class ExpressionPreset:
    name: str
    expression: str
    mode: str = "infix"
    sampling: SamplingConfig | None = None


PRESETS = (
    ExpressionPreset("Onda y parábola", "sen(x) + x ^ 2 / 6"),
    ExpressionPreset("Coseno cúbico · [0, 1], paso 0.001", COSINE_EXPRESSION, sampling=SamplingConfig()),
    ExpressionPreset("Coseno cúbico · reparar * *", "(6.87 + 11 *  *cos(7.23*  x^3))", sampling=SamplingConfig()),
    ExpressionPreset("Seno amortiguado", "sen(x) / (1 + x ^ 2)"),
    ExpressionPreset("Raíces y reparaciones", "sqrt(-16) + 12 / (5 - 5) + ln(-e^2)"),
    ExpressionPreset("Asíntota", "1 / x"),
    ExpressionPreset("Logaritmo", "log(x)"),
    ExpressionPreset("Postfija", "x 2 ^ 3 +", "postfix"),
    ExpressionPreset("Prefija", "+ sin x * 2 x", "prefix"),
)
