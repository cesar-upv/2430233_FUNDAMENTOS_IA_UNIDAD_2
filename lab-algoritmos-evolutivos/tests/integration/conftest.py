import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication

from evolutionary_lab.presentation.windows.main_window import MainWindow


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication([])
    app.setApplicationName("Evolutionary Lab")
    app.setApplicationVersion("0.1.0")
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSizeF(10.5)
    app.setFont(font)
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def window(qt_app: QApplication, settings: QSettings) -> Iterator[MainWindow]:
    window = MainWindow(qt_app, settings)
    window.show()
    qt_app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
