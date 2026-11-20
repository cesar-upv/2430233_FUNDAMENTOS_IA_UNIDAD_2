from math import isfinite


def finite_float(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite real number") from error
    if not isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def require_integer(value: int, name: str, minimum: int | None = None) -> None:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def probability(value: float, name: str) -> float:
    result = finite_float(value, name)
    if not 0 <= result <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return result
