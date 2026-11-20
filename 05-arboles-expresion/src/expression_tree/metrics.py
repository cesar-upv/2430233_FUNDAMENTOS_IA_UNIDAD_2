from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from collections.abc import Sequence

from .models import ExprNode, RepairConfig
from .sampling import SamplePoint, sample_points


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    name: str
    description: str


METRICS = (
    MetricDefinition("mse", "MSE", "Media de (predicción − referencia)². Ideal: 0."),
    MetricDefinition("rmse", "RMSE", "Raíz cuadrada del MSE, en las unidades de y. Ideal: 0."),
    MetricDefinition("nmse", "NMSE", "MSE / varianza poblacional de la referencia. Ideal: 0; 1 equivale a predecir su media."),
    MetricDefinition("r2", "R²", "1 − SSE / SST. Ideal: 1; puede ser negativo. N/D con menos de dos pares o referencia constante."),
    MetricDefinition("mae", "MAE", "Media del error absoluto. Ideal: 0."),
    MetricDefinition("medae", "MedAE", "Mediana del error absoluto. Ideal: 0."),
    MetricDefinition("max_error", "Error máximo", "Máximo error absoluto. Ideal: 0."),
    MetricDefinition("bias", "Sesgo", "Media de predicción − referencia. Ideal: 0; el signo indica sobreestimación o subestimación."),
    MetricDefinition("mape", "MAPE (%)", "100 × media de |error / referencia|. Excluye referencias iguales a cero. Ideal: 0."),
)


@dataclass(frozen=True)
class ErrorMetrics:
    values: dict[str, float | None]
    count: int
    mape_count: int
    notes: tuple[str, ...]


def calculate_metrics(reference: Sequence[float], prediction: Sequence[float]) -> ErrorMetrics:
    if len(reference) != len(prediction) or not reference:
        raise ValueError("Se necesita al menos un par de valores de referencia y predicción del mismo tamaño.")
    if not all(math.isfinite(v) for v in (*reference, *prediction)):
        raise ValueError("Las métricas requieren valores finitos.")
    n, notes = len(reference), []
    try:
        residuals = [p - r for r, p in zip(reference, prediction)]
        absolute = [abs(value) for value in residuals]
        sse = math.fsum(value * value for value in residuals)
        mse = sse / n
        mean = math.fsum(reference) / n
        sst = math.fsum((value - mean) ** 2 for value in reference)
        # SSE/SST equals MSE/population variance, with one fewer rounding step.
        nmse = sse / sst if n >= 2 and sst > 0 else None
        if nmse is None:
            notes.append("NMSE y R² no están definidos: la referencia es constante o hay menos de dos pares.")
        ratios = [abs(error / ref) for ref, error in zip(reference, residuals) if ref != 0]
        if len(ratios) < n:
            notes.append(f"MAPE excluye {n - len(ratios)} referencias iguales a cero.")
        values = {"mse": mse, "rmse": math.sqrt(mse), "nmse": nmse, "r2": 1 - nmse if nmse is not None else None,
                  "mae": math.fsum(absolute) / n, "medae": median(absolute), "max_error": max(absolute),
                  "bias": math.fsum(residuals) / n, "mape": math.fsum(ratios) / len(ratios) * 100 if ratios else None}
        if any(value is not None and not math.isfinite(value) for value in values.values()):
            raise OverflowError
    except (OverflowError, ValueError):
        raise ValueError("Los valores son demasiado grandes para calcular métricas finitas. Reduce su escala.") from None
    return ErrorMetrics(values, n, len(ratios), tuple(notes))


@dataclass(frozen=True)
class ComparisonRow:
    x: float
    reference: float | None
    prediction: float | None
    error: float | None
    repaired: bool


@dataclass(frozen=True)
class ComparisonResult:
    metrics: ErrorMetrics
    rows: tuple[ComparisonRow, ...]
    excluded: int
    repaired: int


def compare_against_points(root: ExprNode, variables: dict[str, float], reference: Sequence[SamplePoint], *, variable: str = "x", repair_config: RepairConfig | None = None) -> ComparisonResult:
    predictions = sample_points(root, variables, (point.x for point in reference), variable=variable, repair_config=repair_config)
    rows = tuple(ComparisonRow(ref.x, ref.y, pred.y, pred.y - ref.y if pred.y is not None and ref.y is not None else None, ref.repaired or pred.repaired) for ref, pred in zip(reference, predictions))
    valid = [row for row in rows if row.error is not None]
    if not valid:
        raise ValueError("No hay pares válidos para comparar. Revisa el dominio, los datos o la reparación.")
    metrics = calculate_metrics([row.reference for row in valid], [row.prediction for row in valid])
    return ComparisonResult(metrics, rows, len(rows) - len(valid), sum(row.repaired for row in valid))
