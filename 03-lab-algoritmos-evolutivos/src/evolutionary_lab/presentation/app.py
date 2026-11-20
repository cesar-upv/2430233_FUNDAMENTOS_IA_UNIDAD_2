import sys
from importlib.metadata import version

from PySide6.QtWidgets import QApplication

from evolutionary_lab.presentation.strings import text
from evolutionary_lab.presentation.windows.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(text("app_name"))
    app.setApplicationVersion(version("evolutionary-lab"))
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSizeF(10.5)
    app.setFont(font)

    window = MainWindow(app)
    window.show()
    return app.exec()
