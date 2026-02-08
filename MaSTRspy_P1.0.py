#!/usr/bin/env python3
"""
MaSTRspy P1.0 - Smart Interactive Workflow Manager
Complete implementation: Auto-detection, Dynamic workflow, Results viewer, Beautiful UI

Features:
- Automatic file type detection (POD5/BAM/FASTQ)
- Dynamic workflow configuration
- Interactive filtering with sliders and presets
- Live progress monitoring
- Integrated results viewer with plots
- Light/Dark themes
- Logo integration throughout

Author: MalsLabs
Version: P1.0
"""

import sys
import os
import subprocess
import tempfile
import re
import glob
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFileDialog, QLineEdit, QTextEdit,
    QMessageBox, QStatusBar, QDialog, QDialogButtonBox, QGroupBox,
    QDoubleSpinBox, QSpinBox, QSlider, QCheckBox, QProgressBar,
    QScrollArea, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QGridLayout, QTabWidget
)
from PySide6.QtGui import QPixmap, QFont, QColor
from PySide6.QtCore import Qt, QObject, Signal, QThread


class FileType(Enum):
    POD5 = "pod5"
    BAM_ALIGNED = "bam_aligned"
    BAM_UNALIGNED = "bam_unaligned"
    FASTQ = "fastq"
    UNKNOWN = "unknown"


class WorkflowStage(Enum):
    BASECALLING = "basecalling"
    DEMULTIPLEXING = "demultiplexing"
    PREPPING = "prepping"
    ANALYSIS = "analysis"


FILTER_PRESETS = {
    "None": {"min_dorado_q": 0.0, "min_mean_q": 0.0, "min_len": 0, "min_acc": 0.0},
    "Lenient": {"min_dorado_q": 8.0, "min_mean_q": 8.0, "min_len": 100, "min_acc": 0.80},
    "Moderate": {"min_dorado_q": 10.0, "min_mean_q": 10.0, "min_len": 200, "min_acc": 0.85},
    "Stringent": {"min_dorado_q": 12.0, "min_mean_q": 12.0, "min_len": 300, "min_acc": 0.90},
    "Custom": {}
}

DEMUX_KITS = [
    "None",
    "SQK-RBK114-24",
    "SQK-NBD114-24",
    "SQK-RBK110-96",
    "SQK-NBD112-24"
]


LIGHT_STYLE = """
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 11pt;
    color: #1e1e1e;
    background-color: #fcfcfc;
}
QMainWindow {
    background-color: #f5f5f5;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #005a9e;
}
QPushButton:disabled {
    background-color: #cccccc;
    color: #666666;
}
QPushButton#secondaryButton {
    background-color: #6c757d;
}
QPushButton#secondaryButton:hover {
    background-color: #5a6268;
}
QPushButton#successButton {
    background-color: #28a745;
}
QPushButton#successButton:hover {
    background-color: #218838;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 2px solid #e0e0e0;
    border-radius: 6px;
    padding: 8px;
}
QGroupBox {
    font-weight: bold;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
}
QSlider::groove:horizontal {
    border: 1px solid #bbb;
    background: #e0e0e0;
    height: 8px;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    border: 1px solid #005a9e;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QProgressBar {
    border: 2px solid #e0e0e0;
    border-radius: 6px;
    text-align: center;
    height: 25px;
}
QProgressBar::chunk {
    background-color: #0078d4;
}
QTabBar::tab {
    background-color: #e0e0e0;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #0078d4;
    color: white;
}
"""

DARK_STYLE = """
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 11pt;
    color: #e0e0e0;
    background-color: #2b2b2b;
}
QMainWindow {
    background-color: #1e1e1e;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: bold;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #005a9e;
}
QPushButton:disabled {
    background-color: #4f4f4f;
    color: #9e9e9e;
}
QPushButton#secondaryButton {
    background-color: #495057;
}
QPushButton#secondaryButton:hover {
    background-color: #343a40;
}
QPushButton#successButton {
    background-color: #28a745;
}
QPushButton#successButton:hover {
    background-color: #1e7e34;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #3c3c3c;
    border: 2px solid #555555;
    border-radius: 6px;
    padding: 8px;
    color: #e0e0e0;
}
QGroupBox {
    font-weight: bold;
    border: 2px solid #555555;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #2b2b2b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
}
QSlider::groove:horizontal {
    border: 1px solid #555;
    background: #3c3c3c;
    height: 8px;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QProgressBar {
    border: 2px solid #555555;
    border-radius: 6px;
    text-align: center;
    height: 25px;
    color: #e0e0e0;
}
QProgressBar::chunk {
    background-color: #0078d4;
}
QTextEdit {
    font-family: 'Consolas', 'Courier New', monospace;
}
QTabBar::tab {
    background-color: #3c3c3c;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #e0e0e0;
}
QTabBar::tab:selected {
    background-color: #0078d4;
    color: white;
}
"""


class LogoManager:
    def __init__(self, script_dir: str):
        self.mastrspy_logo = os.path.join(script_dir, "logo.jpg")
        self.malslabs_logo = os.path.join(script_dir, "Malslabs_Logo.jpg")

    def create_logo_label(self, logo_type: str, size: int) -> QLabel:
        label = QLabel()
        path = self.mastrspy_logo if logo_type == 'mastrspy' else self.malslabs_logo

        if os.path.exists(path):
            pixmap = QPixmap(path).scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label.setPixmap(pixmap)

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label


