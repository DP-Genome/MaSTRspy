"""Experiment name and output directory page."""

import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.logo import LogoManager


class ExperimentPage(QWidget):
    next_clicked = Signal()
    back_clicked = Signal()

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(_create_page_header(logo_manager, "Experiment Setup"))
        layout.addSpacing(20)

        name_group = QGroupBox("Experiment Information")
        name_layout = QVBoxLayout(name_group)
        name_layout.addWidget(QLabel("Experiment Name:"))
        self.exp_name_edit = QLineEdit()
        self.exp_name_edit.setPlaceholderText("e.g., Sample_Run1_2024")
        name_layout.addWidget(self.exp_name_edit)
        layout.addWidget(name_group)

        output_group = QGroupBox("Output Location")
        output_layout = QVBoxLayout(output_group)
        output_layout.addWidget(QLabel("Output Directory:"))

        output_path_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output directory...")
        self.output_path_edit.setReadOnly(True)
        output_path_layout.addWidget(self.output_path_edit)

        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self._browse_output_dir)
        output_path_layout.addWidget(output_browse_btn)

        output_layout.addLayout(output_path_layout)
        layout.addWidget(output_group)

        self.workflow_summary_label = QLabel()
        self.workflow_summary_label.setWordWrap(True)
        self.workflow_summary_label.setStyleSheet(
            "background-color: #e8f4f8; padding: 15px; border-radius: 6px;"
        )
        layout.addWidget(self.workflow_summary_label)

        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self._validate_and_next)
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)

    def _browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", os.path.expanduser("~")
        )
        if path:
            self.output_path_edit.setText(path)

    def _validate_and_next(self):
        if not self.exp_name_edit.text().strip():
            QMessageBox.warning(
                self, "Missing Info", "Please enter an experiment name."
            )
            return
        if not self.output_path_edit.text():
            QMessageBox.warning(
                self, "Missing Info", "Please select an output directory."
            )
            return
        self.next_clicked.emit()

    def set_workflow_summary(self, summary_html: str):
        self.workflow_summary_label.setText(summary_html)

    def get_exp_name(self) -> str:
        return self.exp_name_edit.text()

    def get_output_dir(self) -> str:
        return self.output_path_edit.text()


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
