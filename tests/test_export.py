"""Tests for src.pipeline.export module."""

import os

import pytest

from src.pipeline.export import (
    _write_combined_profiles,
    _write_combined_summaries,
    _write_overview,
    export_combined_report,
)
from pathlib import Path


# ---------------------------------------------------------------------------
# Helper to create barcode summary / profile TSV files in a temp directory
# ---------------------------------------------------------------------------

SUMMARY_HEADER = "Barcode\tLocus\tCE_Number\tMotif\tRawCounts\tNormalizedCounts\n"
PROFILE_HEADER = (
    "Barcode\tLocus\tAllele_Rank\tCE_Number\tMotif\t"
    "RawCounts\tNormalizedCounts\tStatus\tZygosity\n"
)


def _create_summary_file(directory: str, barcode: str, rows: list[tuple]):
    """Write a barcode summary TSV.

    Each row is (Barcode, Locus, CE_Number, Motif, RawCounts, NormalizedCounts).
    """
    path = os.path.join(directory, f"{barcode}_summary.tsv")
    with open(path, "w") as f:
        f.write(SUMMARY_HEADER)
        for row in rows:
            f.write("\t".join(str(v) for v in row) + "\n")
    return path


def _create_profile_file(directory: str, barcode: str, rows: list[tuple]):
    """Write a barcode profile TSV.

    Each row is (Barcode, Locus, Allele_Rank, CE_Number, Motif,
                 RawCounts, NormalizedCounts, Status, Zygosity).
    """
    path = os.path.join(directory, f"{barcode}_Profile.tsv")
    with open(path, "w") as f:
        f.write(PROFILE_HEADER)
        for row in rows:
            f.write("\t".join(str(v) for v in row) + "\n")
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def summaries_dir(tmp_dir):
    """Create a summaries directory populated with two barcodes."""
    sdir = os.path.join(tmp_dir, "summaries")
    os.makedirs(sdir)

    _create_summary_file(sdir, "barcode01", [
        ("barcode01", "D3S1358", "15", "[TCTA]15", "200", "1.0"),
        ("barcode01", "D3S1358", "16", "[TCTA]16", "180", "0.9"),
        ("barcode01", "vWA", "17", "[TCTG]17", "150", "1.0"),
    ])
    _create_summary_file(sdir, "barcode02", [
        ("barcode02", "D3S1358", "14", "[TCTA]14", "100", "1.0"),
        ("barcode02", "vWA", "18", "[TCTG]18", "90", "0.95"),
    ])

    _create_profile_file(sdir, "barcode01", [
        ("barcode01", "D3S1358", "1", "15", "[TCTA]15", "200", "1.0", "PASS", "Heterozygous"),
        ("barcode01", "D3S1358", "2", "16", "[TCTA]16", "180", "0.9", "PASS", "Heterozygous"),
        ("barcode01", "vWA", "1", "17", "[TCTG]17", "150", "1.0", "PASS", "Homozygous"),
    ])
    _create_profile_file(sdir, "barcode02", [
        ("barcode02", "D3S1358", "1", "14", "[TCTA]14", "100", "1.0", "PASS", "Homozygous"),
        ("barcode02", "vWA", "1", "18", "[TCTG]18", "90", "0.95", "FAIL", ""),
    ])

    return sdir


# ---------------------------------------------------------------------------
# Tests for _write_combined_summaries
# ---------------------------------------------------------------------------

