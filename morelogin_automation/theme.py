"""Premium dark theme (QSS) shared across the desktop app."""

from __future__ import annotations

# Core palette
BG = "#0b0e14"
BG_ELEVATED = "#10151f"
CARD = "#141a24"
CARD_HOVER = "#19212d"
BORDER = "#232c39"
BORDER_STRONG = "#2d3848"
TEXT = "#e6edf3"
TEXT_MUTED = "#8b97a7"
TEXT_FAINT = "#5f6b7a"
ACCENT = "#6d5efc"
ACCENT_2 = "#00c2ff"
SUCCESS = "#2ee6a6"
DANGER = "#ff5c7a"
WARNING = "#ffb454"


APP_QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QDialog {{
    background-color: {BG};
}}

QWidget#headerBar {{
    background: transparent;
}}

QLabel#appTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
    letter-spacing: 0.5px;
}}

QLabel#appSubtitle {{
    font-size: 12px;
    color: {TEXT_MUTED};
    letter-spacing: 0.3px;
}}

QLabel#appBadge {{
    color: {ACCENT_2};
    background: rgba(0, 194, 255, 0.10);
    border: 1px solid rgba(0, 194, 255, 0.35);
    border-radius: 11px;
    padding: 3px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}

QGroupBox {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    margin-top: 16px;
    padding: 18px 16px 16px 16px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 2px;
    padding: 2px 8px;
    color: {TEXT_MUTED};
    background: transparent;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}}

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QLineEdit, QComboBox {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}

QLineEdit:hover, QComboBox:hover {{
    border-color: {BORDER_STRONG};
}}

QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}

QLineEdit:read-only {{
    color: {TEXT_MUTED};
    background-color: #0e131c;
}}

QComboBox::drop-down {{
    border: none;
    width: 26px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {TEXT_MUTED};
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    padding: 4px;
    outline: none;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}

QPushButton {{
    background-color: {CARD_HOVER};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    padding: 9px 18px;
    color: {TEXT};
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #202a38;
    border-color: {ACCENT};
}}

QPushButton:pressed {{
    background-color: #18202c;
}}

QPushButton:disabled {{
    color: {TEXT_FAINT};
    background-color: #11161f;
    border-color: {BORDER};
}}

QPushButton#primaryBtn {{
    background-color: {ACCENT};
    border: none;
    color: #ffffff;
    padding: 10px 26px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}

QPushButton#primaryBtn:hover {{
    background-color: #7d70ff;
}}

QPushButton#primaryBtn:pressed {{
    background-color: #5c4fe0;
}}

QPushButton#primaryBtn:disabled {{
    background-color: #2a2f44;
    color: {TEXT_FAINT};
}}

QPushButton#dangerBtn {{
    background-color: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
    padding: 10px 24px;
    font-weight: 700;
}}

QPushButton#dangerBtn:hover {{
    background-color: rgba(255, 92, 122, 0.12);
}}

QPushButton#dangerBtn:disabled {{
    border-color: {BORDER};
    color: {TEXT_FAINT};
    background: transparent;
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    border: 1px solid {BORDER_STRONG};
    color: {TEXT_MUTED};
}}

QPushButton#ghostBtn:hover {{
    border-color: {ACCENT_2};
    color: {ACCENT_2};
}}

QTextEdit {{
    background-color: #080b11;
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 10px;
    color: #c9d4e0;
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    selection-background-color: {ACCENT};
}}

QMenuBar {{
    background-color: {BG};
    color: {TEXT_MUTED};
    border-bottom: 1px solid {BORDER};
    padding: 3px 6px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 8px;
}}

QMenuBar::item:selected {{
    background: {CARD_HOVER};
    color: {TEXT};
}}

QMenu {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 22px;
    border-radius: 6px;
    color: {TEXT};
}}

QMenu::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}

QStatusBar {{
    background-color: {BG_ELEVATED};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}

QStatusBar QLabel {{
    color: {TEXT_MUTED};
    padding: 2px 10px;
}}

QStatusBar::item {{
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 6px 10px;
}}

QMessageBox {{
    background-color: {CARD};
}}

QMessageBox QLabel {{
    color: {TEXT};
}}
"""


LOGIN_QSS = f"""
QDialog {{
    background-color: {BG};
}}

QFrame#loginCard {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 18px;
}}

QLabel#loginBrand {{
    color: {ACCENT_2};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 3px;
}}

QLabel#loginTitle {{
    color: {TEXT};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

QLabel#loginSubtitle {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}

QLineEdit {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 11px 13px;
    color: {TEXT};
    font-size: 13px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus {{
    border-color: {ACCENT};
}}

QPushButton#loginBtn {{
    background-color: {ACCENT};
    border: none;
    color: #ffffff;
    padding: 12px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.5px;
}}

QPushButton#loginBtn:hover {{
    background-color: #7d70ff;
}}

QPushButton#loginBtn:pressed {{
    background-color: #5c4fe0;
}}

QPushButton#loginBtn:disabled {{
    background-color: #2a2f44;
    color: {TEXT_FAINT};
}}

QPushButton#linkBtn {{
    background: transparent;
    border: none;
    color: {TEXT_MUTED};
    font-weight: 600;
    padding: 8px;
}}

QPushButton#linkBtn:hover {{
    color: {ACCENT_2};
}}

QLabel#statusMsg {{
    font-size: 12px;
}}
"""
