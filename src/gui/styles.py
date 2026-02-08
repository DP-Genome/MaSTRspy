"""Light and dark theme stylesheets for MaSTRspy GUI."""

LIGHT_STYLE = """
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 11pt;
    color: #1e1e1e;
    background-color: #fcfcfc;
}
QMainWindow {
    background-color: #f5f5f5;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #005a9e;
}
QPushButton:disabled {
    background-color: #cccccc;
    color: #666666;
}
QPushButton#secondaryButton {
    background-color: #6c757d;
}
QPushButton#secondaryButton:hover {
    background-color: #5a6268;
}
QPushButton#successButton {
    background-color: #28a745;
}
QPushButton#successButton:hover {
    background-color: #218838;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 2px solid #e0e0e0;
    border-radius: 6px;
    padding: 8px;
}
QGroupBox {
    font-weight: bold;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
}
QSlider::groove:horizontal {
    border: 1px solid #bbb;
    background: #e0e0e0;
    height: 8px;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    border: 1px solid #005a9e;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QProgressBar {
    border: 2px solid #e0e0e0;
    border-radius: 6px;
    text-align: center;
    height: 25px;
}
QProgressBar::chunk {
    background-color: #0078d4;
}
QTabBar::tab {
    background-color: #e0e0e0;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #0078d4;
    color: white;
}
"""

DARK_STYLE = """
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 11pt;
    color: #e0e0e0;
    background-color: #2b2b2b;
}
QMainWindow {
    background-color: #1e1e1e;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #005a9e;
}
QPushButton:disabled {
    background-color: #4f4f4f;
    color: #9e9e9e;
}
QPushButton#secondaryButton {
    background-color: #495057;
}
QPushButton#secondaryButton:hover {
    background-color: #343a40;
}
QPushButton#successButton {
    background-color: #28a745;
}
QPushButton#successButton:hover {
    background-color: #1e7e34;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #3c3c3c;
    border: 2px solid #555555;
    border-radius: 6px;
    padding: 8px;
    color: #e0e0e0;
}
QGroupBox {
    font-weight: bold;
    border: 2px solid #555555;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #2b2b2b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
}
QSlider::groove:horizontal {
    border: 1px solid #555;
    background: #3c3c3c;
    height: 8px;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QProgressBar {
    border: 2px solid #555555;
    border-radius: 6px;
    text-align: center;
    height: 25px;
    color: #e0e0e0;
}
QProgressBar::chunk {
    background-color: #0078d4;
}
QTextEdit {
    font-family: 'Consolas', 'Courier New', monospace;
}
QTabBar::tab {
    background-color: #3c3c3c;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #e0e0e0;
}
QTabBar::tab:selected {
    background-color: #0078d4;
    color: white;
}
"""