class FileDetector:
    @staticmethod
    def detect_file_type(path: str) -> Tuple[FileType, List[str]]:
        path_obj = Path(path)
        if not path_obj.exists():
            return FileType.UNKNOWN, []

        files = list(path_obj.iterdir()) if path_obj.is_dir() else [path_obj]

        pod5_files = [f for f in files if f.suffix.lower() == '.pod5']
        if pod5_files:
            return FileType.POD5, [str(f) for f in pod5_files]

        fastq_files = [f for f in files if f.suffix.lower() in ['.fastq', '.fq']]
        if fastq_files:
            return FileType.FASTQ, [str(f) for f in fastq_files]

        bam_files = [f for f in files if f.suffix.lower() == '.bam']
        if bam_files:
            try:
                result = subprocess.run(
                    ['samtools', 'view', '-c', '-F', '4', str(bam_files[0])],
                    capture_output=True, text=True, timeout=10
                )
                is_aligned = int(result.stdout.strip()) > 0
                return (FileType.BAM_ALIGNED if is_aligned else FileType.BAM_UNALIGNED), \
                       [str(f) for f in bam_files]
            except:
                return FileType.BAM_UNALIGNED, [str(f) for f in bam_files]

        return FileType.UNKNOWN, []


class WorkflowManager:
    def __init__(self, file_type: FileType):
        self.file_type = file_type
        self.stages = self._build_stages()

    def _build_stages(self) -> List[WorkflowStage]:
        if self.file_type == FileType.POD5:
            return [WorkflowStage.BASECALLING, WorkflowStage.DEMULTIPLEXING,
                   WorkflowStage.PREPPING, WorkflowStage.ANALYSIS]
        elif self.file_type in [FileType.FASTQ, FileType.BAM_UNALIGNED]:
            return [WorkflowStage.PREPPING, WorkflowStage.ANALYSIS]
        elif self.file_type == FileType.BAM_ALIGNED:
            return [WorkflowStage.ANALYSIS]
        return []

    def needs_basecalling(self) -> bool:
        return WorkflowStage.BASECALLING in self.stages

    def needs_prepping(self) -> bool:
        return WorkflowStage.PREPPING in self.stages


class FullWorkflowWorker(QObject):
    log_message = Signal(str)
    stage_started = Signal(str)
    stage_complete = Signal(str)
    finished = Signal(int, str)

    def __init__(self, params: Dict[str, Any], script_dir: str):
        super().__init__()
        self.params = params
        self.script_dir = script_dir

    def run(self):
        try:
            p = self.params
            exp_output_dir = os.path.join(p['output_dir'], p['exp_name'])
            os.makedirs(exp_output_dir, exist_ok=True)

            if p.get('file_type') == FileType.POD5:
                self.stage_started.emit("Basecalling")
                basecalled_bam = os.path.join(exp_output_dir, "1_basecalled.bam")

                cmd = ['dorado', 'basecaller', p['model_path'], p['input_path']]
                if not self._run_stage(cmd, basecalled_bam, is_basecaller=True):
                    self.finished.emit(1, "")
                    return
                self.stage_complete.emit("Basecalling")

                self.stage_started.emit("Demultiplexing")
                demux_dir = os.path.join(exp_output_dir, "2_demuxed")
                os.makedirs(demux_dir, exist_ok=True)

                if p.get('demux_kit') != "None":
                    cmd = ['dorado', 'demux', '--output-dir', demux_dir,
                          '--kit-name', p['demux_kit'], basecalled_bam]
                    if not self._run_stage(cmd):
                        self.finished.emit(1, "")
                        return
                else:
                    target = os.path.join(demux_dir, os.path.basename(basecalled_bam))
                    if not os.path.exists(target):
                        os.symlink(basecalled_bam, target)

                self.stage_complete.emit("Demultiplexing")
                input_for_prepping = demux_dir
            else:
                input_for_prepping = p['input_path']

            if p.get('needs_prepping', True):
                self.stage_started.emit("Prepping")
                prepped_dir = os.path.join(exp_output_dir, "3_prepped")
                os.makedirs(prepped_dir, exist_ok=True)

                prep_script = os.path.join(self.script_dir, "MaSTR_Prepping_P1.0.sh")
                cmd = [
                    'bash', prep_script,
                    '--input', input_for_prepping,
                    '--output', prepped_dir,
                    '--ref', p['ref_genome'],
                    '--exp_name', p['exp_name'],
                    '--input-type', p.get('input_type', 'bam'),
                    '--min-dorado-q', str(p.get('min_dorado_q', 0)),
                    '--min-mean-q', str(p.get('min_mean_q', 0)),
                    '--min-len', str(p.get('min_len', 0)),
                    '--min-acc', str(p.get('min_acc', 0))
                ]

                if not self._run_stage(cmd):
                    self.finished.emit(1, "")
                    return
                self.stage_complete.emit("Prepping")
                input_for_analysis = prepped_dir
            else:
                input_for_analysis = input_for_prepping

            self.stage_started.emit("Analysis")
            analysis_dir = os.path.join(exp_output_dir, "4_analysis")

            input_config_content = self._generate_input_config(input_for_analysis, analysis_dir, p)

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as f:
                f.write(input_config_content)
                input_config_path = f.name

            tools_config = os.path.join(self.script_dir, "config", "ToolsConfig.txt")
            analysis_script = os.path.join(self.script_dir, "MaSTRspy_Analysis_P1.0.sh")

            cmd = ['bash', analysis_script, input_config_path, tools_config]

            if not self._run_stage(cmd):
                os.remove(input_config_path)
                self.finished.emit(1, "")
                return

            os.remove(input_config_path)
            self.stage_complete.emit("Analysis")

            results_dir = os.path.join(analysis_dir, "Countings", "Summaries")
            self.finished.emit(0, results_dir)

        except Exception as e:
            self.log_message.emit(f"\n[ERROR] Workflow failed: {e}\n")
            self.finished.emit(1, "")

    def _run_stage(self, command: List[str], output_file: str = None,
                   is_basecaller: bool = False) -> bool:
        try:
            log_cmd = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
            self.log_message.emit(f"[CMD] {log_cmd}\n")

            if is_basecaller:
                with open(output_file, "wb") as f_out:
                    process = subprocess.Popen(
                        command, stdout=f_out, stderr=subprocess.PIPE, text=True
                    )
                    for line in iter(process.stderr.readline, ''):
                        self.log_message.emit(line.rstrip())
                    return_code = process.wait()
            else:
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                for line in iter(process.stdout.readline, ''):
                    self.log_message.emit(line.rstrip())
                process.stdout.close()
                return_code = process.wait()

            return return_code == 0

        except Exception as e:
            self.log_message.emit(f"\n[ERROR] Stage failed: {e}\n")
            return False

    def _generate_input_config(self, input_dir: str, output_dir: str,
                               params: Dict) -> str:
        norm_cutoff = params.get('norm_cutoff', 0.10)
        norm_cutoff_overrides = params.get('norm_cutoff_overrides', '')

        master_config = os.path.join(self.script_dir, "config", "InputConfig.txt")
        if os.path.exists(master_config):
            with open(master_config, 'r') as f:
                lines = f.readlines()

            new_lines = []
            saw_norm_cutoff = False
            saw_norm_overrides = False

            for line in lines:
                if re.match(r'^\s*INPUT_DIR=', line):
                    new_lines.append(f'INPUT_DIR="{input_dir}"\n')
                elif re.match(r'^\s*OUTPUT_DIR=', line):
                    new_lines.append(f'OUTPUT_DIR="{output_dir}"\n')
                elif re.match(r'^\s*INPUT_BAM=', line):
                    new_lines.append('INPUT_BAM="yes"\n')
                elif re.match(r'^\s*NORM_CUTOFF=', line):
                    saw_norm_cutoff = True
                    new_lines.append(f'NORM_CUTOFF={norm_cutoff}\n')
                elif re.match(r'^\s*NORM_CUTOFF_OVERRIDES=', line):
                    saw_norm_overrides = True
                    if norm_cutoff_overrides:
                        new_lines.append(f'NORM_CUTOFF_OVERRIDES="{norm_cutoff_overrides}"\n')
                    else:
                        new_lines.append('NORM_CUTOFF_OVERRIDES=\n')
                else:
                    new_lines.append(line)

            if not saw_norm_cutoff:
                new_lines.append(f'NORM_CUTOFF={norm_cutoff}\n')
            if not saw_norm_overrides:
                if norm_cutoff_overrides:
                    new_lines.append(f'NORM_CUTOFF_OVERRIDES="{norm_cutoff_overrides}"\n')
                else:
                    new_lines.append('NORM_CUTOFF_OVERRIDES=\n')

            return "".join(new_lines)
        else:
            config_str = f'''INPUT_DIR="{input_dir}"
OUTPUT_DIR="{output_dir}"
INPUT_BAM="yes"
NORM_CUTOFF={norm_cutoff}
'''
            if norm_cutoff_overrides:
                config_str += f'NORM_CUTOFF_OVERRIDES="{norm_cutoff_overrides}"\n'

            return config_str


