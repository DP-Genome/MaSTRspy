"""Processing page with live log and pipeline stage indicators."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.logo import LogoManager


class ProcessingPage(QWidget):
    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(_create_page_header(logo_manager, "Processing"))
        layout.addSpacing(20)

        self.processing_status = QLabel("Initializing workflow...")
        self.processing_status.setFont(
            QFont("Segoe UI", 14, QFont.Weight.Bold)
        )
        self.processing_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.processing_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        stages_group = QGroupBox("Pipeline Stages")
        stages_layout = QVBoxLayout(stages_group)

        self.stage_labels = {}
        for stage in ["Basecalling", "Demultiplexing", "Prepping", "Analysis"]:
            stage_layout = QHBoxLayout()
            icon_label = QLabel("...")
            stage_label = QLabel(stage)
            stage_layout.addWidget(icon_label)
            stage_layout.addWidget(stage_label)
            stage_layout.addStretch()
            stages_layout.addLayout(stage_layout)
            self.stage_labels[stage] = (icon_label, stage_label)

        layout.addWidget(stages_group)

        log_group = QGroupBox("Detailed Log")
        log_layout = QVBoxLayout(log_group)
        self.processing_log = QTextEdit()
        self.processing_log.setReadOnly(True)
        self.processing_log.setMaximumHeight(200)
        log_layout.addWidget(self.processing_log)
        layout.addWidget(log_group)

        layout.addStretch()

    def reset_stages(self):
        for icon_label, _ in self.stage_labels.values():
            icon_label.setText("...")
        self.processing_log.clear()

    def on_stage_started(self, stage_name: str):
        self.processing_status.setText(f"Running: {stage_name}...")
        if stage_name in self.stage_labels:
            icon_label, _ = self.stage_labels[stage_name]
            icon_label.setText("[...]")

    def on_stage_complete(self, stage_name: str):
        if stage_name in self.stage_labels:
            icon_label, _ = self.stage_labels[stage_name]
            icon_label.setText("[OK]")

    def append_log(self, message: str):
        self.processing_log.append(message)
        self.processing_log.verticalScrollBar().setValue(
            self.processing_log.verticalScrollBar().maximum()
        )


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
