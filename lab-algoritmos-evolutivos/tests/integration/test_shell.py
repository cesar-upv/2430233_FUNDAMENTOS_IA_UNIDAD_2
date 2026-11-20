import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenuBar,
    QPushButton,
    QSplitter,
    QTabWidget,
)

from evolutionary_lab.presentation.windows.main_window import MainWindow


def test_window_shows_shell_with_simulation_action(window: MainWindow) -> None:
    assert window.isVisible()
    assert window.windowTitle() == "Evolutionary Lab"
    assert window.navigation.count() == 3
    for name in ("shellSplitter", "simulationSplitter"):
        splitter = window.findChild(QSplitter, name)
        assert splitter is not None
        assert splitter.count() == 2
        assert not splitter.childrenCollapsible()
    assert (
        window.findChild(QPushButton, "startSimulation")
        is window.simulation.start_button
    )
    for index in range(window.navigation.count()):
        item = window.navigation.item(index)
        assert item is not None and not item.icon().isNull()


def test_sidebar_supports_mouse_and_keyboard(window: MainWindow) -> None:
    navigation = window.navigation
    for index in range(navigation.count()):
        item = navigation.item(index)
        assert item is not None
        QTest.mouseClick(
            navigation.viewport(),
            Qt.MouseButton.LeftButton,
            pos=navigation.visualItemRect(item).center(),
        )
        assert window.workspaces.currentIndex() == index
        assert window.section_title.text() == item.text()
    navigation.setCurrentRow(0)
    navigation.setFocus()
    QTest.keyClick(navigation, Qt.Key.Key_Down)
    assert window.workspaces.currentIndex() == 1


def test_horizontal_tabs_remember_each_section(window: MainWindow) -> None:
    for section in range(window.navigation.count()):
        window.navigation.setCurrentRow(section)
        tabs = window.workspaces.currentWidget()
        assert isinstance(tabs, QTabWidget)
        assert tabs.tabPosition() == QTabWidget.TabPosition.North
        assert tabs.count() >= 2
        for index in range(tabs.count()):
            QTest.mouseClick(
                tabs.tabBar(),
                Qt.MouseButton.LeftButton,
                pos=tabs.tabBar().tabRect(index).center(),
            )
            assert tabs.currentIndex() == index
            page = tabs.currentWidget()
            assert page is not None and page.isVisible()
    window.navigation.setCurrentRow(0)
    tabs = window.workspaces.currentWidget()
    assert isinstance(tabs, QTabWidget)
    assert tabs.currentIndex() == tabs.count() - 1


def test_settings_and_appearance_preserve_existing_navigation(
    window: MainWindow, qt_app: QApplication
) -> None:
    window.navigation.setCurrentRow(1)
    previous_tabs = window.workspaces.currentWidget()
    assert isinstance(previous_tabs, QTabWidget)
    previous_tabs.setCurrentIndex(1)
    QTest.mouseClick(window.settings_button, Qt.MouseButton.LeftButton)
    assert window.settings_button.isChecked()
    assert window.navigation.currentRow() == -1
    assert window.workspaces.currentWidget() == window.settings_tabs
    assert window.settings_tabs.count() == 1
    assert window.appearance.isVisible()
    assert not window.settings_button.icon().isNull()
    window.appearance.setCurrentIndex(1)
    light = qt_app.palette().color(QPalette.ColorRole.Window)
    window.appearance.setCurrentIndex(2)
    dark = qt_app.palette().color(QPalette.ColorRole.Window)
    assert light.lightness() > dark.lightness()
    assert window.workspaces.currentWidget() == window.settings_tabs
    window.appearance.setCurrentIndex(0)
    window.navigation.setCurrentRow(1)
    assert not window.settings_button.isChecked()
    assert window.workspaces.currentWidget() == previous_tabs
    assert previous_tabs.currentIndex() == 1
    assert window.isVisible()


@pytest.mark.parametrize("index", [0, 1, 2])
def test_theme_preference_survives_a_process_restart(
    window: MainWindow, settings: QSettings, index: int
) -> None:
    window.appearance.setCurrentIndex((index + 1) % 3)
    window.appearance.setCurrentIndex(index)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; "
            "from PySide6.QtCore import QSettings; "
            "from PySide6.QtWidgets import QApplication; "
            "from evolutionary_lab.presentation.windows.main_window import MainWindow; "
            "app = QApplication([]); "
            "settings = QSettings(sys.argv[1], QSettings.Format.IniFormat); "
            "window = MainWindow(app, settings); "
            "assert window.appearance.currentIndex() == int(sys.argv[2]); "
            "assert settings.value('appearance/theme') == "
            "('system', 'light', 'dark')[int(sys.argv[2])]; "
            "window.close()",
            settings.fileName(),
            str(index),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_invalid_saved_theme_falls_back_to_system(
    qt_app: QApplication, settings: QSettings
) -> None:
    settings.setValue("appearance/theme", "unavailable-theme")
    window = MainWindow(qt_app, settings)
    assert window.appearance.currentIndex() == 0
    window.deleteLater()


def test_quit_shortcut_remains_available_without_menu(window: MainWindow) -> None:
    assert window.findChild(QMenuBar) is None
    assert not window.quit_action.shortcut().isEmpty()
    QTest.keySequence(window, window.quit_action.shortcut())
    assert not window.isVisible()


def test_minimum_size_keeps_workspace_text_visible(window: MainWindow) -> None:
    window.resize(window.minimumSize())
    for mode in (1, 2):
        window.appearance.setCurrentIndex(mode)
        for settings_visible in (True, False):
            if settings_visible:
                window.settings_button.click()
                assert window.workspaces.currentWidget() == window.settings_tabs
            else:
                window.navigation.setCurrentRow(0)
            QTest.qWait(20)
            for label in window.findChildren(QLabel):
                if label.isVisible() and label.wordWrap():
                    assert label.height() >= label.heightForWidth(label.width()), (
                        label.text()
                    )


def test_installed_entry_point_opens_and_exits() -> None:
    repository = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "scripts/smoke_gui.py"],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Qt smoke OK: offscreen" in result.stdout
