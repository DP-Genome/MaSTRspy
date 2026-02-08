#!/usr/bin/env python3
"""MaSTRspy - Smart STR Analysis Pipeline.

CLI entry point.  Usage:
    MaSTRspy activate   – launch the GUI
"""

import argparse
import sys


def _activate(args):
    """Launch the PySide6 GUI application."""
    from PySide6.QtWidgets import QApplication

    from src.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("MaSTRspy")
    app.setApplicationVersion("P1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(
        prog="MaSTRspy",
        description="MaSTRspy - Smart STR Analysis Pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("activate", help="Launch the MaSTRspy GUI")

    args = parser.parse_args()

    if args.command == "activate":
        _activate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
