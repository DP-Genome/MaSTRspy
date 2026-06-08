"""Analysis options page (reference genome, norm cutoff, overrides)."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.config import compute_thread_split
from src.gui.dialogs.overrides_editor import LociOverridesDialog
from src.gui.logo import LogoManager
from src.gui.page_utils import create_page_header


class AnalysisOptionsPage(QWidget):
    next_clicked = Signal()
    back_clicked = Signal()

    def __init__(self, logo_manager: LogoManager, project_dir: str, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(create_page_header(logo_manager, "Analysis Options"))
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
        ref_browse_btn.clicked.connect(self._browse_ref_genome)
        ref_path_layout.addWidget(ref_browse_btn)

        ref_layout.addLayout(ref_path_layout)
        layout.addWidget(ref_group)

        db_group = QGroupBox("STR Database")
        db_layout = QVBoxLayout(db_group)

        db_select_layout = QHBoxLayout()
        db_select_layout.addWidget(QLabel("Database:"))
        self.db_combo = QComboBox()
        self.db_combo.addItems(["RefSeq", "UCSC"])
        db_select_layout.addWidget(self.db_combo)
        db_select_layout.addStretch()
        db_layout.addLayout(db_select_layout)

        db_help = QLabel(
            "Select the STR database for analysis. "
            "RefSeq and UCSC use different coordinate systems."
        )
        db_help.setObjectName("helpText")
        db_layout.addWidget(db_help)

        layout.addWidget(db_group)

        norm_group = QGroupBox("Normalization Cutoff")
        norm_layout = QVBoxLayout(norm_group)

        norm_slider_layout = QHBoxLayout()
        norm_slider_layout.addWidget(QLabel("Global Norm Cutoff:"))
        self.norm_cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.norm_cutoff_slider.setRange(0, 50)
        self.norm_cutoff_slider.setValue(10)
        self.norm_cutoff_slider.valueChanged.connect(self._update_norm_cutoff_label)
        norm_slider_layout.addWidget(self.norm_cutoff_slider)
        self.norm_cutoff_label = QLabel("0.10")
        norm_slider_layout.addWidget(self.norm_cutoff_label)

        norm_layout.addLayout(norm_slider_layout)
        norm_layout.addWidget(QLabel("Default threshold for filtering top alleles"))

        norm_layout.addSpacing(10)
        overrides_layout = QHBoxLayout()
        overrides_layout.addWidget(QLabel("Per-Locus Overrides (optional):"))
        self.overrides_path_edit = QLineEdit()
        self.overrides_path_edit.setPlaceholderText(
            "Optional: path to overrides.tsv (locus<TAB>cutoff)"
        )
        overrides_layout.addWidget(self.overrides_path_edit)

        overrides_browse_btn = QPushButton("Browse...")
        overrides_browse_btn.clicked.connect(self._browse_overrides_file)
        overrides_layout.addWidget(overrides_browse_btn)

        edit_overrides_btn = QPushButton("Edit Overrides...")
        edit_overrides_btn.setToolTip("Open table editor for per-locus thresholds")
        edit_overrides_btn.clicked.connect(self._open_overrides_editor)
        overrides_layout.addWidget(edit_overrides_btn)

        norm_layout.addLayout(overrides_layout)

        help_text = QLabel(
            "Overrides TSV format: <locus><TAB><cutoff>\n" "Example: DYS458<TAB>0.15"
        )
        help_text.setObjectName("helpText")
        norm_layout.addWidget(help_text)

        layout.addWidget(norm_group)

        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout(perf_group)

        threads_layout = QHBoxLayout()
        threads_layout.addWidget(QLabel("Total Threads:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(2, 256)
        self.threads_spin.setValue(os.cpu_count() or 16)
        self.threads_spin.valueChanged.connect(self._update_thread_split_label)
        threads_layout.addWidget(self.threads_spin)

        self.thread_split_label = QLabel()
        threads_layout.addWidget(self.thread_split_label)
        threads_layout.addStretch()

        perf_layout.addLayout(threads_layout)

        thread_help = QLabel("Controls parallelism for the analysis stage")
        thread_help.setObjectName("helpText")
        perf_layout.addWidget(thread_help)

        perf_layout.addSpacing(10)
        self.snv_checkbox = QCheckBox("Enable SNV calling (freebayes)")
        self.snv_checkbox.setChecked(False)
        self.snv_checkbox.setToolTip(
            "Run freebayes to call SNVs within STR regions. "
            "Does not affect STR genotyping results."
        )
        perf_layout.addWidget(self.snv_checkbox)

        snv_help = QLabel(
            "Optional: calls SNVs per locus. Does not affect STR genotyping."
        )
        snv_help.setObjectName("helpText")
        perf_layout.addWidget(snv_help)

        layout.addWidget(perf_group)
        self._update_thread_split_label()

        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Review")
        next_btn.clicked.connect(self.next_clicked.emit)
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)

    def _browse_ref_genome(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Genome (.mmi)",
            os.path.expanduser("~"),
            "Minimap2 Index (*.mmi);;All Files (*)",
        )
        if path:
            self.ref_genome_edit.setText(path)

    def _browse_overrides_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Per-Locus Overrides TSV",
            self.project_dir,
            "TSV files (*.tsv *.txt);;All Files (*)",
        )
        if path:
            self.overrides_path_edit.setText(path)

    def _open_overrides_editor(self):
        tsv_path = self.overrides_path_edit.text().strip()

        if not tsv_path:
            tsv_path, _ = QFileDialog.getSaveFileName(
                self,
                "Select or Create Overrides TSV",
                os.path.join(self.project_dir, "overrides.tsv"),
                "TSV files (*.tsv);;All Files (*)",
            )
            if not tsv_path:
                return

            if not os.path.exists(tsv_path):
                with open(tsv_path, "w") as f:
                    f.write("# Per-locus Norm_cutoff overrides\n")
                    f.write("# Format: <locus><TAB><cutoff>\n")
                    f.write("# Example:\n")
                    f.write("# DYS458\t0.15\n")
                    f.write("# TPOX\t0.12\n")
                QMessageBox.information(
                    self,
                    "Template Created",
                    f"Created template file:\n{tsv_path}\n\n"
                    "Add your locus overrides in the editor.",
                )

            self.overrides_path_edit.setText(tsv_path)

        if not os.path.isfile(tsv_path):
            QMessageBox.critical(
                self,
                "File Not Found",
                f"Overrides file does not exist:\n{tsv_path}",
            )
            return

        try:
            dlg = LociOverridesDialog(tsv_path, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not open overrides editor:\n{e}"
            )

    def _update_norm_cutoff_label(self):
        value = self.norm_cutoff_slider.value() / 100
        self.norm_cutoff_label.setText(f"{value:.2f}")

    def get_ref_genome(self) -> str:
        return self.ref_genome_edit.text()

    def get_norm_cutoff(self) -> float:
        return self.norm_cutoff_slider.value() / 100

    def get_overrides_path(self) -> str:
        return self.overrides_path_edit.text().strip()

    def get_num_threads(self) -> int:
        return self.threads_spin.value()

    def get_enable_snv(self) -> bool:
        return self.snv_checkbox.isChecked()

    def _get_db_base_dir(self) -> str:
        """Return the base directory for the selected database."""
        db_name = self.db_combo.currentText()
        if db_name == "RefSeq":
            return os.path.join(
                self.project_dir,
                "MaSTR_Database",
                "Database",
                "RefSeq",
                "RefSeq_MaSTR_DatabaseV5",
            )
        else:
            return os.path.join(
                self.project_dir,
                "MaSTR_Database",
                "Database",
                "UCSC",
                "UCSC_MaSTR_DatabaseV5",
            )

    def get_str_fasta(self) -> str:
        return os.path.join(self._get_db_base_dir(), "Database")

    def get_str_bed(self) -> str:
        return os.path.join(self._get_db_base_dir(), "Database")

    def get_region_bed(self) -> str:
        return os.path.join(self._get_db_base_dir(), "DBv5.bed")

    def get_database_name(self) -> str:
        return self.db_combo.currentText()

    def _update_thread_split_label(self):
        total = self.threads_spin.value()
        jobs, tpj = compute_thread_split(total)
        self.thread_split_label.setText(f"\u2192 {jobs} jobs \u00d7 {tpj} threads each")