class LociOverridesDialog(QDialog):
    def __init__(self, tsv_path: str, parent=None):
        super().__init__(parent)
        self.tsv_path = tsv_path
        self.setWindowTitle("Edit Per-Locus Norm_cutoff Overrides")
        self.setMinimumSize(600, 500)

        self._prefix_lines = []
        self._rows = []

        layout = QVBoxLayout(self)

        info = QLabel(
            "Edit per-locus overrides for Norm_cutoff thresholds.\n"
            "Column 1: Locus name (read-only)\n"
            "Column 2: Cutoff value (editable)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Locus", "Norm_cutoff"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._load_tsv()

    def _load_tsv(self):
        if not os.path.isfile(self.tsv_path):
            QMessageBox.warning(self, "File Not Found", f"File does not exist:\n{self.tsv_path}")
            return

        with open(self.tsv_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                self._prefix_lines.append(line)
                continue

            parts = stripped.split('\t')
            locus = parts[0] if parts else ""
            cutoff = parts[1] if len(parts) > 1 else ""
            self._rows.append((locus, cutoff))

        self.table.setRowCount(len(self._rows))
        for r, (locus, cutoff) in enumerate(self._rows):
            item_locus = QTableWidgetItem(locus)
            item_locus.setFlags(item_locus.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, item_locus)

            item_cutoff = QTableWidgetItem(str(cutoff))
            self.table.setItem(r, 1, item_cutoff)

    def _on_accept(self):
        updated_rows = []

        for r in range(self.table.rowCount()):
            locus_item = self.table.item(r, 0)
            cutoff_item = self.table.item(r, 1)

            locus = (locus_item.text() if locus_item else "").strip()
            cutoff = (cutoff_item.text() if cutoff_item else "").strip()

            if locus == "":
                QMessageBox.critical(self, "Invalid Row", f"Row {r+1} has empty locus name")
                return

            try:
                float(cutoff)
            except:
                QMessageBox.critical(self, "Invalid Cutoff",
                                   f"Row {r+1} for locus '{locus}' has invalid cutoff: '{cutoff}'")
                return

            updated_rows.append((locus, cutoff))

        tmp_path = self.tsv_path + ".tmp"
        with open(tmp_path, 'w') as f:
            if self._prefix_lines:
                f.writelines(self._prefix_lines)
            for locus, cutoff in updated_rows:
                f.write(f"{locus}\t{cutoff}\n")

        os.replace(tmp_path, self.tsv_path)
        self.accept()


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

        tables_widget = QWidget()
        tables_layout = QVBoxLayout(tables_widget)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Barcode:"))
        self.barcode_combo = QComboBox()
        self.barcode_combo.currentTextChanged.connect(self.load_barcode_table)
        selector_layout.addWidget(self.barcode_combo)
        selector_layout.addStretch()
        tables_layout.addLayout(selector_layout)

        self.summary_table = QTableWidget()
        self.summary_table.setAlternatingRowColors(True)
        tables_layout.addWidget(self.summary_table)

        self.tabs.addTab(tables_widget, "Summary Tables")

        profiles_widget = QWidget()
        profiles_layout = QVBoxLayout(profiles_widget)

        profile_selector_layout = QHBoxLayout()
        profile_selector_layout.addWidget(QLabel("Select Barcode:"))
        self.profile_barcode_combo = QComboBox()
        self.profile_barcode_combo.currentTextChanged.connect(self.load_barcode_profile)
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
        legend_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        profiles_layout.addWidget(legend_label)

        self.tabs.addTab(profiles_widget, "Barcode Profiles")

        plots_widget = QWidget()
        plots_layout = QVBoxLayout(plots_widget)

        plot_selector_layout = QHBoxLayout()
        plot_selector_layout.addWidget(QLabel("Select Barcode:"))
        self.plot_barcode_combo = QComboBox()
        self.plot_barcode_combo.currentTextChanged.connect(self.load_barcode_plot)
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
        open_folder_btn.clicked.connect(self.open_results_folder)
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.load_results()

    def load_results(self):
        summaries_dir = self.results_dir
        if not os.path.exists(summaries_dir):
            summaries_dir = os.path.dirname(self.results_dir)

        summary_files = glob.glob(os.path.join(summaries_dir, "*_summary.tsv"))

        if summary_files:
            barcodes = [os.path.basename(f).replace("_summary.tsv", "")
                       for f in summary_files]
            self.barcode_combo.addItems(barcodes)
            self.profile_barcode_combo.addItems(barcodes)
            self.plot_barcode_combo.addItems(barcodes)

    def load_barcode_table(self, barcode: str):
        if not barcode:
            return

        summary_file = os.path.join(self.results_dir, f"{barcode}_summary.tsv")
        if not os.path.exists(summary_file):
            return

        try:
            with open(summary_file, 'r') as f:
                lines = f.readlines()

            if len(lines) < 2:
                return

            headers = lines[0].strip().split('\t')
            data_lines = [line.strip().split('\t') for line in lines[1:] if line.strip()]

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

    def load_barcode_profile(self, barcode: str):
        if not barcode:
            return

        profile_file = os.path.join(self.results_dir, f"{barcode}_Profile.tsv")
        if not os.path.exists(profile_file):
            self.profile_table.setRowCount(0)
            self.profile_table.setColumnCount(1)
            self.profile_table.setHorizontalHeaderLabels(["Info"])
            item = QTableWidgetItem(f"No profile found for {barcode}\n\nRun with MaSTRspy_Analysis_P1.0.sh to generate profiles.")
            self.profile_table.setItem(0, 0, item)
            return

        try:
            with open(profile_file, 'r') as f:
                lines = f.readlines()

            if len(lines) < 2:
                return

            headers = lines[0].strip().split('\t')
            data_lines = [line.strip().split('\t') for line in lines[1:] if line.strip()]

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

    def load_barcode_plot(self, barcode: str):
        if not barcode:
            return

        plots_dir = os.path.join(self.results_dir, "Plots")
        plot_file = os.path.join(plots_dir, f"{barcode}_plot.png")

        if not os.path.exists(plot_file):
            self.plot_label.setText(f"No plot found for {barcode}\n\nLooked in: {plots_dir}")
            return

        try:
            pixmap = QPixmap(plot_file)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    1100, 700,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.plot_label.setPixmap(scaled_pixmap)
            else:
                self.plot_label.setText(f"Could not load plot for {barcode}")
        except Exception as e:
            self.plot_label.setText(f"Error loading plot: {e}")

    def open_results_folder(self):
        parent_dir = os.path.dirname(self.results_dir)
        if sys.platform == 'linux':
            subprocess.Popen(['xdg-open', parent_dir])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', parent_dir])
        elif sys.platform == 'win32':
            subprocess.Popen(['explorer', parent_dir])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.logo_manager = LogoManager(self.script_dir)
        self.workflow_manager: Optional[WorkflowManager] = None
        self.detected_files: List[str] = []
        self.file_type: FileType = FileType.UNKNOWN
        self.workflow_params = {}
        self.current_results_dir = ""

        self.setWindowTitle("MaSTRspy P1.0 - Smart Workflow Manager")
        self.setGeometry(100, 50, 1000, 800)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.create_all_pages()
        self.apply_theme(False)

    def create_all_pages(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.addStretch(1)

        mastrspy_logo = self.logo_manager.create_logo_label('mastrspy', 200)
        layout.addWidget(mastrspy_logo)

        title = QLabel("Welcome to MaSTRspy")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Smart STR Analysis Pipeline")
        subtitle.setFont(QFont("Segoe UI", 16))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666666;")
        layout.addWidget(subtitle)

        layout.addSpacing(40)

        desc = QLabel(
            "Automatically detects your file type and guides you\n"
            "through the appropriate workflow - from raw signals to results."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(20)

        start_btn = QPushButton("Get Started")
        start_btn.setMinimumHeight(50)
        start_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(2)

        bottom_layout = QHBoxLayout()
        self.dark_mode_check = QCheckBox("Dark Mode")
        self.dark_mode_check.stateChanged.connect(self.toggle_dark_mode)
        bottom_layout.addWidget(self.dark_mode_check)
        bottom_layout.addStretch()
        malslabs_logo = self.logo_manager.create_logo_label('malslabs', 60)
        bottom_layout.addWidget(malslabs_logo)
        layout.addLayout(bottom_layout)

        self.stacked_widget.addWidget(page)

        self.create_file_selection_page()
        self.create_experiment_page()
        self.create_basecalling_page()
        self.create_filtering_page()
        self.create_analysis_page()
        self.create_review_page()
        self.create_processing_page()
        self.create_results_page()

    def create_page_header(self, title: str) -> QHBoxLayout:
        header = QHBoxLayout()
        mastrspy = self.logo_manager.create_logo_label('mastrspy', 40)
        header.addWidget(mastrspy)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        header.addWidget(title_label)

        header.addStretch()

        malslabs = self.logo_manager.create_logo_label('malslabs', 40)
        header.addWidget(malslabs)

        return header

    def create_file_selection_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Select Input Files"))
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
        browse_btn.clicked.connect(self.browse_input_files)
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
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        self.next_from_files_btn = QPushButton("Next")
        self.next_from_files_btn.setEnabled(False)
        self.next_from_files_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        nav_layout.addWidget(self.next_from_files_btn)

        layout.addLayout(nav_layout)
        self.stacked_widget.addWidget(page)

    def create_experiment_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Experiment Setup"))
        layout.addSpacing(20)

        name_group = QGroupBox("Experiment Information")
        name_layout = QVBoxLayout(name_group)
        name_layout.addWidget(QLabel("Experiment Name:"))
        self.exp_name_edit = QLineEdit()
        self.exp_name_edit.setPlaceholderText("e.g., Sample_Run1_2024")
        name_layout.addWidget(self.exp_name_edit)
        layout.addWidget(name_group)

        output_group = QGroupBox("Output Location")
        output_layout = QVBoxLayout(output_group)
        output_layout.addWidget(QLabel("Output Directory:"))

        output_path_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output directory...")
        self.output_path_edit.setReadOnly(True)
        output_path_layout.addWidget(self.output_path_edit)

        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self.browse_output_dir)
        output_path_layout.addWidget(output_browse_btn)

        output_layout.addLayout(output_path_layout)
        layout.addWidget(output_group)

        self.workflow_summary_label = QLabel()
        self.workflow_summary_label.setWordWrap(True)
        self.workflow_summary_label.setStyleSheet(
            "background-color: #e8f4f8; padding: 15px; border-radius: 6px;"
        )
        layout.addWidget(self.workflow_summary_label)

        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.from_experiment_to_options)
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)
        self.stacked_widget.addWidget(page)

    def create_basecalling_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Basecalling Options"))
        layout.addSpacing(20)

        model_group = QGroupBox("Dorado Basecalling Model")
        model_layout = QVBoxLayout(model_group)
        model_layout.addWidget(QLabel("Model Directory:"))

        model_path_layout = QHBoxLayout()
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText("Select Dorado model directory...")
        self.model_path_edit.setReadOnly(True)
        model_path_layout.addWidget(self.model_path_edit)

        model_browse_btn = QPushButton("Browse...")
        model_browse_btn.clicked.connect(self.browse_model_dir)
        model_path_layout.addWidget(model_browse_btn)

        model_layout.addLayout(model_path_layout)
        layout.addWidget(model_group)

        demux_group = QGroupBox("Demultiplexing")
        demux_layout = QVBoxLayout(demux_group)
        demux_layout.addWidget(QLabel("Barcode Kit:"))
        self.demux_kit_combo = QComboBox()
        self.demux_kit_combo.addItems(DEMUX_KITS)
        demux_layout.addWidget(self.demux_kit_combo)
        layout.addWidget(demux_group)

        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)
        self.stacked_widget.addWidget(page)

    def create_filtering_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Filtering Options"))
        layout.addSpacing(20)

        preset_group = QGroupBox("Filter Presets")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(FILTER_PRESETS.keys())
        self.preset_combo.setCurrentText("Moderate")
        self.preset_combo.currentTextChanged.connect(self.apply_filter_preset)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        layout.addWidget(preset_group)

        filters_group = QGroupBox("Individual Filters")
        filters_layout = QGridLayout(filters_group)

        filters_layout.addWidget(QLabel("Min Dorado Q:"), 0, 0)
        self.min_dorado_q_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_dorado_q_slider.setRange(0, 20)
        self.min_dorado_q_slider.setValue(10)
        self.min_dorado_q_slider.valueChanged.connect(self.update_filter_labels)
        filters_layout.addWidget(self.min_dorado_q_slider, 0, 1)
        self.min_dorado_q_label = QLabel("10")
        filters_layout.addWidget(self.min_dorado_q_label, 0, 2)

        filters_layout.addWidget(QLabel("Min Mean Q:"), 1, 0)
        self.min_mean_q_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_mean_q_slider.setRange(0, 20)
        self.min_mean_q_slider.setValue(10)
        self.min_mean_q_slider.valueChanged.connect(self.update_filter_labels)
        filters_layout.addWidget(self.min_mean_q_slider, 1, 1)
        self.min_mean_q_label = QLabel("10")
        filters_layout.addWidget(self.min_mean_q_label, 1, 2)

        filters_layout.addWidget(QLabel("Min Length:"), 2, 0)
        self.min_len_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_len_slider.setRange(0, 1000)
        self.min_len_slider.setValue(200)
        self.min_len_slider.setSingleStep(50)
        self.min_len_slider.valueChanged.connect(self.update_filter_labels)
        filters_layout.addWidget(self.min_len_slider, 2, 1)
        self.min_len_label = QLabel("200")
        filters_layout.addWidget(self.min_len_label, 2, 2)

        filters_layout.addWidget(QLabel("Min Accuracy:"), 3, 0)
        self.min_acc_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_acc_slider.setRange(0, 100)
        self.min_acc_slider.setValue(85)
        self.min_acc_slider.valueChanged.connect(self.update_filter_labels)
        filters_layout.addWidget(self.min_acc_slider, 3, 1)
        self.min_acc_label = QLabel("0.85")
        filters_layout.addWidget(self.min_acc_label, 3, 2)

        layout.addWidget(filters_group)
        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.navigate_back_from_filtering)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(5))
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)
        self.stacked_widget.addWidget(page)

    def create_analysis_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Analysis Options"))
        layout.addSpacing(20)

        ref_group = QGroupBox("Reference Genome")
        ref_layout = QVBoxLayout(ref_group)
        ref_layout.addWidget(QLabel("Reference Genome Index (.mmi):"))

        ref_path_layout = QHBoxLayout()
        self.ref_genome_edit = QLineEdit()
        self.ref_genome_edit.setPlaceholderText("Select reference genome .mmi file...")
        self.ref_genome_edit.setReadOnly(True)
        ref_path_layout.addWidget(self.ref_genome_edit)

        ref_browse_btn = QPushButton("Browse...")
        ref_browse_btn.clicked.connect(self.browse_ref_genome)
        ref_path_layout.addWidget(ref_browse_btn)

        ref_layout.addLayout(ref_path_layout)
        layout.addWidget(ref_group)

        norm_group = QGroupBox("Normalization Cutoff")
        norm_layout = QVBoxLayout(norm_group)

        norm_slider_layout = QHBoxLayout()
        norm_slider_layout.addWidget(QLabel("Global Norm Cutoff:"))
        self.norm_cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.norm_cutoff_slider.setRange(0, 50)
        self.norm_cutoff_slider.setValue(10)
        self.norm_cutoff_slider.valueChanged.connect(self.update_norm_cutoff_label)
        norm_slider_layout.addWidget(self.norm_cutoff_slider)
        self.norm_cutoff_label = QLabel("0.10")
        norm_slider_layout.addWidget(self.norm_cutoff_label)

        norm_layout.addLayout(norm_slider_layout)
        norm_layout.addWidget(QLabel("Default threshold for filtering top alleles"))

        norm_layout.addSpacing(10)
        overrides_layout = QHBoxLayout()
        overrides_layout.addWidget(QLabel("Per-Locus Overrides (optional):"))
        self.overrides_path_edit = QLineEdit()
        self.overrides_path_edit.setPlaceholderText("Optional: path to overrides.tsv (locus<TAB>cutoff)")
        overrides_layout.addWidget(self.overrides_path_edit)

        overrides_browse_btn = QPushButton("Browse...")
        overrides_browse_btn.clicked.connect(self.browse_overrides_file)
        overrides_layout.addWidget(overrides_browse_btn)

        edit_overrides_btn = QPushButton("Edit Overrides...")
        edit_overrides_btn.setToolTip("Open table editor for per-locus thresholds")
        edit_overrides_btn.clicked.connect(self.open_overrides_editor)
        overrides_layout.addWidget(edit_overrides_btn)

        norm_layout.addLayout(overrides_layout)

        help_text = QLabel(
            "Overrides TSV format: <locus><TAB><cutoff>\n"
            "Example: DYS458<TAB>0.15"
        )
        help_text.setStyleSheet("color: #666666; font-size: 9pt;")
        norm_layout.addWidget(help_text)

        layout.addWidget(norm_group)

        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Review")
        next_btn.clicked.connect(self.go_to_review)
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)
        self.stacked_widget.addWidget(page)

    def create_review_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Review & Confirm"))
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
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(5))
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        run_btn = QPushButton("Start Workflow")
        run_btn.setObjectName("successButton")
        run_btn.setMinimumHeight(50)
        run_btn.clicked.connect(self.start_workflow_execution)
        nav_layout.addWidget(run_btn)

        layout.addLayout(nav_layout)
        self.stacked_widget.addWidget(page)

    def create_processing_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Processing"))
        layout.addSpacing(20)

        self.processing_status = QLabel("Initializing workflow...")
        self.processing_status.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
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
        self.stacked_widget.addWidget(page)

    def create_results_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(self.create_page_header("Results"))
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
        view_results_btn.clicked.connect(self.open_results_viewer)
        actions_layout.addWidget(view_results_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setMinimumHeight(50)
        open_folder_btn.clicked.connect(self.open_results_folder)
        actions_layout.addWidget(open_folder_btn)

        layout.addLayout(actions_layout)
        layout.addStretch()

        new_analysis_btn = QPushButton("Start New Analysis")
        new_analysis_btn.setObjectName("successButton")
        new_analysis_btn.clicked.connect(self.reset_workflow)
        layout.addWidget(new_analysis_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stacked_widget.addWidget(page)

    def browse_input_files(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Directory", os.path.expanduser("~"))
        if path:
            self.input_path_edit.setText(path)
            self.detect_files(path)

    def detect_files(self, path: str):
        self.file_type, self.detected_files = FileDetector.detect_file_type(path)

        if self.file_type == FileType.UNKNOWN:
            self.detection_label.setText("No supported files detected")
            self.detection_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
            self.file_count_label.setText("")
            self.next_from_files_btn.setEnabled(False)
            QMessageBox.warning(self, "Unknown File Type",
                              "No POD5, FASTQ, or BAM files found.")
        else:
            file_type_names = {
                FileType.POD5: "POD5 Files (Raw Signals)",
                FileType.FASTQ: "FASTQ Files (Basecalled)",
                FileType.BAM_ALIGNED: "BAM Files (Aligned)",
                FileType.BAM_UNALIGNED: "BAM Files (Unaligned)"
            }

            self.detection_label.setText(f"Detected: {file_type_names[self.file_type]}")
            self.detection_label.setStyleSheet("color: #388e3c; font-weight: bold;")
            self.file_count_label.setText(f"{len(self.detected_files)} files found")
            self.next_from_files_btn.setEnabled(True)

            self.workflow_manager = WorkflowManager(self.file_type)
            self.status_bar.showMessage(f"Ready: {len(self.detected_files)} files detected")

    def browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.path.expanduser("~"))
        if path:
            self.output_path_edit.setText(path)

    def from_experiment_to_options(self):
        if not self.exp_name_edit.text().strip():
            QMessageBox.warning(self, "Missing Info", "Please enter an experiment name.")
            return

        if not self.output_path_edit.text():
            QMessageBox.warning(self, "Missing Info", "Please select an output directory.")
            return

        self.update_workflow_summary()

        if self.workflow_manager.needs_basecalling():
            self.stacked_widget.setCurrentIndex(3)
        else:
            self.stacked_widget.setCurrentIndex(4)

    def update_workflow_summary(self):
        if not self.workflow_manager:
            return

        stages = []
        if self.workflow_manager.needs_basecalling():
            stages.extend(["Basecalling", "Demultiplexing"])
        if self.workflow_manager.needs_prepping():
            stages.append("Prepping (Alignment & Filtering)")
        stages.extend(["STR Analysis", "Results & Plotting"])

        summary = (
            f"<b>Detected Input:</b> {self.file_type.value.upper()}<br><br>"
            f"<b>Pipeline Stages:</b><br>"
            + "<br>".join([f"  {i+1}. {name}" for i, name in enumerate(stages)])
        )

        self.workflow_summary_label.setText(summary)

    def browse_model_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Dorado Model", os.path.expanduser("~"))
        if path:
            self.model_path_edit.setText(path)

    def apply_filter_preset(self, preset_name: str):
        if preset_name == "Custom":
            return

        preset = FILTER_PRESETS[preset_name]
        self.min_dorado_q_slider.setValue(int(preset['min_dorado_q']))
        self.min_mean_q_slider.setValue(int(preset['min_mean_q']))
        self.min_len_slider.setValue(preset['min_len'])
        self.min_acc_slider.setValue(int(preset['min_acc'] * 100))

    def update_filter_labels(self):
        self.min_dorado_q_label.setText(str(self.min_dorado_q_slider.value()))
        self.min_mean_q_label.setText(str(self.min_mean_q_slider.value()))
        self.min_len_label.setText(str(self.min_len_slider.value()))
        self.min_acc_label.setText(f"{self.min_acc_slider.value() / 100:.2f}")
        self.preset_combo.setCurrentText("Custom")

    def navigate_back_from_filtering(self):
        if self.workflow_manager.needs_basecalling():
            self.stacked_widget.setCurrentIndex(3)
        else:
            self.stacked_widget.setCurrentIndex(2)

    def browse_ref_genome(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Reference Genome (.mmi)",
            os.path.expanduser("~"),
            "Minimap2 Index (*.mmi);;All Files (*)"
        )
        if path:
            self.ref_genome_edit.setText(path)

    def browse_overrides_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Per-Locus Overrides TSV",
            self.script_dir,
            "TSV files (*.tsv *.txt);;All Files (*)"
        )
        if path:
            self.overrides_path_edit.setText(path)

    def open_overrides_editor(self):
        tsv_path = self.overrides_path_edit.text().strip()

        if not tsv_path:
            tsv_path, _ = QFileDialog.getSaveFileName(
                self,
                "Select or Create Overrides TSV",
                os.path.join(self.script_dir, "overrides.tsv"),
                "TSV files (*.tsv);;All Files (*)"
            )
            if not tsv_path:
                return

            if not os.path.exists(tsv_path):
                with open(tsv_path, 'w') as f:
                    f.write("# Per-locus Norm_cutoff overrides\n")
                    f.write("# Format: <locus><TAB><cutoff>\n")
                    f.write("# Example:\n")
                    f.write("# DYS458\t0.15\n")
                    f.write("# TPOX\t0.12\n")
                QMessageBox.information(
                    self,
                    "Template Created",
                    f"Created template file:\n{tsv_path}\n\n"
                    "Add your locus overrides in the editor."
                )

            self.overrides_path_edit.setText(tsv_path)

        if not os.path.isfile(tsv_path):
            QMessageBox.critical(self, "File Not Found",
                               f"Overrides file does not exist:\n{tsv_path}")
            return

        try:
            dlg = LociOverridesDialog(tsv_path, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open overrides editor:\n{e}")

    def update_norm_cutoff_label(self):
        value = self.norm_cutoff_slider.value() / 100
        self.norm_cutoff_label.setText(f"{value:.2f}")

    def prepare_workflow_params(self):
        self.workflow_params = {
            'file_type': self.file_type,
            'input_path': self.input_path_edit.text(),
            'exp_name': self.exp_name_edit.text(),
            'output_dir': self.output_path_edit.text(),
            'ref_genome': self.ref_genome_edit.text(),
            'min_dorado_q': self.min_dorado_q_slider.value(),
            'min_mean_q': self.min_mean_q_slider.value(),
            'min_len': self.min_len_slider.value(),
            'min_acc': self.min_acc_slider.value() / 100,
            'norm_cutoff': self.norm_cutoff_slider.value() / 100,
            'norm_cutoff_overrides': self.overrides_path_edit.text().strip(),
            'needs_prepping': self.workflow_manager.needs_prepping()
        }

        if self.workflow_manager.needs_basecalling():
            self.workflow_params['model_path'] = self.model_path_edit.text()
            self.workflow_params['demux_kit'] = self.demux_kit_combo.currentText()

        if self.file_type == FileType.FASTQ:
            self.workflow_params['input_type'] = 'fastq'
        else:
            self.workflow_params['input_type'] = 'bam'

    def go_to_review(self):
        self.prepare_workflow_params()
        self.populate_review()
        self.stacked_widget.setCurrentIndex(6)

    def populate_review(self):
        p = self.workflow_params

        review_text = f"""
<h2>Workflow Configuration</h2>

<h3>Input</h3>
<b>File Type:</b> {self.file_type.value.upper()}<br>
<b>Input Path:</b> {p['input_path']}<br>
<b>Files:</b> {len(self.detected_files)}<br>

<h3>Experiment</h3>
<b>Name:</b> {p['exp_name']}<br>
<b>Output:</b> {p['output_dir']}<br>

<h3>Reference</h3>
<b>Genome:</b> {p['ref_genome']}<br>
"""

        if self.workflow_manager.needs_basecalling():
            review_text += f"""
<h3>Basecalling</h3>
<b>Model:</b> {p['model_path']}<br>
<b>Demux Kit:</b> {p['demux_kit']}<br>
"""

        if self.workflow_manager.needs_prepping():
            review_text += f"""
<h3>Filtering</h3>
<b>Min Dorado Q:</b> {p['min_dorado_q']}<br>
<b>Min Mean Q:</b> {p['min_mean_q']}<br>
<b>Min Length:</b> {p['min_len']}<br>
<b>Min Accuracy:</b> {p['min_acc']:.2f}<br>
"""

        review_text += f"""
<h3>Analysis</h3>
<b>Norm Cutoff:</b> {p['norm_cutoff']:.2f}<br>
"""

        if p.get('norm_cutoff_overrides'):
            review_text += f"<b>Per-Locus Overrides:</b> {p['norm_cutoff_overrides']}<br>"

        self.review_text.setHtml(review_text)

    def start_workflow_execution(self):
        self.stacked_widget.setCurrentIndex(7)

        for icon_label, _ in self.stage_labels.values():
            icon_label.setText("...")

        self.worker_thread = QThread()
        self.worker = FullWorkflowWorker(self.workflow_params, self.script_dir)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_message.connect(self.append_processing_log)
        self.worker.stage_started.connect(self.on_stage_started)
        self.worker.stage_complete.connect(self.on_stage_complete)
        self.worker.finished.connect(self.on_workflow_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def on_stage_started(self, stage_name: str):
        self.processing_status.setText(f"Running: {stage_name}...")
        if stage_name in self.stage_labels:
            icon_label, _ = self.stage_labels[stage_name]
            icon_label.setText("[...]")

    def on_stage_complete(self, stage_name: str):
        if stage_name in self.stage_labels:
            icon_label, _ = self.stage_labels[stage_name]
            icon_label.setText("[OK]")

    def append_processing_log(self, message: str):
        self.processing_log.append(message)
        self.processing_log.verticalScrollBar().setValue(
            self.processing_log.verticalScrollBar().maximum()
        )

    def on_workflow_finished(self, return_code: int, results_dir: str):
        if return_code == 0:
            self.current_results_dir = results_dir
            self.results_info.setText(
                f"Analysis completed!\n\nResults: {results_dir}"
            )
            self.stacked_widget.setCurrentIndex(8)
            self.status_bar.showMessage("Workflow completed!")
        else:
            QMessageBox.critical(self, "Workflow Failed",
                               "Check the log for details.")
            self.status_bar.showMessage("Workflow failed")

    def open_results_viewer(self):
        if self.current_results_dir and os.path.exists(self.current_results_dir):
            viewer = ResultsViewerDialog(self.current_results_dir, self)
            viewer.exec()
        else:
            QMessageBox.warning(self, "No Results", "No results available.")

    def open_results_folder(self):
        if self.current_results_dir:
            parent_dir = os.path.dirname(self.current_results_dir)
            if sys.platform == 'linux':
                subprocess.Popen(['xdg-open', parent_dir])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', parent_dir])
            elif sys.platform == 'win32':
                subprocess.Popen(['explorer', parent_dir])

    def reset_workflow(self):
        self.workflow_params = {}
        self.current_results_dir = ""
        self.stacked_widget.setCurrentIndex(0)
        self.status_bar.showMessage("Ready for new analysis")

    def toggle_dark_mode(self, state):
        self.apply_theme(state == Qt.CheckState.Checked.value)

    def apply_theme(self, dark_mode: bool):
        app = QApplication.instance()
        app.setStyleSheet(DARK_STYLE if dark_mode else LIGHT_STYLE)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MaSTRspy")
    app.setApplicationVersion("P1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