class TestWriteCombinedSummaries:
    def test_merges_summaries_with_single_header(self, summaries_dir, tmp_dir):
        summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
        output = os.path.join(tmp_dir, "combined_summary.tsv")
        _write_combined_summaries(summary_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()

        # Header should appear exactly once
        header_count = sum(1 for l in lines if l.startswith("Barcode\tLocus"))
        assert header_count == 1

        # All data rows present: 3 from barcode01 + 2 from barcode02
        data_lines = [l for l in lines if not l.startswith("Barcode\tLocus")]
        assert len(data_lines) == 5

    def test_first_line_is_header(self, summaries_dir, tmp_dir):
        summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
        output = os.path.join(tmp_dir, "combined_summary.tsv")
        _write_combined_summaries(summary_files, output, print)

        with open(output, "r") as f:
            first_line = f.readline()
        assert first_line.strip() == SUMMARY_HEADER.strip()

    def test_empty_file_list(self, tmp_dir):
        output = os.path.join(tmp_dir, "combined_empty.tsv")
        _write_combined_summaries([], output, print)
        with open(output, "r") as f:
            content = f.read()
        assert content == ""

    def test_single_barcode(self, tmp_dir):
        sdir = os.path.join(tmp_dir, "single")
        os.makedirs(sdir)
        _create_summary_file(sdir, "barcode01", [
            ("barcode01", "D3S1358", "15", "[TCTA]15", "200", "1.0"),
        ])
        summary_files = sorted(Path(sdir).glob("barcode*_summary.tsv"))
        output = os.path.join(tmp_dir, "combined_single.tsv")
        _write_combined_summaries(summary_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()
        assert len(lines) == 2  # header + 1 data row

    def test_blank_lines_are_skipped(self, tmp_dir):
        sdir = os.path.join(tmp_dir, "blanks")
        os.makedirs(sdir)
        path = os.path.join(sdir, "barcode01_summary.tsv")
        with open(path, "w") as f:
            f.write(SUMMARY_HEADER)
            f.write("barcode01\tD3S1358\t15\t[TCTA]15\t200\t1.0\n")
            f.write("\n")  # blank line
            f.write("barcode01\tvWA\t17\t[TCTG]17\t150\t1.0\n")

        summary_files = [Path(path)]
        output = os.path.join(tmp_dir, "combined_blanks.tsv")
        _write_combined_summaries(summary_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()
        # Header + 2 data rows (blank line skipped)
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# Tests for _write_combined_profiles
# ---------------------------------------------------------------------------

class TestWriteCombinedProfiles:
    def test_merges_profiles_with_single_header(self, summaries_dir, tmp_dir):
        profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))
        output = os.path.join(tmp_dir, "combined_profile.tsv")
        _write_combined_profiles(profile_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()

        header_count = sum(1 for l in lines if l.startswith("Barcode\tLocus\tAllele"))
        assert header_count == 1

        # 3 rows from barcode01 + 2 rows from barcode02
        data_lines = [l for l in lines if not l.startswith("Barcode\tLocus\tAllele")]
        assert len(data_lines) == 5

    def test_first_line_is_profile_header(self, summaries_dir, tmp_dir):
        profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))
        output = os.path.join(tmp_dir, "combined_profile.tsv")
        _write_combined_profiles(profile_files, output, print)

        with open(output, "r") as f:
            first_line = f.readline()
        assert first_line.strip() == PROFILE_HEADER.strip()

    def test_empty_profile_list(self, tmp_dir):
        output = os.path.join(tmp_dir, "empty_profiles.tsv")
        _write_combined_profiles([], output, print)
        with open(output, "r") as f:
            content = f.read()
        assert content == ""


# ---------------------------------------------------------------------------
# Tests for _write_overview
# ---------------------------------------------------------------------------

