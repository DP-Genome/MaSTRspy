"""Process a single STR locus for a sample BAM file.

Replaces process_locus_for_sample() from MaSTRspy_Analysis_P1.0.sh.
"""

import os
import subprocess
import tempfile
from typing import Callable, Dict, Optional


def process_locus(
    sample_bam: str,
    str_bed: str,
    config: Dict,
    temp_dir: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> None:
    """Process one STR locus for a given sample BAM.

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
        xatlas (str): path to xatlas
    """
    output_dir = config["output_dir"]
    str_fasta_dir = config["str_fasta"]
    read_type = config.get("read_type", "ont")
    num_threads = str(config.get("num_threads", 16))
    norm_cutoff = config.get("norm_cutoff", 0.1)
    overrides = config.get("overrides", {})

    bedtools = config.get("bedtools", "bedtools")
    samtools = config.get("samtools", "samtools")
    minimap = config.get("minimap", "minimap2")
    xatlas = config.get("xatlas", "xatlas")

    bam_name = os.path.basename(sample_bam)
    bed_name = os.path.basename(str_bed)
    bed_fname = os.path.splitext(bed_name)[0]

    log(f"\n# Working on Sample: [{bam_name}] for STR Locus: [{bed_name}]")

    # Create temp dir if not provided
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

    # Step 1: Intersect regions and create FASTQ
    log("## Step 1/5: Intersecting reads from STR region...")
    with open(intersected_bam, "w") as out:
        subprocess.run(
            [bedtools, "intersect", "-a", sample_bam, "-b", str_bed],
            stdout=out,
            check=True,
        )
    subprocess.run(
        [bedtools, "bamtofastq", "-i", intersected_bam, "-fq", intersected_fq],
        check=True,
    )

    # Step 2: Map extracted reads to the STR motif reference
    log("## Step 2/5: Mapping extracted reads to STR motif reference...")
    motif_fa = os.path.join(str_fasta_dir, f"{bed_fname}.fa")
    map_preset = "map-ont" if read_type == "ont" else "map-pb"
    subprocess.run(
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
        check=True,
    )

    # Step 3: Convert SAM to sorted, indexed BAM
    log("## Step 3/5: Sorting and indexing motif alignments...")
    subprocess.run(
        [samtools, "view", "-S", "-b", motif_mapped_sam, "-o", motif_mapped_bam],
        check=True,
    )
    subprocess.run(
        [samtools, "sort", "-o", motif_mapped_sorted_bam, motif_mapped_bam],
        check=True,
    )
    subprocess.run(
        [samtools, "index", motif_mapped_sorted_bam],
        check=True,
    )

    # Step 4: Call SNVs with xatlas
    log("## Step 4/5: Calling SNVs with xatlas...")
    snv_dir = os.path.join(output_dir, "SNVcalls")
    os.makedirs(snv_dir, exist_ok=True)
    snv_prefix = os.path.join(snv_dir, f"{bed_fname}_{bam_name}")
    subprocess.run(
        [
            xatlas,
            "-r",
            motif_fa,
            "-i",
            motif_mapped_sorted_bam,
            "-s",
            snv_prefix,
            "-p",
            snv_prefix,
        ],
        check=True,
    )

    # Step 5: Count and normalize STR alleles
    log("## Step 5/5: Counting and normalizing STR alleles...")
    counting_dir = os.path.join(output_dir, "Countings")
    os.makedirs(counting_dir, exist_ok=True)
    allele_freq_file = os.path.join(
        counting_dir, f"{bed_fname}_{bam_name}_Allele_freqs.txt"
    )

    # Get allele counts: samtools view -q 1 -F 2308 | cut -f 3 | sort | uniq -c
    view_proc = subprocess.Popen(
        [samtools, "view", "-q", "1", "-F", "2308", motif_mapped_sorted_bam],
        stdout=subprocess.PIPE,
        text=True,
    )

    # Count alleles
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

    # Normalize with maximum
    max_count = sorted_alleles[0][1] if sorted_alleles else 1

    with open(allele_freq_file, "w") as f:
        f.write("STR\tRawCounts\tNormalizedCounts\n")
        for allele, count in sorted_alleles:
            normalized = count / max_count
            f.write(f"{allele}\t{count}\t{normalized}\n")

    # Determine effective norm cutoff for this locus
    effective_norm_cutoff = overrides.get(bed_fname, norm_cutoff)

    log(
        f"### Filtering for top two alleles "
        f"(Normalized count >= {effective_norm_cutoff})..."
    )

    toptwo_file = os.path.join(counting_dir, f"{bed_fname}_{bam_name}_Toptwo.txt")

    # Extract top two alleles above cutoff
    top_alleles = []
    for allele, count in sorted_alleles:
        normalized = count / max_count
        if normalized >= effective_norm_cutoff:
            # Parse allele name: extract the bracket part and last number
            # Replace _ with space, split ] to get separate parts
            cleaned = allele.replace("_", " ").replace("]", "] ")
            parts = cleaned.split()
            if parts:
                locus_part = parts[0]
                allele_num = parts[-2] if len(parts) >= 3 else parts[-1]
                top_alleles.append((locus_part, allele_num, normalized))
        if len(top_alleles) >= 2:
            break

    # Sort by normalized count descending
    top_alleles.sort(key=lambda x: x[2], reverse=True)

    with open(toptwo_file, "w") as f:
        f.write("Locus\tAllele\tNormalizedCounts\n")
        for locus, allele_num, norm in top_alleles:
            f.write(f"{locus}\t{allele_num}\t{norm}\n")

    log(f"## Done processing locus {bed_fname} for sample {bam_name}.")

    # Clean up temp files
    for tmp in [intersected_bam, intersected_fq, motif_mapped_sam, motif_mapped_bam]:
        if os.path.exists(tmp):
            os.remove(tmp)
