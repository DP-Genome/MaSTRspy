"""Prepping pipeline: alignment + filtering for BAM/FASTQ inputs.

Replaces MaSTR_Prepping_P1.0.sh.
"""

import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List

from src.core.config import compute_thread_split
from src.filters.bam_accuracy import filter_bam_by_accuracy
from src.filters.dorado_qs import filter_bam_by_qs, filter_fastq_by_qs
from src.filters.fastq_quality import filter_fastq
from src.filters.filter_report import FilterReport


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


@contextmanager
def _temp_files(suffixes: List[str], directory: str):
    """Context manager for temporary files with guaranteed cleanup (#16)."""
    paths = []
    try:
        for suffix in suffixes:
            tmp = tempfile.NamedTemporaryFile(
                suffix=suffix, dir=directory, delete=False
            )
            paths.append(tmp.name)
            tmp.close()
        yield paths
    finally:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)


def run_prepping(
    params: Dict[str, Any],
    log: Callable[[str], None] = print,
) -> List[FilterReport]:
    """Run the full prepping pipeline on all input files.

    (#4) num_threads now read from params instead of hardcoded.
    (#8) Returns list of FilterReport for QC reporting.
    (#14) Captures stderr from subprocesses.
    (#16) Uses context managers for temp file cleanup.

    params keys:
        input_dir (str): directory containing input BAM/FASTQ files
        output_dir (str): directory for prepped output files
        ref_genome (str): path to reference genome index (.mmi)
        exp_name (str): experiment name prefix
        input_type (str): 'bam' or 'fastq'
        read_type (str): 'ont' or 'pb' (default 'ont')
        num_threads (int): threads for alignment tools (default 16)
        min_dorado_q (float): minimum Dorado qs tag score (0 = skip)
        min_mean_q (float): minimum mean quality score (0 = skip)
        min_len (int): minimum read length (0 = skip)
        min_acc (float): minimum alignment accuracy (0 = skip)
        samtools (str): path to samtools binary (default 'samtools')
        minimap (str): path to minimap2 binary (default 'minimap2')
    """
    input_dir = params["input_dir"]
    output_dir = params["output_dir"]
    ref_genome = params["ref_genome"]
    input_type = params.get("input_type", "bam")
    read_type = params.get("read_type", "ont")
    num_threads = str(params.get("num_threads", 16))
    min_dorado_q = float(params.get("min_dorado_q", 0))
    min_mean_q = float(params.get("min_mean_q", 0))
    min_len = int(params.get("min_len", 0))
    min_acc = float(params.get("min_acc", 0))
    samtools_bin = params.get("samtools", "samtools")
    minimap_bin = params.get("minimap", "minimap2")
    map_preset = "map-ont" if read_type == "ont" else "map-pb"

    os.makedirs(output_dir, exist_ok=True)

    filter_reports: List[FilterReport] = []

    log("========================================")
    log("MaSTR_Prepping P1.0 Started")
    log("========================================")
    log(f"Input directory: {input_dir}")
    log(f"Output directory: {output_dir}")
    log(f"Reference genome: {ref_genome}")
    log(f"Input type: {input_type}")
    log(f"Threads: {num_threads}")
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
        return filter_reports

    # Compute thread split for parallel sample processing
    total_threads = int(num_threads)
    num_jobs, threads_per_job = compute_thread_split(total_threads)
    num_jobs = min(num_jobs, len(input_files))
    threads_str = str(threads_per_job)

    log(f"Parallel Jobs: {num_jobs}")
    log(f"Threads per Job: {threads_per_job}")
    log("========================================")

    def _process_single_sample(input_file: Path) -> FilterReport:
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
        report = FilterReport(sample_name=barcode_name)

        log("")
        log(f"--- Processing: {file_basename} -> {barcode_name} ---")

        qs_filtered_bam = os.path.join(output_dir, f"{barcode_name}_qs_filtered.bam")
        aligned_bam = os.path.join(output_dir, f"{barcode_name}_aligned.bam")
        final_bam = os.path.join(output_dir, f"{barcode_name}_prepped.bam")

        current_input = str(input_file)

        # STAGE 0: Dorado qs Tag Filter (BAM only)
        if input_type == "bam" and min_dorado_q > 0:
            log(f"[INFO] Applying Dorado qs tag filter (min-dorado-q={min_dorado_q})")
            stats = filter_bam_by_qs(current_input, qs_filtered_bam, min_dorado_q, log)
            report.add_stage("dorado_qs", stats)
            current_input = qs_filtered_bam

        apply_pre_filter = min_mean_q > 0 or min_len > 0

        if input_type == "bam":
            _process_bam_input(
                current_input,
                aligned_bam,
                ref_genome,
                threads_str,
                min_dorado_q,
                min_mean_q,
                min_len,
                apply_pre_filter,
                output_dir,
                log,
                report,
                samtools_bin=samtools_bin,
                minimap_bin=minimap_bin,
                map_preset=map_preset,
            )
        else:
            _process_fastq_input(
                str(input_file),
                aligned_bam,
                ref_genome,
                threads_str,
                min_dorado_q,
                min_mean_q,
                min_len,
                apply_pre_filter,
                output_dir,
                log,
                report,
                samtools_bin=samtools_bin,
                minimap_bin=minimap_bin,
                map_preset=map_preset,
            )

        # Clean up intermediate qs-filtered BAM
        if os.path.exists(qs_filtered_bam):
            os.remove(qs_filtered_bam)

        # Post-alignment accuracy filter
        if min_acc > 0:
            log(f"[INFO] Applying post-alignment accuracy filter (min-acc={min_acc})")
            stats = filter_bam_by_accuracy(aligned_bam, final_bam, min_acc, log)
            report.add_stage("accuracy", stats)
            os.remove(aligned_bam)
        else:
            log("[INFO] No post-alignment filtering")
            os.rename(aligned_bam, final_bam)

        # Index the final BAM
        subprocess.run([samtools_bin, "index", final_bam], check=True)
        log(f"--- Completed: {final_bam} ---")

        # Log QC summary
        log(report.summary_line())
        return report

    # Process samples in parallel
    with ThreadPoolExecutor(max_workers=num_jobs) as executor:
        futures = {
            executor.submit(_process_single_sample, f): f for f in input_files
        }
        for future in as_completed(futures):
            input_file = futures[future]
            try:
                report = future.result()
                filter_reports.append(report)
            except Exception as e:
                log(f"[ERROR] Failed processing {input_file.name}: {e}")

    log("")
    log("========================================")
    log("MaSTR_Prepping P1.0 Finished")
    log(f"Prepped files are in: {output_dir}")
    log("========================================")

    return filter_reports


