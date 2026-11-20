from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# Flexoki light, https://stephango.com/flexoki
PAPER = "#FFFCF0"
SURFACE = "#F2F0E5"
BORDER = "#DAD8CE"
INK = "#100F0F"
MUTED = "#6F6E69"
BLUE = "#205EA6"
GREEN = "#536907"
ORANGE = "#9D4310"
RED = "#AF3029"

NODE_STYLES = {
    "op": ("#FFE7CE", "#9D4310", "OPERADOR"),
    "unary": ("#FCE1EE", "#A02F6F", "SIGNO"),
    "func": ("#E1ECEB", "#1C6C66", "FUNCIÓN"),
    "number": (PAPER, "#575653", "NÚMERO"),
    "constant": ("#EDEECF", "#536907", "CONSTANTE"),
    "variable": ("#E2D9E9", "#5E409D", "VARIABLE"),
}

ASSETS = Path(__file__).parent / "assets"

QSS = f"""
QWidget {{ color: {INK}; font-family: 'Inter', 'Noto Sans', 'Segoe UI', sans-serif; font-size: 13px; }}
QMainWindow, QWidget#Root {{ background: {SURFACE}; }}
QFrame#Surface, QWidget#Surface {{ background: {PAPER}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#Header {{ background: transparent; }}
QLabel {{ background: transparent; border: none; }}
QLabel#Title {{ font-size: 23px; font-weight: 650; }}
QLabel#PanelTitle {{ font-size: 15px; font-weight: 650; }}
QLabel#Muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#Result {{ font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; font-size: 25px; color: {BLUE}; }}
QLabel#Error {{ color: {RED}; background: #FFE1D5; padding: 9px 12px; border-radius: 6px; }}
QLabel#Warning {{ color: {ORANGE}; background: #FFE7CE; padding: 8px 10px; border-radius: 6px; }}
QPushButton {{ background: {PAPER}; border: 1px solid #CECDC3; border-radius: 6px; padding: 7px 11px; font-weight: 550; min-height: 18px; }}
QPushButton:hover {{ background: #E6E4D9; border-color: #B7B5AC; }}
QPushButton:pressed {{ background: #DAD8CE; }}
QPushButton:focus {{ border: 1px solid {BLUE}; }}
QPushButton:disabled {{ color: #878580; background: {SURFACE}; border-color: #E6E4D9; }}
QPushButton#Primary {{ background: {BLUE}; color: {PAPER}; border-color: {BLUE}; padding: 8px 16px; }}
QPushButton#Primary:hover {{ background: #184F90; }}
QPushButton#Primary:pressed {{ background: #123F75; }}
QPushButton#Primary:disabled {{ background: #CECDC3; border-color: #CECDC3; color: #575653; }}
QPushButton#Quiet {{ border: 1px solid transparent; background: transparent; color: #575653; }}
QPushButton#Quiet:hover {{ background: #E6E4D9; }}
QPushButton#Icon {{ padding: 5px; min-width: 22px; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {PAPER}; border: 1px solid #CECDC3; border-radius: 5px; padding: 6px 8px; min-height: 20px; selection-background-color: #B9D7E9; selection-color: {INK}; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border-color: #9F9D96; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {BLUE}; }}
QLineEdit#Expression {{ font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; font-size: 18px; border: none; padding: 10px 8px; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ background: {SURFACE}; color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{ image: url({ASSETS / 'down.svg'}); width: 14px; height: 14px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 19px; border: none; background: transparent; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 19px; border: none; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({ASSETS / 'up.svg'}); width: 12px; height: 12px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({ASSETS / 'down.svg'}); width: 12px; height: 12px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{ background: #E6E4D9; }}
QComboBox QAbstractItemView {{ background: {PAPER}; selection-background-color: #E1ECEB; selection-color: {INK}; border: 1px solid {BORDER}; }}
QCheckBox {{ spacing: 7px; background: transparent; min-height: 22px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #B7B5AC; border-radius: 3px; background: {PAPER}; }}
QCheckBox::indicator:checked {{ background: {BLUE}; border-color: {BLUE}; image: url({ASSETS / 'check.svg'}); }}
QCheckBox::indicator:hover {{ border-color: {BLUE}; }}
QCheckBox::indicator:disabled {{ background: #E6E4D9; border-color: #CECDC3; }}
QCheckBox:disabled {{ color: {MUTED}; }}
QTabWidget::tab-bar {{ alignment: left; }}
QTabWidget::pane {{ border: 0px; background: {PAPER}; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 9px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {BLUE}; border-bottom-color: {BLUE}; }}
QTabBar::tab:hover {{ background: {SURFACE}; color: {INK}; }}
QTabBar::tab:focus {{ color: {BLUE}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #CECDC3; min-height: 24px; border-radius: 4px; }}
QScrollBar::handle:vertical:hover {{ background: #9F9D96; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #CECDC3; min-width: 24px; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: #CECDC3; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QListWidget, QTableWidget, QPlainTextEdit {{ background: {PAPER}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px; selection-background-color: #E1ECEB; selection-color: {INK}; }}
QListWidget::item {{ padding: 8px 6px; border-bottom: 1px solid #E6E4D9; }}
QListWidget::item:selected {{ background: #E1ECEB; color: {INK}; }}
QHeaderView::section {{ background: {SURFACE}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px; color: {MUTED}; }}
QToolTip {{ background: {INK}; color: {PAPER}; border: none; padding: 7px; }}
QSlider::groove:horizontal {{ background: #DAD8CE; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {BLUE}; width: 12px; margin: -5px 0; border-radius: 6px; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Inter", 10))
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, SURFACE), (QPalette.ColorRole.WindowText, INK), (QPalette.ColorRole.Base, PAPER), (QPalette.ColorRole.AlternateBase, SURFACE), (QPalette.ColorRole.Text, INK), (QPalette.ColorRole.Button, PAPER), (QPalette.ColorRole.ButtonText, INK), (QPalette.ColorRole.Highlight, BLUE), (QPalette.ColorRole.HighlightedText, PAPER), (QPalette.ColorRole.PlaceholderText, MUTED)):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(QSS)
