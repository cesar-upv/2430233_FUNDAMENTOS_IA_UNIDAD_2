from evolutionary_lab.presentation.strings import text


class ConfigurationInputError(ValueError):
    pass


def explain_error(message: str) -> str:
    key = {
        "Real offspring is outside configured domains": "error_real_bounds",
        "real offspring must be a finite real number": "error_real_overflow",
        "Active one-point crossover requires at least two genes": (
            "error_short_chromosome"
        ),
        "Encoding grid is finer than floating-point domain spacing": (
            "error_precision_grid"
        ),
        "Precision must be positive": "error_precision",
        "Selection weights have zero total": "error_zero_fitness",
        "Identity fitness requires a nonnegative objective": "error_negative_fitness",
        "objective result must be a finite real number": "error_nonfinite_objective",
        "Book minimization fitness requires nonnegative cmax": "error_negative_cmax",
        "fitness offset must be a finite real number": "error_fitness_overflow",
        "selection fitness must be a finite real number": "error_fitness_overflow",
    }.get(message, "run_error")
    return text(key)
