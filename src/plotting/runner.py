"""Run R plotting scripts for STR profile visualization."""

import os
import subprocess
from pathlib import Path
from typing import Callable


def run_r_plots(
    summaries_dir: str,
    r_script_path: str,
    logo_path: str,
    log: Callable[[str], None] = print,
) -> None:
    """Run the R plotting script for each barcode summary file.

    Args:
        summaries_dir: directory containing barcode*_summary.tsv files
        r_script_path: path to STR_Profile_Plots_P1.0.R
        logo_path: path to logo.jpg for watermarking
    """
    log("--- Starting R script for each barcode summary ---")

    plots_dir = os.path.join(summaries_dir, "Plots")
    os.makedirs(plots_dir, exist_ok=True)

    if not os.path.isfile(r_script_path):
        log(f"Warning: R script '{r_script_path}' not found. Skipping.")
        return

    summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))

    for summary_file in summary_files:
        if summary_file.stat().st_size == 0:
            continue

        log(f"Running R analysis on: {summary_file.name}")

        output_name = summary_file.name.replace("_summary.tsv", "")
        output_plot = os.path.join(plots_dir, f"{output_name}_plot.png")

        cmd = ["Rscript", r_script_path, str(summary_file), output_plot]
        if os.path.isfile(logo_path):
            cmd.append(logo_path)

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            log(f"[WARNING] R script failed for {summary_file.name}: {e.stderr}")
        except FileNotFoundError:
            log("[WARNING] Rscript not found. Skipping plot generation.")
            return

    log("--- R analysis complete for all barcodes. ---")
