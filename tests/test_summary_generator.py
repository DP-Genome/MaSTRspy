"""Tests for src.pipeline.summary_generator module."""

import os

import pytest

from src.pipeline.summary_generator import generate_summaries, _normalize_counts


class TestNormalizeCounts:
    def test_max_normalization(self):
        raw = [("allele1", 100), ("allele2", 50)]
        result = _normalize_counts(raw, method="max")
        assert len(result) == 2
        assert result[0] == ("allele1", 100, 1.0)
        assert result[1] == ("allele2", 50, 0.5)

    def test_total_normalization(self):
        raw = [("allele1", 60), ("allele2", 40)]
        result = _normalize_counts(raw, method="total")
        assert result[0] == ("allele1", 60, 0.6)
        assert result[1] == ("allele2", 40, 0.4)

    def test_empty_input(self):
        assert _normalize_counts([], method="max") == []

    def test_single_allele(self):
        raw = [("allele1", 50)]
        result = _normalize_counts(raw, method="max")
        assert result[0] == ("allele1", 50, 1.0)

    def test_zero_counts(self):
        raw = [("allele1", 0), ("allele2", 0)]
        result = _normalize_counts(raw, method="max")
        # Denominator should be 1 (avoid division by zero)
        assert result[0][2] == 0.0
        assert result[1][2] == 0.0

    def test_noise_floor_method(self):
        raw = [("a", 100), ("b", 50)]
        result = _normalize_counts(raw, method="noise_floor")
        # With < 10 counts, noise floor is not applied
        assert result[0] == ("a", 100, 1.0)
        assert result[1] == ("b", 50, 0.5)


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
        assert "PASS" in content

    def test_profile_status_flagged(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
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
        result = generate_summaries(counting_dir, 0.1, {})
        summaries_dir = os.path.join(counting_dir, "Summaries")
        assert os.path.isdir(summaries_dir)
        # No barcode dirs, so no quality metrics (only quality report header)
        assert result == {}
        # Quality report should still be created (with header only)
        report_file = os.path.join(summaries_dir, "sample_quality_report.tsv")
        assert os.path.isfile(report_file)

    def test_returns_quality_metrics(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        result = generate_summaries(counting_dir, 0.1, {})
        assert "barcode01" in result
        metrics = result["barcode01"]
        assert "total_loci" in metrics
        assert "loci_with_calls" in metrics
        assert "quality_pct" in metrics
        assert metrics["total_loci"] == 2

    def test_creates_quality_report(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        report_file = os.path.join(
            counting_dir, "Summaries", "sample_quality_report.tsv"
        )
        assert os.path.isfile(report_file)
        with open(report_file) as f:
            lines = f.readlines()
        assert len(lines) >= 2  # Header + at least 1 barcode

    def test_profile_has_zygosity_column(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        generate_summaries(counting_dir, 0.1, {})
        profile_file = os.path.join(
            counting_dir, "Summaries", "barcode01_Profile.tsv"
        )
        with open(profile_file) as f:
            header = f.readline()
        assert "Zygosity" in header

    def test_normalization_method_total(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        result = generate_summaries(
            counting_dir, 0.1, {}, normalization_method="total"
        )
        assert "barcode01" in result

    def test_stutter_filter_disabled(self, tmp_dir):
        counting_dir = self._setup_barcode_dir(tmp_dir)
        result = generate_summaries(
            counting_dir, 0.1, {}, stutter_filter=False
        )
        assert "barcode01" in result
