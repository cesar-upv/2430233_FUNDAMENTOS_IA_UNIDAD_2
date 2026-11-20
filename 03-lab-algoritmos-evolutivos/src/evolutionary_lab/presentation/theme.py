from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class Appearance(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ThemeColors:
    window: str
    surface: str
    navigation: str
    foreground: str
    muted: str
    accent: str
    selected: str
    border: str
    on_accent: str


LIGHT = ThemeColors(
    window="#f5f7fa",
    surface="#ffffff",
    navigation="#edf1f5",
    foreground="#202a36",
    muted="#536274",
    accent="#19615e",
    selected="#deeeea",
    border="#ced7df",
    on_accent="#ffffff",
)
DARK = ThemeColors(
    window="#141a22",
    surface="#1b242e",
    navigation="#111820",
    foreground="#e5eaf0",
    muted="#a5b3c2",
    accent="#78cabe",
    selected="#233e3c",
    border="#384653",
    on_accent="#141a22",
)


def apply_theme(app: QApplication, appearance: Appearance) -> ThemeColors:
    system_dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    dark = appearance == Appearance.DARK or (
        appearance == Appearance.SYSTEM and system_dark
    )
    colors = DARK if dark else LIGHT
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, colors.window),
        (QPalette.ColorRole.WindowText, colors.foreground),
        (QPalette.ColorRole.Base, colors.surface),
        (QPalette.ColorRole.AlternateBase, colors.navigation),
        (QPalette.ColorRole.Text, colors.foreground),
        (QPalette.ColorRole.Button, colors.surface),
        (QPalette.ColorRole.ButtonText, colors.foreground),
        (QPalette.ColorRole.ToolTipBase, colors.surface),
        (QPalette.ColorRole.ToolTipText, colors.foreground),
        (QPalette.ColorRole.Highlight, colors.selected),
        (QPalette.ColorRole.HighlightedText, colors.accent),
        (QPalette.ColorRole.PlaceholderText, colors.muted),
        (QPalette.ColorRole.Light, colors.surface),
        (QPalette.ColorRole.Midlight, colors.navigation),
        (QPalette.ColorRole.Mid, colors.border),
        (QPalette.ColorRole.Dark, colors.border),
        (QPalette.ColorRole.Shadow, colors.border),
        (QPalette.ColorRole.Link, colors.accent),
        (QPalette.ColorRole.Accent, colors.accent),
    ):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.muted))
    app.setPalette(palette)
    app.setStyleSheet(
        f"""
        QMainWindow, QWidget#workspace {{ background: {colors.window}; }}
        QWidget#sidebar, QStatusBar {{ background: {colors.navigation}; }}
        QLabel {{ color: {colors.foreground}; background: transparent; }}
        QLabel#brand {{ font-size: 23px; font-weight: 600; }}
        QLabel#sectionTitle {{ font-size: 24px; font-weight: 600; }}
        QLabel#emptyTitle {{ font-size: 20px; font-weight: 600; }}
        QLabel#panelTitle {{ font-size: 14px; font-weight: 600; }}
        QLabel#chartTitle, QLabel#parameterSectionTitle {{
            font-size: 16px; font-weight: 600; }}
        QLabel#summaryLabel {{ color: {colors.muted}; font-size: 12px; }}
        QLabel#summaryValue {{ font-size: 19px; font-weight: 600; }}
        QLabel#legendLabel {{ font-size: 12px; }}
        QLabel#muted {{ color: {colors.muted}; }}
        QLabel#version {{ color: {colors.muted}; font-size: 12px; }}
        QListWidget {{ background: transparent; border: none; outline: none; }}
        QListWidget::item {{ padding: 10px 12px; border-radius: 6px;
            border: 1px solid transparent; }}
        QListWidget::item:hover {{ background: {colors.surface}; }}
        QListWidget::item:selected {{ background: {colors.selected};
            color: {colors.accent}; font-weight: 600; }}
        QListWidget::item:focus {{ border: 1px solid {colors.accent}; }}
        QTabWidget::pane {{ background: {colors.surface};
            border: 1px solid {colors.border}; border-radius: 8px; }}
        QTabBar::tab {{ background: transparent; color: {colors.muted};
            padding: 12px 18px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ color: {colors.accent};
            border-bottom: 2px solid {colors.accent}; }}
        QTabBar::tab:hover {{ background: {colors.selected}; }}
        QTabBar::tab:focus {{ background: {colors.selected}; }}
        QWidget#emptyWorkspace {{ background: {colors.surface}; }}
        QWidget#appearanceWorkspace {{ background: {colors.surface}; }}
        QFrame#settingsDivider {{ background: {colors.border}; border: none; }}
        QFrame#inspector {{ background: {colors.navigation}; border-radius: 6px; }}
        QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
            background: {colors.surface};
            color: {colors.foreground}; border: 1px solid {colors.border};
            border-radius: 5px; padding: 7px 12px; }}
        QPushButton:hover, QComboBox:hover {{ border-color: {colors.accent}; }}
        QPushButton:focus, QComboBox:focus {{ border-color: {colors.accent}; }}
        QPushButton:pressed {{ background: {colors.selected}; }}
        QPushButton:checked {{ background: {colors.selected};
            color: {colors.accent}; border-color: {colors.accent}; font-weight: 600; }}
        QPushButton:disabled {{ color: {colors.muted};
            background: {colors.navigation}; }}
        QPushButton[primary="true"] {{ background: {colors.accent};
            color: {colors.on_accent}; border-color: {colors.accent};
            font-weight: 600; }}
        QPushButton[primary="true"]:focus, QPushButton[primary="true"]:hover {{
            border-color: {colors.foreground}; }}
        QPushButton[primary="true"]:pressed {{ background: {colors.selected};
            color: {colors.accent}; }}
        QPushButton[primary="true"]:disabled {{ background: {colors.navigation};
            color: {colors.muted}; border-color: {colors.border}; }}
        QPushButton#settingsNavigation {{ background: transparent;
            border: 1px solid transparent; padding: 10px 12px; text-align: left;
            font-weight: 400; }}
        QPushButton#settingsNavigation:hover {{ background: {colors.surface}; }}
        QPushButton#settingsNavigation:checked {{ background: {colors.selected};
            color: {colors.accent}; font-weight: 600; }}
        QPushButton#settingsNavigation:focus {{ border-color: {colors.accent}; }}
        QComboBox QAbstractItemView {{ background: {colors.surface};
            color: {colors.foreground}; selection-background-color: {colors.selected};
            selection-color: {colors.accent}; }}
        QSplitter::handle {{ background: {colors.window}; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: {colors.surface}; }}
        QCheckBox {{ color: {colors.foreground}; }}
        QSlider::groove:horizontal {{ height: 4px; background: {colors.border}; }}
        QSlider::handle:horizontal {{ background: {colors.accent}; width: 14px;
            margin: -5px 0; border-radius: 7px; }}
        QSplitter::handle:hover {{ background: {colors.border}; }}
        QStatusBar {{ color: {colors.muted}; border-top: 1px solid {colors.border}; }}
        QToolTip {{ background: {colors.surface};
            color: {colors.foreground}; border: 1px solid {colors.border}; }}
        """
    )
    return colors
