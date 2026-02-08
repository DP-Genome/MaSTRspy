"""Main window shell that wires all pages together."""

import os
import subprocess
import sys
from typing import List, Optional

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
)

from src.core.config import compute_thread_split
from src.core.file_detector import FileType
from src.core.workflow import WorkflowManager
from src.gui.dialogs.results_viewer import ResultsViewerDialog
from src.gui.logo import LogoManager
from src.gui.pages.analysis_options import AnalysisOptionsPage
from src.gui.pages.basecalling import BasecallingPage
from src.gui.pages.experiment import ExperimentPage
from src.gui.pages.file_selection import FileSelectionPage
from src.gui.pages.filtering import FilteringPage
from src.gui.pages.processing import ProcessingPage
from src.gui.pages.results import ResultsPage
from src.gui.pages.review import ReviewPage
from src.gui.pages.welcome import WelcomePage
from src.gui.styles import DARK_STYLE, LIGHT_STYLE
from src.gui.workers import FullWorkflowWorker


class MainWindow(QMainWindow):
    # Page indices
    PAGE_WELCOME = 0
    PAGE_FILE_SELECTION = 1
    PAGE_EXPERIMENT = 2
    PAGE_BASECALLING = 3
    PAGE_FILTERING = 4
    PAGE_ANALYSIS = 5
    PAGE_REVIEW = 6
    PAGE_PROCESSING = 7
    PAGE_RESULTS = 8

    def __init__(self):
        super().__init__()

        self.project_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.logo_manager = LogoManager(self.project_dir)
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

        self._create_all_pages()
        self._connect_signals()
        self.apply_theme(False)

    def _create_all_pages(self):
        self.welcome_page = WelcomePage(self.logo_manager)
        self.stacked_widget.addWidget(self.welcome_page)  # 0

        self.file_selection_page = FileSelectionPage(self.logo_manager)
        self.stacked_widget.addWidget(self.file_selection_page)  # 1

        self.experiment_page = ExperimentPage(self.logo_manager)
        self.stacked_widget.addWidget(self.experiment_page)  # 2

        self.basecalling_page = BasecallingPage(self.logo_manager)
        self.stacked_widget.addWidget(self.basecalling_page)  # 3

        self.filtering_page = FilteringPage(self.logo_manager)
        self.stacked_widget.addWidget(self.filtering_page)  # 4

        self.analysis_page = AnalysisOptionsPage(self.logo_manager, self.project_dir)
        self.stacked_widget.addWidget(self.analysis_page)  # 5

        self.review_page = ReviewPage(self.logo_manager)
        self.stacked_widget.addWidget(self.review_page)  # 6

        self.processing_page = ProcessingPage(self.logo_manager)
        self.stacked_widget.addWidget(self.processing_page)  # 7

        self.results_page = ResultsPage(self.logo_manager)
        self.stacked_widget.addWidget(self.results_page)  # 8

    def _connect_signals(self):
        # Welcome
        self.welcome_page.next_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_FILE_SELECTION)
        )
        self.welcome_page.dark_mode_changed.connect(self.apply_theme)

        # File Selection
        self.file_selection_page.back_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_WELCOME)
        )
        self.file_selection_page.next_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_EXPERIMENT)
        )
        self.file_selection_page.files_detected.connect(self._on_files_detected)

        # Experiment
        self.experiment_page.back_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_FILE_SELECTION)
        )
        self.experiment_page.next_clicked.connect(self._from_experiment_to_options)

        # Basecalling
        self.basecalling_page.back_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_EXPERIMENT)
        )
        self.basecalling_page.next_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_FILTERING)
        )

        # Filtering
        self.filtering_page.back_clicked.connect(self._navigate_back_from_filtering)
        self.filtering_page.next_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_ANALYSIS)
        )

        # Analysis Options
        self.analysis_page.back_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_FILTERING)
        )
        self.analysis_page.next_clicked.connect(self._go_to_review)

        # Review
        self.review_page.back_clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self.PAGE_ANALYSIS)
        )
        self.review_page.start_clicked.connect(self._start_workflow_execution)

        # Results
        self.results_page.view_results_clicked.connect(self._open_results_viewer)
        self.results_page.open_folder_clicked.connect(self._open_results_folder)
        self.results_page.new_analysis_clicked.connect(self._reset_workflow)

    def _on_files_detected(self, file_type: FileType, files: list):
        self.file_type = file_type
        self.detected_files = files
        self.workflow_manager = WorkflowManager(file_type)
        self.status_bar.showMessage(f"Ready: {len(files)} files detected")

    def _from_experiment_to_options(self):
        self._update_workflow_summary()
        if self.workflow_manager and self.workflow_manager.needs_basecalling():
            self.stacked_widget.setCurrentIndex(self.PAGE_BASECALLING)
        else:
            self.stacked_widget.setCurrentIndex(self.PAGE_FILTERING)

    def _update_workflow_summary(self):
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
            + "<br>".join([f"  {i + 1}. {name}" for i, name in enumerate(stages)])
        )
        self.experiment_page.set_workflow_summary(summary)

    def _navigate_back_from_filtering(self):
        if self.workflow_manager and self.workflow_manager.needs_basecalling():
            self.stacked_widget.setCurrentIndex(self.PAGE_BASECALLING)
        else:
            self.stacked_widget.setCurrentIndex(self.PAGE_EXPERIMENT)

    def _prepare_workflow_params(self):
        self.workflow_params = {
            "file_type": self.file_type,
            "input_path": self.file_selection_page.get_input_path(),
            "exp_name": self.experiment_page.get_exp_name(),
            "output_dir": self.experiment_page.get_output_dir(),
            "ref_genome": self.analysis_page.get_ref_genome(),
            "min_dorado_q": self.filtering_page.get_min_dorado_q(),
            "min_mean_q": self.filtering_page.get_min_mean_q(),
            "min_len": self.filtering_page.get_min_len(),
            "min_acc": self.filtering_page.get_min_acc(),
            "norm_cutoff": self.analysis_page.get_norm_cutoff(),
            "norm_cutoff_overrides": self.analysis_page.get_overrides_path(),
            "num_threads": self.analysis_page.get_num_threads(),
            "enable_snv": self.analysis_page.get_enable_snv(),
            "needs_prepping": (
                self.workflow_manager.needs_prepping()
                if self.workflow_manager
                else True
            ),
        }

        if self.workflow_manager and self.workflow_manager.needs_basecalling():
            self.workflow_params["model_path"] = self.basecalling_page.get_model_path()
            self.workflow_params["demux_kit"] = self.basecalling_page.get_demux_kit()

        if self.file_type == FileType.FASTQ:
            self.workflow_params["input_type"] = "fastq"
        else:
            self.workflow_params["input_type"] = "bam"

    def _go_to_review(self):
        self._prepare_workflow_params()
        self._populate_review()
        self.stacked_widget.setCurrentIndex(self.PAGE_REVIEW)

    def _populate_review(self):
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

        if self.workflow_manager and self.workflow_manager.needs_basecalling():
            review_text += f"""
<h3>Basecalling</h3>
<b>Model:</b> {p['model_path']}<br>
<b>Demux Kit:</b> {p['demux_kit']}<br>
"""

        if self.workflow_manager and self.workflow_manager.needs_prepping():
            review_text += f"""
<h3>Filtering</h3>
<b>Min Dorado Q:</b> {p['min_dorado_q']}<br>
<b>Min Mean Q:</b> {p['min_mean_q']}<br>
<b>Min Length:</b> {p['min_len']}<br>
<b>Min Accuracy:</b> {p['min_acc']:.2f}<br>
"""

        snv_status = "Enabled" if p.get("enable_snv") else "Disabled"
        review_text += f"""
<h3>Analysis</h3>
<b>Norm Cutoff:</b> {p['norm_cutoff']:.2f}<br>
<b>SNV Calling (xatlas):</b> {snv_status}<br>
"""

        if p.get("norm_cutoff_overrides"):
            review_text += (
                f"<b>Per-Locus Overrides:</b> " f"{p['norm_cutoff_overrides']}<br>"
            )

        total_threads = p.get("num_threads", 16)
        jobs, tpj = compute_thread_split(total_threads)
        review_text += f"""
<h3>Performance</h3>
<b>Total Threads:</b> {total_threads}<br>
<b>Parallel Jobs:</b> {jobs}<br>
<b>Threads per Job:</b> {tpj}<br>
"""

        self.review_page.set_review_html(review_text)

    def _start_workflow_execution(self):
        self.stacked_widget.setCurrentIndex(self.PAGE_PROCESSING)
        self.processing_page.reset_stages()

        self.worker_thread = QThread()
        self.worker = FullWorkflowWorker(self.workflow_params, self.project_dir)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_message.connect(self.processing_page.append_log)
        self.worker.stage_started.connect(self.processing_page.on_stage_started)
        self.worker.stage_complete.connect(self.processing_page.on_stage_complete)
        self.worker.finished.connect(self._on_workflow_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def _on_workflow_finished(self, return_code: int, results_dir: str):
        if return_code == 0:
            self.current_results_dir = results_dir
            self.results_page.set_results_info(
                f"Analysis completed!\n\nResults: {results_dir}"
            )
            self.stacked_widget.setCurrentIndex(self.PAGE_RESULTS)
            self.status_bar.showMessage("Workflow completed!")
        else:
            QMessageBox.critical(self, "Workflow Failed", "Check the log for details.")
            self.status_bar.showMessage("Workflow failed")

    def _open_results_viewer(self):
        if self.current_results_dir and os.path.exists(self.current_results_dir):
            viewer = ResultsViewerDialog(self.current_results_dir, self)
            viewer.exec()
        else:
            QMessageBox.warning(self, "No Results", "No results available.")

    def _open_results_folder(self):
        if self.current_results_dir:
            parent_dir = os.path.dirname(self.current_results_dir)
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", parent_dir])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", parent_dir])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", parent_dir])

    def _reset_workflow(self):
        self.workflow_params = {}
        self.current_results_dir = ""
        self.stacked_widget.setCurrentIndex(self.PAGE_WELCOME)
        self.status_bar.showMessage("Ready for new analysis")

    def apply_theme(self, dark_mode: bool):
        app = QApplication.instance()
        app.setStyleSheet(DARK_STYLE if dark_mode else LIGHT_STYLE)
