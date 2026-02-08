"""Welcome/landing page for MaSTRspy."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.logo import LogoManager


class WelcomePage(QWidget):
    next_clicked = Signal()
    dark_mode_changed = Signal(bool)

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.addStretch(1)

        mastrspy_logo = logo_manager.create_logo_label("mastrspy", 200)
        layout.addWidget(mastrspy_logo)

        title = QLabel("Welcome to MaSTRspy")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Smart STR Analysis Pipeline")
        subtitle.setFont(QFont("Segoe UI", 16))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666666;")
        layout.addWidget(subtitle)

        layout.addSpacing(40)

        desc = QLabel(
            "Automatically detects your file type and guides you\n"
            "through the appropriate workflow - from raw signals to results."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(20)

        start_btn = QPushButton("Get Started")
        start_btn.setMinimumHeight(50)
        start_btn.clicked.connect(self.next_clicked.emit)
        layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(2)

        bottom_layout = QHBoxLayout()
        self.dark_mode_check = QCheckBox("Dark Mode")
        self.dark_mode_check.stateChanged.connect(
            lambda state: self.dark_mode_changed.emit(
                state == Qt.CheckState.Checked.value
            )
        )
        bottom_layout.addWidget(self.dark_mode_check)
        bottom_layout.addStretch()
        malslabs_logo = logo_manager.create_logo_label("malslabs", 60)
        bottom_layout.addWidget(malslabs_logo)
        layout.addLayout(bottom_layout)
