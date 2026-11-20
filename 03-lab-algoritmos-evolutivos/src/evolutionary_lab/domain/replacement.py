from dataclasses import dataclass
from enum import StrEnum

from evolutionary_lab.domain.models import Population


class ReplacementStrategy(StrEnum):
    BOOK_REFERENCE = "book_reference"
    CLASSROOM_CONDITIONAL = "classroom_conditional"


@dataclass(frozen=True)
class ReplacementResult:
    population: Population
    accepted: tuple[bool, ...]
