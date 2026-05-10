#!/usr/bin/env python3
"""MaSTRspy - Smart STR Analysis Pipeline.

CLI entry point.  Usage:
    MaSTRspy activate   – launch the GUI
    MaSTRspy setup      – auto-detect tools and write ToolsConfig.txt
"""

import argparse
import os
import shutil
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


def _setup(args):
    """Auto-detect installed tools and write their paths to ToolsConfig.txt."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_dir, "config", "ToolsConfig.txt")

    tools = {
        "BEDTOOLS": "bedtools",
        "MINIMAP": "minimap2",
        "SAMTOOLS": "samtools",
        "XATLAS": "xatlas",
        "DORADO": "dorado",
        "RSCRIPT": "Rscript",
    }

    lines = ["#=========================================Tools global path==========================================\n"]
    for key, name in tools.items():
        path = shutil.which(name)
        if path:
            print(f"  [FOUND]     {name}: {path}")
            lines.append(f"{key}={path}\n")
        else:
            print(f"  [NOT FOUND] {name}: using bare name (must be on PATH)")
            lines.append(f"{key}={name}\n")

    with open(config_path, "w") as f:
        f.writelines(lines)

    print(f"\nToolsConfig.txt written to: {config_path}")


def main():
    parser = argparse.ArgumentParser(
        prog="MaSTRspy",
        description="MaSTRspy - Smart STR Analysis Pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("activate", help="Launch the MaSTRspy GUI")
    subparsers.add_parser("setup", help="Auto-detect tools and write ToolsConfig.txt")

    args = parser.parse_args()

    if args.command == "activate":
        _activate(args)
    elif args.command == "setup":
        _setup(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
