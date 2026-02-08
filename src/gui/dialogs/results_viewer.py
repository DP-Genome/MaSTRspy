"""Dialog for viewing analysis results (tables, profiles, plots)."""

import glob
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ResultsViewerDialog(QDialog):
    def __init__(self, results_dir: str, parent=None):
        super().__init__(parent)
        self.results_dir = results_dir
        self.setWindowTitle("MaSTRspy Results Viewer")
        self.setMinimumSize(1200, 800)

        layout = QVBoxLayout(self)

        header = QLabel("Analysis Results")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.tabs = QTabWidget()

        # Summary Tables tab
        tables_widget = QWidget()
        tables_layout = QVBoxLayout(tables_widget)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Barcode:"))
        self.barcode_combo = QComboBox()
        self.barcode_combo.currentTextChanged.connect(self._load_barcode_table)
        selector_layout.addWidget(self.barcode_combo)
        selector_layout.addStretch()
        tables_layout.addLayout(selector_layout)

        self.summary_table = QTableWidget()
        self.summary_table.setAlternatingRowColors(True)
        tables_layout.addWidget(self.summary_table)

        self.tabs.addTab(tables_widget, "Summary Tables")

        # Barcode Profiles tab
        profiles_widget = QWidget()
        profiles_layout = QVBoxLayout(profiles_widget)

        profile_selector_layout = QHBoxLayout()
        profile_selector_layout.addWidget(QLabel("Select Barcode:"))
        self.profile_barcode_combo = QComboBox()
        self.profile_barcode_combo.currentTextChanged.connect(
            self._load_barcode_profile
        )
        profile_selector_layout.addWidget(self.profile_barcode_combo)
        profile_selector_layout.addStretch()
        profiles_layout.addLayout(profile_selector_layout)

        self.profile_table = QTableWidget()
        self.profile_table.setAlternatingRowColors(True)
        profiles_layout.addWidget(self.profile_table)

        legend_label = QLabel(
            "<b>Barcode Profile:</b> Top 2 alleles per locus<br>"
            "PASS = Above normalization threshold<br>"
            "FLAGGED = Below threshold (possible artifact/stutter)"
        )
        legend_label.setWordWrap(True)
        legend_label.setStyleSheet(
            "padding: 10px; background-color: #f0f0f0; border-radius: 5px;"
        )
        profiles_layout.addWidget(legend_label)

        self.tabs.addTab(profiles_widget, "Barcode Profiles")

        # Plots tab
        plots_widget = QWidget()
        plots_layout = QVBoxLayout(plots_widget)

        plot_selector_layout = QHBoxLayout()
        plot_selector_layout.addWidget(QLabel("Select Barcode:"))
        self.plot_barcode_combo = QComboBox()
        self.plot_barcode_combo.currentTextChanged.connect(self._load_barcode_plot)
        plot_selector_layout.addWidget(self.plot_barcode_combo)
        plot_selector_layout.addStretch()
        plots_layout.addLayout(plot_selector_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.plot_label = QLabel("No plot available")
        self.plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self.plot_label)
        plots_layout.addWidget(scroll)

        self.tabs.addTab(plots_widget, "Plots")

        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        open_folder_btn = QPushButton("Open Results Folder")
        open_folder_btn.clicked.connect(self._open_results_folder)
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self._load_results()

    def _load_results(self):
        summaries_dir = self.results_dir
        if not os.path.exists(summaries_dir):
            summaries_dir = os.path.dirname(self.results_dir)

        summary_files = glob.glob(os.path.join(summaries_dir, "*_summary.tsv"))

        if summary_files:
            barcodes = [
                os.path.basename(f).replace("_summary.tsv", "") for f in summary_files
            ]
            self.barcode_combo.addItems(barcodes)
            self.profile_barcode_combo.addItems(barcodes)
            self.plot_barcode_combo.addItems(barcodes)

    def _load_barcode_table(self, barcode: str):
        if not barcode:
            return

        summary_file = os.path.join(self.results_dir, f"{barcode}_summary.tsv")
        if not os.path.exists(summary_file):
            return

        try:
            with open(summary_file, "r") as f:
                lines = f.readlines()

            if len(lines) < 2:
                return

            headers = lines[0].strip().split("\t")
            data_lines = [
                line.strip().split("\t") for line in lines[1:] if line.strip()
            ]

            self.summary_table.setColumnCount(len(headers))
            self.summary_table.setRowCount(len(data_lines))
            self.summary_table.setHorizontalHeaderLabels(headers)

            for row, data in enumerate(data_lines):
                for col, value in enumerate(data):
                    item = QTableWidgetItem(value)
                    self.summary_table.setItem(row, col, item)

            self.summary_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load table: {e}")

    def _load_barcode_profile(self, barcode: str):
        if not barcode:
            return

        profile_file = os.path.join(self.results_dir, f"{barcode}_Profile.tsv")
        if not os.path.exists(profile_file):
            self.profile_table.setRowCount(0)
            self.profile_table.setColumnCount(1)
            self.profile_table.setHorizontalHeaderLabels(["Info"])
            item = QTableWidgetItem(
                f"No profile found for {barcode}\n\n"
                "Run analysis to generate profiles."
            )
            self.profile_table.setItem(0, 0, item)
            return

        try:
            with open(profile_file, "r") as f:
                lines = f.readlines()

            if len(lines) < 2:
                return

            headers = lines[0].strip().split("\t")
            data_lines = [
                line.strip().split("\t") for line in lines[1:] if line.strip()
            ]

            self.profile_table.setColumnCount(len(headers))
            self.profile_table.setRowCount(len(data_lines))
            self.profile_table.setHorizontalHeaderLabels(headers)

            for row, data in enumerate(data_lines):
                for col, value in enumerate(data):
                    item = QTableWidgetItem(value)

                    if col == 7 and len(data) > 7:
                        if "PASS" in value:
                            item.setBackground(QColor(200, 255, 200))
                        elif "FLAGGED" in value:
                            item.setBackground(QColor(255, 200, 200))

                    self.profile_table.setItem(row, col, item)

            self.profile_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load profile: {e}")

    def _load_barcode_plot(self, barcode: str):
        if not barcode:
            return

        plots_dir = os.path.join(self.results_dir, "Plots")
        plot_file = os.path.join(plots_dir, f"{barcode}_plot.png")

        if not os.path.exists(plot_file):
            self.plot_label.setText(
                f"No plot found for {barcode}\n\nLooked in: {plots_dir}"
            )
            return

        try:
            pixmap = QPixmap(plot_file)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    1100,
                    700,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.plot_label.setPixmap(scaled_pixmap)
            else:
                self.plot_label.setText(f"Could not load plot for {barcode}")
        except Exception as e:
            self.plot_label.setText(f"Error loading plot: {e}")

    def _open_results_folder(self):
        parent_dir = os.path.dirname(self.results_dir)
        if sys.platform == "linux":
            subprocess.Popen(["xdg-open", parent_dir])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", parent_dir])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", parent_dir])
