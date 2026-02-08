"""Basecalling options page (Dorado model + demux kit)."""

import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.config import DEMUX_KITS
from src.gui.logo import LogoManager


class BasecallingPage(QWidget):
    next_clicked = Signal()
    back_clicked = Signal()

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(_create_page_header(logo_manager, "Basecalling Options"))
        layout.addSpacing(20)

        model_group = QGroupBox("Dorado Basecalling Model")
        model_layout = QVBoxLayout(model_group)
        model_layout.addWidget(QLabel("Model Directory:"))

        model_path_layout = QHBoxLayout()
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText(
            "Select Dorado model directory..."
        )
        self.model_path_edit.setReadOnly(True)
        model_path_layout.addWidget(self.model_path_edit)

        model_browse_btn = QPushButton("Browse...")
        model_browse_btn.clicked.connect(self._browse_model_dir)
        model_path_layout.addWidget(model_browse_btn)

        model_layout.addLayout(model_path_layout)
        layout.addWidget(model_group)

        demux_group = QGroupBox("Demultiplexing")
        demux_layout = QVBoxLayout(demux_group)
        demux_layout.addWidget(QLabel("Barcode Kit:"))
        self.demux_kit_combo = QComboBox()
        self.demux_kit_combo.addItems(DEMUX_KITS)
        demux_layout.addWidget(self.demux_kit_combo)
        layout.addWidget(demux_group)

        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.next_clicked.emit)
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)

    def _browse_model_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Dorado Model", os.path.expanduser("~")
        )
        if path:
            self.model_path_edit.setText(path)

    def get_model_path(self) -> str:
        return self.model_path_edit.text()

    def get_demux_kit(self) -> str:
        return self.demux_kit_combo.currentText()


def _create_page_header(logo_manager: LogoManager, title: str) -> QHBoxLayout:
    header = QHBoxLayout()
    mastrspy = logo_manager.create_logo_label("mastrspy", 40)
    header.addWidget(mastrspy)

    title_label = QLabel(title)
    title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
    header.addWidget(title_label)

    header.addStretch()

    malslabs = logo_manager.create_logo_label("malslabs", 40)
    header.addWidget(malslabs)

    return header
