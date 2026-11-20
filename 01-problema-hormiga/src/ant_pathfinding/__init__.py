"""Ant Pathfinding: visualize multi-goal pathfinding on an editable grid.

Qt is imported inside :func:`main` so that importing this package stays free of it.
"""


def main() -> int:
    """Show the editor window and run the Qt event loop; returns the exit code."""
    import sys

    from PySide6.QtWidgets import QApplication

    from ant_pathfinding.presentation.qt.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    window.show()
    return app.exec()
