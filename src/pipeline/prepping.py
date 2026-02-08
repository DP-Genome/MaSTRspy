"""Prepping pipeline: alignment + filtering for BAM/FASTQ inputs.

Replaces MaSTR_Prepping_P1.0.sh.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict

from src.filters.bam_accuracy import filter_bam_by_accuracy
from src.filters.dorado_qs import filter_bam_by_qs, filter_fastq_by_qs
from src.filters.fastq_quality import filter_fastq


def _extract_barcode_name(sample_name: str, log: Callable[[str], None]) -> str:
    """Extract standardized barcode name from a filename stem.

    Handles patterns like: barcode12, barcode_12, BC12, bc_12, _12, unclassified.
    Falls back to the original sample_name if no barcode pattern is found.
    """
    # Pattern 1: barcodeXX or barcode_XX
    m = re.search(r"barcode[_]?(\d{1,2})", sample_name, re.IGNORECASE)
    if m:
        return f"barcode{int(m.group(1)):02d}"

    # Pattern 2: BCXX or BC_XX
    m = re.search(r"[Bb][Cc][_]?(\d{1,2})", sample_name)
    if m:
        return f"barcode{int(m.group(1)):02d}"

    # Pattern 3: trailing _XX (1-96)
    m = re.search(r"_(\d{1,2})$", sample_name)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 96:
            return f"barcode{num:02d}"

    # Pattern 4: unclassified
    if "unclassified" in sample_name.lower():
        return "unclassified"

    log(
        f"[WARNING] Could not detect barcode number in '{sample_name}'. "
        "Using original filename as identifier."
    )
    return sample_name


def run_prepping(params: Dict[str, Any], log: Callable[[str], None] = print) -> None:
    """Run the full prepping pipeline on all input files.

    params keys:
        input_dir (str): directory containing input BAM/FASTQ files
        output_dir (str): directory for prepped output files
        ref_genome (str): path to reference genome index (.mmi)
        exp_name (str): experiment name prefix
        input_type (str): 'bam' or 'fastq'
        min_dorado_q (float): minimum Dorado qs tag score (0 = skip)
        min_mean_q (float): minimum mean quality score (0 = skip)
        min_len (int): minimum read length (0 = skip)
        min_acc (float): minimum alignment accuracy (0 = skip)
    """
    input_dir = params["input_dir"]
    output_dir = params["output_dir"]
    ref_genome = params["ref_genome"]
    input_type = params.get("input_type", "bam")
    min_dorado_q = float(params.get("min_dorado_q", 0))
    min_mean_q = float(params.get("min_mean_q", 0))
    min_len = int(params.get("min_len", 0))
    min_acc = float(params.get("min_acc", 0))

    os.makedirs(output_dir, exist_ok=True)

    log("========================================")
    log("MaSTR_Prepping P1.0 Started")
    log("========================================")
    log(f"Input directory: {input_dir}")
    log(f"Output directory: {output_dir}")
    log(f"Reference genome: {ref_genome}")
    log(f"Input type: {input_type}")
    log("----------------------------------------")
    log("Filtering parameters:")
    log(f"  Min Dorado qs tag: {min_dorado_q}")
    log(f"  Min mean quality: {min_mean_q}")
    log(f"  Min read length: {min_len}")
    log(f"  Min accuracy: {min_acc}")
    log("========================================")

    # Find input files
    input_path = Path(input_dir)
    if input_type == "bam":
        input_files = sorted(input_path.glob("*.bam"))
    else:
        input_files = sorted(
            list(input_path.glob("*.fastq")) + list(input_path.glob("*.fq"))
        )

    if not input_files:
        log(f"[ERROR] No {input_type} files found in {input_dir}")
        return

    for input_file in input_files:
        file_basename = input_file.name

        # Extract sample name (remove extension)
        if input_type == "bam":
            sample_name = input_file.stem
        else:
            sample_name = file_basename
            for ext in [".fastq", ".fq"]:
                if sample_name.endswith(ext):
                    sample_name = sample_name[: -len(ext)]
                    break

        barcode_name = _extract_barcode_name(sample_name, log)

        log("")
        log(f"--- Processing: {file_basename} -> {barcode_name} ---")

        qs_filtered_bam = os.path.join(output_dir, f"{barcode_name}_qs_filtered.bam")
        aligned_bam = os.path.join(output_dir, f"{barcode_name}_aligned.bam")
        final_bam = os.path.join(output_dir, f"{barcode_name}_prepped.bam")

        current_input = str(input_file)

        # STAGE 0: Dorado qs Tag Filter (BAM only)
        if input_type == "bam" and min_dorado_q > 0:
            log(f"[INFO] Applying Dorado qs tag filter (min-dorado-q={min_dorado_q})")
            filter_bam_by_qs(current_input, qs_filtered_bam, min_dorado_q, log)
            current_input = qs_filtered_bam

        apply_pre_filter = min_mean_q > 0 or min_len > 0

        if input_type == "bam":
            _process_bam_input(
                current_input,
                aligned_bam,
                ref_genome,
                min_dorado_q,
                min_mean_q,
                min_len,
                apply_pre_filter,
                output_dir,
                log,
            )
        else:
            _process_fastq_input(
                str(input_file),
                aligned_bam,
                ref_genome,
                min_dorado_q,
                min_mean_q,
                min_len,
                apply_pre_filter,
                output_dir,
                log,
            )

        # Clean up intermediate qs-filtered BAM
        if os.path.exists(qs_filtered_bam):
            os.remove(qs_filtered_bam)

        # Post-alignment accuracy filter
        if min_acc > 0:
            log(f"[INFO] Applying post-alignment accuracy filter (min-acc={min_acc})")
            filter_bam_by_accuracy(aligned_bam, final_bam, min_acc, log)
            os.remove(aligned_bam)
        else:
            log("[INFO] No post-alignment filtering")
            os.rename(aligned_bam, final_bam)

        # Index the final BAM
        subprocess.run(["samtools", "index", final_bam], check=True)
        log(f"--- Completed: {final_bam} ---")

    log("")
    log("========================================")
    log("MaSTR_Prepping P1.0 Finished")
    log(f"Prepped files are in: {output_dir}")
    log("========================================")


def _process_bam_input(
    current_input: str,
    aligned_bam: str,
    ref_genome: str,
    min_dorado_q: float,
    min_mean_q: float,
    min_len: int,
    apply_pre_filter: bool,
    output_dir: str,
    log: Callable[[str], None],
) -> None:
    """Process BAM input: convert to FASTQ, optionally filter, align, sort."""
    if apply_pre_filter:
        log(
            f"[INFO] Applying pre-alignment filters "
            f"(min-mean-q={min_mean_q}, min-len={min_len})"
        )
        # BAM -> FASTQ -> filter -> align -> sort
        with (
            tempfile.NamedTemporaryFile(
                suffix=".fastq", dir=output_dir, delete=False
            ) as tmp_fq,
            tempfile.NamedTemporaryFile(
                suffix=".fastq", dir=output_dir, delete=False
            ) as tmp_filtered,
        ):
            tmp_fq_path = tmp_fq.name
            tmp_filtered_path = tmp_filtered.name

        try:
            # samtools fastq
            with open(tmp_fq_path, "w") as fq_out:
                subprocess.run(
                    ["samtools", "fastq", "-@4", current_input],
                    stdout=fq_out,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            # fastq filter
            filter_fastq(tmp_fq_path, tmp_filtered_path, min_mean_q, min_len, log)
            # minimap2 | samtools sort
            minimap_proc = subprocess.Popen(
                [
                    "minimap2",
                    "-ax",
                    "map-ont",
                    "--MD",
                    "-t",
                    "32",
                    ref_genome,
                    tmp_filtered_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["samtools", "sort", "-@4", "-o", aligned_bam, "-"],
                stdin=minimap_proc.stdout,
                check=True,
            )
            minimap_proc.wait()
        finally:
            for p in [tmp_fq_path, tmp_filtered_path]:
                if os.path.exists(p):
                    os.remove(p)
    else:
        log("[INFO] No pre-alignment filtering")
        # BAM -> FASTQ -> align -> sort
        fastq_proc = subprocess.Popen(
            ["samtools", "fastq", "-@4", current_input],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        minimap_proc = subprocess.Popen(
            ["minimap2", "-ax", "map-ont", "--MD", "-t", "32", ref_genome, "-"],
            stdin=fastq_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["samtools", "sort", "-@4", "-o", aligned_bam, "-"],
            stdin=minimap_proc.stdout,
            check=True,
        )
        fastq_proc.wait()
        minimap_proc.wait()


def _process_fastq_input(
    input_file: str,
    aligned_bam: str,
    ref_genome: str,
    min_dorado_q: float,
    min_mean_q: float,
    min_len: int,
    apply_pre_filter: bool,
    output_dir: str,
    log: Callable[[str], None],
) -> None:
    """Process FASTQ input: optionally filter by qs/quality, align, sort."""
    apply_dorado_filter = min_dorado_q > 0

    if apply_dorado_filter or apply_pre_filter:
        # Need intermediate filtered FASTQ files
        current_path = input_file

        with (
            tempfile.NamedTemporaryFile(
                suffix=".fastq", dir=output_dir, delete=False
            ) as tmp1,
            tempfile.NamedTemporaryFile(
                suffix=".fastq", dir=output_dir, delete=False
            ) as tmp2,
        ):
            tmp1_path = tmp1.name
            tmp2_path = tmp2.name

        try:
            if apply_dorado_filter and apply_pre_filter:
                log(
                    f"[INFO] Applying Dorado qs filter "
                    f"(min-dorado-q={min_dorado_q}) and pre-alignment "
                    f"filters (min-mean-q={min_mean_q}, min-len={min_len})"
                )
                filter_fastq_by_qs(current_path, tmp1_path, min_dorado_q, log)
                filter_fastq(tmp1_path, tmp2_path, min_mean_q, min_len, log)
                current_path = tmp2_path
            elif apply_dorado_filter:
                log(
                    f"[INFO] Applying Dorado qs filter "
                    f"(min-dorado-q={min_dorado_q})"
                )
                filter_fastq_by_qs(current_path, tmp1_path, min_dorado_q, log)
                current_path = tmp1_path
            elif apply_pre_filter:
                log(
                    f"[INFO] Applying pre-alignment filters "
                    f"(min-mean-q={min_mean_q}, min-len={min_len})"
                )
                filter_fastq(current_path, tmp1_path, min_mean_q, min_len, log)
                current_path = tmp1_path

            # Align filtered FASTQ
            minimap_proc = subprocess.Popen(
                [
                    "minimap2",
                    "-ax",
                    "map-ont",
                    "--MD",
                    "-t",
                    "32",
                    ref_genome,
                    current_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["samtools", "sort", "-@4", "-o", aligned_bam, "-"],
                stdin=minimap_proc.stdout,
                check=True,
            )
            minimap_proc.wait()
        finally:
            for p in [tmp1_path, tmp2_path]:
                if os.path.exists(p):
                    os.remove(p)
    else:
        log("[INFO] No pre-alignment filtering")
        minimap_proc = subprocess.Popen(
            [
                "minimap2",
                "-ax",
                "map-ont",
                "--MD",
                "-t",
                "32",
                ref_genome,
                input_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["samtools", "sort", "-@4", "-o", aligned_bam, "-"],
            stdin=minimap_proc.stdout,
            check=True,
        )
        minimap_proc.wait()
