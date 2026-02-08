"""File selection page with auto-detection."""

import os
from typing import List, Tuple

from PySide6.QtCore import Qt, Signal
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

from src.core.file_detector import FileType, detect_file_type
from src.gui.logo import LogoManager


class FileSelectionPage(QWidget):
    next_clicked = Signal()
    back_clicked = Signal()
    files_detected = Signal(FileType, list)

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(_create_page_header(logo_manager, "Select Input Files"))
        layout.addSpacing(20)

        instructions = QLabel(
            "Choose your input directory. MaSTRspy will automatically\n"
            "detect the file type and configure the workflow."
        )
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)

        layout.addSpacing(30)

        file_group = QGroupBox("Input Selection")
        file_layout = QVBoxLayout(file_group)

        path_layout = QHBoxLayout()
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("No files selected...")
        self.input_path_edit.setReadOnly(True)
        path_layout.addWidget(self.input_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_input_files)
        path_layout.addWidget(browse_btn)

        file_layout.addLayout(path_layout)

        self.detection_label = QLabel("Waiting for file selection...")
        self.detection_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        self.detection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_layout.addWidget(self.detection_label)

        self.file_count_label = QLabel("")
        self.file_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_layout.addWidget(self.file_count_label)

        layout.addWidget(file_group)
        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        self.next_btn = QPushButton("Next")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

    def _browse_input_files(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Input Directory", os.path.expanduser("~")
        )
        if path:
            self.input_path_edit.setText(path)
            self._detect_files(path)

    def _detect_files(self, path: str):
        file_type, detected_files = detect_file_type(path)

        if file_type == FileType.UNKNOWN:
            self.detection_label.setText("No supported files detected")
            self.detection_label.setStyleSheet(
                "color: #d32f2f; font-weight: bold;"
            )
            self.file_count_label.setText("")
            self.next_btn.setEnabled(False)
            QMessageBox.warning(
                self,
                "Unknown File Type",
                "No POD5, FASTQ, or BAM files found.",
            )
        else:
            file_type_names = {
                FileType.POD5: "POD5 Files (Raw Signals)",
                FileType.FASTQ: "FASTQ Files (Basecalled)",
                FileType.BAM_ALIGNED: "BAM Files (Aligned)",
                FileType.BAM_UNALIGNED: "BAM Files (Unaligned)",
            }
            self.detection_label.setText(
                f"Detected: {file_type_names[file_type]}"
            )
            self.detection_label.setStyleSheet(
                "color: #388e3c; font-weight: bold;"
            )
            self.file_count_label.setText(f"{len(detected_files)} files found")
            self.next_btn.setEnabled(True)
            self.files_detected.emit(file_type, detected_files)

    def get_input_path(self) -> str:
        return self.input_path_edit.text()


def _create_page_header(logo_manager: LogoManager, title: str) -> QHBoxLayout:
    from PySide6.QtGui import QFont

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
