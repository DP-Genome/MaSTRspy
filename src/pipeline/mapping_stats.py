"""Compute mapping statistics and region overlap for BAM files."""

import os
import subprocess
from pathlib import Path
from typing import Callable


def compute_mapping_stats(
    bam_path: str,
    output_dir: str,
    samtools: str = "samtools",
    log: Callable[[str], None] = print,
) -> None:
    """Compute total, mapped, and unmapped read counts for a BAM file.

    Writes a MappingStats.txt file to output_dir.
    """
    bam_name = os.path.basename(bam_path)
    log(f"Calculating mapping stats for {bam_name}...")

    result = subprocess.run(
        [samtools, "flagstat", bam_path],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.strip().split("\n")

    # Line 1: total reads, Line 5: mapped reads
    total = int(lines[0].split()[0])
    mapped = int(lines[4].split()[0])
    unmapped = total - mapped

    stats_file = os.path.join(output_dir, f"{bam_name}_MappingStats.txt")
    with open(stats_file, "w") as f:
        f.write("TotalReads\tIntersectMappedReads(Ratio)\tUnmapedReads(Ration)\n")
        if total > 0:
            mapped_pct = mapped / total * 100
            unmapped_pct = unmapped / total * 100
            f.write(
                f"{total}\t{mapped} ({mapped_pct:.6g}%)\t"
                f"{unmapped} ({unmapped_pct:.6g}%)\n"
            )
        else:
            f.write(f"{total}\t{mapped} (0%)\t{unmapped} (0%)\n")


def compute_region_overlap(
    bam_path: str,
    bed_path: str,
    output_dir: str,
    samtools: str = "samtools",
    log: Callable[[str], None] = print,
) -> None:
    """Compute overlap between BAM reads and BED regions.

    Writes a regions.OverlapStats.txt file to output_dir.
    """
    bam_name = os.path.basename(bam_path)

    # Total primary mapped reads
    result = subprocess.run(
        [samtools, "view", "-c", "-F", "2308", bam_path],
        capture_output=True,
        text=True,
        check=True,
    )
    bam_cov = int(result.stdout.strip())

    # Reads overlapping regions
    result = subprocess.run(
        [samtools, "view", "-c", "-F", "2308", "-L", bed_path, bam_path],
        capture_output=True,
        text=True,
        check=True,
    )
    region_cov = int(result.stdout.strip())

    overlap_file = os.path.join(
        output_dir, f"{bam_name}.regions.OverlapStats.txt"
    )
    with open(overlap_file, "w") as f:
        f.write("GenomicMapping\tRegionsOverllaped\tRatio\n")
        if bam_cov > 0:
            ratio = region_cov / bam_cov * 100
            f.write(f"{bam_cov}\t{region_cov}\t{ratio:.6g}(%)\n")
        else:
            f.write(f"{bam_cov}\t{region_cov}\t0(%)\n")
