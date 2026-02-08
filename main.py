#!/usr/bin/env python3
"""MaSTRspy - Smart STR Analysis Pipeline.

Entry point: launches the PySide6 GUI application.
"""

import sys

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MaSTRspy")
    app.setApplicationVersion("P1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
