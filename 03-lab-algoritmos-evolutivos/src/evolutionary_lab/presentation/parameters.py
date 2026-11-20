from dataclasses import dataclass
from math import isfinite

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.domain.evaluation import FitnessPolicy
from evolutionary_lab.domain.models import (
    Interval,
    OptimizationDirection,
    Representation,
)
from evolutionary_lab.domain.problems import OptimizationProblem
from evolutionary_lab.domain.replacement import ReplacementStrategy
from evolutionary_lab.domain.selection import SelectionMethod, ZeroWeightPolicy
from evolutionary_lab.domain.variation import (
    MutationMethod,
    RealBoundsPolicy,
    RealCrossoverMethod,
    ReproductionPolicy,
    SbxFormula,
)
from evolutionary_lab.evolution.engine import validate_configuration
from evolutionary_lab.presentation.errors import ConfigurationInputError, explain_error
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.problems.registry import (
    PROBLEMS,
    VARIABLE_DIMENSION_PROBLEMS,
    get_problem,
)

SELECTIONS = tuple(SelectionMethod)
REPLACEMENTS = tuple(ReplacementStrategy)
REPRODUCTIONS = tuple(ReproductionPolicy)
ZERO_POLICIES = tuple(ZeroWeightPolicy)
MAX_HISTORY_INDIVIDUALS = 100_000


class PercentageSpinBox(QDoubleSpinBox):
    def textFromValue(self, value: float) -> str:
        return (
            self.locale()
            .toString(value, "f", self.decimals())
            .rstrip("0")
            .rstrip(self.locale().decimalPoint())
        )


@dataclass
class VariableInput:
    lower: QLineEdit
    upper: QLineEdit
    precision: QLineEdit


def _choices(keys: tuple[str, ...]) -> QComboBox:
    combo = QComboBox()
    combo.addItems([text(key) for key in keys])
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(16)
    return combo


def _group(title_key: str) -> tuple[QWidget, QVBoxLayout, QFormLayout]:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    title = QLabel(text(title_key))
    title.setObjectName("parameterSectionTitle")
    layout.addWidget(title)
    form = QFormLayout()
    form.setSpacing(8)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    layout.addLayout(form)
    return widget, layout, form


def _row(
    form: QFormLayout, key: str, control: QWidget, tooltip: str | None = None
) -> None:
    label = QLabel(text(key))
    label.setWordWrap(True)
    label.setFixedWidth(180)
    label.setBuddy(control)
    control.setAccessibleName(text(key))
    if tooltip:
        control.setToolTip(text(tooltip))
    form.addRow(label, control)


def _note(key: str) -> QLabel:
    label = QLabel(text(key))
    label.setWordWrap(True)
    label.setObjectName("muted")
    return label


