from __future__ import annotations

import csv
import math
from decimal import Decimal
from pathlib import Path
from collections.abc import Iterable

from .sampling import MAX_SAMPLES, SamplePoint


def write_points_csv(path: str | Path, points: Iterable[SamplePoint], *, step: float = 0.001, x_min: float = 0.0) -> int:
    """Preserve every grid point; an undefined y is an empty CSV field."""
    if not math.isfinite(step) or step <= 0 or not math.isfinite(x_min):
        raise ValueError("El paso debe ser positivo y el inicio debe ser finito.")
    decimals = max(3, -Decimal(str(step)).normalize().as_tuple().exponent, -Decimal(str(x_min)).normalize().as_tuple().exponent)
    decimals = min(decimals, 12)
    count = 0
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("x", "y"))
        for point in points:
            writer.writerow((f"{point.x:.{decimals}f}", "" if point.y is None else format(point.y, ".15g")))
            count += 1
    return count


def read_points_csv(path: str | Path) -> tuple[SamplePoint, ...]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(4096)
        stream.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(stream, dialect, skipinitialspace=True, strict=True)
        try:
            header = next(reader, [])
            columns = [value.strip().lower() for value in header]
            if len(columns) != 2 or set(columns) != {"x", "y"}:
                raise ValueError("El CSV debe tener exactamente las columnas x,y en la primera fila.")
            xi, yi = columns.index("x"), columns.index("y")
            points = []
            for line, row in enumerate(reader, 2):
                if not row or all(not cell.strip() for cell in row):
                    continue
                if len(points) >= MAX_SAMPLES:
                    raise ValueError(f"El CSV excede {MAX_SAMPLES:,} filas de datos.")
                if len(row) != 2:
                    raise ValueError(f"Fila {line}: se esperaban dos columnas.")
                try:
                    x = float(row[xi])
                    y = float(row[yi]) if row[yi].strip() else None
                except ValueError:
                    raise ValueError(f"Fila {line}: x e y deben ser números con punto decimal.") from None
                if not math.isfinite(x) or (y is not None and not math.isfinite(y)):
                    raise ValueError(f"Fila {line}: no se permiten NaN ni infinito.")
                points.append(SamplePoint(x, y, error="Dato y ausente." if y is None else None))
        except csv.Error as exc:
            raise ValueError(f"Formato CSV no válido: {exc}") from exc
    if not points:
        raise ValueError("El CSV no contiene filas de datos.")
    return tuple(points)
