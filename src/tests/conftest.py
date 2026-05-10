"""Shared fixtures for MaSTRspy tests."""

import os
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_input_config(tmp_dir):
    """Create a sample InputConfig.txt file."""
    path = os.path.join(tmp_dir, "InputConfig.txt")
    with open(path, "w") as f:
        f.write('INPUT_DIR="/data/input"\n')
        f.write('OUTPUT_DIR="/data/output"\n')
        f.write('INPUT_BAM="yes"\n')
        f.write('READ_TYPE="ont"\n')
        f.write("NORM_CUTOFF=0.1\n")
        f.write("# This is a comment\n")
        f.write("\n")
        f.write('GENOME_FASTA="/ref/genome.fa"\n')
    return path


@pytest.fixture
def sample_overrides_tsv(tmp_dir):
    """Create a sample overrides TSV file."""
    path = os.path.join(tmp_dir, "overrides.tsv")
    with open(path, "w") as f:
        f.write("# Locus\tCutoff\n")
        f.write("D3S1358\t0.4\n")
        f.write("vWA\t0.4\n")
        f.write("DYS481\t0.5\n")
    return path


@pytest.fixture
def sample_fastq(tmp_dir):
    """Create a sample FASTQ file with known quality scores."""
    path = os.path.join(tmp_dir, "test.fastq")
    with open(path, "w") as f:
        # Read 1: length=10, mean_q ~= 30
        f.write("@read1\n")
        f.write("ACGTACGTAC\n")
        f.write("+\n")
        f.write("??????????\n")  # ASCII 63 => Q30
        # Read 2: length=5, mean_q ~= 30
        f.write("@read2\n")
        f.write("ACGTA\n")
        f.write("+\n")
        f.write("?????\n")
        # Read 3: length=10, mean_q ~= 5
        f.write("@read3\n")
        f.write("GGGGGGGGGG\n")
        f.write("+\n")
        f.write("&&&&&&&&&&\n")  # ASCII 38 => Q5
    return path


@pytest.fixture
def sample_fastq_with_qs(tmp_dir):
    """Create a sample FASTQ file with Dorado qs tags in headers."""
    path = os.path.join(tmp_dir, "test_qs.fastq")
    with open(path, "w") as f:
        # Read 1: qs=15.0
        f.write("@read1 qs:f:15.0\n")
        f.write("ACGTACGTAC\n")
        f.write("+\n")
        f.write("??????????\n")
        # Read 2: qs=8.0
        f.write("@read2 qs:f:8.0\n")
        f.write("ACGTA\n")
        f.write("+\n")
        f.write("?????\n")
        # Read 3: qs=3.0
        f.write("@read3 qs:f:3.0\n")
        f.write("GGGGGGGGGG\n")
        f.write("+\n")
        f.write("&&&&&&&&&&\n")
    return path


@pytest.fixture
def counting_dir_with_files(tmp_dir):
    """Create a Countings directory with sample allele frequency files."""
    counting_dir = os.path.join(tmp_dir, "Countings")
    os.makedirs(counting_dir)

    # Create barcode01 files
    for locus in ["D3S1358", "vWA"]:
        fname = f"{locus}_barcode01_prepped.bam_Allele_freqs.txt"
        with open(os.path.join(counting_dir, fname), "w") as f:
            f.write("STR\tRawCounts\tNormalizedCounts\n")
            f.write(f"{locus}_CE15_[TCTA]15\t100\t1.0\n")
            f.write(f"{locus}_CE16_[TCTA]16\t80\t0.8\n")
            f.write(f"{locus}_CE10_[TCTA]10\t5\t0.05\n")

    # Create a Toptwo file (should be cleaned up)
    with open(os.path.join(counting_dir, "D3S1358_barcode01_Toptwo.txt"), "w") as f:
        f.write("dummy\n")

    return counting_dir
