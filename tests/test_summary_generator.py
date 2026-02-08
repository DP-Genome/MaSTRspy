"""Tests for src.pipeline.summary_generator module."""

import os

import pytest

from src.pipeline.summary_generator import generate_summaries


class TestGenerateSummaries:
    def _setup_barcode_dir(self, tmp_dir):
        """Create a barcode directory structure with allele freq files."""
        counting_dir = os.path.join(tmp_dir, "Countings")
        barcode_dir = os.path.join(counting_dir, "barcode01")
        os.makedirs(barcode_dir)

        # Locus D3S1358
        with open(
            os.path.join(barcode_dir, "D3S1358_Allele_freqs.txt"), "w"
        ) as f:
            f.write("STR\tRawCounts\tNormalizedCounts\n")
            f.write("D3S1358_CE15_[TCTA]15\t100\t1.0\n")
            f.write("D3S1358_CE16_[TCTA]16\t80\t0.8\n")
            f.write("D3S1358_CE10_[TCTA]10\t5\t0.05\n")

        # Locus vWA
        with open(os.path.join(barcode_dir, "vWA_Allele_freqs.txt"), "w") as f:
            f.write("STR\tRawCounts\tNormalizedCounts\n")
            f.write("vWA_CE17_[TCTA]17\t90\t1.0\n")
            f.write("vWA_CE18_[TCTA]18\t70\t0.777\n")

        return counting_dir

    def test_creates_summaries_directory(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        assert os.path.isdir(os.path.join(counting_dir, "Summaries"))

    def test_creates_summary_tsv(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        summary_file = os.path.join(
            counting_dir, "Summaries", "barcode01_summary.tsv"
        )
        assert os.path.isfile(summary_file)

    def test_creates_profile_tsv(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        profile_file = os.path.join(
            counting_dir, "Summaries", "barcode01_Profile.tsv"
        )
        assert os.path.isfile(profile_file)

    def test_summary_contains_all_alleles(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        summary_file = os.path.join(
            counting_dir, "Summaries", "barcode01_summary.tsv"
        )
        with open(summary_file) as f:
            lines = f.readlines()
        # Header + 3 alleles from D3S1358 + 2 alleles from vWA = 6 lines
        assert len(lines) == 6
        assert "barcode01" in lines[1]
        assert "D3S1358" in lines[1]

    def test_profile_has_max_two_per_locus(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        profile_file = os.path.join(
            counting_dir, "Summaries", "barcode01_Profile.tsv"
        )
        with open(profile_file) as f:
            lines = f.readlines()
        # Header + 2 from D3S1358 + 2 from vWA = 5 lines
        assert len(lines) == 5

    def test_profile_status_pass(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        profile_file = os.path.join(
            counting_dir, "Summaries", "barcode01_Profile.tsv"
        )
        with open(profile_file) as f:
            content = f.read()
        # All top alleles have normalized >= 0.1, so they should PASS
        assert "PASS" in content

    def test_profile_status_flagged(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        # Set high cutoff so second alleles get flagged
        generate_summaries(counting_dir, 0.9, {})
        profile_file = os.path.join(
            counting_dir, "Summaries", "barcode01_Profile.tsv"
        )
        with open(profile_file) as f:
            content = f.read()
        assert "FLAGGED" in content

    def test_overrides_applied(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        overrides = {"D3S1358": 0.9}
        generate_summaries(counting_dir, 0.1, overrides)
        profile_file = os.path.join(
            counting_dir, "Summaries", "barcode01_Profile.tsv"
        )
        with open(profile_file) as f:
            content = f.read()
        # D3S1358 has override cutoff of 0.9, so the 0.8 allele should be flagged
        assert "FLAGGED" in content

    def test_empty_barcode_directory(self, tmp_dir):
        counting_dir = os.path.join(tmp_dir, "Countings")
        barcode_dir = os.path.join(counting_dir, "barcode01")
        os.makedirs(barcode_dir)
        generate_summaries(counting_dir, 0.1, {})
        summary_file = os.path.join(
            counting_dir, "Summaries", "barcode01_summary.tsv"
        )
        assert os.path.isfile(summary_file)
        with open(summary_file) as f:
            lines = f.readlines()
        assert len(lines) == 1  # Header only

    def test_no_barcode_directories(self, tmp_dir):
        counting_dir = os.path.join(tmp_dir, "Countings")
        os.makedirs(counting_dir)
        generate_summaries(counting_dir, 0.1, {})
        summaries_dir = os.path.join(counting_dir, "Summaries")
        assert os.path.isdir(summaries_dir)
        # No barcode dirs, so no summary files
        files = os.listdir(summaries_dir)
        assert len(files) == 0
