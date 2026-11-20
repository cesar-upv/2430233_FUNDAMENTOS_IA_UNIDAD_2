from __future__ import annotations

import math
from dataclasses import dataclass

from .evaluation import evaluate_tree
from .models import ExprNode, RepairConfig
from .sampling import SamplePoint, SamplingConfig, sample_points


@dataclass(frozen=True)
class CurveData:
    segments: list[list[tuple[float, float]]]
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    valid_samples: int
    invalid_samples: int
    repaired_samples: int
    variable: str
    repaired: bool
    points: tuple[SamplePoint, ...] = ()


def sample_curve(root: ExprNode, variables: dict[str, float], *, variable: str = "x", x_min: float = -10, x_max: float = 10, samples: int = 601, step: float | None = None, repair_config: RepairConfig | None = None) -> CurveData:
    if not all(math.isfinite(v) for v in (x_min, x_max)) or x_min >= x_max:
        raise ValueError("El inicio del intervalo debe ser menor que el final.")
    if step is None and not 3 <= samples <= 4001:
        raise ValueError("Usa entre 3 y 4001 muestras.")
    cfg = repair_config or RepairConfig(enabled=False)
    bindings = dict(variables)
    points: list[tuple[float, float | None]] = []
    invalid, repaired = 0, 0

    def value_at(x: float) -> tuple[float | None, bool]:
        bindings[variable] = x
        value, _, error, notes = evaluate_tree(root, bindings, cfg, annotate=False, trace=False)
        return (None if error or value is None or not math.isfinite(value) else value), bool(notes)

    xs = SamplingConfig(x_min, x_max, step).grid() if step is not None else tuple(x_min + (x_max - x_min) * i / (samples - 1) for i in range(samples))
    raw_points = sample_points(root, variables, xs, variable=variable, repair_config=cfg)
    for point in raw_points:
        invalid += point.y is None
        repaired += point.repaired
        points.append((point.x, point.y))
    ys = sorted(y for _, y in points if y is not None)
    if ys:
        # Trim isolated pole spikes from the viewport, keeping the sampled data intact.
        trim = int(len(ys) * 0.015) if len(ys) > 40 else 0
        low, high = ys[trim], ys[-trim - 1]
        pad = max((high - low) * 0.12, 0.5 if abs(high - low) < 1e-9 else 1e-6)
        y_min, y_max = low - pad, high + pad
    else:
        y_min, y_max = -1.0, 1.0
    span = y_max - y_min
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for x, y in points:
        if y is None:
            if current:
                segments.append(current)
                current = []
            continue
        if current:
            px, py = current[-1]
            mid, _ = value_at((px + x) / 2)
            # A pole or jump must not be rendered as a line through the graph.
            jump = abs(y - py) > span * 0.4
            singular = mid is None or (mid is not None and abs(mid - (py + y) / 2) > span * 0.5)
            if jump or singular:
                segments.append(current)
                current = []
        current.append((x, y))
    if current:
        segments.append(current)
    return CurveData(segments, x_min, x_max, y_min, y_max, len(ys), invalid, repaired, variable, cfg.enabled, raw_points)
