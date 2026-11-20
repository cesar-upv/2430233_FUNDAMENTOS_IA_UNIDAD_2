from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from collections.abc import Iterable

from .evaluation import evaluate_tree
from .models import ExprNode, RepairConfig

MAX_SAMPLES = 10_001


@dataclass(frozen=True)
class SamplingConfig:
    x_min: float = 0.0
    x_max: float = 1.0
    step: float = 0.001

    def grid(self) -> tuple[float, ...]:
        if not all(math.isfinite(v) for v in (self.x_min, self.x_max, self.step)):
            raise ValueError("Intervalo y paso deben ser números finitos.")
        if self.x_min >= self.x_max:
            raise ValueError("El inicio del intervalo debe ser menor que el final.")
        if self.step <= 0:
            raise ValueError("El paso debe ser mayor que cero.")
        start, end, step = (Decimal(str(v)) for v in (self.x_min, self.x_max, self.step))
        try:
            count = int((end - start) // step) + 1
        except (InvalidOperation, OverflowError):
            raise ValueError("El paso es demasiado pequeño para este intervalo.") from None
        if count > MAX_SAMPLES:
            raise ValueError(f"El intervalo y paso exceden {MAX_SAMPLES:,} puntos. Aumenta el paso.")
        if count < 2:
            raise ValueError("El paso debe permitir al menos dos puntos en el intervalo.")
        points = tuple(float(start + i * step) for i in range(count))
        if any(b <= a for a, b in zip(points, points[1:])):
            raise ValueError("El paso es demasiado pequeño para distinguir los valores x.")
        return points


@dataclass(frozen=True)
class SamplePoint:
    x: float
    y: float | None
    repaired: bool = False
    error: str | None = None


def sample_points(root: ExprNode, variables: dict[str, float], xs: Iterable[float], *, variable: str = "x", repair_config: RepairConfig | None = None) -> tuple[SamplePoint, ...]:
    cfg = repair_config or RepairConfig(enabled=False)
    bindings = dict(variables)
    points = []
    for x in xs:
        bindings[variable] = x
        value, _, error, repairs = evaluate_tree(root, bindings, cfg, annotate=False, trace=False)
        if value is not None and not math.isfinite(value):
            error, value = "Resultado no finito.", None
        points.append(SamplePoint(x, None if error else value, bool(repairs), error))
    return tuple(points)
