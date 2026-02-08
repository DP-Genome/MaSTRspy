"""Logo management for MaSTRspy GUI."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class LogoManager:
    def __init__(self, project_dir: str):
        self.mastrspy_logo = os.path.join(project_dir, "logo.jpg")
        self.malslabs_logo = os.path.join(project_dir, "Malslabs_Logo.jpg")

    def create_logo_label(self, logo_type: str, size: int) -> QLabel:
        label = QLabel()
        path = self.mastrspy_logo if logo_type == "mastrspy" else self.malslabs_logo

        if os.path.exists(path):
            pixmap = QPixmap(path).scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pixmap)

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label
