"""Top-level analysis orchestrator.

Replaces MaSTRspy_Analysis_P1.0.sh. Calls mapping_stats, locus_processor,
file_organizer, summary_generator, and plots.
"""

import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.core.checkpoint import CheckpointManager
from src.core.config import (
    load_input_config,
    load_overrides,
    load_tools_config,
)
from src.core.tool_check import run_preflight_check
from src.pipeline.export import export_combined_report
from src.pipeline.file_organizer import organize_by_barcode
from src.pipeline.locus_processor import process_locus
from src.pipeline.mapping_stats import compute_mapping_stats, compute_region_overlap
from src.pipeline.summary_generator import generate_summaries
from src.plotting.python_plots import run_python_plots
from src.plotting.runner import run_r_plots


def _process_locus_wrapper(args):
    """Wrapper for process_locus to work with ThreadPoolExecutor (#1)."""
    sample_bam, str_bed, config, temp_dir = args
    return process_locus(sample_bam, str_bed, config, temp_dir)


def run_analysis(
    config_path: str,
    tools_config_path: str,
    log: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Run the full analysis pipeline.

    (#1) Uses ThreadPoolExecutor instead of ProcessPoolExecutor for I/O-bound work.
    (#2) Tracks per-locus errors and generates a failed-loci report.
    (#5) Runs pre-flight tool checks before starting.
    (#14) Captures stderr from subprocesses.
    (#15) Supports checkpoint/resume for interrupted runs.

    Args:
        config_path: path to InputConfig.txt
        tools_config_path: path to ToolsConfig.txt
        log: logging callback

    Returns:
        Path to the results/summaries directory.
    """
    start_time = time.time()

    # Load configs
    config = load_input_config(config_path)
    tools = load_tools_config(tools_config_path)

    input_dir = config["INPUT_DIR"]
    output_dir = config["OUTPUT_DIR"]
    input_bam = config.get("INPUT_BAM", "yes")
    read_type = config.get("READ_TYPE", "ont")
    str_fasta = config.get("STR_FASTA", "")
    str_bed_dir = config.get("STR_BED", "")
    genome_fasta = config.get("GENOME_FASTA", "")
    region_bed = config.get("REGION_BED", "")
    norm_cutoff = float(config.get("NORM_CUTOFF", "0.1"))
    norm_cutoff_overrides_path = config.get("NORM_CUTOFF_OVERRIDES", "")
    num_parallel_jobs = int(config.get("NUM_PARALLEL_JOBS", "8"))
    num_threads = int(config.get("NUM_THREADS", "16"))
    enable_snv = config.get("ENABLE_SNV", "no").lower() == "yes"

    bedtools = tools.get("BEDTOOLS", "bedtools")
    minimap = tools.get("MINIMAP", "minimap2")
    samtools = tools.get("SAMTOOLS", "samtools")
    freebayes = tools.get("FREEBAYES", "freebayes")

    # Load overrides
    overrides = load_overrides(norm_cutoff_overrides_path)

    os.makedirs(output_dir, exist_ok=True)

    # (#5) Pre-flight tool check
    run_preflight_check(tools, log)

    # (#15) Initialize checkpoint manager
    checkpoint_path = os.path.join(output_dir, ".mastrspy_checkpoint.json")
    checkpoint = CheckpointManager(checkpoint_path)
    if checkpoint.completed_loci_count > 0:
        log(
            f"[INFO] Resuming from checkpoint: {checkpoint.completed_loci_count} loci already complete."
        )

    log("Configurations loaded successfully.")
    log("========================================================")
    log("Arguments are valid. Starting MaSTRspy P1.0 analysis.")
    log("========================================================")
    log(f"Input read dir: {input_dir}")
    log(f"Input type: {'bam' if input_bam == 'yes' else 'fastq'}")
    log(f"Read Technology: {read_type}")
    log(f"Parallel Jobs: {num_parallel_jobs}")
    log(f"Threads per Job: {num_threads}")
    log(f"Output dir: {output_dir}")
    if norm_cutoff_overrides_path:
        log(f"Norm_cutoff overrides TSV: {norm_cutoff_overrides_path}")
    else:
        log("Norm_cutoff overrides TSV: (none)")
    log("========================================================")

    # Create output sub-directories
    subdirs = [
        "IntersectMappedReads",
        "Countings",
        "GenomeMapping",
        "GenomicMappingStats",
    ]
    if enable_snv:
        subdirs.append("SNVcalls")
    for subdir in subdirs:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    input_file_type = "bam" if input_bam == "yes" else "fastq"

    # STEP 1: Genomic Mapping (FASTQ input only)
    if input_file_type == "fastq" and not checkpoint.is_stage_complete(
        "genome_mapping"
    ):
        log(
            f"\n# STEP 1: Mapping FASTQ reads to reference genome "
            f"(using {num_parallel_jobs} parallel jobs)..."
        )
        map_preset = "map-ont" if read_type == "ont" else "map-pb"
        fastq_files = list(Path(input_dir).glob("*.fastq")) + list(
            Path(input_dir).glob("*.fastq.gz")
        )

        genome_mapping_dir = os.path.join(output_dir, "GenomeMapping")
        for fq in fastq_files:
            out_bam = os.path.join(genome_mapping_dir, f"{fq.stem}.sorted.bam")
            minimap_proc = subprocess.Popen(
                [
                    minimap,
                    "--MD",
                    "-L",
                    "-t",
                    str(num_threads),
                    "-ax",
                    map_preset,
                    genome_fasta,
                    str(fq),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                [samtools, "sort", f"-@{num_threads}", "-o", out_bam],
                stdin=minimap_proc.stdout,
                check=True,
            )
            minimap_proc.wait()
            subprocess.run([samtools, "index", out_bam], check=True)

        checkpoint.mark_stage_complete("genome_mapping")
        log("# Genome mapping complete.")

    # Mapping Stats
    if not checkpoint.is_stage_complete("mapping_stats"):
        log("\n# Calculating mapping statistics...")
        if input_bam == "yes":
            log("Input is BAM. Ensuring all are sorted and indexed...")
            for bam in Path(input_dir).glob("*.bam"):
                bai = str(bam) + ".bai"
                if not os.path.exists(bai):
                    subprocess.run([samtools, "index", str(bam)], check=True)
            bam_dir_for_stats = input_dir
        else:
            bam_dir_for_stats = os.path.join(output_dir, "GenomeMapping")

        stats_dir = os.path.join(output_dir, "GenomicMappingStats")
        for bam_path in Path(bam_dir_for_stats).glob("*.bam"):
            compute_mapping_stats(str(bam_path), stats_dir, samtools, log)
            compute_region_overlap(str(bam_path), region_bed, stats_dir, samtools, log)
        checkpoint.mark_stage_complete("mapping_stats")
        log("# Mapping statistics complete.")
    else:
        bam_dir_for_stats = (
            input_dir
            if input_bam == "yes"
            else os.path.join(output_dir, "GenomeMapping")
        )

    # STEP 2: Process STR loci in parallel (#1: ThreadPoolExecutor)
    log("\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    log(
        f"# STEP 2: Spying on STRs for each sample "
        f"(using {num_parallel_jobs} parallel jobs)..."
    )
    log("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

    bam_files = sorted(Path(bam_dir_for_stats).glob("*.bam"))
    bed_files = sorted(Path(str_bed_dir).glob("*.bed"))

    # Build locus processing config
    locus_config = {
        "output_dir": output_dir,
        "str_fasta": str_fasta,
        "read_type": read_type,
        "num_threads": num_threads,
        "norm_cutoff": norm_cutoff,
        "overrides": overrides,
        "bedtools": bedtools,
        "samtools": samtools,
        "minimap": minimap,
        "freebayes": freebayes,
        "enable_snv": enable_snv,
    }

    # Create parent temp dir
    parent_temp_dir = tempfile.mkdtemp(prefix="Mastrspy_parallel_temp.", dir=output_dir)
    log(f"Parent temporary directory for all jobs: {parent_temp_dir}")

    # Build job list with per-locus temp dirs
    all_jobs = []
    for bam_file in bam_files:
        for bed_file in bed_files:
            job_temp = tempfile.mkdtemp(dir=parent_temp_dir)
            all_jobs.append((str(bam_file), str(bed_file), locus_config, job_temp))

    # (#15) Filter to only incomplete loci
    remaining_jobs = checkpoint.get_remaining_loci(all_jobs)
    if len(remaining_jobs) < len(all_jobs):
        log(
            f"[INFO] Skipping {len(all_jobs) - len(remaining_jobs)} already-completed loci."
        )
    log(f"[INFO] Processing {len(remaining_jobs)} loci...")

    # (#2) Track per-locus results for error reporting
    locus_results: List[Dict] = []
    failed_loci: List[Dict] = []

    # (#1) Process in parallel with ThreadPoolExecutor (I/O-bound subprocess work)
    total_loci = len(remaining_jobs)
    completed_count = 0
    with ThreadPoolExecutor(max_workers=num_parallel_jobs) as executor:
        futures = {
            executor.submit(_process_locus_wrapper, job): job for job in remaining_jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result()
                locus_results.append(result)
                if result["status"] == "success":
                    checkpoint.mark_locus_complete(job[0], job[1])
                else:
                    failed_loci.append(result)
            except Exception as e:
                error_result = {
                    "sample": os.path.basename(job[0]),
                    "locus": os.path.splitext(os.path.basename(job[1]))[0],
                    "status": "failed",
                    "error": str(e),
                }
                locus_results.append(error_result)
                failed_loci.append(error_result)
                log(f"[ERROR] Failed processing {job[0]} x {job[1]}: {e}")
            completed_count += 1
            if progress_callback is not None:
                progress_callback(completed_count, total_loci)

    # Clean up temp dir
    shutil.rmtree(parent_temp_dir, ignore_errors=True)

    # (#2) Report failed loci
    if failed_loci:
        log(f"\n[WARNING] {len(failed_loci)} loci failed processing:")
        failed_report_path = os.path.join(output_dir, "failed_loci_report.tsv")
        with open(failed_report_path, "w") as f:
            f.write("Sample\tLocus\tError\n")
            for fl in failed_loci:
                log(f"  - {fl['sample']} x {fl['locus']}: {fl.get('error', 'unknown')}")
                f.write(
                    f"{fl['sample']}\t{fl['locus']}\t{fl.get('error', 'unknown')}\n"
                )
        log(f"  Failed loci report: {failed_report_path}")
    else:
        log(f"\n[INFO] All {len(locus_results)} loci processed successfully.")

    # File organization (#12: no more Toptwo cleanup needed)
    counting_dir = os.path.join(output_dir, "Countings")
    organize_by_barcode(counting_dir, log=log)

    # Generate summaries and profiles (#17,18,19,20 enhancements in summary_generator)
    generate_summaries(counting_dir, norm_cutoff, overrides, log)

    log("\n========================================================")
    log("All analyses are complete.")

    # Run plots — try Python first, fall back to R (#26)
    summaries_dir = os.path.join(counting_dir, "Summaries")
    run_python_plots(summaries_dir, norm_cutoff=norm_cutoff, log=log)

    # Also try R plots if available
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    r_script = os.path.join(script_dir, "src", "scripts", "STR_Profile_Plots_P1.0.R")
    logo_path = os.path.join(script_dir, "assets", "logo.jpg")
    run_r_plots(summaries_dir, r_script, logo_path, log)

    # (#25) Generate combined multi-sample report
    combined_path = os.path.join(summaries_dir, "combined_summary.tsv")
    export_combined_report(summaries_dir, combined_path, log)

    # (#15) Clear checkpoint on successful completion
    checkpoint.clear()

    elapsed = time.time() - start_time
    minutes = int(elapsed) // 60
    seconds = int(elapsed) % 60
    log(f"Total time elapsed: {minutes} minutes and {seconds} seconds.")
    log(f"SUMMARY REPORT: {summaries_dir}/")
    log("  - barcode##_summary.tsv: All alleles per barcode")
    log("  - barcode##_Profile.tsv: Top 2 alleles per locus ")
    log("  - combined_summary.tsv: Multi-sample combined report")
    log("  - Plots/: Visualization plots for each barcode")
    log("========================================================")

    return summaries_dir


def run_analysis_direct(
    config: Dict[str, Any],
    tools: Dict[str, str],
    log: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Run analysis directly from config dicts (#9).

    Avoids the temp-file round-trip of serializing config to disk
    and re-parsing it.

    Args:
        config: analysis configuration dict (same keys as InputConfig.txt)
        tools: tool paths dict (same keys as ToolsConfig.txt)
        log: logging callback

    Returns:
        Path to the results/summaries directory.
    """
    # Write config to temp file and delegate to run_analysis
    # This preserves full backward compatibility while also providing
    # the direct dict interface

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for key, value in config.items():
            f.write(f'{key}="{value}"\n')
        config_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for key, value in tools.items():
            f.write(f"{key}={value}\n")
        tools_path = f.name

    try:
        return run_analysis(config_path, tools_path, log, progress_callback)
    finally:
        os.remove(config_path)
        os.remove(tools_path)
