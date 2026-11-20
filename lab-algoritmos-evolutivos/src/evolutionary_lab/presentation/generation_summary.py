from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from evolutionary_lab.presentation.strings import text
from evolutionary_lab.simulation.snapshots import GenerationSnapshot

SUMMARY_FIELDS = (
    ("generation", "generation"),
    ("best", "summary_best"),
    ("mean", "generation_mean"),
    ("best_so_far", "best_so_far"),
    ("diversity", "summary_diversity"),
)


class GenerationSummary(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("generationSummary")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)
        self.values: dict[str, QLabel] = {}
        for column, (field, label_key) in enumerate(SUMMARY_FIELDS):
            caption = QLabel(text(label_key))
            caption.setObjectName("summaryLabel")
            caption.setWordWrap(True)
            value = QLabel(text("unavailable"))
            value.setObjectName("summaryValue")
            value.setAccessibleName(text(label_key))
            layout.addWidget(caption, 0, column)
            layout.addWidget(value, 1, column)
            layout.setColumnStretch(column, 1)
            self.values[field] = value
        self.hide()

    def set_snapshot(self, snapshot: GenerationSnapshot) -> None:
        stats = snapshot.statistics
        numbers = {
            "best": stats.best_individual.objective_value,
            "mean": stats.objective_mean,
            "best_so_far": snapshot.best_so_far.objective_value,
            "diversity": stats.normalized_diversity,
        }
        self.values["generation"].setText(str(snapshot.generation_index))
        self.values["generation"].setToolTip(
            text("generation_meta").format(
                generation=snapshot.generation_index, size=len(snapshot.population)
            )
        )
        for field, value in numbers.items():
            self.values[field].setText(
                text("unavailable") if value is None else f"{value:.6f}"
            )
        self.show()

    def clear(self) -> None:
        self.hide()
        for value in self.values.values():
            value.setText(text("unavailable"))
