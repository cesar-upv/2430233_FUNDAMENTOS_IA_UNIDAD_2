from importlib.resources import files

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from evolutionary_lab.presentation.theme import ThemeColors


def icon(name: str, colors: ThemeColors) -> QIcon:
    source = (
        files("evolutionary_lab.presentation")
        .joinpath("assets", "icons", f"{name}.svg")
        .read_bytes()
    )
    result = QIcon()
    for mode, color in (
        (QIcon.Mode.Normal, colors.foreground),
        (QIcon.Mode.Active, colors.foreground),
        (QIcon.Mode.Selected, colors.accent),
        (QIcon.Mode.Disabled, colors.muted),
    ):
        for state in (QIcon.State.Off, QIcon.State.On):
            stroke = (
                colors.accent
                if state == QIcon.State.On and mode != QIcon.Mode.Disabled
                else color
            )
            renderer = QSvgRenderer(
                QByteArray(source.replace(b"currentColor", stroke.encode("ascii")))
            )
            for size in (20, 40):
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                pixmap.setDevicePixelRatio(size / 20)
                result.addPixmap(pixmap, mode, state)
    return result