class TestWriteOverview:
    def test_creates_overview_with_per_barcode_stats(self, summaries_dir, tmp_dir):
        summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
        profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))
        output = os.path.join(tmp_dir, "overview.tsv")
        _write_overview(summary_files, profile_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()

        # Header + 2 barcode rows
        assert len(lines) == 3

    def test_overview_header(self, summaries_dir, tmp_dir):
        summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
        profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))
        output = os.path.join(tmp_dir, "overview.tsv")
        _write_overview(summary_files, profile_files, output, print)

        with open(output, "r") as f:
            header = f.readline().strip()
        expected_cols = [
            "Barcode", "Total_Loci", "Loci_With_Calls",
            "Homozygous", "Heterozygous", "No_Call", "Overall_Quality",
        ]
        assert header == "\t".join(expected_cols)

    def test_barcode01_stats(self, summaries_dir, tmp_dir):
        """barcode01: D3S1358 Heterozygous (2 PASS), vWA Homozygous (1 PASS).
        Total_Loci=2, Loci_With_Calls=2, Homo=1, Hetero=1, No_Call=0, Quality=100.0%
        """
        summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
        profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))
        output = os.path.join(tmp_dir, "overview.tsv")
        _write_overview(summary_files, profile_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()
        bc01_line = [l for l in lines if l.startswith("barcode01")][0]
        parts = bc01_line.strip().split("\t")
        assert parts[0] == "barcode01"
        assert parts[1] == "2"   # Total_Loci
        assert parts[2] == "2"   # Loci_With_Calls
        assert parts[3] == "1"   # Homozygous
        assert parts[4] == "1"   # Heterozygous
        assert parts[5] == "0"   # No_Call
        assert parts[6] == "100.0%"

    def test_barcode02_stats(self, summaries_dir, tmp_dir):
        """barcode02: D3S1358 Homozygous (1 PASS), vWA FAIL with empty zygosity.
        For vWA: zygosity="" and 0 PASS alleles => no_call.
        Total_Loci=2, Loci_With_Calls=1, Homo=1, Hetero=0, No_Call=1, Quality=50.0%
        """
        summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
        profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))
        output = os.path.join(tmp_dir, "overview.tsv")
        _write_overview(summary_files, profile_files, output, print)

        with open(output, "r") as f:
            lines = f.readlines()
        bc02_line = [l for l in lines if l.startswith("barcode02")][0]
        parts = bc02_line.strip().split("\t")
        assert parts[0] == "barcode02"
        assert parts[1] == "2"   # Total_Loci
        assert parts[2] == "1"   # Loci_With_Calls
        assert parts[3] == "1"   # Homozygous
        assert parts[4] == "0"   # Heterozygous
        assert parts[5] == "1"   # No_Call
        assert parts[6] == "50.0%"

    def test_overview_no_profiles(self, tmp_dir):
        """When no profile files exist, overview should have header only."""
        output = os.path.join(tmp_dir, "overview_empty.tsv")
        _write_overview([], [], output, print)

        with open(output, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1  # header only


# ---------------------------------------------------------------------------
# Tests for export_combined_report (integration)
# ---------------------------------------------------------------------------

class TestExportCombinedReport:
    def test_creates_all_output_files(self, summaries_dir, tmp_dir):
        output_path = os.path.join(tmp_dir, "report", "exp_combined_summary.tsv")
        export_combined_report(summaries_dir, output_path)

        assert os.path.exists(output_path)
        profile_path = output_path.replace("_combined_summary", "_combined_profile")
        overview_path = output_path.replace("_combined_summary", "_overview")
        assert os.path.exists(profile_path)
        assert os.path.exists(overview_path)

    def test_creates_output_directory_if_needed(self, summaries_dir, tmp_dir):
        nested = os.path.join(tmp_dir, "deep", "nested", "dir")
        output_path = os.path.join(nested, "exp_combined_summary.tsv")
        # Directory doesn't exist yet
        assert not os.path.exists(nested)
        export_combined_report(summaries_dir, output_path)
        assert os.path.exists(output_path)

    def test_skips_when_no_summaries(self, tmp_dir):
        empty_dir = os.path.join(tmp_dir, "empty_summaries")
        os.makedirs(empty_dir)
        output_path = os.path.join(tmp_dir, "no_output_combined_summary.tsv")
        log_messages = []
        export_combined_report(empty_dir, output_path, log=log_messages.append)
        assert not os.path.exists(output_path)
        assert any("WARNING" in m for m in log_messages)

    def test_log_messages(self, summaries_dir, tmp_dir):
        output_path = os.path.join(tmp_dir, "logged_combined_summary.tsv")
        log_messages = []
        export_combined_report(summaries_dir, output_path, log=log_messages.append)
        log_text = "\n".join(log_messages)
        assert "Generating combined report" in log_text
        assert "complete" in log_text

    def test_combined_summary_has_correct_row_count(self, summaries_dir, tmp_dir):
        output_path = os.path.join(tmp_dir, "exp_combined_summary.tsv")
        export_combined_report(summaries_dir, output_path)

        with open(output_path, "r") as f:
            lines = f.readlines()
        # Header + 3 from barcode01 + 2 from barcode02 = 6
        assert len(lines) == 6

    def test_combined_profile_has_correct_row_count(self, summaries_dir, tmp_dir):
        output_path = os.path.join(tmp_dir, "exp_combined_summary.tsv")
        export_combined_report(summaries_dir, output_path)

        profile_path = output_path.replace("_combined_summary", "_combined_profile")
        with open(profile_path, "r") as f:
            lines = f.readlines()
        # Header + 3 from barcode01 + 2 from barcode02 = 6
        assert len(lines) == 6

    def test_fallback_naming_when_no_combined_summary_in_name(self, summaries_dir, tmp_dir):
        """When output_path doesn't contain '_combined_summary', fallback naming is used."""
        output_path = os.path.join(tmp_dir, "report.tsv")
        export_combined_report(summaries_dir, output_path)

        assert os.path.exists(output_path)
        # Profiles should be at report_profiles.tsv
        profile_path = output_path.replace(".tsv", "_profiles.tsv")
        overview_path = output_path.replace(".tsv", "_overview.tsv")
        assert os.path.exists(profile_path)
        assert os.path.exists(overview_path)

    def test_only_profile_files_missing(self, tmp_dir):
        """When summary files exist but profile files don't, it should still work."""
        sdir = os.path.join(tmp_dir, "only_summaries")
        os.makedirs(sdir)
        _create_summary_file(sdir, "barcode01", [
            ("barcode01", "D3S1358", "15", "[TCTA]15", "200", "1.0"),
        ])
        output_path = os.path.join(tmp_dir, "output_combined_summary.tsv")
        # Should not raise
        export_combined_report(sdir, output_path)
        assert os.path.exists(output_path)
