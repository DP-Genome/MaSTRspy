"""Process a single STR locus for a sample BAM file.

Replaces process_locus_for_sample() from MaSTRspy_Analysis_P1.0.sh.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Callable, Dict, Optional

from src.pipeline.allele_parser import parse_allele_with_counts


def process_locus(
    sample_bam: str,
    str_bed: str,
    config: Dict,
    temp_dir: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> Dict:
    """Process one STR locus for a given sample BAM.

    (#3) Uses allele_parser for robust allele name extraction.
    (#12) No longer generates Toptwo files (redundant with summary_generator).
    (#14) Captures stderr from subprocesses for diagnostics.
    (#16) Guaranteed temp file cleanup via try/finally.

    Returns dict with locus processing results for error tracking (#2).

    config keys:
        output_dir (str): base output directory
        str_fasta (str): directory containing per-locus .fa files
        read_type (str): 'ont' or 'pb'
        num_threads (int): threads for minimap2
        norm_cutoff (float): global normalization cutoff
        overrides (dict): locus -> cutoff overrides
        bedtools (str): path to bedtools
        samtools (str): path to samtools
        minimap (str): path to minimap2
        freebayes (str): path to freebayes
        enable_snv (bool): whether to run freebayes SNV calling
    """
    output_dir = config["output_dir"]
    str_fasta_dir = config["str_fasta"]
    read_type = config.get("read_type", "ont")
    num_threads = str(config.get("num_threads", 16))
    config.get("norm_cutoff", 0.1)
    config.get("overrides", {})

    bedtools = config.get("bedtools", "bedtools")
    samtools = config.get("samtools", "samtools")
    minimap = config.get("minimap", "minimap2")
    freebayes = config.get("freebayes", "freebayes")
    enable_snv = config.get("enable_snv", False)

    bam_name = os.path.basename(sample_bam)
    bed_name = os.path.basename(str_bed)
    bed_fname = os.path.splitext(bed_name)[0]

    result = {
        "sample": bam_name,
        "locus": bed_fname,
        "status": "pending",
        "allele_count": 0,
        "error": None,
    }

    log(f"\n# Working on Sample: [{bam_name}] for STR Locus: [{bed_name}]")

    # Create temp dir if not provided
    owns_temp = temp_dir is None
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
    os.makedirs(temp_dir, exist_ok=True)

    intersected_bam = os.path.join(temp_dir, "intersected.bam")
    intersected_fq = os.path.join(temp_dir, "intersected.fq")
    motif_mapped_sam = os.path.join(temp_dir, "motif_alignment.sam")
    motif_mapped_bam = os.path.join(temp_dir, "motif_alignment.bam")

    intersect_dir = os.path.join(output_dir, "IntersectMappedReads")
    os.makedirs(intersect_dir, exist_ok=True)
    motif_mapped_sorted_bam = os.path.join(
        intersect_dir, f"{bed_fname}_{bam_name}_alignment.sorted.bam"
    )

    try:
        # Step 1: Intersect regions and create FASTQ
        log("## Step 1/5: Intersecting reads from STR region...")
        motif_fa = os.path.join(str_fasta_dir, f"{bed_fname}.fa")
        map_preset = "map-ont" if read_type == "ont" else "map-pb"

        with open(intersected_bam, "wb") as out:
            proc = subprocess.run(
                [bedtools, "intersect", "-a", sample_bam, "-b", str_bed],
                stdout=out,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"bedtools intersect failed: {proc.stderr}")

        proc = subprocess.run(
            [bedtools, "bamtofastq", "-i", intersected_bam, "-fq", intersected_fq],
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"bedtools bamtofastq failed: {proc.stderr}")

        # Step 2: Map extracted reads to the STR motif reference
        log("## Step 2/5: Mapping extracted reads to STR motif reference...")
        proc = subprocess.run(
            [
                minimap,
                "--MD",
                "-L",
                "-t",
                num_threads,
                "-ax",
                map_preset,
                motif_fa,
                intersected_fq,
                "-o",
                motif_mapped_sam,
            ],
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"minimap2 failed: {proc.stderr}")

        # Step 3: Convert SAM to sorted, indexed BAM
        log("## Step 3/5: Sorting and indexing motif alignments...")
        subprocess.run(
            [samtools, "view", "-S", "-b", motif_mapped_sam, "-o", motif_mapped_bam],
            check=True,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [samtools, "sort", "-o", motif_mapped_sorted_bam, motif_mapped_bam],
            check=True,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [samtools, "index", motif_mapped_sorted_bam],
            check=True,
            stderr=subprocess.PIPE,
        )

        # Step 4: Call SNVs with freebayes (optional, non-fatal)
        if enable_snv:
            log("## Step 4/5: Calling SNVs with freebayes...")
            try:
                snv_dir = os.path.join(output_dir, "SNVcalls")
                os.makedirs(snv_dir, exist_ok=True)
                snv_prefix = os.path.join(snv_dir, f"{bed_fname}_{bam_name}")
                vcf_path = snv_prefix + ".vcf"
                with open(vcf_path, "w") as vcf_out:
                    proc = subprocess.run(
                        [freebayes, "-f", motif_fa, motif_mapped_sorted_bam],
                        stdout=vcf_out,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                if proc.returncode != 0:
                    log(
                        f"[WARNING] freebayes failed for {bed_fname}/{bam_name}: "
                        f"{proc.stderr.strip()}"
                    )
            except Exception as e:
                log(f"[WARNING] freebayes skipped for {bed_fname}/{bam_name}: {e}")
        else:
            log("## Step 4/5: SNV calling skipped (disabled)")

        # Step 5: Count and normalize STR alleles
        log("## Step 5/5: Counting and normalizing STR alleles...")
        counting_dir = os.path.join(output_dir, "Countings")
        os.makedirs(counting_dir, exist_ok=True)
        allele_freq_file = os.path.join(
            counting_dir, f"{bed_fname}_{bam_name}_Allele_freqs.txt"
        )

        # Get allele counts
        view_proc = subprocess.Popen(
            [samtools, "view", "-q", "1", "-F", "2308", motif_mapped_sorted_bam],
            stdout=subprocess.PIPE,
            text=True,
        )

        allele_counts = {}
        for line in view_proc.stdout:
            fields = line.strip().split("\t")
            if len(fields) >= 3:
                allele = fields[2]
                if allele != "*":
                    allele_counts[allele] = allele_counts.get(allele, 0) + 1
        view_proc.wait()

        # Sort by count descending
        sorted_alleles = sorted(allele_counts.items(), key=lambda x: x[1], reverse=True)
        max_count = sorted_alleles[0][1] if sorted_alleles else 1

        # (#3) Parse alleles using allele_parser
        parsed_alleles = [
            parse_allele_with_counts(name, count, max_count)
            for name, count in sorted_alleles
        ]

        # Write allele frequency file
        with open(allele_freq_file, "w") as f:
            f.write("STR\tRawCounts\tNormalizedCounts\n")
            for pa in parsed_alleles:
                f.write(f"{pa.raw_name}\t{pa.raw_count}\t{pa.normalized_count}\n")

        # (#12) Toptwo file generation removed — summary_generator handles this

        result["status"] = "success"
        result["allele_count"] = len(parsed_alleles)
        log(
            f"## Done processing locus {bed_fname} for sample {bam_name}. "
            f"({len(parsed_alleles)} alleles)"
        )

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        log(f"[ERROR] Locus {bed_fname} for {bam_name} failed: {e}")

    finally:
        # Clean up temp files (#16)
        for tmp in [
            intersected_bam,
            intersected_fq,
            motif_mapped_sam,
            motif_mapped_bam,
        ]:
            if os.path.exists(tmp):
                os.remove(tmp)
        if owns_temp and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    return result
