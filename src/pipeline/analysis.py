"""Top-level analysis orchestrator.

Replaces MaSTRspy_Analysis_P1.0.sh. Calls mapping_stats, locus_processor,
file_organizer, summary_generator, and R plots.
"""

import os
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict

from src.core.config import load_input_config, load_overrides, load_tools_config
from src.pipeline.file_organizer import organize_by_barcode
from src.pipeline.locus_processor import process_locus
from src.pipeline.mapping_stats import compute_mapping_stats, compute_region_overlap
from src.pipeline.summary_generator import generate_summaries
from src.plotting.runner import run_r_plots


def _process_locus_wrapper(args):
    """Wrapper for process_locus to work with ProcessPoolExecutor."""
    sample_bam, str_bed, config, temp_dir = args
    process_locus(sample_bam, str_bed, config, temp_dir)


def run_analysis(
    config_path: str,
    tools_config_path: str,
    log: Callable[[str], None] = print,
) -> str:
    """Run the full analysis pipeline.

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

    bedtools = tools.get("BEDTOOLS", "bedtools")
    minimap = tools.get("MINIMAP", "minimap2")
    samtools = tools.get("SAMTOOLS", "samtools")
    xatlas = tools.get("XATLAS", "xatlas")

    # Load overrides
    overrides = load_overrides(norm_cutoff_overrides_path)

    os.makedirs(output_dir, exist_ok=True)

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
    for subdir in [
        "IntersectMappedReads",
        "Countings",
        "SNVcalls",
        "GenomeMapping",
        "GenomicMappingStats",
    ]:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    input_file_type = "bam" if input_bam == "yes" else "fastq"

    # STEP 1: Genomic Mapping (FASTQ input only)
    if input_file_type == "fastq":
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
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    samtools,
                    "sort",
                    f"-@{num_threads}",
                    "-o",
                    out_bam,
                ],
                stdin=minimap_proc.stdout,
                check=True,
            )
            minimap_proc.wait()
            subprocess.run([samtools, "index", out_bam], check=True)

        log("# Genome mapping complete.")

    # Mapping Stats
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
    log("# Mapping statistics complete.")

    # STEP 2: Process STR loci in parallel
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
        "xatlas": xatlas,
    }

    # Create parent temp dir
    parent_temp_dir = tempfile.mkdtemp(
        prefix="Mastrspy_parallel_temp.", dir=output_dir
    )
    log(f"Parent temporary directory for all jobs: {parent_temp_dir}")

    # Build job list
    jobs = []
    for bam_file in bam_files:
        for bed_file in bed_files:
            job_temp = tempfile.mkdtemp(dir=parent_temp_dir)
            jobs.append((str(bam_file), str(bed_file), locus_config, job_temp))

    # Process in parallel
    with ProcessPoolExecutor(max_workers=num_parallel_jobs) as executor:
        futures = {
            executor.submit(_process_locus_wrapper, job): job for job in jobs
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                job = futures[future]
                log(f"[ERROR] Failed processing {job[0]} x {job[1]}: {e}")

    # Clean up temp dir
    import shutil

    shutil.rmtree(parent_temp_dir, ignore_errors=True)

    # File organization
    counting_dir = os.path.join(output_dir, "Countings")
    organize_by_barcode(counting_dir, log=log)

    # Generate summaries and profiles
    generate_summaries(counting_dir, norm_cutoff, overrides, log)

    log("\n========================================================")
    log("All analyses are complete.")

    # Run R plots
    summaries_dir = os.path.join(counting_dir, "Summaries")
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    r_script = os.path.join(script_dir, "scripts", "STR_Profile_Plots_P1.0.R")
    logo_path = os.path.join(script_dir, "logo.jpg")
    run_r_plots(summaries_dir, r_script, logo_path, log)

    elapsed = time.time() - start_time
    minutes = int(elapsed) // 60
    seconds = int(elapsed) % 60
    log(f"Total time elapsed: {minutes} minutes and {seconds} seconds.")
    log(f"SUMMARY REPORT: {summaries_dir}/")
    log("  - barcode##_summary.tsv: All alleles per barcode")
    log("  - barcode##_Profile.tsv: Top 2 alleles per locus ")
    log("  - Plots/: Visualization plots for each barcode")
    log("========================================================")

    return summaries_dir
