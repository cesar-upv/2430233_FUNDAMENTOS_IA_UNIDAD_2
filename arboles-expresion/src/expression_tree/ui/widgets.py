from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import MUTED

PATHS = {
    "tree": '<path d="M12 4v5M5 15v-5h14v5"/><circle cx="12" cy="4" r="2.5"/><rect x="2.5" y="15" width="5" height="5" rx="1.5"/><rect x="16.5" y="15" width="5" height="5" rx="1.5"/>',
    "dice": '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r=".7"/><circle cx="16" cy="8" r=".7"/><circle cx="12" cy="12" r=".7"/><circle cx="8" cy="16" r=".7"/><circle cx="16" cy="16" r=".7"/>',
    "fit": '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><rect x="8" y="8" width="8" height="8" rx="1"/>',
    "plus": '<path d="M5 12h14M12 5v14"/>',
    "minus": '<path d="M5 12h14"/>',
    "play": '<path d="m8 5 12 7-12 7Z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "next": '<path d="m5 5 10 7L5 19ZM19 5v14"/>',
    "reset": '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
    "export": '<path d="M12 3v12m-4-8 4-4 4 4M4 13v7h16v-7"/>',
    "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    "curve": '<path d="M3 3v18h18M5 16c4 0 3-10 7-10s3 10 7 10"/>',
}


def icon(name: str, color: str = MUTED, size: int = 18) -> QIcon:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    result = QLabel(text)
    result.setObjectName(name)
    result.setWordWrap(wrap)
    result.setTextFormat(Qt.TextFormat.PlainText)
    return result


def button(text: str, callback=None, *, name: str = "", glyph: str | None = None) -> QPushButton:
    result = QPushButton(text)
    result.setObjectName(name)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    if glyph:
        result.setIcon(icon(glyph, "#FFFCF0" if name == "Primary" else MUTED))
    if callback:
        result.clicked.connect(callback)
    return result


def icon_button(name: str, tooltip: str, callback) -> QPushButton:
    result = button("", callback, name="Icon", glyph=name)
    result.setToolTip(tooltip)
    result.setAccessibleName(tooltip)
    result.setFixedSize(32, 32)
    return result


def surface() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Surface")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    return frame, layout


def rule() -> QFrame:
    frame = QFrame()
    frame.setFixedHeight(1)
    frame.setStyleSheet("background: #DAD8CE; border: none;")
    return frame
