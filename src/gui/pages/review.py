"""Review all settings before starting the workflow."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.logo import LogoManager
from src.gui.page_utils import create_page_header


class ReviewPage(QWidget):
    start_clicked = Signal()
    back_clicked = Signal()

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(create_page_header(logo_manager, "Review & Confirm"))
        layout.addSpacing(20)

        info_label = QLabel("Review your settings before starting:")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        self.review_text = QTextEdit()
        self.review_text.setReadOnly(True)
        self.review_text.setMinimumHeight(400)
        layout.addWidget(self.review_text)

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        run_btn = QPushButton("Start Workflow")
        run_btn.setObjectName("successButton")
        run_btn.setMinimumHeight(50)
        run_btn.clicked.connect(self.start_clicked.emit)
        nav_layout.addWidget(run_btn)

        layout.addLayout(nav_layout)

    def set_review_html(self, html: str):
        self.review_text.setHtml(html)
