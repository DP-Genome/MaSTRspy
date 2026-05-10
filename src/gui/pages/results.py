"""Results/done page with links to open results."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.logo import LogoManager
from src.gui.page_utils import create_page_header


class ResultsPage(QWidget):
    view_results_clicked = Signal()
    open_folder_clicked = Signal()
    new_analysis_clicked = Signal()

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(create_page_header(logo_manager, "Results"))
        layout.addSpacing(20)

        success_icon = QLabel("Done!")
        success_icon.setFont(QFont("Segoe UI", 48))
        success_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(success_icon)

        success_label = QLabel("Workflow Completed Successfully!")
        success_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(success_label)

        layout.addSpacing(30)

        self.results_info = QLabel()
        self.results_info.setWordWrap(True)
        self.results_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.results_info)

        layout.addSpacing(20)

        actions_layout = QHBoxLayout()

        view_results_btn = QPushButton("View Results")
        view_results_btn.setMinimumHeight(50)
        view_results_btn.clicked.connect(self.view_results_clicked.emit)
        actions_layout.addWidget(view_results_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setMinimumHeight(50)
        open_folder_btn.clicked.connect(self.open_folder_clicked.emit)
        actions_layout.addWidget(open_folder_btn)

        layout.addLayout(actions_layout)
        layout.addStretch()

        new_analysis_btn = QPushButton("Start New Analysis")
        new_analysis_btn.setObjectName("successButton")
        new_analysis_btn.clicked.connect(self.new_analysis_clicked.emit)
        layout.addWidget(new_analysis_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_results_info(self, text: str):
        self.results_info.setText(text)