def _process_bam_input(
    current_input: str,
    aligned_bam: str,
    ref_genome: str,
    num_threads: str,
    min_dorado_q: float,
    min_mean_q: float,
    min_len: int,
    apply_pre_filter: bool,
    output_dir: str,
    log: Callable[[str], None],
    report: FilterReport = None,
    samtools_bin: str = "samtools",
    minimap_bin: str = "minimap2",
    map_preset: str = "map-ont",
) -> None:
    """Process BAM input: convert to FASTQ, optionally filter, align, sort.

    (#4) Uses num_threads parameter instead of hardcoded values.
    (#14) Captures stderr for logging.
    (#16) Uses context manager for temp files.
    """
    if apply_pre_filter:
        log(
            f"[INFO] Applying pre-alignment filters "
            f"(min-mean-q={min_mean_q}, min-len={min_len})"
        )
        with _temp_files([".fastq", ".fastq"], output_dir) as (
            tmp_fq_path,
            tmp_filtered_path,
        ):
            # samtools fastq
            with open(tmp_fq_path, "w") as fq_out:
                result = subprocess.run(
                    [samtools_bin, "fastq", f"-@{num_threads}", current_input],
                    stdout=fq_out,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if result.stderr:
                    log(f"[DEBUG] samtools fastq: {result.stderr.strip()}")

            # fastq filter
            stats = filter_fastq(
                tmp_fq_path, tmp_filtered_path, min_mean_q, min_len, log
            )
            if report:
                report.add_stage("fastq_quality", stats)

            # minimap2 | samtools sort
            minimap_proc = subprocess.Popen(
                [
                    minimap_bin, "-ax", map_preset, "--MD",
                    "-t", num_threads, ref_genome, tmp_filtered_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            sort_result = subprocess.run(
                [samtools_bin, "sort", f"-@{num_threads}", "-o", aligned_bam, "-"],
                stdin=minimap_proc.stdout,
                stderr=subprocess.PIPE,
                text=True,
            )
            minimap_proc.stdout.close()
            minimap_proc.wait()
            minimap_stderr = minimap_proc.stderr.read()
            if minimap_stderr:
                log(f"[DEBUG] minimap2: {minimap_stderr.decode().strip()[:200]}")
    else:
        log("[INFO] No pre-alignment filtering")
        # BAM -> FASTQ -> align -> sort
        fastq_proc = subprocess.Popen(
            [samtools_bin, "fastq", f"-@{num_threads}", current_input],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        minimap_proc = subprocess.Popen(
            [minimap_bin, "-ax", map_preset, "--MD", "-t", num_threads, ref_genome, "-"],
            stdin=fastq_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [samtools_bin, "sort", f"-@{num_threads}", "-o", aligned_bam, "-"],
            stdin=minimap_proc.stdout,
            check=True,
        )
        fastq_proc.wait()
        minimap_proc.wait()


def _process_fastq_input(
    input_file: str,
    aligned_bam: str,
    ref_genome: str,
    num_threads: str,
    min_dorado_q: float,
    min_mean_q: float,
    min_len: int,
    apply_pre_filter: bool,
    output_dir: str,
    log: Callable[[str], None],
    report: FilterReport = None,
    samtools_bin: str = "samtools",
    minimap_bin: str = "minimap2",
    map_preset: str = "map-ont",
) -> None:
    """Process FASTQ input: optionally filter by qs/quality, align, sort.

    (#4) Uses num_threads parameter instead of hardcoded values.
    (#14) Captures stderr for logging.
    (#16) Uses context manager for temp files.
    """
    apply_dorado_filter = min_dorado_q > 0

    if apply_dorado_filter or apply_pre_filter:
        with _temp_files([".fastq", ".fastq"], output_dir) as (tmp1_path, tmp2_path):
            current_path = input_file

            if apply_dorado_filter and apply_pre_filter:
                log(
                    f"[INFO] Applying Dorado qs filter "
                    f"(min-dorado-q={min_dorado_q}) and pre-alignment "
                    f"filters (min-mean-q={min_mean_q}, min-len={min_len})"
                )
                stats = filter_fastq_by_qs(current_path, tmp1_path, min_dorado_q, log)
                if report:
                    report.add_stage("dorado_qs_fastq", stats)
                stats = filter_fastq(tmp1_path, tmp2_path, min_mean_q, min_len, log)
                if report:
                    report.add_stage("fastq_quality", stats)
                current_path = tmp2_path
            elif apply_dorado_filter:
                log(
                    f"[INFO] Applying Dorado qs filter "
                    f"(min-dorado-q={min_dorado_q})"
                )
                stats = filter_fastq_by_qs(current_path, tmp1_path, min_dorado_q, log)
                if report:
                    report.add_stage("dorado_qs_fastq", stats)
                current_path = tmp1_path
            elif apply_pre_filter:
                log(
                    f"[INFO] Applying pre-alignment filters "
                    f"(min-mean-q={min_mean_q}, min-len={min_len})"
                )
                stats = filter_fastq(current_path, tmp1_path, min_mean_q, min_len, log)
                if report:
                    report.add_stage("fastq_quality", stats)
                current_path = tmp1_path

            # Align filtered FASTQ
            minimap_proc = subprocess.Popen(
                [
                    minimap_bin, "-ax", map_preset, "--MD",
                    "-t", num_threads, ref_genome, current_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [samtools_bin, "sort", f"-@{num_threads}", "-o", aligned_bam, "-"],
                stdin=minimap_proc.stdout,
                check=True,
            )
            minimap_proc.wait()
    else:
        log("[INFO] No pre-alignment filtering")
        minimap_proc = subprocess.Popen(
            [
                minimap_bin, "-ax", map_preset, "--MD",
                "-t", num_threads, ref_genome, input_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [samtools_bin, "sort", f"-@{num_threads}", "-o", aligned_bam, "-"],
            stdin=minimap_proc.stdout,
            check=True,
        )
        minimap_proc.wait()