class ParameterWorkspace(QWidget):
    run_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._columns = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        self.grid = QGridLayout(content)
        self.grid.setContentsMargins(4, 4, 16, 4)
        self.grid.setHorizontalSpacing(28)
        self.grid.setVerticalSpacing(24)
        self.problem_group, problem_layout, self.problem_form = _group(
            "parameter_problem"
        )
        self.population_group, _, population_form = _group("parameter_population")
        self.operators_group, operators_layout, operators_form = _group(
            "parameter_operators"
        )
        self.execution_group, execution_layout, execution_form = _group(
            "parameter_execution"
        )
        self.groups = (
            self.problem_group,
            self.population_group,
            self.operators_group,
            self.execution_group,
        )
        self.direction = _choices(("maximize", "minimize"))
        self.project_selector = _choices(("project_binary", "project_real"))
        self.encoding_label = QLabel(text("encoding_binary"))
        self.problem_selector = _choices(())
        self.dimensions = QSpinBox()
        self.dimensions.setRange(1, 10)
        self.dimensions.setValue(2)
        self.fitness_policy = _choices(())
        _row(self.problem_form, "project", self.project_selector)
        _row(self.problem_form, "representation", self.encoding_label)
        _row(
            self.problem_form,
            "optimization_direction",
            self.direction,
            "direction_help",
        )
        _row(self.problem_form, "objective_problem", self.problem_selector)
        _row(
            self.problem_form, "variable_count", self.dimensions, "variable_count_help"
        )
        _row(
            self.problem_form,
            "fitness_policy",
            self.fitness_policy,
            "fitness_policy_help",
        )
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        problem_layout.addWidget(self.description)
        self.fitness_help = _note("nonnegative_identity_help")
        problem_layout.addWidget(self.fitness_help)
        self.variable_widget = QWidget()
        self.variable_grid = QGridLayout(self.variable_widget)
        self.variable_grid.setContentsMargins(0, 0, 0, 0)
        self.variable_grid.setSpacing(8)
        self.variables: list[VariableInput] = []
        problem_layout.addWidget(self.variable_widget)
        self.population_size = QSpinBox()
        self.population_size.setRange(1, 500)
        self.population_size.setValue(10)
        self.generation_limit = QSpinBox()
        self.generation_limit.setRange(0, 2000)
        self.generation_limit.setValue(100)
        _row(population_form, "population_size", self.population_size)
        _row(
            population_form,
            "generation_limit",
            self.generation_limit,
            "generation_limit_help",
        )
        self.seed = QLineEdit("42")
        self.seed.setMaxLength(100)
        _row(execution_form, "seed", self.seed, "seed_help")
        self.selection = _choices(
            ("selection_roulette", "selection_sus", "selection_tournament")
        )
        self.crossover = PercentageSpinBox()
        self.mutation = PercentageSpinBox()
        for control, value in ((self.crossover, 70.0), (self.mutation, 1.0)):
            control.setRange(0, 100)
            control.setDecimals(4)
            control.setSuffix(" %")
            control.setValue(value)
        self.reproduction = _choices(("reproduction_book", "reproduction_pairwise"))
        self.replacement = _choices(("replacement_book", "replacement_classroom"))
        self.zero_weights = _choices(("zero_weights_error", "zero_weights_uniform"))
        self.mutation_operator = _choices(("mutation_bit_flip",))
        self.real_crossover = _choices(())
        self.uniform_swap = PercentageSpinBox()
        self.uniform_swap.setRange(0, 100)
        self.uniform_swap.setDecimals(4)
        self.uniform_swap.setSuffix(" %")
        self.uniform_swap.setValue(50)
        self.arithmetic_alpha = QDoubleSpinBox()
        self.arithmetic_alpha.setRange(0, 1)
        self.arithmetic_alpha.setDecimals(4)
        self.arithmetic_alpha.setValue(0.5)
        self.sbx_index = QDoubleSpinBox()
        self.sbx_index.setRange(0, 100)
        self.sbx_index.setValue(1)
        self.sbx_formula = _choices(("sbx_literal", "sbx_continuous"))
        self.bounds_policy = _choices(("bounds_clip", "bounds_reject"))
        _row(operators_form, "selection_method", self.selection, "selection_help")
        _row(
            operators_form, "real_crossover", self.real_crossover, "real_crossover_help"
        )
        _row(operators_form, "mutation_operator", self.mutation_operator)
        _row(operators_form, "crossover_rate", self.crossover, "crossover_help")
        _row(operators_form, "mutation_rate", self.mutation, "mutation_help")
        _row(operators_form, "uniform_swap", self.uniform_swap, "uniform_swap_help")
        _row(
            operators_form,
            "arithmetic_alpha",
            self.arithmetic_alpha,
            "arithmetic_alpha_help",
        )
        _row(operators_form, "sbx_index", self.sbx_index, "sbx_index_help")
        _row(operators_form, "sbx_formula", self.sbx_formula, "sbx_formula_help")
        _row(operators_form, "bounds_policy", self.bounds_policy, "bounds_policy_help")
        _row(
            operators_form,
            "reproduction_policy",
            self.reproduction,
            "reproduction_help",
        )
        _row(
            operators_form, "replacement_strategy", self.replacement, "replacement_help"
        )
        _row(operators_form, "zero_weights", self.zero_weights, "zero_weights_help")
        self.operators_form = operators_form
        self.selection.currentIndexChanged.connect(self._selection_changed)
        self.reproduction_help = _note("reproduction_book_help")
        operators_layout.addWidget(self.reproduction_help)
        self.reproduction.currentIndexChanged.connect(self._describe_reproduction)
        execution_layout.addWidget(_note("parameter_history_note"))
        self.run_button = QPushButton(text("run_parameters"))
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.run_requested.emit)
        execution_layout.addWidget(self.run_button)
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)
        self.direction.currentIndexChanged.connect(self._direction_changed)
        self.problem_selector.currentIndexChanged.connect(self._problem_changed)
        self.dimensions.valueChanged.connect(self._dimensions_changed)
        self.fitness_policy.currentIndexChanged.connect(self._describe_fitness)
        self.project_selector.currentIndexChanged.connect(self._project_changed)
        self.real_crossover.currentIndexChanged.connect(self._real_operator_changed)
        self._direction_changed(0)
        self._arrange()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._arrange()

    def _arrange(self) -> None:
        columns = 2 if self.width() >= 1050 else 1
        if columns == self._columns:
            return
        self._columns = columns
        for row in range(5):
            self.grid.setRowStretch(row, 0)
        for group in self.groups:
            self.grid.removeWidget(group)
        positions = (
            ((0, 0), (1, 0), (0, 1), (1, 1))
            if columns == 2
            else tuple((i, 0) for i in range(4))
        )
        for group, (row, column) in zip(self.groups, positions, strict=True):
            self.grid.addWidget(group, row, column, alignment=Qt.AlignmentFlag.AlignTop)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if columns == 2 else 0)
        self.grid.setRowStretch(2 if columns == 2 else 4, 1)
        # Keep keyboard order consistent with the grouped reading path.
        controls = [
            self.project_selector,
            self.direction,
            self.problem_selector,
            self.dimensions,
            self.fitness_policy,
        ]
        controls += [
            control
            for variable in self.variables
            for control in (variable.lower, variable.upper, variable.precision)
        ]
        controls += [
            self.population_size,
            self.generation_limit,
            self.selection,
            self.real_crossover,
            self.mutation_operator,
            self.crossover,
            self.mutation,
            self.uniform_swap,
            self.arithmetic_alpha,
            self.sbx_index,
            self.sbx_formula,
            self.bounds_policy,
            self.reproduction,
            self.replacement,
            self.zero_weights,
            self.seed,
            self.run_button,
        ]
        for first, second in zip(controls, controls[1:], strict=False):
            QWidget.setTabOrder(first, second)

    def selected_problem(self) -> OptimizationProblem:
        identifier = str(self.problem_selector.currentData())
        return get_problem(
            identifier,
            self.dimensions.value()
            if identifier in VARIABLE_DIMENSION_PROBLEMS
            else None,
        )

    @property
    def representation(self) -> Representation:
        return (
            Representation.BINARY
            if self.project_selector.currentIndex() == 0
            else Representation.REAL
        )

    @Slot(int)
    def _project_changed(self, index: int) -> None:
        self.encoding_label.setText(
            text("encoding_binary" if index == 0 else "encoding_real")
        )
        self._build_variables()

    def _configure_operators(self) -> None:
        is_real = self.representation == Representation.REAL
        previous = self.real_crossover.currentData()
        self.real_crossover.blockSignals(True)
        self.real_crossover.clear()
        for method in RealCrossoverMethod:
            if method != RealCrossoverMethod.ONE_POINT or len(self.variables) > 1:
                self.real_crossover.addItem(text(f"real_cross_{method}"), method)
        selected = self.real_crossover.findData(previous)
        self.real_crossover.setCurrentIndex(
            selected
            if selected >= 0
            else self.real_crossover.findData(RealCrossoverMethod.SBX)
        )
        self.real_crossover.blockSignals(False)
        self.operators_form.setRowVisible(self.real_crossover, is_real)
        self.operators_form.setRowVisible(self.reproduction, not is_real)
        self.mutation_operator.clear()
        self.mutation_operator.addItem(
            text("mutation_uniform_reset" if is_real else "mutation_bit_flip")
        )
        mutation_label = self.operators_form.labelForField(self.mutation)
        assert isinstance(mutation_label, QLabel)
        mutation_label.setText(
            text("real_mutation_rate" if is_real else "mutation_rate")
        )
        self.mutation.setToolTip(
            text("real_mutation_help" if is_real else "mutation_help")
        )
        self.crossover.setToolTip(
            text("real_crossover_probability_help" if is_real else "crossover_help")
        )
        self._real_operator_changed(0)
        self._describe_reproduction(self.reproduction.currentIndex())

    @Slot(int)
    def _real_operator_changed(self, index: int) -> None:
        is_real = self.representation == Representation.REAL
        method = self.real_crossover.currentData()
        for control, visible in (
            (self.uniform_swap, method == RealCrossoverMethod.UNIFORM),
            (self.arithmetic_alpha, method == RealCrossoverMethod.ARITHMETIC),
            (self.sbx_index, method == RealCrossoverMethod.SBX),
            (self.sbx_formula, method == RealCrossoverMethod.SBX),
            (self.bounds_policy, method == RealCrossoverMethod.SBX),
        ):
            self.operators_form.setRowVisible(control, is_real and visible)

    @Slot(int)
    def _direction_changed(self, index: int) -> None:
        direction = (OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE)[
            index
        ]
        self.problem_selector.blockSignals(True)
        self.problem_selector.clear()
        for problem in PROBLEMS.values():
            if problem.direction == direction:
                self.problem_selector.addItem(problem.title, problem.identifier)
        self.problem_selector.blockSignals(False)
        self._problem_changed(0)

    @Slot(int)
    def _problem_changed(self, index: int) -> None:
        if index < 0:
            return
        identifier = str(self.problem_selector.currentData())
        base = get_problem(identifier)
        self.dimensions.blockSignals(True)
        self.dimensions.setValue(len(base.domains))
        self.dimensions.blockSignals(False)
        self.problem_form.setRowVisible(
            self.dimensions, identifier in VARIABLE_DIMENSION_PROBLEMS
        )
        self.fitness_policy.blockSignals(True)
        self.fitness_policy.clear()
        if base.direction == OptimizationDirection.MAXIMIZE:
            self.fitness_policy.addItem(
                text("fitness_identity"), FitnessPolicy.NONNEGATIVE_IDENTITY
            )
        else:
            # Only these registered objectives are nonnegative throughout their domains.
            if identifier in ("project_01.min1", "project_01.rastrigin"):
                self.fitness_policy.addItem(
                    text("fitness_book"), FitnessPolicy.MINIMIZATION_BOOK
                )
            self.fitness_policy.addItem(
                text("fitness_signed"), FitnessPolicy.MINIMIZATION_SIGNED
            )
        self.fitness_policy.blockSignals(False)
        self.problem_form.setRowVisible(
            self.fitness_policy, base.direction == OptimizationDirection.MINIMIZE
        )
        self._describe_fitness(0)
        self._build_variables()

    @Slot(int)
    def _dimensions_changed(self, index: int) -> None:
        self._build_variables()

    def _build_variables(self) -> None:
        while self.variable_grid.count():
            item = self.variable_grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.variables.clear()
        problem = self.selected_problem()
        formula = (
            text("f1_readable")
            if problem.identifier == "project_01.f1"
            else problem.formula
        )
        self.description.setText(
            text("problem_description").format(
                formula=formula,
                domains=" · ".join(
                    f"x{i + 1} ∈ [{d.lower:g}, {d.upper:g}]"
                    for i, d in enumerate(problem.domains)
                ),
            )
        )
        self.description.setToolTip(problem.source_reference or "")
        for column, key in enumerate(
            ("variable", "domain_lower", "domain_upper", "precision_short")
        ):
            caption = _note(key)
            self.variable_grid.addWidget(caption, 0, column)
            caption.setVisible(
                column < 3 or self.representation == Representation.BINARY
            )
        for index, domain in enumerate(problem.domains):
            controls = [
                QLineEdit(value)
                for value in (f"{domain.lower:g}", f"{domain.upper:g}", "0.001")
            ]
            self.variable_grid.addWidget(QLabel(f"x{index + 1}"), index + 1, 0)
            for column, control in enumerate(controls, start=1):
                control.setMaxLength(100)
                control.setMinimumWidth(60)
                control.setAccessibleName(
                    f"x{index + 1} · "
                    + text(
                        ("domain_lower", "domain_upper", "precision_short")[column - 1]
                    )
                )
                control.setToolTip(
                    text("variable_domain_help").format(
                        lower=domain.lower, upper=domain.upper
                    )
                    if column < 3
                    else text("precision_help")
                )
                self.variable_grid.addWidget(control, index + 1, column)
                visible = column < 3 or self.representation == Representation.BINARY
                control.setVisible(visible)
                self.variable_grid.setColumnStretch(column, 1 if visible else 0)
            self.variables.append(VariableInput(*controls))
        self.precision = self.variables[0].precision
        self._configure_operators()
        self._columns = 0
        self._arrange()

    @Slot(int)
    def _describe_fitness(self, index: int) -> None:
        policy = self.fitness_policy.currentData()
        if policy is not None:
            self.fitness_help.setText(text(f"{policy}_help"))

    @Slot(int)
    def _describe_reproduction(self, index: int) -> None:
        self.reproduction_help.setText(
            text(
                "real_reproduction_help"
                if self.representation == Representation.REAL
                else "reproduction_book_help"
                if index == 0
                else "reproduction_pairwise_help"
            )
        )

    @Slot(int)
    def _selection_changed(self, index: int) -> None:
        self.operators_form.setRowVisible(
            self.zero_weights, SELECTIONS[index] != SelectionMethod.BINARY_TOURNAMENT
        )

    def configuration(self) -> ExperimentConfig:
        problem = self.selected_problem()
        domains = []
        precisions = []
        for index, (variable, allowed) in enumerate(
            zip(self.variables, problem.domains, strict=True)
        ):
            try:
                domain = Interval(
                    float(variable.lower.text().replace(",", ".")),
                    float(variable.upper.text().replace(",", ".")),
                )
                if domain.lower < allowed.lower or domain.upper > allowed.upper:
                    raise ValueError
                domains.append(domain)
            except ValueError as error:
                raise ConfigurationInputError(
                    text("error_variable_domain").format(
                        variable=index + 1, lower=allowed.lower, upper=allowed.upper
                    )
                ) from error
            if self.representation == Representation.REAL:
                continue
            try:
                precision = float(variable.precision.text().strip().replace(",", "."))
                if not isfinite(precision) or precision <= 0:
                    raise ValueError
                precisions.append(precision)
            except ValueError as error:
                raise ConfigurationInputError(text("error_precision")) from error
        try:
            seed = int(self.seed.text().strip())
        except ValueError as error:
            raise ConfigurationInputError(text("error_seed")) from error
        config = ExperimentConfig(
            problem_id=problem.identifier,
            domains=tuple(domains),
            precision=tuple(precisions),
            population_size=self.population_size.value(),
            generation_limit=self.generation_limit.value(),
            seed=seed,
            representation=self.representation,
            mutation_method=MutationMethod.BIT_FLIP
            if self.representation == Representation.BINARY
            else MutationMethod.UNIFORM_RESET,
            real_crossover_method=RealCrossoverMethod(self.real_crossover.currentData())
            if self.representation == Representation.REAL
            else None,
            real_uniform_swap_probability=self.uniform_swap.value() / 100,
            arithmetic_alpha=self.arithmetic_alpha.value(),
            sbx_distribution_index=self.sbx_index.value(),
            sbx_formula=tuple(SbxFormula)[self.sbx_formula.currentIndex()],
            real_bounds_policy=(RealBoundsPolicy.CLIP, RealBoundsPolicy.REJECT)[
                self.bounds_policy.currentIndex()
            ],
            direction=problem.direction,
            fitness_policy=FitnessPolicy(self.fitness_policy.currentData()),
            selection_method=SELECTIONS[self.selection.currentIndex()],
            crossover_probability=self.crossover.value() / 100,
            mutation_probability=self.mutation.value() / 100,
            reproduction_policy=ReproductionPolicy.PAIRWISE
            if self.representation == Representation.REAL
            else REPRODUCTIONS[self.reproduction.currentIndex()],
            replacement_strategy=REPLACEMENTS[self.replacement.currentIndex()],
            zero_weight_policy=ZERO_POLICIES[self.zero_weights.currentIndex()],
        )
        if (
            config.population_size * (config.generation_limit + 1)
            > MAX_HISTORY_INDIVIDUALS
        ):
            raise ConfigurationInputError(
                text("error_history_size").format(limit=MAX_HISTORY_INDIVIDUALS)
            )
        try:
            validate_configuration(config, problem)
        except ValueError as error:
            raise ConfigurationInputError(explain_error(str(error))) from error
        return config

    @Slot(bool)
    def set_running(self, running: bool) -> None:
        self.setEnabled(not running)
