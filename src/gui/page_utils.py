"""Shared utilities for GUI pages."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel

from src.gui.logo import LogoManager


def create_page_header(logo_manager: LogoManager, title: str) -> QHBoxLayout:
    """Create a standard page header with MaSTRspy and MaLSLabs logos."""
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
