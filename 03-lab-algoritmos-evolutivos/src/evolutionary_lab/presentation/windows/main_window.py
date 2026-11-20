from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from evolutionary_lab.presentation.icons import icon
from evolutionary_lab.presentation.parameters import ParameterWorkspace
from evolutionary_lab.presentation.simulation_workspace import SimulationWorkspace
from evolutionary_lab.presentation.statistics_view import StatisticsWorkspace
from evolutionary_lab.presentation.strings import text
from evolutionary_lab.presentation.theme import Appearance, apply_theme

SECTIONS = (
    ("laboratory", "laboratory_description", ("simulation", "analysis", "parameters")),
    ("experiments", "experiments_description", ("history", "comparison")),
    ("learning", "learning_description", ("concepts", "exercises")),
)
APPEARANCES = (Appearance.SYSTEM, Appearance.LIGHT, Appearance.DARK)
SECTION_ICONS = ("flask-2", "folders", "book-2")
APPEARANCE_ICONS = ("device-desktop", "sun", "moon")


def _label(key: str, name: str = "", *, wrap: bool = True) -> QLabel:
    label = QLabel(text(key))
    label.setObjectName(name)
    label.setWordWrap(wrap)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _empty_workspace(key: str) -> QWidget:
    page = QWidget()
    page.setObjectName("emptyWorkspace")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 32, 32, 32)
    layout.setSpacing(12)
    layout.addStretch()
    title = _label(f"{key}_empty_title", "emptyTitle")
    description = _label(f"{key}_empty_description", "muted")
    title.setMaximumWidth(560)
    description.setMaximumWidth(560)
    layout.addWidget(title)
    layout.addWidget(description)
    layout.addStretch()
    return page


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication, settings: QSettings | None = None) -> None:
        super().__init__()
        self._app = app
        self._settings = (
            settings
            if settings is not None
            else QSettings("EvolutionaryLab", "EvolutionaryLab")
        )
        self.setWindowTitle(text("app_name"))
        self.setMinimumSize(900, 740)
        self.resize(1180, 760)

        self.quit_action = QAction(text("quit"), self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        self.addAction(self.quit_action)

        self.navigation = QListWidget()
        self.navigation.setObjectName("sectionNavigation")
        self.navigation.setAccessibleName(text("navigation"))
        self.navigation.setIconSize(QSize(20, 20))
        self.navigation.setSpacing(4)
        self.navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.workspaces = QStackedWidget()
        self.workspaces.setObjectName("sectionWorkspaces")
        self.section_title = _label("laboratory", "sectionTitle")
        self.section_description = _label("laboratory_description", "muted")
        self.appearance = QComboBox()
        self.appearance.setObjectName("appearanceSelector")
        self.appearance.setAccessibleName(text("theme"))
        self.appearance.setMinimumWidth(168)
        self.appearance.setMinimumHeight(38)
        self.appearance.setMaximumWidth(220)
        self.appearance.setIconSize(QSize(20, 20))
        for mode in APPEARANCES:
            self.appearance.addItem(text(mode.value))
        stored = self._settings.value("appearance/theme", Appearance.SYSTEM.value)
        try:
            appearance = (
                Appearance(stored) if isinstance(stored, str) else Appearance.SYSTEM
            )
        except ValueError:
            appearance = Appearance.SYSTEM
        self.appearance.setCurrentIndex(APPEARANCES.index(appearance))
        self._settings_feedback = _label("preferences_saved", "muted")
        self.settings_button = QPushButton(text("settings"))
        self.settings_button.setObjectName("settingsNavigation")
        self.settings_button.setCheckable(True)
        self.settings_button.setMinimumHeight(46)
        self.settings_button.setIconSize(QSize(20, 20))
        self.simulation = SimulationWorkspace()
        self.parameters = ParameterWorkspace()
        self.statistics = StatisticsWorkspace()
        self.simulation.config_provider = self.parameters.configuration
        self.simulation.problem_provider = self.parameters.selected_problem
        self.simulation.history_changed.connect(self.statistics.set_history)
        self.simulation.generation_changed.connect(self.statistics.select_generation)
        self.simulation.computation_changed.connect(self.parameters.set_running)
        self.parameters.run_requested.connect(self._start_from_parameters)
        self.parameters.project_selector.currentIndexChanged.connect(
            self._update_project_description
        )

        for title, _description, tabs in SECTIONS:
            item = QListWidgetItem(text(title))
            item.setSizeHint(QSize(0, 46))
            self.navigation.addItem(item)
            workspaces = QTabWidget()
            workspaces.setAccessibleName(text("workspaces"))
            workspaces.setObjectName(f"{title}Tabs")
            workspaces.setDocumentMode(True)
            for tab in tabs:
                if tab == "simulation":
                    page: QWidget = self.simulation
                elif tab == "analysis":
                    page = self.statistics
                elif tab == "parameters":
                    page = self.parameters
                else:
                    page = _empty_workspace(tab)
                workspaces.addTab(page, text(tab))
            self.workspaces.addWidget(workspaces)

        self.settings_tabs = QTabWidget()
        self.settings_tabs.setObjectName("settingsTabs")
        self.settings_tabs.setAccessibleName(text("settings_categories"))
        self.settings_tabs.setDocumentMode(True)
        self.settings_tabs.addTab(self._appearance_workspace(), text("appearance"))
        self.workspaces.addWidget(self.settings_tabs)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(216)
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 28, 16, 20)
        sidebar_layout.setSpacing(14)
        sidebar_layout.addWidget(_label("brand_name", "brand"))
        sidebar_layout.addWidget(_label("brand_description", "muted"))
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(self.navigation, 1)
        sidebar_layout.addWidget(self.settings_button)
        sidebar_layout.addSpacing(4)
        version_label = _label("version", "version")
        version_label.setText(text("version").format(version=app.applicationVersion()))
        sidebar_layout.addWidget(version_label)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(28, 24, 28, 20)
        workspace_layout.setSpacing(12)
        workspace_layout.addWidget(self.section_title)
        workspace_layout.addWidget(self.section_description)
        workspace_layout.addSpacing(12)
        workspace_layout.addWidget(self.workspaces, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("shellSplitter")
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(sidebar)
        splitter.addWidget(workspace)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([232, 948])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage(text("shell_status"))

        self.navigation.currentRowChanged.connect(self._select_section)
        self.navigation.setCurrentRow(0)
        self.settings_button.clicked.connect(self._open_settings)
        self.appearance.currentIndexChanged.connect(self._change_appearance)
        app.styleHints().colorSchemeChanged.connect(self._system_appearance_changed)
        self._apply_appearance()

    def _appearance_workspace(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appearanceWorkspace")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        content = QWidget()
        content.setMaximumWidth(780)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(24)
        row = QHBoxLayout()
        row.setSpacing(32)
        theme_label = _label("theme", "panelTitle")
        theme_label.setBuddy(self.appearance)
        row.addWidget(theme_label, 1)
        row.addWidget(self.appearance)
        content_layout.addLayout(row)
        description = _label("theme_description", "muted")
        content_layout.addWidget(description)
        divider = QFrame()
        divider.setObjectName("settingsDivider")
        divider.setFixedHeight(1)
        content_layout.addWidget(divider)
        content_layout.addWidget(self._settings_feedback)
        content_row = QHBoxLayout()
        content_row.addWidget(content, 1)
        content_row.addStretch()
        layout.addLayout(content_row)
        layout.addStretch()
        return page

    def _open_settings(self) -> None:
        self.navigation.setCurrentRow(-1)
        self.settings_button.setChecked(True)
        self.workspaces.setCurrentWidget(self.settings_tabs)
        self.section_title.setText(text("settings"))
        self.section_description.setText(text("settings_description"))

    def _start_from_parameters(self) -> None:
        self.navigation.setCurrentRow(0)
        tabs = self.workspaces.widget(0)
        if isinstance(tabs, QTabWidget):
            tabs.setCurrentIndex(0)
        self.simulation.start_simulation()

    def _select_section(self, index: int) -> None:
        if not 0 <= index < len(SECTIONS):
            return
        title, description, _tabs = SECTIONS[index]
        self.settings_button.setChecked(False)
        self.workspaces.setCurrentIndex(index)
        self.section_title.setText(text(title))
        self.section_description.setText(text(description))
        if index == 0:
            self._update_project_description()

    def _update_project_description(self) -> None:
        if self.navigation.currentRow() == 0:
            is_real = self.parameters.project_selector.currentIndex() == 1
            self.section_description.setText(
                text("project_lab_description").format(
                    project=2 if is_real else 1,
                    encoding=text("real_short" if is_real else "binary_short"),
                )
            )

    def _change_appearance(self, index: int) -> None:
        self._apply_appearance()
        self._settings.setValue("appearance/theme", APPEARANCES[index].value)
        self._settings.sync()
        key = (
            "preferences_saved"
            if self._settings.status() == QSettings.Status.NoError
            else "preferences_save_error"
        )
        self._settings_feedback.setText(text(key))

    def _apply_appearance(self) -> None:
        colors = apply_theme(self._app, APPEARANCES[self.appearance.currentIndex()])
        self.simulation.apply_theme(colors)
        self.statistics.apply_theme(colors)
        for index, name in enumerate(SECTION_ICONS):
            item = self.navigation.item(index)
            if item is not None:
                item.setIcon(icon(name, colors))
        self.settings_button.setIcon(icon("settings", colors))
        self.settings_tabs.setTabIcon(0, icon("palette", colors))
        for index, name in enumerate(APPEARANCE_ICONS):
            self.appearance.setItemIcon(index, icon(name, colors))

    def _system_appearance_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self.appearance.currentIndex() == 0:
            self._apply_appearance()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.simulation.controller.shutdown()
        super().closeEvent(event)
