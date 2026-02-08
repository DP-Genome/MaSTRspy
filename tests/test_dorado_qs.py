"""Tests for src.filters.dorado_qs module."""

import os

import pytest

from src.filters.dorado_qs import filter_fastq_by_qs


class TestFilterFastqByQs:
    def test_filters_by_qs_tag(self, sample_fastq_with_qs, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        # min_qs=10 should keep read1 (15.0) but not read2 (8.0) or read3 (3.0)
        result = filter_fastq_by_qs(sample_fastq_with_qs, out, min_qs=10.0)
        assert result["passed"] == 1
        assert result["filtered"] == 2
        assert result["no_tag_count"] == 0

    def test_all_pass(self, sample_fastq_with_qs, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        result = filter_fastq_by_qs(sample_fastq_with_qs, out, min_qs=1.0)
        assert result["passed"] == 3
        assert result["filtered"] == 0

    def test_all_filtered(self, sample_fastq_with_qs, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        result = filter_fastq_by_qs(sample_fastq_with_qs, out, min_qs=20.0)
        assert result["passed"] == 0
        assert result["filtered"] == 3

    def test_no_qs_tag_passes_through(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        # sample_fastq has no qs tags, so all reads should pass through
        result = filter_fastq_by_qs(sample_fastq, out, min_qs=10.0)
        assert result["passed"] == 3
        assert result["filtered"] == 0
        assert result["no_tag_count"] == 3

    def test_output_valid_fastq(self, sample_fastq_with_qs, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        filter_fastq_by_qs(sample_fastq_with_qs, out, min_qs=10.0)

        with open(out) as f:
            lines = f.readlines()
        assert len(lines) % 4 == 0
        assert len(lines) == 4  # Only 1 read passes
        assert lines[0].startswith("@")

    def test_mixed_tags(self, tmp_dir):
        """Test FASTQ where some reads have qs tags and some don't."""
        inp = os.path.join(tmp_dir, "mixed.fastq")
        out = os.path.join(tmp_dir, "out.fastq")
        with open(inp, "w") as f:
            f.write("@read1 qs:f:15.0\nACGT\n+\n????\n")
            f.write("@read2\nACGT\n+\n????\n")  # no qs tag
            f.write("@read3 qs:f:5.0\nACGT\n+\n????\n")
        result = filter_fastq_by_qs(inp, out, min_qs=10.0)
        assert result["passed"] == 2  # read1 (qs=15) + read2 (no tag, passed)
        assert result["filtered"] == 1  # read3 (qs=5)
        assert result["no_tag_count"] == 1

    def test_qs_tag_formats(self, tmp_dir):
        """Test various qs tag formats that should be recognized."""
        inp = os.path.join(tmp_dir, "formats.fastq")
        out = os.path.join(tmp_dir, "out.fastq")
        with open(inp, "w") as f:
            f.write("@read1 qs:f:15.0\nACGT\n+\n????\n")
            f.write("@read2 qs:i:12\nACGT\n+\n????\n")
            f.write("@read3 qs=15.5\nACGT\n+\n????\n")
        result = filter_fastq_by_qs(inp, out, min_qs=10.0)
        assert result["passed"] == 3
        assert result["filtered"] == 0

    def test_custom_log_callback(self, sample_fastq_with_qs, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        messages = []
        filter_fastq_by_qs(
            sample_fastq_with_qs, out, min_qs=10.0, log=messages.append
        )
        assert any("dorado_qs_filter" in m for m in messages)

    def test_empty_input(self, tmp_dir):
        inp = os.path.join(tmp_dir, "empty.fastq")
        out = os.path.join(tmp_dir, "out.fastq")
        open(inp, "w").close()
        result = filter_fastq_by_qs(inp, out, min_qs=10.0)
        assert result["passed"] == 0
        assert result["filtered"] == 0
