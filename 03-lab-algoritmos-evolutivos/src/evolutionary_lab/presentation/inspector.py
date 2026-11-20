from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from evolutionary_lab.domain.evaluation import MINIMIZATION_POLICIES, FitnessPolicy
from evolutionary_lab.domain.models import BinaryGenotype, RealGenotype
from evolutionary_lab.domain.variation import (
    CrossoverResult,
    RealCrossoverResult,
    RealMutationResult,
)
from evolutionary_lab.evolution.encoding.binary import (
    genotype_to_integer,
    genotype_to_string,
)
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.simulation.snapshots import GenerationSnapshot

FIELDS = (
    "generation",
    "genotype",
    "decimal_genotype",
    "phenotype",
    "objective",
    "fitness",
    "fitness_policy",
    "fitness_reference",
    "seed",
    "parent_slots",
    "parent_probability",
    "parent_draw",
    "cut_point",
    "operator_details",
    "bounds_repairs",
    "mutation_attempt",
    "replacement_decision",
)


class IndividualInspector(QFrame):
    individual_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("inspector")
        self.setMinimumWidth(230)
        self.snapshot: GenerationSnapshot | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel(text("inspector"))
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self.selector = QComboBox()
        self.selector.setAccessibleName(text("individual"))
        layout.addWidget(self.selector)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.form = form = QFormLayout(content)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setSpacing(8)
        self.values: dict[str, QLabel] = {}
        self.labels: dict[str, QLabel] = {}
        for key in FIELDS:
            label = QLabel(text(key))
            label.setObjectName("muted")
            label.setWordWrap(True)
            value = QLabel(text("unavailable"))
            value.setWordWrap(True)
            value.setTextFormat(Qt.TextFormat.PlainText)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label, value)
            self.values[key] = value
            self.labels[key] = label
        for key in ("operator_details", "bounds_repairs"):
            form.setRowVisible(self.values[key], False)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.selector.currentIndexChanged.connect(self._selection_changed)
        self.selector.setEnabled(False)

    def set_snapshot(self, snapshot: GenerationSnapshot) -> None:
        previous = self.selector.currentData()
        self.snapshot = snapshot
        is_real = isinstance(snapshot.population.individuals[0].genotype, RealGenotype)
        for key in ("genotype", "cut_point", "mutation_attempt"):
            self.labels[key].setText(text(f"real_{key}" if is_real else key))
        self.form.setRowVisible(self.values["decimal_genotype"], not is_real)
        for key in ("operator_details", "bounds_repairs"):
            self.form.setRowVisible(self.values[key], is_real)
        self.selector.blockSignals(True)
        self.selector.clear()
        for item in snapshot.population:
            self.selector.addItem(
                text("individual_number").format(identifier=item.identifier),
                item.identifier,
            )
        target = self.selector.findData(previous)
        if target < 0:
            target = self.selector.findData(
                snapshot.statistics.best_individual.identifier
            )
        self.selector.setCurrentIndex(target)
        self.selector.blockSignals(False)
        self.selector.setEnabled(True)
        self._selection_changed(target)

    def select_individual(self, identifier: int) -> None:
        self.selector.setCurrentIndex(self.selector.findData(identifier))

    def clear(self) -> None:
        self.snapshot = None
        self.selector.clear()
        self.selector.setEnabled(False)
        for value in self.values.values():
            value.setText(text("unavailable"))

    def _selection_changed(self, index: int) -> None:
        if self.snapshot is None or index < 0:
            return
        snapshot = self.snapshot
        identifier = int(self.selector.itemData(index))
        individual = next(
            item for item in snapshot.population if item.identifier == identifier
        )
        values = {key: text("unavailable") for key in FIELDS}
        values.update(
            generation=str(snapshot.generation_index),
            phenotype=", ".join(f"{value:.12g}" for value in individual.phenotype),
            objective=f"{individual.objective_value:.12g}",
            fitness=f"{individual.selection_fitness:.12g}"
            if individual.selection_fitness is not None
            else text("unavailable"),
            seed=str(snapshot.config.seed),
        )
        if isinstance(individual.genotype, BinaryGenotype):
            chromosomes = individual.genotype.chromosomes
            values["genotype"] = (
                genotype_to_string(chromosomes[0])
                if len(chromosomes) == 1
                else "\n".join(
                    f"x{i + 1}: {genotype_to_string(item)}"
                    for i, item in enumerate(chromosomes)
                )
            )
            values["decimal_genotype"] = (
                str(genotype_to_integer(chromosomes[0]))
                if len(chromosomes) == 1
                else ", ".join(
                    f"x{i + 1}: {genotype_to_integer(item)}"
                    for i, item in enumerate(chromosomes)
                )
            )
        elif isinstance(individual.genotype, RealGenotype):
            values["genotype"] = "\n".join(
                f"x{i + 1}: {value:.12g}"
                for i, value in enumerate(individual.genotype.values)
            )
        values["fitness_policy"] = text(
            {
                FitnessPolicy.NONNEGATIVE_IDENTITY: "fitness_identity",
                FitnessPolicy.MINIMIZATION_BOOK: "fitness_book",
                FitnessPolicy.MINIMIZATION_SIGNED: "fitness_signed",
                FitnessPolicy.OBJECTIVE_ONLY: "fitness_objective_only",
            }[snapshot.config.fitness_policy]
        )
        if snapshot.config.fitness_policy in MINIMIZATION_POLICIES:
            values["fitness_reference"] = f"{snapshot.statistics.objective_max:.12g}"
        trace = snapshot.trace
        if trace is not None:
            slot = index
            parent = trace.selection.selected[slot]
            values["parent_slots"] = text("parent_origin").format(
                generation=snapshot.generation_index - 1, identifier=parent.identifier
            )
            if trace.selection.distribution is not None:
                source = trace.selection.indices[slot]
                values["parent_probability"] = (
                    f"{trace.selection.distribution.probabilities[source]:.8g}"
                )
                values["parent_draw"] = f"{trace.selection.positions[slot]:.8g}"
            else:
                tournament = trace.selection.tournaments[slot]
                values["parent_draw"] = text("tournament_participants").format(
                    first=tournament.participants[0], second=tournament.participants[1]
                )
            for pair in trace.reproduction.pairs:
                if slot not in pair.parent_slots:
                    continue
                if isinstance(pair.result, RealCrossoverResult):
                    values.update(
                        self._real_crossover_details(
                            pair.result, pair.parent_slots.index(slot)
                        )
                    )
                cuts = (
                    pair.result.cut_points
                    if isinstance(pair.result, CrossoverResult)
                    else ()
                )
                if pair.result.cut_point is not None or cuts:
                    values["cut_point"] = (
                        str(pair.result.cut_point)
                        if not cuts
                        else ", ".join(f"x{i + 1}: {cut}" for i, cut in enumerate(cuts))
                    )
                mate_slot = next(other for other in pair.parent_slots if other != slot)
                mate = trace.selection.selected[mate_slot]
                values["parent_slots"] += ", " + text("individual_number").format(
                    identifier=mate.identifier
                )
            mutation = trace.mutations[slot]
            positions = mutation.mutated_positions
            values["mutation_attempt"] = (
                ", ".join(map(str, positions)) if positions else text("none")
            )
            if isinstance(mutation, RealMutationResult):
                resets = []
                for position in positions:
                    resets.append(
                        text("real_reset_trace").format(
                            variable=position + 1,
                            value=mutation.genotype.values[position],
                            draw=mutation.replacement_draws[position],
                        )
                    )
                values["mutation_attempt"] = "\n".join(resets) or text("none")
            if (
                isinstance(individual.genotype, BinaryGenotype)
                and len(individual.genotype.variable_lengths) > 1
            ):
                start = 0
                variables = []
                for variable, length in enumerate(individual.genotype.variable_lengths):
                    local = [
                        position - start
                        for position in positions
                        if start <= position < start + length
                    ]
                    if local:
                        variables.append(
                            f"x{variable + 1}: " + ", ".join(map(str, local))
                        )
                    start += length
                values["mutation_attempt"] = (
                    "; ".join(variables) if variables else text("none")
                )
            values["replacement_decision"] = text(
                "child_adopted"
                if trace.replacement.accepted[slot]
                else "parent_retained"
            )
        for key, value in values.items():
            self.values[key].setText(value)
        self.individual_selected.emit(identifier)

    @staticmethod
    def _real_crossover_details(
        result: RealCrossoverResult, child_index: int
    ) -> dict[str, str]:
        details = text("real_operator_trace").format(
            operator=text(f"real_cross_{result.method}"), draw=result.random_value
        )
        if not result.applied:
            details += "\n" + text("crossover_skipped")
        if result.alpha is not None:
            details += "\n" + text("real_alpha_trace").format(alpha=result.alpha)
        if result.beta is not None:
            details += "\n" + text("real_sbx_trace").format(
                draw=result.sbx_draw, beta=result.beta
            )
        if result.gene_draws:
            details += "\n" + text("real_swap_trace").format(
                variables=", ".join(f"x{i + 1}" for i in result.swapped_positions)
                or text("none")
            )
        return {
            "operator_details": details,
            "bounds_repairs": ", ".join(
                f"x{i + 1}: {result.raw_offspring[child_index][i]:.8g} → "
                f"{result.offspring[child_index].values[i]:.8g}"
                for i in result.repaired_positions[child_index]
            )
            or text("none"),
        }
