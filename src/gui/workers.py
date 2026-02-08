"""Background worker thread for running the full MaSTRspy workflow."""

import os
import subprocess
import tempfile
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Signal

from src.core.config import generate_input_config
from src.core.file_detector import FileType
from src.pipeline.analysis import run_analysis
from src.pipeline.prepping import run_prepping


class FullWorkflowWorker(QObject):
    log_message = Signal(str)
    stage_started = Signal(str)
    stage_complete = Signal(str)
    finished = Signal(int, str)

    def __init__(self, params: Dict[str, Any], project_dir: str):
        super().__init__()
        self.params = params
        self.project_dir = project_dir

    def run(self):
        try:
            p = self.params
            exp_output_dir = os.path.join(p["output_dir"], p["exp_name"])
            os.makedirs(exp_output_dir, exist_ok=True)

            if p.get("file_type") == FileType.POD5:
                self.stage_started.emit("Basecalling")
                basecalled_bam = os.path.join(exp_output_dir, "1_basecalled.bam")

                cmd = ["dorado", "basecaller", p["model_path"], p["input_path"]]
                if not self._run_stage(cmd, basecalled_bam, is_basecaller=True):
                    self.finished.emit(1, "")
                    return
                self.stage_complete.emit("Basecalling")

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
                input_for_prepping = p["input_path"]

            if p.get("needs_prepping", True):
                self.stage_started.emit("Prepping")
                prepped_dir = os.path.join(exp_output_dir, "3_prepped")
                os.makedirs(prepped_dir, exist_ok=True)

                prep_params = {
                    "input_dir": input_for_prepping,
                    "output_dir": prepped_dir,
                    "ref_genome": p["ref_genome"],
                    "exp_name": p["exp_name"],
                    "input_type": p.get("input_type", "bam"),
                    "min_dorado_q": p.get("min_dorado_q", 0),
                    "min_mean_q": p.get("min_mean_q", 0),
                    "min_len": p.get("min_len", 0),
                    "min_acc": p.get("min_acc", 0),
                }

                run_prepping(prep_params, log=self.log_message.emit)

                self.stage_complete.emit("Prepping")
                input_for_analysis = prepped_dir
            else:
                input_for_analysis = input_for_prepping

            self.stage_started.emit("Analysis")
            analysis_dir = os.path.join(exp_output_dir, "4_analysis")

            master_config = os.path.join(self.project_dir, "config", "InputConfig.txt")
            input_config_content = generate_input_config(
                input_for_analysis, analysis_dir, p, master_config
            )

            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt"
            ) as f:
                f.write(input_config_content)
                input_config_path = f.name

            tools_config = os.path.join(self.project_dir, "config", "ToolsConfig.txt")

            try:
                results_dir = run_analysis(
                    input_config_path,
                    tools_config,
                    log=self.log_message.emit,
                )
            finally:
                os.remove(input_config_path)

            self.stage_complete.emit("Analysis")
            self.finished.emit(0, results_dir)

        except Exception as e:
            self.log_message.emit(f"\n[ERROR] Workflow failed: {e}\n")
            self.finished.emit(1, "")

    def _run_stage(
        self,
        command: List[str],
        output_file: str = None,
        is_basecaller: bool = False,
    ) -> bool:
        """Run an external command stage (basecalling/demux only)."""
        try:
            log_cmd = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
            self.log_message.emit(f"[CMD] {log_cmd}\n")

            if is_basecaller:
                with open(output_file, "wb") as f_out:
                    process = subprocess.Popen(
                        command,
                        stdout=f_out,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    for line in iter(process.stderr.readline, ""):
                        self.log_message.emit(line.rstrip())
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
                    self.log_message.emit(line.rstrip())
                process.stdout.close()
                return_code = process.wait()

            return return_code == 0

        except Exception as e:
            self.log_message.emit(f"\n[ERROR] Stage failed: {e}\n")
            return False
