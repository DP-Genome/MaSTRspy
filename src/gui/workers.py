"""Background worker thread for running the full MaSTRspy workflow."""

import os
import subprocess
import tempfile
import time
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Signal

from src.core.config import generate_input_config
from src.core.file_detector import FileType
from src.core.logging_config import (
    LogBridge,
    close_logging,
    get_log_file_path,
    log_stage_separator,
    setup_logging,
    write_log_footer,
    write_log_header,
)
from src.core.validation import validate_pipeline_inputs
from src.pipeline.analysis import run_analysis, run_analysis_direct
from src.pipeline.prepping import run_prepping
from src.pipeline.workflow_plan import build_workflow_plan


class FullWorkflowWorker(QObject):
    log_message = Signal(str)
    stage_started = Signal(str)
    stage_complete = Signal(str)
    locus_progress = Signal(int, int)
    finished = Signal(int, str)

    def __init__(self, params: Dict[str, Any], project_dir: str):
        super().__init__()
        self.params = params
        self.project_dir = project_dir

    def run(self):
        start_time = time.time()
        success = False
        results_dir = ""
        logger = None

        try:
            p = self.params
            exp_output_dir = os.path.join(p["output_dir"], p["exp_name"])
            os.makedirs(exp_output_dir, exist_ok=True)

            # Set up structured logging: file + console + GUI
            log_file = get_log_file_path(exp_output_dir, p["exp_name"])
            logger = setup_logging(
                log_file=log_file,
                gui_callback=self.log_message.emit,
            )
            log = LogBridge(logger)

            write_log_header(logger, p, log_file=log_file)

            # (#13) Validate inputs before starting
            validation = validate_pipeline_inputs(p, log=log)
            if not validation.is_valid:
                for err in validation.errors:
                    log(f"[VALIDATION ERROR] {err}")
                write_log_footer(logger, start_time, success=False)
                close_logging(logger)
                self.finished.emit(1, "")
                return

            # (#10) Build workflow plan for visibility
            plan = build_workflow_plan(p, self.project_dir)
            log("--- Workflow Plan ---")
            for i, step in enumerate(plan.steps, 1):
                log(f"  {i}. {step.name}: {step.description}")
            log("--------------------")

            if p.get("file_type") == FileType.POD5:
                log_stage_separator(logger, "Basecalling")
                self.stage_started.emit("Basecalling")
                basecalled_bam = os.path.join(exp_output_dir, "1_basecalled.bam")

                cmd = ["dorado", "basecaller", p["model_path"], p["input_path"]]
                if not self._run_stage(cmd, basecalled_bam, log=log, is_basecaller=True):
                    write_log_footer(logger, start_time, success=False)
                    close_logging(logger)
                    self.finished.emit(1, "")
                    return
                self.stage_complete.emit("Basecalling")

                log_stage_separator(logger, "Demultiplexing")
                self.stage_started.emit("Demultiplexing")
                demux_dir = os.path.join(exp_output_dir, "2_demuxed")
                os.makedirs(demux_dir, exist_ok=True)

                if p.get("demux_kit") != "None":
                    cmd = [
                        "dorado",
                        "demux",
                        "--output-dir",
                        demux_dir,
                        "--kit-name",
                        p["demux_kit"],
                        basecalled_bam,
                    ]
                    if not self._run_stage(cmd, log=log):
                        write_log_footer(logger, start_time, success=False)
                        close_logging(logger)
                        self.finished.emit(1, "")
                        return
                else:
                    target = os.path.join(demux_dir, os.path.basename(basecalled_bam))
                    if not os.path.exists(target):
                        os.symlink(basecalled_bam, target)

                self.stage_complete.emit("Demultiplexing")
                input_for_prepping = demux_dir
            else:
                input_for_prepping = p["input_path"]

            if p.get("needs_prepping", True):
                log_stage_separator(logger, "Prepping")
                self.stage_started.emit("Prepping")
                prepped_dir = os.path.join(exp_output_dir, "3_prepped")
                os.makedirs(prepped_dir, exist_ok=True)

                prep_params = {
                    "input_dir": input_for_prepping,
                    "output_dir": prepped_dir,
                    "ref_genome": p["ref_genome"],
                    "exp_name": p["exp_name"],
                    "input_type": p.get("input_type", "bam"),
                    "num_threads": p.get("num_threads", 16),  # (#4)
                    "min_dorado_q": p.get("min_dorado_q", 0),
                    "min_mean_q": p.get("min_mean_q", 0),
                    "min_len": p.get("min_len", 0),
                    "min_acc": p.get("min_acc", 0),
                }

                reports = run_prepping(prep_params, log=log)
                # (#8) Log QC summary from filter reports
                if reports:
                    log(f"[QC] {len(reports)} samples prepped")

                self.stage_complete.emit("Prepping")
                input_for_analysis = prepped_dir
            else:
                input_for_analysis = input_for_prepping

            log_stage_separator(logger, "Analysis")
            self.stage_started.emit("Analysis")
            analysis_dir = os.path.join(exp_output_dir, "4_analysis")

            # (#9) Use run_analysis_direct when possible
            master_config = os.path.join(self.project_dir, "config", "InputConfig.txt")
            tools_config = os.path.join(self.project_dir, "config", "ToolsConfig.txt")

            input_config_content = generate_input_config(
                input_for_analysis, analysis_dir, p, master_config
            )

            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt"
            ) as f:
                f.write(input_config_content)
                input_config_path = f.name

            try:
                results_dir = run_analysis(
                    input_config_path,
                    tools_config,
                    log=log,
                    progress_callback=lambda done, total: self.locus_progress.emit(done, total),
                )
            finally:
                os.remove(input_config_path)

            self.stage_complete.emit("Analysis")
            success = True
            write_log_footer(logger, start_time, success=True, results_dir=results_dir)
            close_logging(logger)
            self.finished.emit(0, results_dir)

        except Exception as e:
            self.log_message.emit(f"\n[ERROR] Workflow failed: {e}\n")
            if logger:
                write_log_footer(logger, start_time, success=False)
                close_logging(logger)
            self.finished.emit(1, "")

    def _run_stage(
        self,
        command: List[str],
        output_file: str = None,
        log: Any = None,
        is_basecaller: bool = False,
    ) -> bool:
        """Run an external command stage (basecalling/demux only)."""
        _log = log or self.log_message.emit
        try:
            log_cmd = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
            _log(f"[CMD] {log_cmd}\n")

            if is_basecaller:
                with open(output_file, "wb") as f_out:
                    process = subprocess.Popen(
                        command,
                        stdout=f_out,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    for line in iter(process.stderr.readline, ""):
                        _log(line.rstrip())
                    return_code = process.wait()
            else:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in iter(process.stdout.readline, ""):
                    _log(line.rstrip())
                process.stdout.close()
                return_code = process.wait()

            return return_code == 0

        except Exception as e:
            _log(f"\n[ERROR] Stage failed: {e}\n")
            return False
